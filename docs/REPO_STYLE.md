# REPO_STYLE.md

Repo-wide conventions for this project and related repos.

## Core philosophies

Core principles guide work in this repo. Cite them by name when making judgment calls. This file is the canonical home for all core principles; sibling docs and `AGENTS.md` should cross-reference, not restate.

- **Long-term over short-term.** Accept a small cost now to avoid larger costs later. Prefer the durable fix over the quick patch, even when the durable fix takes more effort today.
- **Fix the design, not the symptom.** When something behaves wrong, fix the design that allowed the problem. Do not add fallbacks, special cases, or broad try/except blocks just to hide the symptom.
- **Focus on important issues.** Make sure we are worrying about the correct things, and not bikeshedding i.e. spending excessive time discussing trivial issues while neglecting more important ones.
- **Prompt positively.** Tell the model what to do, not what to avoid. Small LMs can confuse negative prompting with positive instructions, which can lead to poor code and seriously flawed results.     Prefer direct instructions like "use explicit key access" over negative ones, like "do not use dict.get()"
- **Atomic task decomposition.** Break hard problems into the smallest independently completable tasks. Each task should have one owner, one clear outcome, and one verification step.
- **Be efficient with time.** Subagents and tokens are cheap, but wall time is not. Optimize for implementation time by spreading atomic tasks in parallel.
- **Fresh subagent per task.** Give each independent task to a new subagent with a self-contained prompt. Reusing a subagent across tasks carries stale context, encourages drift, and weakens independent judgment.
- **Finish the obvious.** Continue while the next safe step is defined by the plan, implied by the task, or required to verify the work. Obvious follow-on work is part of the task, not a bonus. Stop only at a real blocker, risky action, or change to the user's requested outcome.

## Repository structure
- Prefer small, single-purpose scripts at the repo root.
- Create topic folders only when a collection needs grouping.
- Avoid deep nesting; keep paths short.
- Keep `README.md` and `AGENTS.md` at the repo root.
- Determine REPO_ROOT with `git rev-parse --show-toplevel`, not by deriving paths from the current working directory.

## Project type marker

Every repo carries `REPO_TYPE` at the repo root: one lowercase token plus newline. Tokens: `python`, `typescript`, `rust`, `swift`, `other`, `scripted`, `website`, `compiled`, `all`. Every token is a directly usable marker, including the three base types. `all` means the repo consumes every template family and should receive every typed overlay in addition to universal files. Missing marker triggers detection via `tools/detect_repo_type.py`; if detection is unavailable or ambiguous, falls back to `LANG_UNKNOWN`. An unrecognized token in an existing marker (a typo or a not-yet-added type) logs a warning and falls back to `other`, rather than aborting propagation. `LANG_UNKNOWN` repos receive only universal walker-routed files (`docs/`, `tests/`, `devel/`); no `ROUTING_OVERRIDES` `exclude_repos` rule applies. The propagator (`propagate_style_guides.py` entry script + `repolib/` package: `repolib.repo.read_repo_type` reads the marker, `repolib.files.compute_propagation_plan` dispatches overlays) routes files by repo type; `reset_repo.py` writes the marker during bootstrap by calling `repolib` directly (no longer shells out to `propagate_style_guides.py`). `REPO_TYPE` is maintained after bootstrap; it controls future propagation behavior, not just initial scaffolding. File location is the primary routing determinant: every file under `templates/<type>/` ships to that type, files under `docs/`, `tests/`, and `devel/` ship universally. `docs/PYTHON_STYLE.md` ships to all repo types. The only routing exception encoded in `ROUTING_OVERRIDES` is `exclude_repos` (blocks a file from shipping back to its source repo). Conditional overlays (`_folder` convention, see `meta/docs/PROPAGATION_RULES.md`) are selected by a `conditional_overlays` manifest rule. A shared overlay routes one or more files under `templates/shared/<path>` to a chosen SET of repo types via a `shared_overlays` manifest rule (named `paths`, `repo_types`, and an optional `lacks_file` presence condition that ships only when a marker file is absent at the consumer); every `templates/shared/` file must be named by a rule or the shared walk raises. All propagation manifests live in `meta/propagation/manifests.yaml`. `swift` currently ships universal files only (no `templates/swift/` overlay); future swift-specific files are added by folder location (`templates/swift/<path>`) with no code change required.

