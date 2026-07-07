# Standard Library
import os
import ast
import fnmatch
import pathlib
import functools
import tokenize
import subprocess
import importlib.util
import collections.abc

# Single shared set of directory names that no hygiene scan should lint.
# Every entry is a build, cache, or legacy directory. This is the only
# built-in directory-exclusion source; per-test exclusions go through the
# extra_filter callable on discover_files.
SKIP_DIRS = frozenset({
	".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache",
	"old_shell_folder", "legacy",
})


#============================================
@functools.lru_cache(maxsize=None)
def get_repo_root() -> str:
	"""
	Get the repository root using git rev-parse --show-toplevel.

	The result is memoized for the process lifetime: the repo root does not
	change while a pytest run executes, so resolving it once avoids spawning
	git on every rel_to_root/report_path/discover_files call. The hygiene
	suite calls this helper hundreds of times per run.

	Returns:
		str: Absolute path to the repository root.
	"""
	output = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True)
	repo_root = output.strip()
	return repo_root


#============================================
def read_source(path: str) -> str:
	"""
	Read Python source using tokenize.open for encoding correctness.

	tokenize.open honors a PEP 263 coding declaration or a UTF-8 BOM, so
	source files with non-default encodings decode the same way the Python
	tokenizer would read them.

	Args:
		path: Filesystem path to a Python source file.

	Returns:
		str: The full decoded source text.
	"""
	with tokenize.open(path) as handle:
		text = handle.read()
	return text


#============================================
def parse_source(path: str) -> tuple:
	"""
	Read and parse one Python source file into an AST.

	Reads the file via read_source, then parses it with ast.parse. This is
	the single place in the test suite that wraps ast.parse in a try/except
	SyntaxError, so callers branch on the returned error instead of writing
	their own handler.

	Args:
		path: Filesystem path to a Python source file.

	Returns:
		tuple: (tree, error). On success tree is the ast.Module and error is
			None. On a SyntaxError tree is None and error is the raised
			SyntaxError instance (carrying lineno and msg for callers).
	"""
	source = read_source(path)
	# This is the only SyntaxError try/except in the test suite; callers
	# branch on the returned error rather than catching it themselves.
	try:
		tree = ast.parse(source, filename=path)
	except SyntaxError as error:
		return None, error
	return tree, None


#============================================
def iter_imports(tree: ast.Module) -> list:
	"""
	Collect every import node from a parsed module.

	Walks a parsed ast.Module and returns each ast.Import and ast.ImportFrom
	node in document order. This centralizes the import-node walk that several
	import-hygiene tests would otherwise each reimplement.

	Args:
		tree: A parsed ast.Module to walk for import nodes.

	Returns:
		list: ast.Import and ast.ImportFrom nodes found via ast.walk. A list,
			not a generator, so callers can index and iterate repeatedly.
	"""
	nodes = []
	# ast.walk yields every descendant node; keep only the two import kinds.
	for node in ast.walk(tree):
		if isinstance(node, (ast.Import, ast.ImportFrom)):
			nodes.append(node)
	return nodes


#============================================
def rel_to_root(path: str, repo_root: str | None = None) -> str:
	"""
	Convert an absolute path to a repo-relative POSIX path.

	Computes the path relative to repo_root and normalizes separators to
	forward slashes, matching the rel computation used in discover_files. Used
	for parametrize ids and error messages.

	Args:
		path: Absolute filesystem path inside the repository.
		repo_root: Repository root to compute against. Defaults to
			get_repo_root() when None.

	Returns:
		str: Repo-relative path using forward slashes.
	"""
	# Default to the git repo root when no root is supplied.
	if repo_root is None:
		repo_root = get_repo_root()
	# Compute the relative path, then normalize Windows separators to POSIX.
	rel = os.path.relpath(path, repo_root)
	return rel.replace("\\", "/")


#============================================
def report_path(name: str) -> str:
	"""
	Build the absolute path to a repo-root report file.

	Hygiene tests write dev-facing report files (for example
	report_bandit_security.txt) at the repository root. This resolves the full
	filename to an absolute path under get_repo_root().

	Args:
		name: Full report filename, for example "report_bandit_security.txt".

	Returns:
		str: Absolute path to the report file at the repo root.
	"""
	return os.path.join(get_repo_root(), name)


