# Standard Library
import os
import re
import ast
import sys

# PIP3 modules
import pytest

# local repo modules
import file_utils

CHECK_OPTIONAL_IMPORTS_ENV = "CHECK_OPTIONAL_IMPORTS"
REPO_ROOT = file_utils.get_repo_root()
REPORT_NAME = file_utils.report_name(__file__)
REQUIREMENT_FILES = (
	"pip_requirements.txt",
	"pip_requirements-dev.txt",
	"pip_requirements-meta.txt",
	"pip_extras.txt",
	os.path.join("config_files", "pip_requirements.txt"),
	os.path.join("config_files", "pip_requirements-dev.txt"),
	os.path.join("config_files", "pip_extras.txt"),
)
LOCAL_IMPORT_WHITELIST = {
	# Vendored at ~/nsh/local-llm-wrapper and made importable via PYTHONPATH.
	# Imported by bioproblems_site/llm_helpers.py and problem_set_title.py.
	"local_llm_wrapper",
}
IMPORT_REQUIREMENT_ALIASES = {
	"applescript": "py-applescript",
	"bio": "biopython",
	"bs4": "beautifulsoup4",
	"cairo": "pycairo",
	"colour": "colour-science",
	"crypto": "pycryptodome",
	"cv2": "opencv-python",
	"docx": "python-docx",
	"fitz": "pymupdf",
	"google": "google-api-python-client",
	"googleapiclient": "google-api-python-client",
	"imdb": "IMDbPY",
	"image": "pillow",
	"imagedraw": "pillow",
	"imagetk": "pillow",
	"pdfminer": "pdfminer.six",
	"pil": "pillow",
	"pptx": "python-pptx",
	"rottentomatoes": "rottentomatoes-python",
	"yaml": "pyyaml",
}
REQ_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+")

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}


#============================================
def resolve_check_optional_imports() -> bool:
	"""
	Resolve whether to enforce imports guarded by ImportError handling.
	"""
	return os.environ.get(CHECK_OPTIONAL_IMPORTS_ENV) == "1"


#============================================
def normalize_name(name: str) -> str:
	"""
	Normalize a module or requirement name for comparisons.
	"""
	return name.lower().replace("-", "_").replace(".", "_")


#============================================
def parse_requirement_name(line: str) -> str:
	"""
	Parse the base requirement name from one requirements.txt line.
	"""
	plain_line = line.split("#", 1)[0].strip()
	if not plain_line:
		return ""
	if plain_line.startswith(("-", "git+", "http://", "https://")):
		return ""
	plain_line = plain_line.split(";", 1)[0].strip()
	if not plain_line:
		return ""
	plain_line = plain_line.split("[", 1)[0].strip()
	match = REQ_NAME_RE.match(plain_line)
	if not match:
		return ""
	return match.group(0)


#============================================
def load_requirement_modules(repo_root: str) -> tuple[set[str], str]:
	"""
	Load normalized requirement names from known requirement files.
	"""
	modules = set()
	source_paths = []
	for rel_path in REQUIREMENT_FILES:
		candidate = os.path.join(repo_root, rel_path)
		if not os.path.isfile(candidate):
			continue
		source_paths.append(rel_path)
		with open(candidate, "r", encoding="utf-8") as handle:
			for raw_line in handle:
				requirement_name = parse_requirement_name(raw_line)
				if not requirement_name:
					continue
				modules.add(normalize_name(requirement_name))
	if not modules:
		raise RuntimeError(
			"No requirements file found. Expected one of: "
			+ ", ".join(REQUIREMENT_FILES)
		)
	return modules, ", ".join(source_paths)


#============================================
def collect_repo_module_names(paths: list[str]) -> set[str]:
	"""
	Collect importable module names from tracked Python files.
	"""
	module_names = set()
	for path in paths:
		rel_path = file_utils.rel_to_root(path)
		for part in rel_path.split(os.sep)[:-1]:
			if part:
				module_names.add(part)
		base_name = os.path.basename(path)
		if base_name == "__init__.py":
			package_name = os.path.basename(os.path.dirname(path))
			if package_name:
				module_names.add(package_name)
			continue
		if not base_name.endswith(".py"):
			continue
		module_name = os.path.splitext(base_name)[0]
		if module_name:
			module_names.add(module_name)
	return module_names


#============================================
def is_import_error_type(node: ast.AST | None) -> bool:
	"""
	Check whether an except handler type captures import-related exceptions.
	"""
	if node is None:
		return True
	if isinstance(node, ast.Name):
		return node.id in ("ImportError", "ModuleNotFoundError")
	if isinstance(node, ast.Attribute):
		return node.attr in ("ImportError", "ModuleNotFoundError")
	if isinstance(node, ast.Tuple):
		for element in node.elts:
			if is_import_error_type(element):
				return True
	return False


