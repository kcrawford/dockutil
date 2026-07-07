# Tests

This folder holds three test tiers, each with its own execution model. Pytest runs the fast lane under 1 second; the other two tiers run directly and may take longer.

## Layout

```
tests/
  test_*.py              fast pytest unit/integration (collected by pytest)
  test_*.mjs             pure Node tests, no browser (rare)
  conftest.py            pytest config; declares collect_ignore
  conftest.py includes:  collect_ignore = ["e2e", "playwright"]
  e2e/                   non-browser whole-system E2E (shell/Python)
    e2e_*.sh             shell orchestration
    e2e_*.py             Python orchestration
    run_all.sh           OPTIONAL: run all E2E tests at once
```

## How to run

- Fast pytest lane: `pytest tests/`
- Single non-browser E2E: `bash tests/e2e/e2e_<name>.sh` or `source source_me.sh && python3 tests/e2e/e2e_<name>.py` (see [../docs/E2E_TESTS.md](../docs/E2E_TESTS.md))
- Bulk non-browser E2E: `bash tests/e2e/run_all.sh` (if present)

## Why two folders for E2E

Playwright is a tool; E2E is a scope. Not every Playwright test is end-to-end (a layout check or single-interaction smoke test is browser-driven but not E2E). One folder per execution model:

- `tests/e2e/` -- non-browser whole-system orchestration (CLIs, build pipelines, multi-suite runners)


## How pytest stays fast

`tests/conftest.py` declares `collect_ignore = ["e2e", "playwright"]`, so pytest never collects test functions from those subtrees, regardless of filename inside them. The filename conventions (`e2e_*` prefix in `tests/e2e/`, `test_*.mjs` for Playwright) are a readability layer on top of this active guard, enforced by `tests/test_test_naming_conventions.py`.

Important: `collect_ignore` only affects pytest test collection. The repo's lint tests (ASCII compliance, whitespace, pyflakes, indentation, shebangs, etc.) enumerate files via `git ls-files` and still scan files inside `tests/playwright/` and `tests/e2e/`. A non-ASCII character in `tests/playwright/foo.mjs` will still fail the ASCII check - only execution as a pytest test is suppressed.

## See also

- [../docs/PYTEST_STYLE.md](../docs/PYTEST_STYLE.md) -- pytest test-writing rules and fast-lane discipline
- [../docs/E2E_TESTS.md](../docs/E2E_TESTS.md) -- non-browser whole-system E2E conventions
