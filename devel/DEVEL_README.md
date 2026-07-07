# devel scripts

`devel/` holds maintainer-only tools for developing, validating, and releasing
this repository. These files are not product code and are not part of the fast
pytest lane.

Use this folder for scripts that help maintainers do repo-level work:

- Version and release preparation.
- Changelog querying, commit-message drafting, and changelog rotation.
- Documentation repair and repo hygiene cleanup.
- Build-output cleanup that is useful across repo types.
- Template-only developer helpers that should ship into consumer repos under
  their own `devel/` folders.

Do not put reusable library code, runtime application code, or permanent tests
here. Shared test helpers belong in `tests/`; shipped runtime files belong in
the appropriate repo root, package, or `templates/<type>/` path.

## Current root scripts

| File | Kind of work |
| --- | --- |
| [bump_version.py](bump_version.py) | Set or bump repo versions across version files. |
| [changelog_lib.py](changelog_lib.py) | Shared parser and helpers for changelog tools. |
| [commit_changelog.py](commit_changelog.py) | Draft a commit message from new changelog entries. |
| [query_changelog.py](query_changelog.py) | Search active and archived changelog entries. |
| [rotate_changelog.py](rotate_changelog.py) | Move old changelog day blocks into archive files. |
| [flatten_broken_md_links.py](flatten_broken_md_links.py) | Repair or flatten broken Markdown links. |
| [dist_clean.sh](dist_clean.sh) | Remove build artifacts, caches, and dependency installs. |

## Template devel scripts

Some developer tools ship into consumer repos via propagation and appear in `devel/` when present.

`templates/shared/devel/` holds tools that propagate to non-PyPI python, rust, swift, and other
consumer repo types (repos with `pyproject.toml` are excluded by the `lacks_file` condition).
When present in a consumer repo, `devel/make_release.py` prepares a GitHub source
release: CalVer freshness check, free-tag check, committed-LICENSE verification, zip and tgz
archive build with byte-level LICENSE spot-check, LLM-prompt generation for the release
description, optional `docs/RELEASE_HISTORY.md` and `docs/NEWS.md` updates, and printed
`git tag` + `gh release create` commands. Use `--dry-run` to preview or `--write` to update
doc files. See [docs/REPO_STYLE.md](../docs/REPO_STYLE.md) versioning section for the full flow.

Some developer tools are type-specific and live under `templates/<type>/devel/`
so they propagate only to matching consumer repos. Examples include Python
release publishing helpers and TypeScript setup/rendering helpers.

## Running scripts

For Python scripts, use the repo bootstrap environment:

```bash
source source_me.sh && python3 devel/<script>.py
```

Run individual scripts with `--help` for current options. Keep command details
in script help output instead of duplicating them here.