#============================================
def write_report(name: str, text: str) -> str:
	"""
	Write text to a repo-root report file, truncating any prior content.

	Opens the report path in write mode with UTF-8 encoding and writes the
	text verbatim. Callers build the full text (including trailing newlines)
	before calling, so this performs exactly one write.

	Args:
		name: Full report filename, for example "report_bandit_security.txt".
		text: Full report body to write verbatim.

	Returns:
		str: Absolute path to the written report file.
	"""
	# Resolve the absolute report path under the repo root.
	path = report_path(name)
	# Truncate-write the full text in one call.
	with open(path, "w", encoding="utf-8") as handle:
		handle.write(text)
	return path


# Once-per-process guard for clear_stale_reports. Set to True on the first
# successful cleanup run; subsequent calls are no-ops so module imports do
# not re-clean between test modules in the same process.
_STALE_REPORTS_CLEARED: bool = False


#============================================
def clear_stale_reports() -> None:
	"""
	Remove all repo-root files matching report_*.txt on the first call.

	A module-level flag (_STALE_REPORTS_CLEARED) ensures the glob-and-unlink
	pass runs at most once per process, so repeated calls from multiple modules
	within the same pytest run are all no-ops after the first. This prevents
	re-cleaning between module imports and avoids deleting reports written by
	an earlier module in the same run.

	Only regular files are unlinked; directories that happen to match the glob
	(for example a directory named report_dir.txt) are skipped. Zero matches is
	not an error: a clean repo root simply has nothing to remove.

	Behavior is cleanup-only. This function never writes any file.
	"""
	global _STALE_REPORTS_CLEARED
	# Guard: skip if already cleaned in this process.
	if _STALE_REPORTS_CLEARED:
		return
	# Glob only the repo root for report_*.txt matches.
	root = pathlib.Path(get_repo_root())
	for candidate in root.glob("report_*.txt"):
		# Skip non-files (for example directories with a matching name).
		if not candidate.is_file():
			continue
		candidate.unlink()
	# Mark as done so subsequent calls are no-ops.
	_STALE_REPORTS_CLEARED = True


#============================================
def report_name(test_file: str) -> str:
	"""
	Derive the canonical report filename for a hygiene test module.

	Takes the basename of test_file, strips the .py extension and the leading
	test_ prefix, then returns "report_{stem}.txt". This is the single
	authoritative way to map a test module path to its report filename so
	every caller uses the same name without hardcoding it.

	Args:
		test_file: Path (absolute or relative) to the test module, typically
			the value of __file__ inside the test. The basename must start with
			"test_" and end with ".py".

	Returns:
		str: Report filename, for example "report_bandit_security.txt" when test_file
			is ".../tests/test_bandit_security.py".
	"""
	# Extract the base filename without directory components.
	base = os.path.basename(test_file)
	# Require and strip the .py extension; raise loudly on malformed input.
	if not base.endswith(".py"):
		raise ValueError(f"report_name: expected a .py filename, got {base!r}")
	stem = base[:-3]
	# Require and strip the "test_" prefix; raise loudly on malformed input.
	if not stem.startswith("test_"):
		raise ValueError(f"report_name: expected filename to start with 'test_', got {stem!r}")
	topic = stem[len("test_"):]
	# Assemble and return the canonical report filename.
	return f"report_{topic}.txt"


#============================================
def collect_file_violations(
	files: list[str],
	check: collections.abc.Callable[[str], list[str]],
) -> dict[str, list[str]]:
	"""
	Run a non-AST check on each file and keep only files with violations.

	Iterates files in sorted order. For each file, computes the repo-relative
	POSIX path via rel_to_root and calls check(rel). The check receives the
	repo-relative path; a check that needs file content resolves it itself via
	os.path.join(get_repo_root(), rel) (get_repo_root is cached and free). Files
	with no returned lines are omitted from the result.

	Args:
		files: Absolute file paths to check. Sorted internally so the result is
			order-independent.
		check: Callable receiving a repo-relative POSIX path and returning a
			list of violation lines (empty when the file is clean).

	Returns:
		dict[str, list[str]]: Repo-relative POSIX key -> violation lines,
			containing only files with at least one line.
	"""
	result = {}
	# Sort so the scan order is deterministic regardless of caller ordering.
	for path in sorted(files):
		rel = rel_to_root(path)
		lines = check(rel)
		# Only include files that produced at least one violation line.
		if lines:
			result[rel] = lines
	return result