#============================================
class ImportCollector(ast.NodeVisitor):
	"""
	Collect import roots and mark imports inside optional import guards.
	"""

	def __init__(self, source: str) -> None:
		self.imports: list[tuple[int, str, bool, str]] = []
		self._source = source
		self._optional_depth = 0

	def _statement_text(self, node: ast.AST, line_no: int) -> str:
		"""
		Get best-effort source text for one import statement.
		"""
		statement = ast.get_source_segment(self._source, node)
		if statement:
			return statement.strip()
		lines = self._source.splitlines()
		if 1 <= line_no <= len(lines):
			return lines[line_no - 1].strip()
		return ""

	def _record(self, line_no: int, module_name: str, node: ast.AST) -> None:
		if not module_name:
			return
		statement = self._statement_text(node, line_no)
		self.imports.append(
			(line_no, module_name, self._optional_depth > 0, statement)
		)

	def visit_Import(self, node: ast.Import) -> None:
		line_no = getattr(node, "lineno", 0) or 0
		for alias in node.names:
			root = alias.name.split(".", 1)[0]
			self._record(line_no, root, node)

	def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
		if getattr(node, "level", 0):
			return
		module_name = node.module or ""
		root = module_name.split(".", 1)[0]
		line_no = getattr(node, "lineno", 0) or 0
		self._record(line_no, root, node)

	def visit_Try(self, node: ast.Try) -> None:
		import_guarded = False
		for handler in node.handlers:
			if is_import_error_type(handler.type):
				import_guarded = True
				break
		if import_guarded:
			self._optional_depth += 1
		for statement in node.body:
			self.visit(statement)
		for handler in node.handlers:
			self.visit(handler)
		for statement in node.orelse:
			self.visit(statement)
		for statement in node.finalbody:
			self.visit(statement)
		if import_guarded:
			self._optional_depth -= 1


#============================================
def collect_import_roots(path: str) -> tuple[list[tuple[int, str, bool, str]], str]:
	"""
	Collect imported root module names for one file.
	"""
	source = file_utils.read_source(path)
	tree, error = file_utils.parse_source(path)
	if error is not None:
		line_no = getattr(error, "lineno", 0) or 0
		message = error.msg or "Syntax error while parsing imports."
		return [], f"{line_no}: {message}"
	collector = ImportCollector(source)
	collector.visit(tree)
	return collector.imports, ""


#============================================
def normalize_statement_for_report(statement_text: str) -> str:
	"""
	Normalize statement text to one line for readable reports.
	"""
	if not statement_text:
		return "<unavailable>"
	normalized = statement_text.replace("\r\n", "\n").replace("\r", "\n")
	normalized = normalized.replace("\t", "\\t")
	normalized = normalized.replace("\n", "\\n")
	return normalized


#============================================
def get_stdlib_modules() -> set[str]:
	"""
	Get normalized module names that are part of Python stdlib.
	"""
	modules = set()
	for name in sys.builtin_module_names:
		modules.add(normalize_name(name))
	stdlib_names = getattr(sys, "stdlib_module_names", set())
	for name in stdlib_names:
		modules.add(normalize_name(name))
	return modules


#============================================
def is_allowed_module(
	module_name: str,
	repo_modules: set[str],
	stdlib_modules: set[str],
	requirement_modules: set[str],
) -> bool:
	"""
	Return True when a module passes import policy checks.
	"""
	if module_name in LOCAL_IMPORT_WHITELIST:
		return True
	if module_name in repo_modules:
		return True
	normalized = normalize_name(module_name)
	if normalized in stdlib_modules:
		return True
	if normalized in requirement_modules:
		return True
	alias = IMPORT_REQUIREMENT_ALIASES.get(normalized, "")
	if alias and normalize_name(alias) in requirement_modules:
		return True
	return False


