# Standard Library
import ast

# PIP3 modules
import pytest

# local repo modules
import file_utils

FILES = file_utils.discover_files(extensions=(".py",), test_key="import_star")

REPORT_NAME = file_utils.report_name(__file__)

HEADER = "Import star report"

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}


#============================================
def _find_import_star_matches(tree: ast.Module) -> list[tuple[int, str]]:
	"""
	Return (line_no, module_name) tuples for every from-import * in the tree.

	Uses file_utils.iter_imports for consistent import-node gathering.
	Each from-import * yields one tuple; line_no defaults to 0 when absent.

	Args:
		tree: Parsed AST module to scan.

	Returns:
		list[tuple[int, str]]: (line_no, module_name) pairs, one per star import.
	"""
	matches = []
	# Use shared iter_imports instead of a local ast.walk for import-node gathering.
	for node in file_utils.iter_imports(tree):
		if not isinstance(node, ast.ImportFrom):
			continue
		for alias in node.names:
			if alias.name != "*":
				continue
			line_no = getattr(node, "lineno", 0) or 0
			module_name = node.module or ""
			# Prepend dots for relative star imports (e.g., from . import *).
			if getattr(node, "level", 0):
				module_name = f"{'.' * node.level}{module_name}"
			matches.append((line_no, module_name))
			break
	return matches


#============================================
def _format_issue(rel_path: str, line_no: int, module_name: str) -> str:
	"""
	Format a single report line for an import * usage.

	Args:
		rel_path: Repo-relative POSIX path of the file.
		line_no: Line number of the star import.
		module_name: Module name being star-imported (empty string for bare `import *`).

	Returns:
		str: Formatted issue line.
	"""
	if module_name:
		return f"{rel_path}:{line_no}: import * from {module_name}"
	return f"{rel_path}:{line_no}: import *"


#============================================
def check_file(rel: str, tree: ast.Module) -> list[str]:
	"""
	Run import * detection on one parsed module and return violation lines.

	Thin module-specific combiner. Receives a real ast.Module: the shared
	file_utils.collect_python_violations owns parsing and SyntaxError capture, so
	this is only reached for files that parsed cleanly.

	Args:
		rel: Repo-relative POSIX path for error messages.
		tree: Parsed ast.Module for the file.

	Returns:
		list[str]: Violation lines (empty when the file is clean).
	"""
	# Detect all from-import * usages in this file.
	matches = _find_import_star_matches(tree)
	if not matches:
		return []
	# Format and deduplicate issue lines, then sort for stable output.
	issues = sorted(set(_format_issue(rel, line_no, module_name) for line_no, module_name in matches))
	return issues


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
	# Write only when there are violations; cleanup already removed stale reports.
	if lines:
		file_utils.write_report_lines(REPORT_NAME, lines)


#============================================
@pytest.mark.parametrize("path", FILES, ids=file_utils.rel_id)
def test_import_star(path: str) -> None:
	"""Enforce no import * usage repo-wide."""
	rel = file_utils.rel_to_root(path)
	# Python evaluates an assert's message expression ONLY when the assert fails,
	# so format_violation_assert_message runs on the failing path only -- not per pass.
	assert rel not in VIOLATIONS_BY_FILE, file_utils.format_violation_assert_message(
		rel, VIOLATIONS_BY_FILE.get(rel, []), REPORT_NAME
	)