#============================================
def collect_python_violations(
	files: list[str],
	check: collections.abc.Callable[[str, ast.Module], list[str]],
) -> dict[str, list[str]]:
	"""
	Parse each Python file once and run an AST check, capturing SyntaxErrors.

	Iterates files in sorted order. For each file, parses it once via
	parse_source. On a SyntaxError, records exactly one
	f"{rel}: SyntaxError: {error}" entry and skips check for that file. Otherwise
	calls check(rel, tree), so check always receives a real ast.Module. Files
	with no returned lines are omitted from the result.

	Args:
		files: Absolute Python file paths to check. Sorted internally.
		check: Callable receiving a repo-relative POSIX path and a parsed
			ast.Module, returning a list of violation lines.

	Returns:
		dict[str, list[str]]: Repo-relative POSIX key -> violation lines,
			containing only files with at least one line.
	"""
	result = {}
	# Sort so the scan order is deterministic regardless of caller ordering.
	for path in sorted(files):
		rel = rel_to_root(path)
		tree, error = parse_source(path)
		# Parsing failed: record one SyntaxError entry and skip the AST check.
		if tree is None:
			result[rel] = [f"{rel}: SyntaxError: {error}"]
			continue
		lines = check(rel, tree)
		# Only include files that produced at least one violation line.
		if lines:
			result[rel] = lines
	return result


#============================================
def format_violation_report(header: str, violations_by_file: dict[str, list[str]]) -> list[str]:
	"""
	Build the full report body from a violations dict.

	INVARIANT: returns an EMPTY list when violations_by_file is empty -- never
	[header] alone. Callers use the empty/non-empty result to decide whether to
	write a report, so a [header]-on-clean bug would make every clean module
	write a stale report. When non-empty, the header is the first element,
	followed by each file's lines in sorted key order.

	Args:
		header: Header line placed first when there is at least one violation.
		violations_by_file: Repo-relative POSIX key -> list of violation lines.

	Returns:
		list[str]: Raw report lines without trailing newlines. Empty on a clean
			run (empty dict).
	"""
	# Clean run: empty dict yields an empty list so callers write nothing.
	if not violations_by_file:
		return []
	# Emit the header, then each file's lines in sorted key order.
	lines = [header]
	for rel in sorted(violations_by_file):
		lines += violations_by_file[rel]
	return lines


#============================================
def format_violation_assert_message(rel: str, lines: list[str], report_name: str) -> str:
	"""
	Build the per-file assert failure message for a hygiene test.

	Assembles a count, the offending repo-relative path, the joined violation
	lines, and a pointer to the repo-relative report path. Built only on the
	failure path: callers pass this call as the assert message so it runs only
	when the assert fails, not on every passing file.

	Args:
		rel: Repo-relative POSIX path of the offending file.
		lines: Violation lines for that file.
		report_name: Report filename used to resolve the repo-relative pointer.

	Returns:
		str: The assembled assert message.
	"""
	# Resolve the report path as a repo-relative pointer for the message tail.
	report_rel = rel_to_root(report_path(report_name))
	# Assemble count + path + joined lines + report pointer.
	message = f"{len(lines)} violation(s) in {rel}:\n"
	message += "\n".join(lines)
	# Leading space before "See" is intentional: it separates the report pointer
	# from the joined violation lines above it in pytest's failure output.
	message += f"\n See {report_rel}."
	return message


#============================================
def write_report_lines(report_name: str, lines: list[str]) -> str:
	"""
	Write violation lines to a repo-root report file (pure write, no purge).

	Joins lines with newline plus a single trailing newline and truncate-writes
	the report via write_report. Callers invoke this ONLY when lines is non-empty;
	the guarded clear_stale_reports owns removal of clean-run reports.

	Args:
		report_name: Full report filename, for example "report_function_typing.txt".
		lines: Raw violation lines without trailing newlines. Each line gets
			exactly one trailing newline.

	Returns:
		str: Absolute path to the written report file.
	"""
	# Build the full body with one trailing newline, then truncate-write.
	text = "\n".join(lines) + "\n"
	return write_report(report_name, text)