### Repo type inheritance

Concrete repo types inherit overlays from a base type, forming a single-token
inheritance DAG (`repo_type_inherits` in `meta/propagation/manifests.yaml`):
`python -> scripted`, `rust -> compiled`, `swift -> compiled`, `typescript ->
website`. `scripted`, `website`, `compiled`, and `other` are roots with no
parent. `repolib.model.effective_type_chain(repo_type)` returns
`[repo_type, *ancestors]` nearest-first; every overlay- and shared-routing path
consumes this one helper, so a repo receives its own overlay plus every
ancestor's overlay, unioned. A child and its ancestors never ship the same
file, so overlay walk order does not matter for correctness.

Routing rules target a base type so every descendant inherits automatically.
The `source_release` shared overlay targets `[scripted, compiled, other]`:
any future scripted or compiled language picks up `devel/make_release.py`
with no manifest edit, while the website family (`website`, `typescript`)
stays out, because a docs or game site publishes builds rather than GitHub
source releases. `PLAYWRIGHT_TEST_STYLE.md` ships from
`templates/website/docs/` as a normal type overlay (the old
`html_playwright_style` shared-overlay rule and its `[typescript, other]`
hand list are retired); `typescript` receives it by inheriting `website`, so
any repo that serves HTML gets browser-test-authoring style by declaring
`REPO_TYPE=website` (or a type that inherits it) rather than by a per-file
manifest rule.

## AGENTS.md files

Keep `AGENTS.md` files concise and operational. They should usually be around
100-150 lines and focus on specific tasks, workflows, and constraints.
Do not use `AGENTS.md` for long philosophical discussions or duplicated style
guidance. Put canonical explanations in the appropriate `docs/*.md` file, then
link to that file from `AGENTS.md`.
Concise `AGENTS.md` files help coding agents perform better because the
instructions are easier to scan, prioritize, and follow.

### Human guidance

- `docs/HUMAN_GUIDANCE.md`: durable human preferences, project-specific guidance, review expectations, and stable decisions that agents should preserve across planning and implementation work.
- Use this file for long-term guidance that prevents drift across manager and subagent runs.
- Keep entries focused on stable preferences and recurring project decisions, not transient task notes.
- Link to `docs/HUMAN_GUIDANCE.md` from `AGENTS.md` when agents need the guidance during routine work.
- Update this file when the human gives a stable correction, workflow preference, review rule, or project priority that should apply to future tasks.
- Prefer positive phrasing. State the behavior agents should follow.
- Keep detailed history in `docs/CHANGELOG.md`; keep current human guidance in `docs/HUMAN_GUIDANCE.md`.

## README.md and GitHub About descriptions

- The first paragraph of `README.md` is the source text for the GitHub About description.
- The first paragraph must remain readable as raw Markdown source text.
- Repository About descriptions must stay under 250 characters.
- Agents edit only the first paragraph of `README.md`; the user copies that text into the GitHub About field.
- Write a clear, searchable hook that helps readers quickly understand the repository.
- Lead with the repository purpose and the main user benefit.
- Include one distinguishing detail if space allows.
- Prefer concrete nouns and plain language.
- Leave workflow steps, setup instructions, framework lists, and detailed claims for the rest of `README.md`.
- The first paragraph must be pure prose. Do not use badges, Markdown links, images, code spans, or raw URLs.
- Avoid repeating information already obvious, do not include repo name.

Preferred structure:
`[What it is] + [who/use case] + [distinctive detail]`

## Naming
- Use SCREAMING_SNAKE_CASE for Markdown docs filenames, with the .md extension
- For non-Markdown filenames, use only lowercase ASCII letters, numbers, and underscores.
- Prefer snake_case for most filenames. Avoid CamelCase in filenames.
- Use underscores between words and avoid spaces.
- Use `.md` for docs, `.sh` for shell, `.py` for Python.
- Keep filenames descriptive, and consistent with the primary thing the file provides.

