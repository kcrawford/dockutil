# Propagation rules

Where to drop a file so the propagator ships it to the right repos.

## Folder convention

| Want to ... | Put the file under | Ships to |
|---|---|---|
| Doc that every repo gets | docs/ | every repo, overwrite |
| Universal pytest helper | tests/ (test_*.py or helper) | every repo, overwrite |
| Helper script in devel/ | devel/ | every repo, overwrite |
| Starter file that must not clobber existing | templates/<type>/noexist/<consumer-path> | only when missing |
| TypeScript-only file | templates/typescript/<consumer-path> | typescript repos only |
| Rust-only file | templates/rust/<consumer-path> | rust repos only |
| Python-package-only file | add path to PYTHON_LANG_FILES in propagate_style_guides.py | python repos only |
| Root-level file like AGENTS.md | template root + add to ROOT_PROPAGATE_ALLOWLIST | every repo, overwrite |
| Universal gitignore blocks | templates/gitignore.universal | every repo, merged into .gitignore under `# === UNIVERSAL ===` |
| Template-only tooling | tools/<file> | never (template-meta) |

## Precedence

File routing honors a strict precedence order; earlier rules win on conflict:

1. **META_FILES / META_DIRS** - Files in these block-lists never ship to any consumer, even if matched by other rules.
2. **PYTHON_LANG_FILES** - These ship only when `repo_type == 'python'`. Exception: 'other'-typed repos get `docs/PYTHON_STYLE.md` only.
3. **UNIVERSAL_NOEXIST** - Files in this list override the universal overwrite default; they move to noexist_files instead.
4. **Typed noexist** - Templates/<type>/noexist/<path> overrides typed overlay overwrite; same path in noexist always wins.
5. **Typed overlay shadows universal** - When both universal and typed overlay define the same consumer destination, the typed version ships. The propagator prints `[OVERLAY-OVERRIDE] <consumer-path>: typed overlay shadows universal source` to stdout for visibility.

## Exceptions in the manifest

Most additions are drop-and-go. The propagator keeps four short manifests at the top of `propagate_style_guides.py`:

- `ROOT_PROPAGATE_ALLOWLIST` -- root files that DO ship. Default: CLAUDE.md, AGENTS.md, source_me.sh. Add here when introducing a new root-level file all repos need.
- `UNIVERSAL_NOEXIST` -- universal files that ship only when missing at consumer. Default: AGENTS.md, source_me.sh, docs/AUTHORS.md.
- `PYTHON_LANG_FILES` -- files at template root that only ship to python-typed consumers (PYTHON_STYLE.md, submit_to_pypi.py, pip_requirements*.txt). 'other'-typed consumers receive PYTHON_STYLE.md only.
- `META_FILES` / `META_DIRS` / `META_TEST_PREFIXES` -- block-lists for files that NEVER ship (propagator itself, reset_repo, LICENSES/, etc.).

## Examples

- Adding `docs/SHELL_STYLE.md` -- drop in `docs/`, no manifest edit. Every repo gets it.
- Adding `tests/test_security_audit.py` -- drop in `tests/`, every repo gets it.
- Adding `templates/typescript/.eslintignore` -- drop under `templates/typescript/`. TypeScript repos get it at consumer root.
- Adding a new starter `Makefile` that must not clobber existing ones -- drop at `templates/<type>/noexist/Makefile` (per type) or add path to `UNIVERSAL_NOEXIST` + place at template root.
- Adding `docs/FOO_PACKAGE_GUIDE.md` that only python-package repos need -- drop at `docs/FOO_PACKAGE_GUIDE.md` AND add `'docs/FOO_PACKAGE_GUIDE.md'` to `PYTHON_LANG_FILES`.

## What never propagates

Listed in `META_FILES` / `META_DIRS` / `META_TEST_PREFIXES`. Includes the propagator itself, reset_repo.py, tools/detect_repo_type.py, README.md, VERSION, LICENSES/, templates/ (as a dir; only contents under `templates/<type>/` ship), `docs/active_plans/`, `docs/archive/`, `__pycache__/`, `.git/`. Tests starting with `test_propagate_`, `test_reset_repo_`, or `test_detect_repo_type` never ship (template-meta).
