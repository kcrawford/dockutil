# Standard Library
import os
import pathlib
import tokenize

# PIP3 modules
import pytest

# local repo modules
import file_utils

FILES = file_utils.discover_files(extensions=(".py",), test_key="indentation")

REPORT_NAME = file_utils.report_name(__file__)

HEADER = "indentation violations"

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}


#============================================
def multiline_string_lines(path: pathlib.Path) -> set[int]:
	"""
	Collect lines that are part of multiline string tokens.

	Args:
		path: File path.

	Returns:
		set[int]: Line numbers inside multiline strings.
	"""
	in_string: set[int] = set()
	with tokenize.open(path) as handle:
		tokens = tokenize.generate_tokens(handle.readline)
		for token in tokens:
			if token.type != tokenize.STRING:
				continue
			start_line = token.start[0]
			end_line = token.end[0]
			if end_line > start_line:
				in_string.update(range(start_line, end_line + 1))
	return in_string


#============================================
def inspect_file(path: pathlib.Path) -> list[int]:
	"""
	Check a file for mixed leading indentation within a single line.

	Args:
		path: File path.

	Returns:
		list[int]: Line numbers with mixed indentation within a single line.
	"""
	ignore_lines = multiline_string_lines(path)
	with tokenize.open(path) as handle:
		lines = handle.read().splitlines()
	bad_lines = []
	for line_number, line in enumerate(lines, 1):
		if line_number in ignore_lines:
			continue
		if not line.strip():
			continue
		prefix_chars = []
		for ch in line:
			if ch == " " or ch == "\t":
				prefix_chars.append(ch)
				continue
			break
		if not prefix_chars:
			continue
		has_tab = "\t" in prefix_chars
		has_space = " " in prefix_chars
		if has_tab and has_space:
			bad_lines.append(line_number)
			continue
	return bad_lines


#============================================
def summarize_indentation(path: pathlib.Path) -> tuple[int, int] | None:
	"""
	Return first tab line and first space line if both exist in the file.

	Args:
		path: File path.

	Returns:
		tuple[int, int] | None: First tab line and first space line, or None.
	"""
	ignore_lines = multiline_string_lines(path)
	with tokenize.open(path) as handle:
		lines = handle.read().splitlines()
	first_tab_line = None
	first_space_line = None
	for line_number, line in enumerate(lines, 1):
		if line_number in ignore_lines:
			continue
		if not line.strip():
			continue
		prefix_chars = []
		for ch in line:
			if ch == " " or ch == "\t":
				prefix_chars.append(ch)
				continue
			break
		if not prefix_chars:
			continue
		has_tab = "\t" in prefix_chars
		has_space = " " in prefix_chars
		if has_tab and first_tab_line is None:
			first_tab_line = line_number
		if has_space and first_space_line is None:
			first_space_line = line_number
		if first_tab_line and first_space_line:
			return (first_tab_line, first_space_line)
	return None


#============================================
def check_file(rel: str) -> list[str]:
	"""
	Run indentation checks on one file and return any violations.

	Runs inspect_file (mixed indentation within a line) and
	summarize_indentation (tabs and spaces mixed across a file). Files with no
	violations return an empty list. The absolute path is resolved from rel via
	os.path.join(file_utils.get_repo_root(), rel); get_repo_root is cached so
	resolution does not spawn a subprocess per call.

	Args:
		rel: Repo-relative POSIX path for the file to check.

	Returns:
		list[str]: Violation lines (empty when the file is clean).
	"""
	# Resolve the absolute path from the cached repo root.
	abs_path = pathlib.Path(os.path.join(file_utils.get_repo_root(), rel))
	# Check for mixed indentation within individual lines.
	bad_lines = inspect_file(abs_path)
	violations = []
	if bad_lines:
		for ln in bad_lines[:5]:
			violations.append(f"{rel}:{ln}: mixed indentation within line")
	# Check for tabs and spaces mixed across the whole file.
	indent_lines = summarize_indentation(abs_path)
	if indent_lines is not None:
		tab_line, space_line = indent_lines
		violations.append(
			f"{rel}: tabs and spaces in file "
			f"(tab line {tab_line}, space line {space_line})"
		)
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
def test_indentation_style(path: str) -> None:
	"""Fail on mixed indentation within a line or within a file."""
	rel = file_utils.rel_to_root(path)
	# Python evaluates an assert's message expression ONLY when the assert fails,
	# so format_violation_assert_message runs on the failing path only -- not per pass.
	assert rel not in VIOLATIONS_BY_FILE, file_utils.format_violation_assert_message(
		rel, VIOLATIONS_BY_FILE.get(rel, []), REPORT_NAME
	)