## Git moves, renames, and index locks
- Use `git mv` for all renames and moves.
- Do not use `mv` plus add/remove as a fallback. Do not use `git rm` unless deleting a file permanently.
- Only humans run `git commit`. AI agents update `docs/CHANGELOG.md` for human review before committing.
- Before any index-writing Git command (including `git mv`, `git add`, `git rm`, `git checkout`, `git switch`, `git restore`, `git merge`, `git rebase`, `git reset`, `git commit`), verify `.git` is writable by the current user. If not, stop and report a permissions error.
- If `.git/index.lock` exists:
  - Do not modify files and do not run Git commands. Stop and report:
    - lock owner, permissions, and age (mtime)
    - process holding the lock, if detectable (for example, `lsof .git/index.lock`)
  - If a process holds the lock, report an active concurrent Git operation.
  - If no process holds the lock and the lock age is > 5 minutes, report a likely stale lock. Do not delete it automatically.
- If any Git command fails with an index lock error (cannot create `.git/index.lock`), stop immediately. Do not retry and do not fall back to `mv`.
- Error report must include: the command run and full stderr, plus a short next step: close other Git processes, remove a stale lock only if no process holds it, or fix `.git` permissions.

## Pytest failure triage
- For pytest test-writing rules, commands, and failure triage, see [PYTEST_STYLE.md](PYTEST_STYLE.md).

## Changelog rotation
- Rotate `docs/CHANGELOG.md` when it reaches about 1000 lines (`wc -l docs/CHANGELOG.md`).
- Keep complete day blocks together. Do not split entries from the same `## YYYY-MM-DD` heading across files.
- Keep the last two date-heading day blocks in active `docs/CHANGELOG.md` and move older day blocks to archive files.
- "Last two days" means the two most recent `## YYYY-MM-DD` headings present in the changelog, not a rolling 48-hour window; dates may be non-consecutive.
- Use archive filenames in the form `docs/CHANGELOG-YYYY-MM[a-z].md` (for example `docs/CHANGELOG-2026-02a.md`), choosing the next letter for additional rotations in the same month.
- When an archived range spans multiple months, name the archive after the **most recent month included** (the YYYY-MM closest to the active changelog), not the earliest. Example: a rotation moving 2026-01-23 through 2026-04-14 into one file becomes `docs/CHANGELOG-2026-04a.md`. This keeps the most recent archive sortable next to the still-active file.
- Date headings appear in **exactly one file**. A `## YYYY-MM-DD` heading must never exist in both the active changelog and an archive (or in two archives). Before rotating, check the boundary date against the existing newest archive; if it already lives there, drop it from the active file rather than copying it across.
- Preserve reverse-chronological order within each file after rotation.
- Each day block (`## YYYY-MM-DD`) should include the same subsection headings, in this order:
  - `### Additions and New Features`
  - `### Behavior or Interface Changes`
  - `### Fixes and Maintenance`
  - `### Removals and Deprecations`
  - `### Decisions and Failures`
  - `### Developer Tests and Notes`
- Keep section order stable so entries stay easy to scan over time.
- Categories are not required when they would be empty, but every changelog entry must belong to one category.
- Changelog entries are never removed, but they may be rephrased for accuracy and clarity.
- Legacy archives that use the older `CHANGELOG_ARCHIVE_NN.md` form must be renamed to the documented `CHANGELOG-YYYY-MM[a-z].md` form. The new name follows the most-recent-month-in-range rule above (use the most recent `## YYYY-MM-DD` heading inside the archive). Use `git mv` so history is preserved. Only one archive naming style should exist in the repo at any time.
- Automation: [rotate_changelog.py](../devel/rotate_changelog.py) enforces this rotation policy (keeps the two newest day blocks, archives the rest into `docs/CHANGELOG-YYYY-MM[a-z].md`, refuses to clobber boundary dates). [query_changelog.py](../devel/query_changelog.py) searches the active changelog and archives by date range, category, keyword, or source. [commit_changelog.py](../devel/commit_changelog.py) drafts the seed commit message from the changelog bullets newly ADDED in the working tree (via `git diff HEAD` on `docs/CHANGELOG.md`), then restricts those to the most recent run of consecutive day-block headings so an edited older bullet does not leak into the seed. All three share [changelog_lib.py](../devel/changelog_lib.py) (parser/serializer, git helpers, console + prompt helpers).