#============================================
def rel_id(path: str) -> str:
	"""
	Return the repo-relative POSIX path for use as a parametrize id.

	This is the shared parametrize-id callback for aligned hygiene modules,
	replacing the repeated ids=lambda p: file_utils.rel_to_root(p).

	Args:
		path: Absolute filesystem path inside the repository.

	Returns:
		str: Repo-relative POSIX path.
	"""
	return rel_to_root(path)


#============================================
def run_fixer_script(script_name: str, target: str) -> tuple[int, str]:
	"""
	Run a fixer script that lives in the tests directory.

	Resolves the script under tests/ relative to the repo root and runs it with
	the target as its -i argument. Returns (returncode, stderr) for every
	subprocess completion; never raises on a fixer exit code.

	Fixer exit code contracts:
	- fix_ascii_compliance.py: 0=already clean, 1=unfixable characters remain, 2=fixed
	- fix_whitespace.py: 0=already clean or fixed, 1=missing or no-input file, never 2

	Raises RuntimeError only for environment preconditions:
	- script_path does not exist on disk (checked before launch)
	- python3 interpreter not found (FileNotFoundError from subprocess.run)

	These are test environment failures, not per-file fixer outcomes.

	Args:
		script_name: Filename of the fixer script under tests/.
		target: Path passed to the fixer script via its -i flag.

	Returns:
		tuple[int, str]: (returncode, stderr) from the fixer subprocess.
	"""
	# Compute the repo root once; used for both script_path and cwd.
	root = get_repo_root()
	# The fixer scripts live in tests/ relative to the repo root; no fallback path lookup.
	script_path = os.path.join(root, "tests", script_name)
	# Verify the script exists before attempting to launch it.
	if not os.path.isfile(script_path):
		raise RuntimeError(
			f"Fixer script not found: {script_path}; test environment is broken."
		)
	# Run the fixer in the repo root so its own path resolution is consistent.
	# Build the command first so the try body stays a single line per style.
	command = ["python3", script_path, "-i", target]
	try:
		result = subprocess.run(command, capture_output=True, text=True, cwd=root)
	except FileNotFoundError as exc:
		raise RuntimeError("python3 interpreter not found; test environment is broken.") from exc
	# Return the raw outcome; callers interpret the exit code.
	return result.returncode, result.stderr


#============================================
def _run_git(repo_root: str, args: list[str], error_message: str) -> str:
	"""
	Run a git command and return stdout.

	Args:
		repo_root: Repo root used as the working directory.
		args: Git command argument list.
		error_message: Fallback error message.

	Returns:
		str: Command stdout.
	"""
	result = subprocess.run(
		args,
		capture_output=True,
		text=True,
		cwd=repo_root,
	)
	if result.returncode != 0:
		message = result.stderr.strip() or error_message
		raise AssertionError(message)
	return result.stdout


#============================================
def _split_null(output: str) -> list[str]:
	"""
	Split a NUL-separated stdout string into paths.

	Args:
		output: Raw stdout string from git ls-files -z, with NUL between paths.

	Returns:
		list[str]: Non-empty path strings split on the NUL delimiter.
	"""
	paths = []
	for path in output.split("\0"):
		if not path:
			continue
		paths.append(path)
	return paths


# Per-repo_root cache of the whole-repo tracked-file listing. Only the
# no-pattern call (used by discover_files via _gather_all_paths) is cached,
# because that is the listing the 11 hygiene modules each rebuild at
# collection time. Pattern-scoped calls stay uncached. Keyed by repo_root so
# regression tests that point at a temporary root never collide with the real
# repo listing.
_ALL_TRACKED_FILES_CACHE: dict[str, list[str]] = {}