#============================================
def build_violations_by_file(
	paths: list[str],
	repo_modules: set[str],
	stdlib_modules: set[str],
	requirement_modules: set[str],
	check_optional_imports: bool,
) -> dict[str, list[str]]:
	"""
	Build a per-file violations dict for all given paths.

	For each file, collect import roots and check each against the allowed sets.
	Parse errors become violation entries for that file. Import-issue lines for
	a given file are deduped via sorted(set(...)) to preserve the old global-dedup
	semantics scoped to each file. Parse errors are NOT deduped (one entry per
	parse-error line, preserving original behavior).

	Args:
		paths: Absolute paths to Python files to check.
		repo_modules: Set of normalized repo-local module names.
		stdlib_modules: Set of normalized stdlib module names.
		requirement_modules: Set of normalized requirement module names.
		check_optional_imports: Whether to enforce optional import guards.

	Returns:
		dict[str, list[str]]: Repo-relative POSIX path -> list of violation lines.
	"""
	violations_by_file: dict[str, list[str]] = {}
	for path in sorted(paths):
		rel = file_utils.rel_to_root(path)
		import_roots, parse_error = collect_import_roots(path)
		if parse_error:
			# Parse error: record one entry for this file (not deduped).
			violations_by_file[rel] = [f"{rel}:{parse_error}"]
			continue
		# Collect import-policy violations for this file.
		file_issues: list[str] = []
		for line_no, module_name, optional_import, statement_text in import_roots:
			if module_name == "__future__":
				continue
			if optional_import and not check_optional_imports:
				continue
			if is_allowed_module(
				module_name,
				repo_modules,
				stdlib_modules,
				requirement_modules,
			):
				continue
			statement = normalize_statement_for_report(statement_text)
			file_issues.append(f"{rel}:{line_no}: {module_name}: {statement}")
		# Deduplicate per-file import issues, preserving old global-dedup semantics scoped per file.
		deduped = sorted(set(file_issues))
		if deduped:
			violations_by_file[rel] = deduped
	return violations_by_file


#============================================
def make_report_lines(
	violations_by_file: dict[str, list[str]],
	requirement_source: str,
	check_optional_imports: bool,
) -> list[str]:
	"""
	Build the report lines list from the violations dict.

	Returns an empty list when there are no violations so the caller's
	`if lines: write_report_lines(...)` guard works correctly.

	Args:
		violations_by_file: Per-file violations dict.
		requirement_source: Human-readable requirements source string.
		check_optional_imports: Whether optional imports are being checked.

	Returns:
		list[str]: Report lines (empty when clean).
	"""
	if not violations_by_file:
		return []
	# Use the single module-level HEADER as the report header.
	lines = file_utils.format_violation_report(HEADER, violations_by_file)
	# Prepend the metadata lines after the header (index 0).
	metadata = [
		f"Requirements source: {requirement_source}",
		f"CHECK_OPTIONAL_IMPORTS: {int(check_optional_imports)}",
	]
	# Insert metadata right after the first header line.
	lines = [lines[0]] + metadata + lines[1:]
	return lines


FILES = file_utils.discover_files(extensions=(".py",), test_key="import_requirements")

HEADER = "Import requirements report"


#============================================
@pytest.fixture(scope="module", autouse=True)
def collect_report() -> None:
	"""
	Autouse fixture: clear stale reports, populate VIOLATIONS_BY_FILE, write report.

	Builds the three whole-repo module sets once, walks each file distributing
	issue lines into VIOLATIONS_BY_FILE keyed by repo-relative path, then writes
	the report only when violations exist. Calls clear_stale_reports() first
	so a single-module run still clears stale reports.
	"""
	# Once-per-process guarded cleanup of repo-root report_*.txt (no-op after first call).
	file_utils.clear_stale_reports()
	VIOLATIONS_BY_FILE.clear()
	if not FILES:
		return
	check_optional_imports = resolve_check_optional_imports()
	repo_modules = collect_repo_module_names(FILES)
	stdlib_modules = get_stdlib_modules()
	# load_requirement_modules raises RuntimeError when no requirements file is found;
	# that is an environment error, not a test failure -- let it propagate.
	requirement_modules, requirement_source = load_requirement_modules(REPO_ROOT)
	VIOLATIONS_BY_FILE.update(
		build_violations_by_file(
			FILES,
			repo_modules,
			stdlib_modules,
			requirement_modules,
			check_optional_imports,
		)
	)
	lines = make_report_lines(VIOLATIONS_BY_FILE, requirement_source, check_optional_imports)
	# Write only when there are violations; cleanup already removed stale reports.
	if lines:
		file_utils.write_report_lines(REPORT_NAME, lines)


#============================================
@pytest.mark.parametrize("path", FILES, ids=file_utils.rel_id)
def test_import_requirements(path: str) -> None:
	"""Validate imports against stdlib, repo modules, requirements, and whitelist."""
	rel = file_utils.rel_to_root(path)
	# Python evaluates an assert's message expression ONLY when the assert fails,
	# so format_violation_assert_message runs on the failing path only -- not per pass.
	assert rel not in VIOLATIONS_BY_FILE, file_utils.format_violation_assert_message(
		rel, VIOLATIONS_BY_FILE.get(rel, []), REPORT_NAME
	)