## Active plans folder organization
- Working planning artifacts under `docs/active_plans/` are filed into a closed set of subdirectories by kind.
- The five subdirectories are the closed set; adding a new category requires editing this section first.
  - `docs/active_plans/active/` for in-flight plans currently being acted on.
  - `docs/active_plans/audits/` for diagnostic and audit reports.
  - `docs/active_plans/reports/` for status reports and visual-acceptance reports.
  - `docs/active_plans/decisions/` for decision records and clarifications.
  - `docs/active_plans/workstreams/` for agent workstream artifacts.
- Forward-only by default: new files go directly into the matching subdirectory at creation time.
- Existing root-level files under `docs/active_plans/` stay in place; do not relocate them without an explicit, one-time sweep approved by the user.
- Topic-tag filename prefixes are retained inside each subdirectory (for example `no_crop_*`, `css_native_*`) so related artifacts cluster by name.
- Use snake_case filenames for these working docs, not SCREAMING_SNAKE_CASE; the all-caps rule covers durable `docs/*.md` reference docs, not active-plans scratch.
- When a plan is complete and no longer being acted on, close it by moving the file with `git mv` to `docs/archive/` so history is preserved.

## Versioning
- Prefer `pyproject.toml` as the single source of truth when the repo is a single Python package with a single `pyproject.toml`.
- If the repo contains multiple Python packages (multiple `pyproject.toml` files), keep package versions in sync across all `pyproject.toml` files. Unless otherwise stated.
- Maintain a REPO_ROOT/`VERSION` file as well that is sync'd with the `pyproject.toml` version.
- Store the version under `[project] version`.
- Prefer CalVer-style zero-padded year/zero-padded month versioning for new releases, formatted as `0Y.0M.PATCH` (for example `25.02.3rc1`). See https://calver.org/
- Use PEP 440 pre-release tags when needed: `aN` for alpha, `bN` for beta, and `rcN` for release candidates.
- When PATCH == 0, use shorthand `25.02b1` instead of `25.02.0b1`
- Prefer zero-padded 0Y.0M for readability and lexicographic sorting. Packaging tools may normalize 25.02.* to 25.2.*; this does not affect version ordering.
- Reference: [PyPA version specifiers](https://packaging.python.org/en/latest/specifications/version-specifiers/).
- When `devel/make_release.py` is present (propagated from `templates/shared/devel/`), use it to
  prepare GitHub source releases: it checks CalVer freshness, ensures the version tag is free,
  verifies the committed LICENSE, builds and spot-checks zip and tgz archives, generates an
  LLM-drafted release description, and optionally writes `docs/RELEASE_HISTORY.md` and
  `docs/NEWS.md` before printing the tag and `gh release create` commands. Run with `--dry-run`
  to preview all steps without mutating the repo, or `--write` to update the doc files.

## Scripts and executables
- Keep scripts self-contained and single-purpose.
- Add a shebang for executable scripts and keep them runnable directly.
- For repo-local Python commands, use:
  - `source source_me.sh && python ...`
- For pytest commands, use:
  - `pytest tests/`
- Avoid hard-coded interpreter paths in routine command examples.
- Document shared helpers and modules in `docs/USAGE.md` when used across scripts.
- Use `tests/test_pyflakes_code_lint.py` and `tests/test_ascii_compliance.py` for repo-wide lint checks, with `tests/check_ascii_compliance.py` for single-file ASCII/ISO-8859-1 checks and `tests/fix_ascii_compliance.py` for single-file fixes. `tests/test_markdown_links.py` is the repo-wide check that every local Markdown link is GitHub-browsable and well formed.
- For smoke tests, reuse stable output folder names (for example `output_smoke/`) instead of creating one-off output directory names; reusing/overwriting avoids repeated delete-approval prompts.
- In test scripts that need the repository root, import and use the shared `tests/file_utils.py` module:
  ```python
  import file_utils
  REPO_ROOT = file_utils.get_repo_root()
  ```
  This module uses `git rev-parse --show-toplevel` and is propagated across repos automatically.

### source_me.sh contract

- `source_me.sh` is a bash script sourced into your shell, not run directly. It
  enforces bash, sources `~/.bashrc`, and exports the Python runtime flags
  `PYTHONUNBUFFERED` and `PYTHONDONTWRITEBYTECODE`.
- It ships as a NOEXIST starter seed: the consumer repo owns its copy after
  bootstrap, so local edits do not propagate back and are never overwritten.
- Ordering invariant: `source ~/.bashrc` runs FIRST, before any repo-specific
  environment extension. `~/.bashrc` applies local shell setup and clears
  `PYTHONPATH`, so any `PYTHONPATH` line must come after it or be wiped.
- The seed sets no `PYTHONPATH`. One generic seed is shipped to every repo type;
  a universal `PYTHONPATH` is intentionally omitted. Most repos need none, and a
  broad path would mask missing-dependency bugs. `PYTHONPATH` need is per-repo
  (does the repo ship a repo-root package), which varies within a repo type, so
  there are no repo_type-specific seeds either.
- When a repo needs its repo-root modules importable while commands run from a
  subdirectory without installing the repo -- most commonly a repo-root package
  imported package-qualified (for example `import repolib.console`), or scripts
  under `tools/` or `tests/` that import repo-root modules -- uncomment the
  canonical extension block in that repo's `source_me.sh`. Use exactly this
  idiom (it assumes the repo is inside a Git work tree):
  ```bash
  # Must come after sourcing ~/.bashrc, which clears PYTHONPATH.
  REPO_ROOT="$(git rev-parse --show-toplevel)"
  export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
  unset REPO_ROOT
  ```

## Dependency manifests
- Store Python standard dependencies in `pip_requirements.txt` at the repo root and developer dependencies, e.g., pytest in `pip_requirements-dev.txt`.
- Use `pip_requirements.txt` not `requirements.txt` for clarity reasons
- Store Homebrew packages in `Brewfile` at the repo root.
- Use per-subproject manifests only when a subfolder is a standalone project.
- Document non-default system dependencies in `docs/INSTALL.md`.
- In general, we want to require all dependencies, rather than provide work-arounds if they are mssing, because without all the dependencies the program is too crippled to run properly

## Data and outputs
- Keep generated outputs out of git unless they are small and intentional.
- Put large inputs or outputs under a clear folder (for example `data/` or `output/`).
- Note input and output locations in `docs/USAGE.md`.
- Keep sample inputs small and safe.

## Documentation
- Keep repo docs in `docs/` unless a file is explicitly root-level.
- Keep docs current. Remove or replace stale docs.
- Use SCREAMING_SNAKE_CASE for Markdown docs filenames, with the .md extension
- Apply the ALL CAPS rule to files under docs/ (for example docs/INSTALL.md).
- Use underscores between words and avoid spaces.
- Choose clear, descriptive names.
- Keep well-known root-level docs (for example VERSION, README.md, AGENTS.md).
- I prefer to use social media links instead of hard coding my email in repos. For example, Neil Voss, https://bsky.app/profile/neilvosslab.bsky.social
- When referencing files, use Markdown links so users can click through. Markdown links are created using the syntax ``URL``, where "link text" is the clickable text that appears in the document, and "URL" is the web address or file path the link points to. This allows users to navigate between different content easily. Use file-path link text so readers know the exact filename (good: `[MARKDOWN_STYLE.md](MARKDOWN_STYLE.md)`, bad: `[Style Guide for Markdown](MARKDOWN_STYLE.md)`). Only include a backticked path when the link text is not the path.


### Recommended common docs
- `AGENTS.md`: agent instructions, tool constraints, and repo-specific workflow guardrails.
- `README.md`: project purpose, quick start, and links to deeper documentation.
- `LICENSE`: legal terms for using and redistributing the project; keep exact license text.
- `docs/CHANGELOG.md`: chronological, user facing record of changes, grouped by date. Timeline of what changed and when.
- `docs/CHANGELOG.md` entries should also note important failures and key implementation choices so the log remains a useful learning record for later debugging and decision review.
- `docs/CODE_ARCHITECTURE.md`: high-level system design, major components, and data flow.
- `docs/FILE_STRUCTURE.md`: directory map with what belongs where, including generated assets.
- `docs/INSTALL.md`: setup steps, dependencies, and environment requirements.
- `docs/NEWS.md`: curated release highlights and announcements, not a full changelog.
- `docs/RELATED_PROJECTS.md`: sibling repos, shared libraries, and integration touchpoints.
- `docs/RELEASE_HISTORY.md`: organized log of released versions and their release dates. Summarizes notable shipped qualities, including notes, major fixes, and compatibility notes.
- `docs/ROADMAP.md`: planned work, priorities, and what is intentionally not started.
- `docs/TODO.md`: backlog scratchpad for small tasks without timelines.
- `docs/TROUBLESHOOTING.md`: known issues, fixes, and debugging steps with symptoms.
- `docs/USAGE.md`: how to run the tool, CLI flags, and practical examples.

### Centrally maintained docs, do not edit locally
- `docs/AUTHORS.md`: primary maintainers and notable contributors
- `docs/CLAUDE_HOOK_USAGE_GUIDE.md`: generated hook behavior reference, not a repo style source of truth. If repo style differs from hook examples, update repo style docs and recommend a hook rule update upstream.
- `docs/MARKDOWN_STYLE.md`: Markdown writing rules and formatting conventions for this repo.
- `docs/PLAYWRIGHT_TEST_STYLE.md`: browser test authoring style for the website family (`website` and its inheriting `typescript`); ships via the `templates/website/` overlay.
- `docs/PYTEST_STYLE.md`: pytest test-writing rules, commands, fixture policy, and failure triage.
- `docs/PYTHON_STYLE.md`: Python formatting, linting, and project-specific conventions.
- `docs/REPO_STYLE.md`: repo-level organization, conventions, and file placement rules.

### Less common but acceptable
- `docs/COOKBOOK.md`: extended, real-world scenarios that build on usage docs.
- `docs/DEVELOPMENT.md`: local dev workflows, build steps, and release process.
- `docs/FAQ.md`: short answers to common questions and misconceptions.

### File I/O
Possible examples:
- `docs/INPUT_FORMATS.md`: supported input formats, required fields, and validation rules.
- `docs/OUTPUT_FORMATS.md`: generated outputs, schemas, naming rules, and destinations.
- `docs/FILE_FORMATS.md`: combined reference for input and output formats when one doc is clearer.
- `docs/YAML_FILE_FORMAT.md`: YAML schema, examples, and validation requirements.

### Docs not to use
- `CONTRIBUTING.md`: probably better under the DEVELOPMENT.md page
- `CODE_OF_CONDUCT.md`: avoid adding unless project scope changes and it will be maintained.
- `COMMUNITY.md`: avoid adding; this repo does not run a community program.
- `ISSUE_TEMPLATE.md`: avoid adding; this repo does not use GitHub issue templates here.
- `PULL_REQUEST_TEMPLATE.md`: avoid adding; we are not using GitHub PR templates here.
- `SECURITY.md`: avoid adding unless security reporting is formally supported.

### Repo-specific docs are always encouraged
- `docs/CONTAINER.md`: container image details, build steps, and run commands.
- `docs/ENGINES.md`: supported external engines/services and how to select them.
- `docs/EMWY_YAML_v2_SPEC.md`: specification for the EMWY YAML v2 format with examples.
- `docs/MACOS_PODMAN.md`: macOS-specific Podman setup steps and known issues.
- `docs/QUESTION_TYPES.md`: catalog of question types with expected fields and behavior.

## Licensing
Check the license file to match these criteria.

- Most source code is licensed under **GPLv3**, unless stated otherwise.
- Libraries intended for use by proprietary or mixed-source software are licensed under **LGPLv3**.
- Non-code creative works, including text and figures, are licensed under **CC BY-SA 4.0**. Commercial use is permitted.

- Code and non-code materials are licensed separately to reflect different legal and practical requirements.
