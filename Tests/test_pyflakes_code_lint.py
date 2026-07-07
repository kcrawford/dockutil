# Standard Library
import os
import shutil
import subprocess

# PIP3 modules
import pytest

# local repo modules
import file_utils

REPO_ROOT = file_utils.get_repo_root()
REPORT_NAME = file_utils.report_name(__file__)
HEADER = "pyflakes violations"
CHUNK_SIZE = 200

# Module-level dict of repo-relative POSIX key -> list of pyflakes output lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}

FILES = file_utils.discover_files(extensions=(".py",), test_key="pyflakes_code_lint")


#============================================
def chunked(items: list[str], size: int) -> list[list[str]]:
	"""
	Split items into fixed-size chunks.

	Args:
		items: The list to split.
		size: Maximum size for each chunk.

	Returns:
		list[list[str]]: Sub-lists of at most size items.
	"""
	chunks = []
	for start in range(0, len(items), size):
		chunks.append(items[start:start + size])
	return chunks


#============================================
def normalize_path(path: str) -> str:
	"""
	Normalize a path for stable comparisons.

	Args:
		path: Filesystem path.

	Returns:
		str: Absolute, real path.
	"""
	return os.path.realpath(os.path.abspath(path))


#============================================
def index_output_lines(lines: list[str]) -> dict[str, list[str]]:
	"""
	Index pyflakes output lines by normalized file path.

	Args:
		lines: Raw stdout/stderr lines from a pyflakes run.

	Returns:
		dict[str, list[str]]: Normalized absolute path -> list of pyflakes lines.
	"""
	index: dict[str, list[str]] = {}
	for line in lines:
		separator = line.find(":")
		if separator == -1:
			continue
		path_text = line[:separator]
		normalized = normalize_path(path_text)
		if normalized not in index:
			index[normalized] = []
		index[normalized].append(line)
	return index


#============================================
def run_pyflakes(repo_root: str, files: list[str]) -> list[str]:
	"""
	Run pyflakes on a file list and return output lines.

	Args:
		repo_root: Repository root used as the working directory.
		files: Absolute paths of Python files to check.

	Returns:
		list[str]: Combined stdout and stderr lines from pyflakes.
	"""
	if not files:
		return []
	pyflakes_bin = shutil.which("pyflakes")
	if not pyflakes_bin:
		raise RuntimeError("pyflakes not found on PATH.")
	output_lines = []
	for chunk in chunked(files, CHUNK_SIZE):
		result = subprocess.run(
			[pyflakes_bin] + chunk,
			capture_output=True,
			text=True,
			cwd=repo_root,
		)
		if result.stdout:
			output_lines.extend(result.stdout.splitlines())
		if result.stderr:
			output_lines.extend(result.stderr.splitlines())
	return output_lines


#============================================
def collect_violations(files: list[str]) -> dict[str, list[str]]:
	"""
	Run pyflakes once over all files and return per-file violation lines.

	Runs a single batched pyflakes subprocess on the full file list, indexes
	the output by normalized file path, then maps each input file to its
	pyflakes lines using repo-relative POSIX keys. This is the scan-once path:
	one pyflakes invocation for the whole repo, never one per file. Files with
	no pyflakes output are omitted from the returned dict.

	Args:
		files: Absolute paths of Python files to check.

	Returns:
		dict[str, list[str]]: Repo-relative POSIX key -> list of pyflakes
			output lines, containing only files with at least one line.
	"""
	# Single batched pyflakes run over every file (chunked only to stay under argv limits).
	all_lines = run_pyflakes(REPO_ROOT, files)
	# Index raw lines by normalized absolute path for fast per-file lookup.
	line_index = index_output_lines(all_lines)
	result: dict[str, list[str]] = {}
	for path in files:
		normalized = normalize_path(path)
		file_lines = line_index.get(normalized, [])
		if not file_lines:
			continue
		# Store under the repo-relative POSIX key.
		rel = file_utils.rel_to_root(path)
		result[rel] = file_lines
	return result


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
	VIOLATIONS_BY_FILE.update(collect_violations(FILES))
	lines = file_utils.format_violation_report(HEADER, VIOLATIONS_BY_FILE)
	# Write only when there are violations; cleanup already removed stale reports.
	if lines:
		file_utils.write_report_lines(REPORT_NAME, lines)


#============================================
@pytest.mark.parametrize("path", FILES, ids=file_utils.rel_id)
def test_pyflakes(path: str) -> None:
	"""Enforce zero pyflakes violations on every Python file in the repo."""
	rel = file_utils.rel_to_root(path)
	# Python evaluates an assert's message expression ONLY when the assert fails,
	# so format_violation_assert_message runs on the failing path only -- not per pass.
	assert rel not in VIOLATIONS_BY_FILE, file_utils.format_violation_assert_message(
		rel, VIOLATIONS_BY_FILE.get(rel, []), REPORT_NAME
	)
