# Standard Library
import os
import json
import shutil
import tempfile
import subprocess

# PIP3 modules
import pytest

# local repo modules
import file_utils


REPO_ROOT = file_utils.get_repo_root()
REPORT_NAME = file_utils.report_name(__file__)

HEADER = "bandit security violations"

FILES = file_utils.discover_files(extensions=(".py",), test_key="bandit_security")

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}


#============================================
def run_bandit_json(repo_root: str, files: list[str]) -> dict:
	"""
	Run bandit ONCE over all files and return the parsed JSON report.

	Uses the same severity and confidence gates as the legacy aggregate test
	(medium/medium) plus `-f json -o <tmpfile>` so the structured results are
	read from the output FILE, not stdout. Bandit writes progress noise to
	stderr in JSON mode, so stdout and stderr are intentionally ignored.

	Args:
		repo_root: Repository root used as the subprocess working directory.
		files: Absolute paths of the Python files to scan.

	Returns:
		dict: Parsed bandit JSON report with `results` and `errors` keys.
	"""
	# Require bandit on PATH; a missing tool is an environment failure, not a pass.
	bandit_bin = shutil.which("bandit")
	if not bandit_bin:
		raise RuntimeError("bandit not found on PATH.")
	# Allocate a scratch output file for the JSON report and remove it after parsing.
	report_fd, report_file = tempfile.mkstemp(prefix="bandit_", suffix=".json")
	os.close(report_fd)
	command = [
		bandit_bin,
		"--severity-level",
		"medium",
		"--confidence-level",
		"medium",
		"-f",
		"json",
		"-o",
		report_file,
	] + files
	# One subprocess call per module run; stdout/stderr carry only progress noise.
	subprocess.run(command, capture_output=True, text=True, cwd=repo_root)
	with open(report_file, encoding="utf-8") as handle:
		report = json.load(handle)
	# Clean up the scratch report file now that the JSON is parsed.
	os.remove(report_file)
	return report


#============================================
def format_result_line(result: dict) -> str:
	"""
	Build one readable violation line from a single bandit result record.

	The line preserves the load-bearing fields: test id, severity, confidence,
	line number, and issue text, in a stable format suitable for the report.

	Args:
		result: One element of the bandit JSON `results` list.

	Returns:
		str: A single formatted violation line.
	"""
	# Pull the required fields directly; bandit always emits these on a result.
	test_id = result["test_id"]
	severity = result["issue_severity"]
	confidence = result["issue_confidence"]
	line_number = result["line_number"]
	issue_text = result["issue_text"]
	# Stable one-line shape: "B108 [MEDIUM/MEDIUM] line 12: <issue text>".
	line = f"{test_id} [{severity}/{confidence}] line {line_number}: {issue_text}"
	return line


#============================================
def collect_violations(files: list[str]) -> dict[str, list[str]]:
	"""
	Run bandit once and group formatted violation lines by repo-relative file.

	Each JSON result is keyed into the returned dict by the repo-relative POSIX
	path of its filename. Any entries in the bandit `errors` list are attached
	to the affected file when a filename is present; an error without an
	attributable file is an environment failure and raises RuntimeError.

	Args:
		files: Absolute paths of the Python files to scan.

	Returns:
		dict[str, list[str]]: Repo-relative POSIX key -> list of violation lines.
	"""
	violations_by_file: dict[str, list[str]] = {}
	# Empty discovery means nothing to scan; return an empty mapping.
	if not files:
		return violations_by_file
	report = run_bandit_json(REPO_ROOT, files)
	# Map each result to its repo-relative file key, preserving the key fields.
	for result in report["results"]:
		rel = file_utils.rel_to_root(result["filename"])
		line = format_result_line(result)
		violations_by_file.setdefault(rel, []).append(line)
	# Surface scan errors: attach to the affected file, or fail loudly if unattributable.
	for error in report["errors"]:
		filename = error["filename"]
		if not filename:
			raise RuntimeError(f"bandit scan error with no file: {error['reason']}")
		rel = file_utils.rel_to_root(filename)
		violations_by_file.setdefault(rel, []).append(f"scan error: {error['reason']}")
	return violations_by_file


#============================================
@pytest.fixture(scope="module", autouse=True)
def collect_report() -> None:
	"""
	Autouse fixture: clear stale reports, populate VIOLATIONS_BY_FILE, write report.

	Runs the guarded once-per-process cleanup first, rebuilds the module-level
	violations dict from a single bandit JSON run, then writes the report only
	when there are violations. Cleanup owns removal of clean-run reports, so a
	clean module writes nothing.
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
def test_bandit_security(path: str) -> None:
	"""Enforce no medium-or-higher bandit security findings repo-wide."""
	rel = file_utils.rel_to_root(path)
	# The assert message expression runs ONLY on the failing path, not per pass.
	assert rel not in VIOLATIONS_BY_FILE, file_utils.format_violation_assert_message(
		rel, VIOLATIONS_BY_FILE.get(rel, []), REPORT_NAME
	)
