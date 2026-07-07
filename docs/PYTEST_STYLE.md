# PYTEST_STYLE.md

Language Model guide to Neil pytest usage.

## Is this a good pytest?

Run this checklist before writing a new pytest or approving one in review. Any unchecked item is a reason to reconsider, delete, or rewrite the test. A missing pytest is cheaper than a fragile one.

- [ ] Tests logic that could plausibly be wrong (parser, math, round-trip, behavioral property).
- [ ] Not a trivial wrapper around a stdlib call.
- [ ] Will still pass next week without code changes.
- [ ] Independent of today's date, current time, or "now".
- [ ] Asserts meaningful output, not collection length (`len(items) == 7`).
- [ ] Asserts required behavior, not required-key lists (`set(d) == {"a", "b"}`).
- [ ] Asserts callable behavior, not function or attribute name lists.
- [ ] Asserts user-visible behavior, not hardcoded defaults or tunable constants (timeouts, thresholds, magic numbers).
- [ ] Asserts object behavior, not dataclass field assignment (`obj.x == 5` right after `obj = C(x=5)`).
- [ ] Works offline (no network, no real subprocess CLI round-trips).
- [ ] Uses deterministic timing and fixed seeds (no sleeps, no unseeded randomness).
- [ ] Writes only inside `tmp_path`.
- [ ] Finishes in well under one second.
- [ ] Slower tests live in `tests/e2e/` or `tests/playwright/` (see [E2E_TESTS.md](E2E_TESTS.md)).
- [ ] One or two assertions per function (not five on a simple function).
- [ ] Test body free of complex logic; complex logic moved to a helper and tested there.
- [ ] Targets code that will remain in the repo (not `_temp.*` or ad-hoc debugging scripts).
- [ ] Writes setup and test inputs inline rather than in an external on-disk data file, except for the fixture cases listed in [Fixture policy](#fixture-policy).

See [Good tests](#good-tests) for examples of stable assertion shapes and [Brittle tests](#brittle-tests) for the rationale behind each red flag above.

## Test structure

* Prefer pytest for automated tests when a repo has more than a few simple asserts.
* `tests/` (including `tests/playwright/` and `tests/e2e/`) is the only place `assert` statements should appear in this repo. Plain scripts and library modules must not contain `assert`. See [PYTHON_STYLE.md](PYTHON_STYLE.md#assert) for the rationale (module-level asserts slow script startup).
* Pytest is the fast lane: keep tests deterministic and quick. Slow end-to-end tests live in `tests/playwright/` (browser-driven) and `tests/e2e/` (shell/Python) and run outside pytest (excluded via `collect_ignore = ["e2e", "playwright"]` in `tests/conftest.py`); see [E2E_TESTS.md](E2E_TESTS.md).
* Store tests in `tests/` with files named `test_*.py`.
* Use `tests/conftest.py` for pytest configuration, collection hooks, and shared pytest setup.
* Test functions should be named `test_*` and should use plain `assert`.
* Keep tests small and deterministic.
* Avoid network calls, random behavior, and time based logic unless mocked.
* Keep setup inline and close to the test.
* Use `tmp_path` for temp files.
* Avoid complex logic inside tests.
* If test logic needs comments, move the logic into helper functions and test those helpers.
* Before writing any test, ask: "will this test still pass next week without code changes?"
* If a test will not stay stable without code changes, do not write it.
* One or two assertions per function is enough.
* Five assertions for a simple function is overkill.
* Do not test trivial behavior or thin wrappers around standard library calls.
* Do not create permanent pytest files for temporary or scratch code.
* Do not write tests for `_temp.*` files, ad-hoc debugging scripts, or any code intended to be deleted shortly after use.
* Tests in `tests/` are reserved for code that will remain in the repo.

## Fixture policy

Write test inputs directly in the test by default. Put the setup near the assertion so the test is
easy to read, move, and maintain.

Inline means the test input is written directly in the test file, close to the assertion. Use a
literal string, literal object, short list, or a short helper function used only by tests in that
same file.

This policy covers both test data files under `tests/fixtures/` and custom `@pytest.fixture`
functions.

Use fixtures for these durable cases:

1. Use the builtin `tmp_path` fixture when a test needs a temporary file or directory.
2. Use the vendored `collect_report` autouse harness for hygiene report checks. See [Hygiene report files](#hygiene-report-files).
3. Use an existing repo file directly when that real file's required shape or loader behavior is
   what the test checks -- a shipped config, a template, or committed production data that already
   exists for a non-test reason.

For all other tests, write the input directly in the test.

Use `tmp_path` for file-shaped test input -- a CSV, YAML, JSON, image, or similar -- that exists
only for the test: write the inline data into a `tmp_path` file at runtime, so the data lives in the
test and the file exists only during the run. Add a permanent committed file only when that file
already has a non-test purpose in the repo, or when a human explicitly approves it as durable shared
test infrastructure.

During early implementation, keep scratch setup in the test. Once the behavior is pinned, keep that
setup in the test instead of moving it into a shared fixture.

Treat a committed `tests/fixtures/` directory as shared test infrastructure. Get explicit human
sign-off before adding one. These directories often accumulate stale files after their first use.

## Three-tier test layout

Test files are organized by execution model and scope:

* **`tests/test_*.py`** - Fast, deterministic unit and integration tests. Rules: no network, no file I/O beyond `tmp_path`, no sleeps, no subprocess CLI round-trips. Examples: lint checks (pyflakes, ASCII compliance, indentation), parser correctness, round-trip invariants.
* **`tests/e2e/`** - Non-browser end-to-end (shell or Python orchestration); excluded from pytest (outside scope of `pytest tests/`); run via explicit shell or Python runner. Examples: full bootstrap flow, multi-repo propagation with real git operations, CLI round-trip chains.
* **`tests/playwright/`** - Browser-driven E2E; excluded from pytest; run via Playwright runner or explicit shell. Examples: full-stack web app flows, UI interaction and assertion, rendered-output verification. The website family (`website` and its inheriting `typescript`) includes `PLAYWRIGHT_TEST_STYLE.md`, shipped via the `templates/website/` overlay, in their propagated `docs/` folder for browser test authoring rules.

## Runtime budget

* Every pytest under `tests/` should finish in well under one second. `pytest tests/` is the
  fast lane; slow tests poison it and discourage running the suite during development.
* If a check needs sleeps, real subprocess calls, real network, large file trees beyond
  `tmp_path`, model loads, or a multi-step CLI run, it is not a pytest. Move it to
  `tests/playwright/` (browser-driven) or `tests/e2e/` (shell/Python) per [E2E_TESTS.md](E2E_TESTS.md).
* Prefer deleting a slow or fragile pytest over rewriting it. Less is more.

## Good tests

Tests should verify logic that could plausibly be wrong, using assertions that remain stable
when unrelated code changes. Good tests survive refactors, renamed fields, added config keys,
and tuned constants.

* **Pure function correctness**: fixed inputs produce expected outputs, such as math, parsing,
  or encoding.
* **Round-trip invariants**: encode then decode, serialize then deserialize, or convert then
  convert back.
* **Behavioral properties**: `score A > score B`, output is sorted, or result is within a range.
* **Error detection**: invalid input produces errors or warnings.
* **Boundary enforcement**: architectural rules like core code must not import PySide6.

```python
# Good: tests logic with fixed inputs
assert parse_title_year("The.Matrix.1999.BluRay.mkv") == ("The Matrix", "1999")

# Good: round-trip invariant
scene_x, scene_y = transform.pixel_to_scene(frame, px, py)
px_rt, py_rt = transform.scene_to_pixel(frame, scene_x, scene_y)
assert numpy.isclose(px_rt, px, atol=0.5)

# Good: behavioral property, not a hardcoded value
assert 0.0 <= score <= 1.0
assert score_exact_match > score_different_title
```

## Brittle tests

Avoid tests that assert on dates, collection sizes, lists of required keys, hardcoded defaults,
tunable constants, or dataclass storage. These break when unrelated code changes and provide no
real value. When in doubt, delete. A missing pytest is cheaper than a fragile one. This is the
design-first philosophy applied to tests: see [REPO_STYLE.md](REPO_STYLE.md#core-philosophies).

### Inline inputs, not external data files

Prefer inline, self-contained test inputs. A test that reads an external on-disk data file is
fragile by design: the file is a dependency that can move, be renamed, or be deleted, and when it
vanishes the test fails for reasons unrelated to the code under test. If the missing file is loaded
at module import time, the failure takes the whole test module down with it, not just the one case.
Embed small real inputs directly in the test (a literal string, a short list, a few-line sample) so
the case cannot drift out of existence.

The hazard is a checked-in sample file the test reads at runtime: inline the content instead, or
if the data is genuinely large, treat the round trip as an end-to-end check under `tests/e2e/` per
[E2E_TESTS.md](E2E_TESTS.md).

## Basic commands

Use this as the default test command:

```bash
pytest tests/
```

For targeted runs:

```bash
pytest tests/test_example.py
pytest tests/ -k name
pytest tests/ -x
```

`tests/conftest.py` handles the pytest environment setup. Do not duplicate that setup in the
pytest command.

## Hygiene file discovery

Repo-hygiene tests (ascii, whitespace, pyflakes, shebangs, and similar enumerating tests) must
get their file list from one shared helper, `file_utils.discover_files`. It is the canonical
discovery API: it owns git scope selection, absolute-path join, dedupe, skip-dir filtering,
extension filtering, the `isfile` check, and the sort. Use `file_utils.discover_files` as the
single source of file discovery; the shared `SKIP_DIRS` and `path_has_skip_dir` live only in
`file_utils.py`.

Signature:

```python
discover_files(extensions=None, extra_filter=None, *, test_key=None, repo_root=None) -> list[str]
```

`test_key` and `repo_root` are keyword-only (note the bare `*`). The module-level discovered list
in a hygiene test is named `FILES` (not `_FILES`).

Three contracts:

- Returns ABSOLUTE paths, sorted ascending.
- `extra_filter` receives a REPO-RELATIVE POSIX path (for example `tests/foo.py`) and returns
  `True` to keep the file. `None` keeps all files.
- `extensions=None` means all files; otherwise extension match is case-insensitive (pass
  lowercase suffixes like `(".py",)`).

Normal hygiene tests call `discover_files(extensions=..., test_key="<stem>")`; `discover_files`
resolves the repo root itself via `get_repo_root()` (a negligible extra call). Pass `repo_root=`
only in `file_utils` regression tests that point discovery at a temporary directory.

### Three exclusion layers

Discovery filters files through three layers, in order:

- Layer 1, `SKIP_DIRS` (vendored, `file_utils.py`): universal directory exclusions.
  Identical across all repos.
- Layer 2, `REPO_HYGIENE_FILTERS` (repo-local, `tests/conftest.py`): per-test repo-local
  file/glob exclusions. This is the only home for repo-specific exclusions, because `conftest.py`
  survives propagation while vendored files (`file_utils.py` and every `tests/test_*.py`) are
  overwritten. It is a dict keyed by `"all"` or a vendored test key, with values that are lists of
  repo-relative POSIX glob patterns matched via `fnmatch.fnmatchcase`. A match excludes the file.
  A test key is the test filename stem with the leading `test_` removed (for example
  `test_pyflakes_code_lint.py` -> `"pyflakes_code_lint"`). Recursive subtree exclusion needs an
  explicit trailing `/**` (for example `"temp_scripts/**"`).
- Layer 3, `extra_filter` (vendored call site): a universal per-test SELECTION mechanism only
  (for example keep only `__init__.py`). Keep all repo-specific exclusions in
  `tests/conftest.py REPO_HYGIENE_FILTERS`; vendored files hold only universal logic.

A normal hygiene test calls `discover_files` with its `test_key` so Layer 2 can target it:

```python
FILES = file_utils.discover_files(extensions=(".py",), test_key="pyflakes_code_lint")
```

The repo-local `tests/conftest.py` declares any repo-specific exclusions:

```python
# tests/conftest.py
REPO_HYGIENE_FILTERS = {
	"all": ["temp_scripts/**", "TEMPLATE.py"],
	"ascii_compliance": ["human_readable-*.html"],
}
```

Usage example (normal hygiene test):

```python
FILES = file_utils.discover_files(extensions=(".py",), test_key="ascii_compliance")
```

Pass `repo_root=` in `file_utils` regression tests that point discovery at a temporary
directory:

```python
# Regression test: point discovery at a controlled temporary root.
result = file_utils.discover_files(extensions=(".py",), repo_root=tmp_root)
```

### Additional helpers in file_utils.py

Shared helpers that complement `discover_files`:

- `iter_imports(tree: ast.Module)` -- yields every `ast.Import` and `ast.ImportFrom` node from
  a parsed module tree. Use in import-checking tests instead of local AST-walk loops.
- `rel_to_root(path, repo_root=None)` -- returns a repo-relative POSIX string suitable for
  parametrize ids and assertion messages (for example `tests/foo.py`).
- `rel_id(abs_path: str) -> str` -- thin wrapper around `rel_to_root` for use as
  `ids=file_utils.rel_id` in `@pytest.mark.parametrize`.
- `run_fixer_script(script_name, target)` -- shared subprocess wrapper: runs
  `tests/<script_name> -i target` and returns `(returncode, stderr)` for every subprocess
  completion; it never raises on a fixer exit code. Callers convert bad outcomes into per-file
  violation data. Raises `RuntimeError` only for environment preconditions (missing script file,
  missing python3 interpreter). Fixer exit codes: `fix_ascii_compliance.py` 0=clean,
  1=issues remain, 2=fixed; `fix_whitespace.py` 0=clean-or-fixed, 1=missing input. Used by the
  ASCII and whitespace auto-fix tests.
- `collect_file_violations(files, check)` -- iterate `files`, call `check(rel)` per file,
  return `dict[str, list[str]]` keyed by repo-relative POSIX path. Use when the checker handles
  its own parsing (for example pyflakes).
- `collect_python_violations(files, check)` -- like `collect_file_violations` but parses each
  `.py` file into an AST once; calls `check(rel, tree)`; records one `SyntaxError` entry when
  parsing fails and skips that file's rule checks.
- `format_violation_report(header, violations_by_file)` -- return a `list[str]` for writing to
  a report file; returns `[]` when `violations_by_file` is empty.
- `format_violation_assert_message(rel, lines, report_name)` -- return a
  human-readable assertion failure message for the per-file violation lines (`lines: list[str]`);
  evaluated only on failure.
- `write_report_lines(report_name: str, lines: list[str]) -> str` -- truncate-write the full
  report when `lines` is non-empty (one `\n` per line, one trailing `\n`). Called only when
  violations exist; `clear_stale_reports` owns removal of stale reports on clean runs.
- `clear_stale_reports() -> None` -- delete all `report_*.txt` files at the repo root; guarded
  once per process so multiple hygiene modules in the same pytest session each invoke it but
  only the first does the filesystem work.
- `report_name(test_file: str) -> str` -- derive the canonical `report_<stem>.txt` filename.
  Pass `__file__`; every hygiene test sets `REPORT_NAME = file_utils.report_name(__file__)` so
  the name is always derived from the filename, never hardcoded.

### Hygiene report files

Every hygiene test writes a `report_<topic>.txt` at the repo root when violations exist. The
report is NOT written on a clean run; `clear_stale_reports` removes leftover reports once per
process at suite start so stale files from prior runs do not persist.

**Canonical module shape:**

```python
# Standard Library
import pytest

# local repo modules
import file_utils

REPORT_NAME = file_utils.report_name(__file__)
HEADER = "VIOLATIONS: <topic>"
FILES = file_utils.discover_files(extensions=(".py",), test_key="<stem>")
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}

@pytest.fixture(scope="module", autouse=True)
def collect_report() -> None:
	file_utils.clear_stale_reports()
	VIOLATIONS_BY_FILE.clear()
	VIOLATIONS_BY_FILE.update(file_utils.collect_python_violations(FILES, check_file))
	lines = file_utils.format_violation_report(HEADER, VIOLATIONS_BY_FILE)
	if lines:
		file_utils.write_report_lines(REPORT_NAME, lines)

@pytest.mark.parametrize("rel", [file_utils.rel_to_root(f) for f in FILES], ids=file_utils.rel_id)
def test_topic(rel: str) -> None:
	msg = file_utils.format_violation_assert_message(rel, VIOLATIONS_BY_FILE.get(rel, []), REPORT_NAME)
	assert rel not in VIOLATIONS_BY_FILE, msg
```

The `collect_report` autouse fixture above is the named shared-infrastructure exception under
[Fixture policy](#fixture-policy): it stays a fixture because the harness itself, not
test-specific data, is what needs to run once per module.

Notes on the shape:

- `collect_python_violations` handles AST parse-once and records `SyntaxError` entries for
  unparseable files; use `collect_file_violations` when the checker does its own parsing.
- `clear_stale_reports` is the first line of the fixture; it runs once per process regardless
  of how many hygiene modules invoke it.
- `write_report_lines` is called only when `lines` is non-empty; never call it with an empty
  list to "purge" -- that is `clear_stale_reports`'s job.
- No `raise AssertionError` and no `pytest.fail(` in hygiene modules; use plain `assert`.
- Precondition guards (missing tool, bad environment) use `RuntimeError`.

**Report lifecycle and `-k` independence:**

Any run of a hygiene module writes that module's complete report (all violations, not just
selected cases). When `-k <file>` is passed, the fixture still precomputes the full
`VIOLATIONS_BY_FILE` dict; only the per-file `assert` cases are filtered by `-k`. This
means `-k tests/foo.py` selects only that file's test case but the fixture still scans every
file, so the report is complete and accurate for the whole module. Do not short-circuit the
fixture to scan only selected files -- that produces partial, misleading reports.

### Hygiene guard tests

Two vendored hygiene tests keep the discovery scaffold clean:

- `tests/test_function_typing.py` -- AST-based guard that enforces the typing rule repo-wide:
  the `typing` module is not used, and every `def` carries param and return type annotations.
  Use builtin generics (`list`, `dict`, `tuple`, `set`) and PEP 604 unions (`X | None`).
  Use `collections.abc` (for example `collections.abc.Callable`) for callable and iterable params.
- `tests/test_pytest_hygiene.py` -- AST guard ensuring hygiene tests keep all file-discovery
  logic in `file_utils` (the shared `SKIP_DIRS`, `path_has_skip_dir`, and `gather_*` discovery
  live there). See the "discovery lives in file_utils" guidance above.

## Failure triage

* If you are unsure whether a failing pytest result is pre-existing or introduced by your
  current work, assume it is new first.
* Reason: we try not to commit code with known failing tests, so a fresh failure is usually
  related to current uncommitted changes.
* If uncertainty remains, inspect `git diff` and check whether the suspicious lines are part
  of current uncommitted edits.
* Never use `git stash` as a diagnostic step for this.