#============================================
def list_tracked_files(
	repo_root: str,
	patterns: list[str] | None = None,
	error_message: str | None = None,
) -> list[str]:
	"""
	List tracked files using git ls-files.

	The no-pattern whole-repo listing (patterns is None or empty) is memoized
	per repo_root in _ALL_TRACKED_FILES_CACHE, so discover_files does not spawn
	git ls-files once per hygiene module at collection time. Pattern-scoped
	calls are never cached and always spawn git, since their result depends on
	the pathspecs. The cache is keyed by repo_root so tmp-root regression tests
	stay isolated from the real repo listing.

	Args:
		repo_root: Absolute path to the repository root directory.
		patterns: Optional list of pathspecs to pass after -- to git ls-files.
			When None or empty, all tracked files are listed.
		error_message: Message for AssertionError on git failure. Defaults to
			"Failed to list tracked files."

	Returns:
		list[str]: Repo-relative POSIX paths of all matching tracked files.
	"""
	if error_message is None:
		error_message = "Failed to list tracked files."
	# Serve the whole-repo (no-pattern) listing from the per-root cache.
	if not patterns:
		cached = _ALL_TRACKED_FILES_CACHE.get(repo_root)
		if cached is not None:
			# Return a copy so callers cannot mutate the cached listing.
			return list(cached)
		output = _run_git(repo_root, ["git", "ls-files", "-z"], error_message)
		paths = _split_null(output)
		_ALL_TRACKED_FILES_CACHE[repo_root] = paths
		return list(paths)
	# Pattern-scoped listing: always spawn git, never cache.
	command = ["git", "ls-files", "-z", "--"] + patterns
	output = _run_git(repo_root, command, error_message)
	return _split_null(output)


#============================================
def path_has_skip_dir(path: str) -> bool:
	"""
	Check whether any path SEGMENT equals a skipped directory.

	Match a full segment: "legacy/foo.py" is skipped, "notlegacy/foo.py"
	is kept. Normalize separators to "/" first so git-style and OS-style
	paths behave the same.

	Args:
		path: A path string, separators in either "/" or "\\" form.

	Returns:
		bool: True when any full segment is in SKIP_DIRS.
	"""
	# Normalize Windows-style separators so segment splitting is uniform.
	normalized = path.replace("\\", "/")
	parts = normalized.split("/")
	# Match a full path segment, never a substring.
	for part in parts:
		if part in SKIP_DIRS:
			return True
	return False


