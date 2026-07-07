# Standard Library
import ast

# PIP3 modules
import pytest

# local repo modules
import file_utils

FILES = file_utils.discover_files(extensions=(".py",), test_key="function_typing")

REPORT_NAME = file_utils.report_name(__file__)

HEADER = "function typing violations"

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}

# Args that never require an annotation (implicit type from the call protocol).
IMPLICIT_ARG_NAMES = frozenset({"self", "cls"})


#============================================
def _annotatable_args(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
	"""
	Return the args that require a type annotation for the given function def.

	Combines posonlyargs, args, and kwonlyargs and excludes self and cls, which
	are exempt because their type is implicit from the call protocol. Does not
	include *args (vararg) or **kwargs (kwarg), which are never required.

	Args:
		func_node: A parsed FunctionDef or AsyncFunctionDef AST node.

	Returns:
		list[ast.arg]: Argument nodes that must carry an annotation.
	"""
	# Combine all annotatable groups into one flat list.
	all_args = func_node.args.posonlyargs + func_node.args.args + func_node.args.kwonlyargs
	# Filter out self and cls; they are exempt from annotation.
	return [arg for arg in all_args if arg.arg not in IMPLICIT_ARG_NAMES]


#============================================
def _is_typing_import(node: ast.Import | ast.ImportFrom) -> bool:
	"""
	Return True if the import node references the typing module.

	Detects `import typing`, `import typing as X`, `import typing.something`,
	`from typing import ...`, and `from typing.x import y`. All of these are
	banned in this repo; callers should use builtin generics and PEP 604 unions.

	Args:
		node: An ast.Import or ast.ImportFrom node from a parsed module.

	Returns:
		bool: True when the node imports from the typing module.
	"""
	if isinstance(node, ast.Import):
		# Catch `import typing`, `import typing as X`, and `import typing.something`.
		return any(
			alias.name == "typing" or alias.name.startswith("typing.")
			for alias in node.names
		)
	# Catch `from typing import ...` and `from typing.x import y`.
	return node.module == "typing" or (
		node.module is not None and node.module.startswith("typing.")
	)


#============================================
def check_no_typing_import(tree: ast.Module, rel: str) -> list[str]:
	"""
	Return violations when the file imports from the typing module.

	A plain builtin type like `list`, `dict`, or `tuple` satisfies every
	annotation gate in this repo. Use builtin generics and PEP 604 unions
	(`X | None`) instead of the typing module.

	Checks for `import typing`, `import typing as X`, `import typing.something`,
	and `from typing import ...`. All four forms are banned.

	Args:
		tree: Parsed AST module.
		rel: Repo-relative POSIX path for error messages.

	Returns:
		list[str]: Violation messages (empty when clean).
	"""
	violations = []
	for node in file_utils.iter_imports(tree):
		if _is_typing_import(node):
			violations.append(
				f"{rel}:{node.lineno}: write `import typing` as builtin generics "
				"(list, dict, tuple) and PEP 604 unions (X | None) instead."
			)
	return violations


#============================================
def check_function_annotations(tree: ast.Module, rel: str) -> list[str]:
	"""
	Return violations for any function def missing return or argument annotations.

	A plain builtin type satisfies the gate -- `-> list` or `-> None` is enough
	for a return annotation, and `x: str` or `x: object` is enough for a param.
	Parametrized generics like `list[str]` are also accepted; the gate requires
	only that SOME annotation is present.

	Walks the tree and checks every ast.FunctionDef and ast.AsyncFunctionDef.
	Requires:
	- A return annotation (node.returns is not None).
	- An annotation on each positional-only, regular, and keyword-only arg,
	  except `self` and `cls` which are implicitly typed.

	Does NOT require annotations on *args (vararg) or **kwargs (kwarg).
	Lambdas are skipped (they cannot carry annotations).

	Args:
		tree: Parsed AST module.
		rel: Repo-relative POSIX path for error messages.

	Returns:
		list[str]: Violation messages, one per missing annotation.
	"""
	violations = []
	for node in ast.walk(tree):
		if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
			continue
		func_name = node.name
		lineno = node.lineno
		# Check return annotation -- a plain type like `-> list` or `-> None` is enough.
		if node.returns is None:
			violations.append(
				f"{rel}:{lineno}: {func_name}() needs a return annotation -- "
				"a plain type like `-> list` or `-> None` is enough."
			)
		# Check each annotatable argument; a bare type like `x: str` or `x: object` is enough.
		for arg in _annotatable_args(node):
			if arg.annotation is None:
				violations.append(
					f"{rel}:{lineno}: {func_name}() arg `{arg.arg}` needs an annotation -- "
					"a bare type like `x: str`, or `x: object` when the type is open, is enough."
				)
	return violations


#============================================
def check_file(rel: str, tree: ast.Module) -> list[str]:
	"""
	Run every typing check on one parsed module and combine the violations.

	Thin module-specific combiner over check_no_typing_import and
	check_function_annotations. Receives a real ast.Module: the shared
	file_utils.collect_python_violations owns parsing and SyntaxError capture, so
	this is only reached for files that parsed cleanly.

	Args:
		rel: Repo-relative POSIX path for error messages.
		tree: Parsed ast.Module for the file.

	Returns:
		list[str]: Combined violation lines (empty when the file is clean).
	"""
	# Accumulate violations from each typing rule check.
	violations = check_no_typing_import(tree, rel)
	violations += check_function_annotations(tree, rel)
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
	VIOLATIONS_BY_FILE.update(file_utils.collect_python_violations(FILES, check_file))
	lines = file_utils.format_violation_report(HEADER, VIOLATIONS_BY_FILE)
	# Write only when there are violations; cleanup already removed stale reports.
	if lines:
		file_utils.write_report_lines(REPORT_NAME, lines)


#============================================
@pytest.mark.parametrize("path", FILES, ids=file_utils.rel_id)
def test_function_typing(path: str) -> None:
	"""Enforce no typing-module imports and full function annotations repo-wide."""
	rel = file_utils.rel_to_root(path)
	# Python evaluates an assert's message expression ONLY when the assert fails,
	# so format_violation_assert_message runs on the failing path only -- not per pass.
	assert rel not in VIOLATIONS_BY_FILE, file_utils.format_violation_assert_message(
		rel, VIOLATIONS_BY_FILE.get(rel, []), REPORT_NAME
	)
