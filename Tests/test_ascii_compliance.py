# Standard Library
import os
import re
import sys
import types
import random
import importlib.util

# PIP3 modules
import pytest

# local repo modules
import file_utils

REPO_ROOT = file_utils.get_repo_root()
REPORT_NAME = file_utils.report_name(__file__)
ERROR_RE = re.compile(r":[0-9]+:[0-9]+:")
CODEPOINT_RE = re.compile(r"non-ISO-8859-1 character U\+([0-9A-Fa-f]{4,6})")
ERROR_SAMPLE_COUNT = 5
PROGRESS_EVERY = 1

HEADER = "ASCII compliance errors detected:"

ASCII_EXTENSIONS = {
	".md",
	".txt",
	".py",
	".js",
	".jsx",
	".ts",
	".tsx",
	".html",
	".htm",
	".css",
	".json",
	".yml",
	".yaml",
	".toml",
	".ini",
	".cfg",
	".conf",
	".sh",
	".bash",
	".zsh",
	".fish",
	".csv",
	".tsv",
	".xml",
	".svg",
	".sql",
	".rb",
	".php",
	".java",
	".c",
	".h",
	".cpp",
	".hpp",
	".go",
	".rs",
	".swift",
}

# Module-level file list built once at import time for the ascii compliance scan.
FILES = file_utils.discover_files(
	extensions=ASCII_EXTENSIONS,
	test_key="ascii_compliance",
)

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}


#============================================
def load_module(name: str, path: str) -> types.ModuleType:
	"""
	Load a module from a file path without sys.path edits.

	Args:
		name: Module name to register.
		path: File path to load.

	Returns:
		types.ModuleType: The loaded module.
	"""
	spec = importlib.util.spec_from_file_location(name, path)
	if spec is None or spec.loader is None:
		raise RuntimeError(f"Unable to load module: {path}")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


#============================================
def is_emoji_codepoint(codepoint: int) -> bool:
	"""
	Check whether a codepoint is likely an emoji.

	Args:
		codepoint: Unicode codepoint integer.

	Returns:
		bool: True when the codepoint is in a known emoji range.
	"""
	if 0x1F000 <= codepoint <= 0x1FAFF:
		return True
	if 0x2600 <= codepoint <= 0x27BF:
		return True
	return False


#============================================
def is_ascii_bytes(file_path: str, chunk_size: int = 1024 * 1024) -> bool:
	"""
	Check whether a file contains only ASCII bytes.

	Args:
		file_path: Absolute path to the file.
		chunk_size: Number of bytes to read per chunk.

	Returns:
		bool: True when every byte is in the ASCII range.
	"""
	with open(file_path, "rb") as handle:
		while True:
			chunk = handle.read(chunk_size)
			if not chunk:
				break
			if not chunk.isascii():
				return False
	return True


#============================================
def shorten_error_path(line: str) -> str:
	"""
	Shorten a full error path to just the basename.

	Args:
		line: Error line beginning with a file path followed by a colon.

	Returns:
		str: Error line with the path replaced by its basename.
	"""
	separator = line.find(":")
	if separator == -1:
		return line
	path = line[:separator]
	remainder = line[separator:]
	return f"{os.path.basename(path)}{remainder}"


#============================================
def sample_errors(lines: list[str], count: int) -> list[str]:
	"""
	Sample up to N error lines.

	Args:
		lines: Full list of error lines.
		count: Maximum number to return.

	Returns:
		list[str]: Up to count randomly selected lines.
	"""
	if len(lines) <= count:
		return list(lines)
	return random.sample(lines, count)


#============================================
def list_error_files(lines: list[str]) -> list[str]:
	"""
	Collect unique file paths from error lines.

	Args:
		lines: Error lines, each starting with a file path followed by a colon.

	Returns:
		list[str]: Sorted unique file paths extracted from the lines.
	"""
	paths = set()
	for line in lines:
		separator = line.find(":")
		if separator == -1:
			continue
		paths.add(line[:separator])
	return sorted(paths)


#============================================
def count_error_details(lines: list[str]) -> tuple[dict[str, int], dict[str, int]]:
	"""
	Count errors by file and by Unicode codepoint.

	Args:
		lines: Error lines containing file paths and codepoint references.

	Returns:
		tuple[dict[str, int], dict[str, int]]: Counts by file path and by codepoint hex string.
	"""
	file_counts: dict[str, int] = {}
	codepoint_counts: dict[str, int] = {}
	for line in lines:
		match = CODEPOINT_RE.search(line)
		if not match:
			continue
		separator = line.find(":")
		if separator == -1:
			continue
		file_path = line[:separator]
		file_counts[file_path] = file_counts.get(file_path, 0) + 1
		codepoint = match.group(1).upper()
		codepoint_counts[codepoint] = codepoint_counts.get(codepoint, 0) + 1
	return file_counts, codepoint_counts


