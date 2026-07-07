# Standard Library
import os
import stat

# PIP3 modules
import pytest

# local repo modules
import file_utils


REPO_ROOT = file_utils.get_repo_root()
PYTHON_SHEBANG = "#!/usr/bin/env python3"
REPORT_NAME = file_utils.report_name(__file__)
HEADER = "Shebang issues found:"
# discover_files excludes symlinks via isfile; no extension filter -- shebangs
# apply to any file type tracked in the repo.
FILES = file_utils.discover_files(test_key="shebangs")

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}


#============================================
def read_shebang(path: str) -> str:
	"""
	Read the shebang line if present.

	Args:
		path: File path.

	Returns:
		str: Shebang line without newline, or empty string if none.
	"""
	try:
		with open(path, "rb") as handle:
			line = handle.readline(200)
	except OSError:
		return ""
	if not line.startswith(b"#!"):
		return ""
	# Rust inner attributes start with #![ and are not shebangs
	if line.startswith(b"#!["):
		return ""
	try:
		return line.decode("utf-8").rstrip("\n")
	except UnicodeDecodeError:
		return line.decode("utf-8", errors="replace").rstrip("\n")


#============================================
def is_executable(path: str) -> bool:
	"""
	Check whether any executable bit is set on a file.

	Args:
		path: File path.

	Returns:
		bool: True if executable for user/group/other.
	"""
	try:
		mode = os.stat(path).st_mode
	except OSError:
		return False
	return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


#============================================
def has_main_guard(path: str) -> bool:
	"""
	Check whether a Python file has a __name__ == '__main__' guard.

	Args:
		path: File path.

	Returns:
		bool: True if the file contains a main guard pattern.
	"""
	try:
		with open(path, "r", encoding="utf-8", errors="ignore") as handle:
			content = handle.read()
	except OSError:
		return False
	# Look for common patterns
	patterns = [
		"__name__ == '__main__'",
		'__name__ == "__main__"',
		"__name__=='__main__'",
		'__name__=="__main__"',
	]
	for pattern in patterns:
		if pattern in content:
			return True
	return False


#============================================
def is_test_file(path: str) -> bool:
	"""
	Detect whether a Python file is a test file.

	Checks if the filename matches test_*.py and the content
	imports pytest.

	Args:
		path: Absolute file path.

	Returns:
		bool: True if the file is a pytest test file.
	"""
	basename = os.path.basename(path)
	if not basename.startswith("test_") or not basename.endswith(".py"):
		return False
	try:
		with open(path, "r", encoding="utf-8", errors="ignore") as handle:
			content = handle.read()
	except OSError:
		return False
	if "import pytest" in content or "from pytest" in content:
		return True
	return False


#============================================
def check_file(rel: str) -> list[str]:
	"""
	Check one file for shebang and executable-bit violations.

	Resolves the absolute path from the repo-relative path, then checks all
	seven shebang/executable categories. Returns one violation line per
	triggered category in the form "{rel}: {category}".

	Args:
		rel: Repo-relative POSIX path of the file to check.

	Returns:
		list[str]: Violation lines (empty when the file is clean).
	"""
	# Resolve absolute path for all file-level checks.
	abs_path = os.path.join(REPO_ROOT, rel)
	shebang = read_shebang(abs_path)
	exec_flag = is_executable(abs_path)
	is_python = abs_path.endswith(".py")
	has_guard = has_main_guard(abs_path) if is_python else False

	violations = []
	# A shebang must be paired with the executable bit.
	if shebang and not exec_flag:
		violations.append(f"{rel}: shebang_not_executable")
	# An executable bit must be paired with a shebang.
	if exec_flag and not shebang:
		violations.append(f"{rel}: executable_no_shebang")
	# Python shebangs must use exactly the canonical form.
	if shebang and "python" in shebang:
		if shebang != PYTHON_SHEBANG:
			violations.append(f"{rel}: python_shebang_invalid")

	# Python-specific main guard alignment checks.
	if is_python:
		if shebang and not has_guard:
			violations.append(f"{rel}: shebang_without_main_guard")
		if has_guard and not shebang and exec_flag:
			violations.append(f"{rel}: main_guard_missing_shebang")

		# Test files must not have shebangs or executable bits.
		if is_test_file(abs_path):
			if shebang:
				violations.append(f"{rel}: test_file_has_shebang")
			if exec_flag:
				violations.append(f"{rel}: test_file_is_executable")

	return violations


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
	VIOLATIONS_BY_FILE.update(file_utils.collect_file_violations(FILES, check_file))
	lines = file_utils.format_violation_report(HEADER, VIOLATIONS_BY_FILE)
	# Write only when there are violations; cleanup already removed stale reports.
	if lines:
		file_utils.write_report_lines(REPORT_NAME, lines)


#============================================
@pytest.mark.parametrize("path", FILES, ids=file_utils.rel_id)
def test_shebang_executable_alignment(path: str) -> None:
	"""Ensure shebangs and executable bits are aligned for every tracked file."""
	rel = file_utils.rel_to_root(path)
	# Python evaluates an assert's message expression ONLY when the assert fails,
	# so format_violation_assert_message runs on the failing path only -- not per pass.
	assert rel not in VIOLATIONS_BY_FILE, file_utils.format_violation_assert_message(
		rel, VIOLATIONS_BY_FILE.get(rel, []), REPORT_NAME
	)
