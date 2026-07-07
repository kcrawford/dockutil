# Standard Library
import ast

# PIP3 modules
import pytest

# local repo modules
import file_utils

FILES = file_utils.discover_files(extensions=(".py",), test_key="import_dot")

REPORT_NAME = file_utils.report_name(__file__)

HEADER = "Import dot report"

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}


#============================================
def format_issue(rel_path: str, line_no: int, import_root: str) -> str:
	"""
	Format a report line for a relative from-import statement.

	Args:
		rel_path: Repo-relative POSIX path for the file containing the import.
		line_no: Line number of the offending import statement.
		import_root: The leading dot(s) and optional module name, e.g. '.repolib'.

	Returns:
		str: Human-readable violation line.
	"""
	return f"{rel_path}:{line_no}: relative import from {import_root}"


#============================================
def check_file(rel: str, tree: ast.Module) -> list[str]:
	"""
	Return violations for any relative from-import in the parsed module.

	Scans import nodes via file_utils.iter_imports and records any ImportFrom
	node whose level > 0. Deduplicates and sorts before returning. Only reached
	for files that parsed cleanly; the shared collect_python_violations owns
	SyntaxError capture.

	Args:
		rel: Repo-relative POSIX path for error messages.
		tree: Parsed ast.Module for the file.

	Returns:
		list[str]: Violation lines (empty when the file is clean).
	"""
	# Collect each relative from-import node (level > 0 means relative).
	issues = []
	for node in file_utils.iter_imports(tree):
		if not isinstance(node, ast.ImportFrom):
			continue
		if getattr(node, "level", 0) <= 0:
			continue
		line_no = getattr(node, "lineno", 0) or 0
		module_name = node.module or ""
		# Build the dotted import root, e.g. '.' or '.repolib'.
		import_root = f"{'.' * node.level}{module_name}"
		issues.append(format_issue(rel, line_no, import_root))
	# Deduplicate and sort so output is stable.
	return sorted(set(issues))


#============================================
@pytest.fixture(scope="module", autouse=True)
def collect_report() -> None:
	"""
	Autouse fixture: clear stale reports, populate VIOLATIONS_BY_FILE, write report.

	Runs the guarded once-per-process cleanup first, rebuilds the module-level
	violations dict via the shared harness, then writes the report only when
	there are violations. Cleanup owns removal of clean-run reports, so a clean
	module writes nothing.
	"""
	# Once-per-process guarded cleanup of repo-root report_*.txt (no-op after first call).
	file_utils.clear_stale_reports()
	# Clear any state left from a previous collection in the same process.
	VIOLATIONS_BY_FILE.clear()
	VIOLATIONS_BY_FILE.update(file_utils.collect_python_violations(FILES, check_file))
	lines = file_utils.format_violation_report(HEADER, VIOLATIONS_BY_FILE)
	# Report is exactly format_violation_report's output (header + sorted file lines).
	if lines:
		file_utils.write_report_lines(REPORT_NAME, lines)


#============================================
@pytest.mark.parametrize("path", FILES, ids=file_utils.rel_id)
def test_import_dot(path: str) -> None:
	"""Enforce no relative from-imports repo-wide."""
	rel = file_utils.rel_to_root(path)
	# Python evaluates an assert's message expression ONLY when the assert fails,
	# so format_violation_assert_message runs on the failing path only -- not per pass.
	assert rel not in VIOLATIONS_BY_FILE, file_utils.format_violation_assert_message(
		rel, VIOLATIONS_BY_FILE.get(rel, []), REPORT_NAME
	)