#============================================
def top_items(counts: dict[str, int], limit: int) -> list[tuple[str, int]]:
	"""
	Sort a count dictionary by descending count.

	Args:
		counts: Mapping of label to integer count.
		limit: Maximum number of items to return.

	Returns:
		list[tuple[str, int]]: Up to limit items sorted by descending count.
	"""
	items = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
	return items[:limit]


#============================================
def format_issue_line(
	file_path: str,
	line_number: int,
	column_number: int,
	codepoint: int,
) -> str:
	"""
	Format an ASCII compliance issue line.

	Args:
		file_path: Path to the file containing the issue.
		line_number: Line number of the issue.
		column_number: Column number of the issue.
		codepoint: Unicode codepoint integer.

	Returns:
		str: Formatted issue description line.
	"""
	display_char = chr(codepoint)
	if not display_char.isprintable():
		display_char = "?"
	codepoint_text = f"U+{codepoint:04X}"
	return (
		f"{file_path}:{line_number}:{column_number}: "
		f"non-ISO-8859-1 character {codepoint_text} {display_char}"
	)


#============================================
def scan_file(
	file_path: str,
	check_module: types.ModuleType,
	apply_fix: bool,
) -> tuple[int, list[str], bool]:
	"""
	Check a file and optionally apply fixes.

	Args:
		file_path: Absolute path to the file to scan.
		check_module: Loaded check_ascii_compliance module.
		apply_fix: Whether to run the fixer script on non-compliant files.

	Returns:
		tuple[int, list[str], bool]: Status code (0=clean, 1=errors, 2=fixed),
			list of error lines, and whether a fix was applied. Status 1 also
			covers two fixer-outcome cases: an unexpected fixer exit code
			(not 0/1/2, re-check skipped), and fixer exit 1 where the re-check
			finds no remaining violations (recorded as an inconsistency line).
	"""
	if is_ascii_bytes(file_path):
		return 0, [], False

	content, read_error = check_module.read_text(file_path)
	if read_error:
		return 1, [read_error], False

	issues = check_module.check_ascii_compliance(content)
	if not issues:
		return 0, [], False

	# Run the shared fixer script in-place; returns (returncode, stderr), never raises.
	changed = False
	if apply_fix:
		returncode, stderr = file_utils.run_fixer_script("fix_ascii_compliance.py", file_path)
		# Unexpected exit code: fixer itself is broken; skip re-check to avoid stale output.
		if returncode not in (0, 1, 2):
			violation = f"{file_path}:0:0: fixer failed (exit {returncode}): {stderr}"
			return 1, [violation], False
		changed = True
		# Re-read and re-check the file after the fixer has written it.
		# The re-check is the source of truth for violation lines; fixer stderr is ignored.
		content, read_error = check_module.read_text(file_path)
		if read_error:
			return 1, [read_error], True
		issues = check_module.find_non_latin1_chars(content)
		if not issues:
			# Fixer exited 1 but re-check found no violations: record inconsistency.
			if returncode == 1:
				inconsistency = f"{file_path}:0:0: fixer exited 1 but re-check found no violations"
				return 1, [inconsistency], True
			return 2, [], True

	error_lines = []
	for line_number, column_number, codepoint in issues:
		error_lines.append(
			format_issue_line(file_path, line_number, column_number, codepoint)
		)
	total_message = f"{file_path}:0:0: found {len(issues)} non-ISO-8859-1 characters"
	error_lines.append(total_message)
	return 1, error_lines, changed


