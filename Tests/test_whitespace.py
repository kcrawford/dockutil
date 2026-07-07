"""Repo-wide whitespace hygiene: BOM, CRLF, trailing whitespace, missing final newline."""

# Standard Library
import os

# PIP3 modules
import pytest

# local repo modules
import file_utils

# Text-format extensions that the whitespace hygiene check scans.
EXTENSIONS = (
	".md", ".txt", ".py", ".sh", ".bash", ".zsh",
	".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".conf",
	".csv", ".tsv", ".html", ".htm", ".css",
)

FILES = file_utils.discover_files(extensions=EXTENSIONS, test_key="whitespace")

REPORT_NAME = file_utils.report_name(__file__)

HEADER = "whitespace violations"

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}


#============================================
def _check_whitespace_bytes(data: bytes) -> list[str]:
	"""
	Detect whitespace issues in raw file bytes.

	Checks for UTF-8 BOM, CRLF or bare CR line endings, trailing whitespace on
	any line, and a missing final newline. Returns short label strings for each
	issue found, matching the original violation wording.

	Args:
		data: Raw bytes content of a file.

	Returns:
		list[str]: Issue labels found (empty when the file is clean).
	"""
	issues = []
	if data.startswith(b"\xef\xbb\xbf"):
		issues.append("utf-8 BOM")
	if b"\r\n" in data:
		issues.append("CRLF line endings")
	elif b"\r" in data:
		issues.append("CR line endings")

	# Normalize line endings for trailing-whitespace and final-newline checks.
	normalized = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
	for line in normalized.split(b"\n"):
		if line.endswith(b" ") or line.endswith(b"\t"):
			issues.append("trailing whitespace")
			break

	if normalized and not normalized.endswith(b"\n"):
		issues.append("missing final newline")
	return issues


#============================================
def check_file(rel: str) -> list[str]:
	"""
	Check one file for whitespace issues and return formatted violation lines.

	Resolves the repo-relative path to an absolute path, reads the raw bytes,
	and delegates to _check_whitespace_bytes. Returns a single formatted line
	when issues are found so collect_file_violations can store it.

	Args:
		rel: Repo-relative POSIX path of the file to check.

	Returns:
		list[str]: Single-element list with the formatted violation line, or
			empty list when the file is clean.
	"""
	# Resolve the absolute path from the repo-relative path.
	abs_path = os.path.join(file_utils.get_repo_root(), rel)
	with open(abs_path, "rb") as handle:
		data = handle.read()
	issues = _check_whitespace_bytes(data)
	if not issues:
		return []
	# Format matches original: "rel: issue1, issue2" in sorted order.
	violation_line = f"{rel}: " + ", ".join(sorted(set(issues)))
	return [violation_line]


#============================================
@pytest.fixture(scope="module", autouse=True)
def collect_report(pytestconfig: pytest.Config) -> None:
	"""
	Autouse fixture: clear stale reports, optionally fix violating files, populate VIOLATIONS_BY_FILE.

	Fixer logic runs here so it NEVER runs inside a parametrized test case.
	For each violating file, when fixing is enabled (--no-ascii-fix not set),
	runs fix_whitespace.py in-place then re-scans so VIOLATIONS_BY_FILE reflects
	only remaining (unfixed) violations. Writes the report only when violations remain.

	Args:
		pytestconfig: Pytest configuration object used to resolve the fix flag.
	"""
	# Once-per-process guarded cleanup of repo-root report_*.txt (no-op after first call).
	file_utils.clear_stale_reports()
	# Clear any state left from a previous collection in the same process.
	VIOLATIONS_BY_FILE.clear()

	# Resolve whether fixes should be applied from the pytest config option.
	# Matches the same option name and default used by test_ascii_compliance.py.
	apply_fix = not pytestconfig.getoption("no_ascii_fix", default=False)

	# Initial scan: collect all files with violations.
	initial_violations = file_utils.collect_file_violations(FILES, check_file)

	if apply_fix:
		# For each violating file, run the fixer then re-scan.
		for rel, _lines in initial_violations.items():
			abs_path = os.path.join(file_utils.get_repo_root(), rel)
			# run_fixer_script returns (returncode, stderr); never raises on fixer outcome.
			returncode, stderr = file_utils.run_fixer_script("fix_whitespace.py", abs_path)
			if returncode != 0:
				# Non-zero exit: fixer failed; record as violation and skip re-scan.
				VIOLATIONS_BY_FILE[rel] = [
					f"{rel}:0:0: fixer failed (exit {returncode}): {stderr}"
				]
				continue
			# Re-scan the file after the fixer has written it (exit 0 only).
			remaining = check_file(rel)
			if remaining:
				# Violations persist after fix; record them.
				VIOLATIONS_BY_FILE[rel] = remaining
		# Files not in initial_violations are clean; they stay out of VIOLATIONS_BY_FILE.
	else:
		# No fixing: all initial violations become the final result.
		VIOLATIONS_BY_FILE.update(initial_violations)

	lines = file_utils.format_violation_report(HEADER, VIOLATIONS_BY_FILE)
	# Write only when there are violations; cleanup already removed stale reports.
	if lines:
		file_utils.write_report_lines(REPORT_NAME, lines)


#============================================
@pytest.mark.parametrize("path", FILES, ids=file_utils.rel_id)
def test_whitespace_hygiene(path: str) -> None:
	"""Fail on whitespace issues in tracked text files."""
	rel = file_utils.rel_to_root(path)
	# Python evaluates an assert's message expression ONLY when the assert fails,
	# so format_violation_assert_message runs on the failing path only -- not per pass.
	assert rel not in VIOLATIONS_BY_FILE, file_utils.format_violation_assert_message(
		rel, VIOLATIONS_BY_FILE.get(rel, []), REPORT_NAME
	)