#============================================
def _load_repo_hygiene_filters() -> dict:
	"""
	Load the repo-local hygiene-filter registry from conftest.

	The registry is the repo-local exclusion layer (Layer 2). It lives in
	tests/conftest.py as a module attribute REPO_HYGIENE_FILTERS, because
	conftest survives propagation (propagation only merges a collect_ignore
	block into it) while vendored test files and this module do not. Vendored
	files must hold no repo-specific data, so repo-specific exclusions live
	here instead.

	The registry loads from the explicit tests/conftest.py path anchored at
	the repo root, never by module name. A module-name lookup would resolve
	to whichever conftest.py pytest imported first: under full-suite
	collection order a same-basename conftest elsewhere (for example
	tests/meta/conftest.py, which sorts before test_*) can win
	sys.modules["conftest"] and silently shadow the real registry. Loading by
	file path removes that shadowing entirely.

	An absent conftest or an absent REPO_HYGIENE_FILTERS attribute is normal:
	a repo with no repo-local exclusions simply has an empty registry.

	Returns:
		dict: Mapping of key -> list of repo-relative POSIX glob patterns.
			Keys are "all" plus vendored test keys. Empty when absent.
	"""
	# Anchor the load at the explicit repo-root conftest path, not a name.
	conftest_path = os.path.join(get_repo_root(), "tests", "conftest.py")
	# An absent conftest is normal for a repo with no repo-local exclusions.
	if not os.path.isfile(conftest_path):
		return {}
	# Load by file path under a private module name so the load never touches
	# or trusts sys.modules["conftest"]; do not insert it into sys.modules.
	spec = importlib.util.spec_from_file_location("_repo_hygiene_conftest", conftest_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	registry = getattr(module, "REPO_HYGIENE_FILTERS", {})
	return registry



#============================================
def discover_files(
	extensions: collections.abc.Iterable | None = None,
	extra_filter: collections.abc.Callable | None = None,
	*,
	test_key: str | None = None,
	repo_root: str | None = None,
) -> list[str]:
	"""
	Discover all tracked files for a hygiene scan.

	This is the canonical file-discovery helper for repo-hygiene tests. It
	owns all invariant discovery work (absolute-path join, dedupe, skip-dir
	filtering, extension filtering, isfile check, and sort). Tests inject
	only what is genuinely per-test. Discovery always scans all tracked files
	via git ls-files with no env-var dependency.

	Exclusion uses three layers, applied in this order:

	- Layer 1, SKIP_DIRS (vendored, this module): universal directory
	  exclusions via path_has_skip_dir; identical across all repos.
	- Layer 2, REPO_HYGIENE_FILTERS (repo-local, tests/conftest.py): per-test
	  repo-local file/glob exclusions keyed by "all" or a vendored test_key.
	  This is the home for any repo-specific exclusion, because conftest
	  survives propagation while vendored files do not.
	- Layer 3, extra_filter (vendored call site): a universal per-test
	  SELECTION mechanism only (for example keep only __init__.py), never a
	  home for repo-specific exclusions.

	Args:
		extensions: Optional iterable of file extensions to keep (each like
			".py"); None means all files. Extension match is case-insensitive.
		extra_filter: Optional callable receiving a REPO-RELATIVE POSIX path
			and returning True to keep the file. None means keep all.
		test_key: Keyword-only. Vendored test key (the test filename stem
			without the leading "test_", for example "pyflakes_code_lint")
			used to select per-test-key Layer 2 patterns. None means only the
			"all" patterns apply.
		repo_root: Keyword-only injection point for tests only; normal callers
			omit it. Defaults to get_repo_root() when None. Regression tests
			pass it in by keyword to point discovery at a controlled tmp root.

	Returns:
		list[str]: Sorted ABSOLUTE paths that pass every filter.
	"""
	# When repo_root is not provided, compute it via get_repo_root().
	if repo_root is None:
		repo_root = get_repo_root()
	# Lowercase the extension set once so step 6 comparison is well-defined.
	extension_set = None
	if extensions is not None:
		extension_set = {ext.lower() for ext in extensions}

	# Step 1: gather all tracked file absolute paths. _gather_all_paths joins
	# each git-relative path to repo_root with no env dependency.
	raw = _gather_all_paths(repo_root)

	# Step 2-3: normalize to clean absolute paths and dedupe on the result.
	seen = set()
	abs_paths = []
	for joined in raw:
		abs_path = os.path.normpath(os.path.abspath(joined))
		if abs_path in seen:
			continue
		seen.add(abs_path)
		abs_paths.append(abs_path)

	# Hoist the registry load and pattern list once before the loop so
	# _load_repo_hygiene_filters() is called only once per discover_files call,
	# not once per file.
	registry = _load_repo_hygiene_filters()
	hygiene_patterns = list(registry.get("all", []))
	if test_key is not None:
		hygiene_patterns += list(registry.get(test_key, []))

	# Steps 4-9: apply the filter pipeline in contract order.
	matches = []
	for abs_path in abs_paths:
		# Step 4: repo-relative POSIX path for skip-dir and extra_filter.
		rel = os.path.relpath(abs_path, repo_root).replace("\\", "/")
		# Step 5: Layer 1 -- drop any path under a skipped directory.
		if path_has_skip_dir(rel):
			continue
		# Step 6: case-insensitive extension filter when requested.
		if extension_set is not None:
			ext = os.path.splitext(abs_path)[1].lower()
			if ext not in extension_set:
				continue
		# Step 7: Layer 2 -- repo-local hygiene excludes from conftest.
		if any(fnmatch.fnmatchcase(rel, pattern) for pattern in hygiene_patterns):
			continue
		# Step 8: Layer 3 -- per-test selection filter on the relative path.
		if extra_filter is not None and not extra_filter(rel):
			continue
		# Step 9: keep only real files.
		if not os.path.isfile(abs_path):
			continue
		matches.append(abs_path)

	# Step 10: sort ascending and return absolute paths.
	matches.sort()
	return matches


#============================================
def _gather_all_paths(repo_root: str) -> list[str]:
	"""
	Gather all tracked files joined to repo_root (no filtering).

	Args:
		repo_root: Absolute path to the repository root directory; used as
			the base for os.path.join on each repo-relative path.

	Returns:
		list[str]: Absolute paths to every tracked file under repo_root,
			in the order returned by git ls-files.
	"""
	paths = []
	for path in list_tracked_files(repo_root):
		paths.append(os.path.join(repo_root, path))
	return paths