#============================================
def print_violation_summary(all_lines: list[str]) -> None:
	"""
	Print the three-phase error summary (first/random/last) to stdout.

	Args:
		all_lines: All raw error lines collected across files.
	"""
	error_lines = [line for line in all_lines if ERROR_RE.search(line)]

	print("")
	print(f"First {ERROR_SAMPLE_COUNT} errors")
	for line in error_lines[:ERROR_SAMPLE_COUNT]:
		print(shorten_error_path(line))
	print("-------------------------")
	print("")

	print(f"Random {ERROR_SAMPLE_COUNT} errors")
	for line in sample_errors(error_lines, ERROR_SAMPLE_COUNT):
		print(shorten_error_path(line))
	print("-------------------------")
	print("")

	print(f"Last {ERROR_SAMPLE_COUNT} errors")
	for line in error_lines[-ERROR_SAMPLE_COUNT:]:
		print(shorten_error_path(line))
	print("-------------------------")
	print("")

	error_files = list_error_files(error_lines)
	error_file_count = len(error_files)
	file_counts, codepoint_counts = count_error_details(error_lines)
	emoji_count = 0
	for codepoint in codepoint_counts:
		codepoint_int = int(codepoint, 16)
		if is_emoji_codepoint(codepoint_int):
			emoji_count += codepoint_counts[codepoint]

	if error_file_count <= 5:
		print(f"Files with errors ({error_file_count})")
		for path in error_files:
			count = file_counts.get(path, 0)
			print(f"{file_utils.rel_to_root(path)}: {count}")
		print("")
	else:
		print(f"Files with errors: {error_file_count}")
		top_files = top_items(file_counts, ERROR_SAMPLE_COUNT)
		if top_files:
			print("")
			print("Top 5 files by error count")
			for path, count in top_files:
				display_path = file_utils.rel_to_root(path)
				print(f"{display_path}: {count}")
	top_codepoints = top_items(codepoint_counts, ERROR_SAMPLE_COUNT)
	if top_codepoints:
		print("")
		print("Top 5 Unicode characters by frequency")
		for codepoint, count in top_codepoints:
			display_char = chr(int(codepoint, 16))
			if not display_char.isprintable() or display_char.isspace():
				display_char = "?"
			print(f"U+{codepoint} {display_char}: {count}")
	if emoji_count:
		print("")
		print(f"Found {emoji_count} emoji codepoints; handle them case by case.")


#============================================
@pytest.fixture(scope="module", autouse=True)
def collect_report(pytestconfig: pytest.Config) -> None:
	"""
	Autouse fixture: scan files, apply fixer if needed, populate VIOLATIONS_BY_FILE.

	Fixer logic runs here so it NEVER runs inside a parametrized test case.
	A fixer failure on one file becomes that file's violation entry, never a
	fixture exception, so a single bad file cannot error the whole module.
	Builds VIOLATIONS_BY_FILE from the post-fix re-scan. Writes the report only
	when violations remain after fixing. Dict is built directly (not via
	collect_file_violations) because the fixer interplay requires a custom
	scan-fix-rescan loop per file.

	Args:
		pytestconfig: Pytest configuration object used to resolve the fix flag.
	"""
	# Once-per-process guarded cleanup of repo-root report_*.txt.
	file_utils.clear_stale_reports()
	# Clear any state left from a previous collection in the same process.
	VIOLATIONS_BY_FILE.clear()

	check_path = os.path.join(REPO_ROOT, "tests", "check_ascii_compliance.py")
	if not os.path.isfile(check_path):
		raise RuntimeError(f"Missing script: {check_path}")
	check_module = load_module("check_ascii_compliance", check_path)

	if not FILES:
		return

	# Resolve whether fixes should be applied from the pytest config option.
	apply_fix = not pytestconfig.getoption("no_ascii_fix", default=False)
	progress_enabled = sys.stderr.isatty()
	if progress_enabled:
		print(f"ascii_compliance: scanning {len(FILES)} files...", file=sys.stderr)

	# Per-file scan: for each file, check -> optionally fix -> re-check.
	# Collect all raw lines for the summary printout, and rel-keyed lines for VIOLATIONS_BY_FILE.
	all_lines: list[str] = []
	for index, file_path in enumerate(sorted(FILES), start=1):
		rel = file_utils.rel_to_root(file_path)
		status, file_lines, _ = scan_file(file_path, check_module, apply_fix)
		all_lines.extend(file_lines)
		# Status 1 means violations remain after any fix attempt.
		if status == 1 and file_lines:
			VIOLATIONS_BY_FILE[rel] = file_lines
		if progress_enabled and (status != 0 or index % PROGRESS_EVERY == 0):
			if status == 0:
				sys.stderr.write(".")
			elif status == 2:
				sys.stderr.write("+")
			else:
				sys.stderr.write("!")
			sys.stderr.flush()

	if progress_enabled:
		sys.stderr.write("\n")
		sys.stderr.flush()

	# Print three-phase summary when there are violations.
	if VIOLATIONS_BY_FILE:
		print_violation_summary(all_lines)
	else:
		print("No errors found!!!")

	lines = file_utils.format_violation_report(HEADER, VIOLATIONS_BY_FILE)
	# Write only when there are violations; cleanup already removed stale reports.
	if lines:
		file_utils.write_report_lines(REPORT_NAME, lines)


#============================================
@pytest.mark.parametrize("path", FILES, ids=file_utils.rel_id)
def test_ascii_compliance(path: str) -> None:
	"""Enforce ASCII/ISO-8859-1 compliance for every tracked source file."""
	rel = file_utils.rel_to_root(path)
	# Python evaluates an assert's message expression ONLY when the assert fails,
	# so format_violation_assert_message runs on the failing path only -- not per pass.
	assert rel not in VIOLATIONS_BY_FILE, file_utils.format_violation_assert_message(
		rel, VIOLATIONS_BY_FILE.get(rel, []), REPORT_NAME
	)
