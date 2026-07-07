# Claude hook usage guide

_Last updated: 2026-06-30 21:10 UTC. Source of truth: `claude-code-permissions-hook`
repo. Mirrors in sibling repos (e.g. `starter-repo-template`) are copies; do not
edit mirrors directly._

Timestamp format: `YYYY-MM-DD HH:MM UTC` (ISO 8601 date + 24-hour clock, UTC).
Regenerate on every audit; derive from the latest `## YYYY-MM-DD` heading in
`docs/CHANGELOG.md` plus current commit time.

Best practices for AI agents in repos using the `claude-code-permissions-hook`:
what is allowed, denied, and passed through, with preferred alternatives for denied
patterns. Claude-specific (not Codex). Repo style conventions live in
[REPO_STYLE.md](REPO_STYLE.md) and [PYTHON_STYLE.md](PYTHON_STYLE.md).

## Trust model

The hook optimizes for high task completion with bounded blast radius: allow routine local work, deny/steer on machine-changing actions, prompt on high-impact operations.

## Guide philosophy

This guide is moving toward principles over catalog. It teaches how the hook
decides -- decompose a command into leaves, match each leaf, pick an outcome --
plus the safe-zone and blast-radius reasoning behind those decisions and the
fast recovery path when a leaf is denied. Aim for the smallest set of
principles that lets a reader predict any outcome.

- Treat the TOML config as the source of truth for exact patterns and for the
  deny `reason` text. The agent sees that reason live at runtime, so the guide
  stays focused on principles and recovery.
- Let per-repo-type and single-tool specifics live in the config, where they
  apply.
- Prefer principle plus recovery, and let the config carry the specifics.

As older sections are touched, trim them toward this model.

## Overview

The permissions hook intercepts every Claude Code tool call and evaluates it against TOML config rules. Each call gets one of three outcomes:

| Outcome | Meaning |
| --- | --- |
| **Allow** | Tool call proceeds automatically |
| **Deny** | Tool call is blocked with an error message |
| **Passthrough** | Falls back to Claude Code's default permission flow (user prompt) |

### Command decomposition

The hook decomposes compound commands (`&&`, `||`, `;`, pipes) into leaf sub-commands:

- **Deny** if ANY leaf matches a deny rule
- **Allow** if ALL leaves match allow rules
- **Passthrough** if any leaf has no matching rule (and none denied)

A compound command fails as a whole even if only one leaf is illegal. If `find ... ; ls ...` is denied, the `ls ...` half would have run on its own -- drop the denied leaf and re-run rather than rewriting both.

Unwraps `bash -c "..."` and extracts `$(...)`. Strips environment-variable prefixes (`NODE_PATH=/foo node script.js` -> `node script.js`).

### Max chain length

Commands with more than **5** chained sub-commands are denied automatically.

### Bash-side reference for redirected commands

`Read`, `Edit`, and `Write` are first-class Claude Code tool calls. The Grep/Glob tools are not exposed in this agent context, so Bash `grep`/`rg` is the primary file-search path. `grep`/`rg` against a file path is **allowed in safe zones** (CWD-relative, workspace, `/tmp`, narrow `~/.claude` subtrees) and denied only when the path escapes them (out-of-zone absolute, bare `~`, `..`). `find` is likewise allowed read-only in those safe zones. The columns below show denied Bash forms, preferred recovery paths, and Bash forms that remain allowed.

| Denied Bash form | Preferred recovery | Allowed Bash forms |
| --- | --- | --- |
| `cat /path/to/file`, `head -20 /path`, `tail -20 /path` | Read tool with `file_path`, `offset`, `limit` | `... \| cat`, `... \| head -5`, `... \| tail -5` (pipeline, no file arg) |
| `grep root /etc/passwd`, `rg pat /usr/...` (out-of-zone), `/usr/bin/grep ...` (abs binary), `egrep`/`fgrep` | read a known file with the Read tool, or narrow to a relative/workspace path | `grep -n pat src/file`, `rg pat docs/`, `grep foo /tmp/x`, `grep -n foo ~/<workspace>/repo/x`, `... \| grep pat` |
| `find /etc -name '*.conf'`, `find . -delete`, `find /Users` (unsafe shapes) | Use bounded read-only `find` in a safe path zone (`.`, `/tmp`, `~/<workspace>/...`, `/Users/<me>/<workspace>/...`). For repo content, `git ls-files <pathspec>` is still preferred. | `find . -name '*.py'`, `find /tmp -type f`, `find ~/<workspace>/repo -type f` |
| `sed -n '10,20p' file.txt` | Read tool with `offset=10`, `limit=11` | `... \| sed -n '10,20p'` (pipeline) |

The deny rules cover all binary variants (alternate names, absolute paths like
`/usr/bin/grep` or `/opt/homebrew/.../grep`, `rg`). The fastest path through a
deny is the preferred recovery in column two; column three covers cases where
Bash is still the right shape.

## Allowed commands

### Python

```bash
source source_me.sh && python3 script.py
python3 -m pytest tests/test_foo.py
pytest tests/test_foo.py -k test_name
pyflakes script.py
```

Always use `source source_me.sh && python3` for running Python. Direct `python3`
invocations also work. Command substitution (`` ` `` or `$(...)`) is blocked in
Python commands.

### Git

Allowed git subcommands:

`add`, `branch`, `check-ignore`, `checkout`, `diff`, `ls-files`, `ls-tree`,
`log`, `mv`, `pull`, `remote`, `restore`, `rev-parse`, `show`, `status`, `worktree`

The `-C <path>` flag is supported before the subcommand.

```bash
git status
git diff --staged
git log --oneline -10
git -C /path/to/repo status
git mv old_name.py new_name.py
```

### Cargo

All cargo subcommands are allowed except: `publish`, `yank`, `login`, `logout`,
`owner`, `install`. Command substitution is blocked.

```bash
cargo build
cargo test
cargo clippy -- -D warnings
cargo fmt --check
```

### Shell scripts

```bash
bash script.sh
./script.sh
./script.py
./subdir/script.py
tools/runner.py          # bare relative-path scripts
scripts/build.sh
```

`bash -n script.sh` (syntax check) is denied -- inspect the script with the
Read tool instead.

### Built binaries (.build/, target/)

Run a freshly-built first-party binary from the CWD, or from its full
workspace-absolute path. SwiftPM emits under `.build/`, Cargo under
`target/debug|release/`. `..` and command substitution fall to passthrough;
absolute paths outside the workspace also stay passthrough.

```bash
.build/debug/app --version                       # allowed (CWD-relative)
~/<workspace>/repo/.build/debug/app --version    # allowed (workspace-absolute)
/abs/outside/.build/debug/app                    # passthrough (outside workspace)
```

### Safe utilities

These commands are allowed as single commands. Command substitution is blocked, except that a backtick or `$(` inside a single-quoted `grep`/`rg`/`find` pattern is literal and allowed.

**File and text processing:**
`cat`, `colordiff`, `comm`, `cut`, `diff`, `expand`, `file`, `fmt`, `fold`,
`grep`, `head`, `jq`, `mediainfo`, `nl`, `od`, `paste`, `pdftotext`, `rg`, `sed`,
`seq`, `shuf`, `sort`, `tac`, `tail`, `tee`, `tr`, `unexpand`, `uniq`, `wc`, `xargs`

**Filesystem navigation:**
`basename`, `cd`, `chmod`, `cp`, `dirname`, `du`, `df`, `ls`, `lsof`, `mkdir`,
`mktemp`, `open`, `readlink`, `realpath`, `stat`, `tar`, `touch`, `tree`, `type`,
`unzip`, `which`

**Process and system info:**
`curl`, `date`, `echo`, `env`, `export`, `expr`, `false`, `id`, `ln`, `md5`,
`nproc`, `numfmt`, `pgrep`, `pkill`, `printenv`, `printf`, `ps`, `pwd`,
`screencapture`, `sleep`, `source`, `test`, `timeout`, `true`, `tty`, `uname`,
`unlink`, `wc`, `whoami`, `xcrun`, `xxd`

Note: Some of these (like `cat`, `head`, `tail`) deny when used with a file path
argument -- use the Read tool for file inspection, and `git ls-files <pathspec>`
plus targeted Read for file search; piped `grep`/`rg` on already-bounded stdout
stays allowed. `awk` is denied entirely; use `cut` for field extraction or a
`_temp.py` helper.

### Local runtimes

**Node.js:**
`node` is broadly allowed -- any `node <flags> <args...>` invocation auto-allows
except inline eval (`-e`/`--eval`, denied) and command substitution. This covers
directory-form test runs and flag combinations a narrower rule would miss.

```bash
node script.js                       # allowed
node --import tsx --test tests/      # allowed (directory form)
node --watch script.mjs              # allowed
node script.js -e foo                # allowed (file arg before -e, not inline eval)
```

**npx (whitelisted packages):**
Allowed for: `tsc`, `tsx`, `eslint`, `prettier`, `playwright`, `esbuild`,
`vitest`, `jest`, `vite`, `http-server`, `serve`, `tailwindcss`,
`@biomejs/biome`, `nodemon`, `concurrently`. Unknown packages require user
approval (npx fetches and executes, beyond info-gathering, so this stays a
whitelist rather than a broad allow).

```bash
npx tsc --noEmit              # allowed
npx vitest run                # allowed
npx some-package              # requires approval
```

If `npx tsc` fails because TypeScript is not installed, run `npm install --save-dev typescript` (whitelisted).

**rustc and rustup:**
`rustc` is broadly allowed for local compilation, mirroring the existing
`cargo`/`swift` allows. `rustup` is allowed for read-only verbs only:
`show`, `which`, `--version`, `component list`, `toolchain list`,
`target list`. Mutating verbs (`install`, `default`, `override`, `update`,
`toolchain install`) stay passthrough -- installs are gated.

```bash
rustc --edition 2021 src/main.rs   # allowed
rustup show                         # allowed
rustup toolchain list                # allowed
rustup toolchain install stable      # passthrough (install)
```

**eslint and prettier (direct):**
`eslint` and `prettier` are allowed as direct commands for linting and formatting.

```bash
eslint src/app.ts
prettier --write src/
```

**Deno:**
`deno` is allowed for `run`, `check`, `fmt`, `lint`, and `test` subcommands,
plus `--version` queries. Remote URLs and `deno eval` are not auto-allowed.

```bash
deno run script.ts
deno check script.ts
deno fmt --check
deno lint
deno test
deno --version
```

### Podman (containers)

Read-only inspection, build, compose, lifecycle, and exec are allowed:

```bash
podman ps
podman pod ls
podman images
podman logs web
podman inspect web
podman info
podman build -t foo .
podman compose up -d
podman compose down
podman start web
podman stop web
podman restart web
podman exec web ls /var/www
podman exec web cat /etc/hostname
```

Destructive operations are denied: `podman rm -f`, `podman rmi -f`,
`podman kill`, `podman stop -t 0`, `podman system prune`,
`podman volume rm|prune`, `podman network rm|prune`, `podman image rm|prune`.
Ask the user to run these manually if truly needed.

Note: arguments to `podman exec` are not re-decomposed by the hook, so a
destructive shell inside a container (`podman exec web rm -rf /tmp/x`) is not
blocked. Destructive behavior inside a container is a container-level concern.

### Tools scoped to /tmp scratch dirs

These tools are auto-allowed when every path argument lives under `/tmp/` or `/private/tmp/`, but denied for paths outside scratch directories (`/Users`, `/etc`, `/usr`, `/opt`, `/var`, `/Library`, `/System`, etc.):

`ffmpeg`, `sox`, `convert`, `magick`, `mogrify`, `gm`, `optipng`, `pngcrush`, `jpegoptim`, `cwebp`, `tesseract`, `qpdf`, `pdftk`, `gs`, `lame`, `flac`, `pandoc`, `soffice`, `pdftoppm`

```bash
ffmpeg -i /tmp/in.wav /tmp/out.m4a              # allowed
sox /tmp/clip.wav -n trim 0 20 stat             # allowed
convert /tmp/in.png /tmp/out.jpg                # allowed
pdftoppm -png -r 90 /tmp/doc.pdf /tmp/page      # allowed
ffmpeg -i /tmp/in.wav /Users/me/out.wav         # passthrough (out of tmp)
convert in.png out.png                          # passthrough (no tmp path)
```

This is partial for `pandoc`/`soffice`: the common "workspace input, `/tmp`
output" shape (for example `soffice --convert-to pdf --outdir /tmp
report.docx`) still passes through, because separating input path from
output path needs lookahead the hook's regex engine does not have.

`sips` write forms (`-c`, `-z`, `-s`, `--out`) are also `/tmp`-scoped here; `sips -g`
metadata reads are allowed at any path. `ffmpeg ... -f null -` (decode-only validation,
no output file) is allowed for any input path.

`magick identify` and `magick -list` are allowed at any path (read-only,
never write) -- this is separate from the `/tmp`-scoped convert/transform
forms above, which still require every path under `/tmp`.

```bash
magick identify /Users/me/repo/docs/screenshot.png   # allowed
magick -list font                                     # allowed
magick /tmp/a.png -resize 50% /tmp/b.png               # allowed (tmp-scoped transform)
magick /Users/me/a.png -resize 50% /Users/me/b.png     # passthrough (transform, out of tmp)
```

### macOS read-only inspection

`diskutil list` / `diskutil info` are allowed (read verbs); destructive verbs
(`eraseDisk`, `partitionDisk`, `unmountDisk`) stay passthrough. `plutil -lint` and
`plutil -convert ... -o -` (stdout) are allowed; convert-to-file forms passthrough.

### Read-only inspectors

`xmllint` (without `-o`/`--output`), `strings`, and `fc-list` are allowed at
any path -- none of them write. `xmllint --output out.xml in.xml` (writes a
file) stays passthrough. `screenshot` (the easy-screenshot CLI used by the
screenshot-docs skill) is also allowed.

```bash
xmllint --format data.xml         # allowed
xmllint --output out.xml in.xml   # passthrough (writes a file)
strings /path/to/binary           # allowed
fc-list | grep -i mono            # allowed
screenshot --help                 # allowed
```

### File deletion (safe patterns)

The `rm` command is denied by default, but these specific patterns are allowed:

| Pattern | Example |
| --- | --- |
| Underscore-prefixed files | `rm _temp.py`, `rm -f /path/to/_scratch.sh` |
| `/tmp/` paths | `rm /tmp/test_output.json` |
| Cache directories | `rm -rf __pycache__`, `rm -r ~/Library/Caches/foo` |
| `git rm` with relative paths | `git rm old_file.py` |
| `rmdir` (empty-dir only) | `rmdir /tmp/empty`, `rmdir src/content/old/` |

`rmdir` (including `rmdir -p`) is allowed because it only removes empty directories and fails if non-empty. Use to clean up empty source directories after `git mv` chains.

### Package managers

**pip read-only:**
`pip show`, `pip list`, `pip freeze`, `pip check`

**npm (broad allow, installs/exec/publish/auth excluded):**
`npm` is broadly allowed -- this blesses running first-party scripts from the
local `package.json` (`npm run`, `npm test`), the same trust already granted
to `./script.sh` and `node script.js`. Excluded (stay passthrough): installs
and removals (`install`, `i`, `ci`, `add`, `update`, `upgrade`, `uninstall`,
`remove`, `rm`, `prune`, `dedupe`), `exec`/`x`, `publish`/`unpublish`, auth
(`login`, `logout`, `adduser`, `owner`, `deprecate`, `token`, `star`,
`unstar`), `pkg set`/`pkg delete`, and `audit fix`. The dedicated
`npm install --save-dev typescript` allow is unchanged.

**brew read-only:**
`brew list`, `brew info`, `brew search`, `brew --prefix`

```bash
pip show numpy
npm list --depth=0
npm run build
npm test                        # allowed (broad npm allow)
npm view react versions         # allowed
npm pkg get scripts             # allowed (read-only)
npm install --save-dev typescript  # allowed (dedicated allow)
npm install lodash              # passthrough (install)
npm exec cowsay hi              # passthrough (excluded)
brew info python
```

### File access zones

The hook may contain rules for Claude Code tools that are not exposed in
every agent context (`Grep` and `Glob` in particular -- see notes
below). This guide recommends only recovery paths observed to be
available in the target context.

| Tool | Allowed paths |
| --- | --- |
| Read | `~/nsh/`, `~/.<dotdirs>`, site-packages, `/tmp/`, `/var/folders/` |
| Write | `~/nsh/`, `~/.claude/`, `/tmp/` |
| Edit | `~/nsh/`, `~/.claude/`, `/tmp/` |
| Glob | Supported defensively when exposed by Claude Code; not a standard recovery path in this agent context |
| Grep | Supported defensively when exposed by Claude Code; not a standard recovery path in this agent context |

All file tools block path traversal (`..`). Reading `.env` and `.secret` files is denied.

### Web tools

`WebFetch` and `WebSearch` are allowed without restrictions.

### Agent types

Any agent with a valid name matching the pattern `^[a-zA-Z][a-zA-Z0-9_:-]*$` is
allowed. This includes built-in types (Explore, Plan, general-purpose) and custom
agents in `~/.claude/agents/`. Missing `subagent_type` falls through to user prompt.

### Orchestration tools

These tools are auto-allowed: `TaskOutput`, `TaskCreate`, `TaskList`, `TaskGet`,
`TaskUpdate`, `TaskStop`, `Skill`, `SendMessage`, `TeamCreate`, `TeamDelete`,
`NotebookEdit`.

Playwright MCP browser tools (`mcp__plugin_playwright_playwright__browser_*`)
are also allowed.

## When something is blocked

The agent sees the exact deny `reason` the moment a command is blocked, and that
runtime reason is the source of truth -- it always names the positive next step.
This is only the fast path for the common cases, not a catalog of every deny; the
TOML config holds those patterns.

The recurring principle: do local, first-party, read-only work directly; reach
for a tool or a scratch file instead of an inline or out-of-zone shell form; and
let the human own machine-changing and history-changing actions.

| When you want to... | Do this |
| --- | --- |
| Read a file | Read tool with `file_path`/`offset`/`limit`, not `cat`/`head`/`tail`/`sed <file>` |
| Search file contents | `grep`/`rg` on a relative or workspace path (`grep -rn pat src/`); for an out-of-zone path, Read a known file or narrow the path |
| List files | `ls <dir>` or `git ls-files <pathspec>`; read-only `find` in a safe path zone |
| Run inline code | Write `_temp.py` / `_temp.mjs` and run it, not `python -c` / `node -e` / heredocs |
| Run a loop | Put it in `_temp.sh` / `_temp.py`, not inline `for`/`while` |
| Rename or move a file | `git mv` for tracked files; `cp` plus a `_`-scratch otherwise |
| Delete a file | Underscore-prefix scratch (`rm _temp.py`), a `/tmp/` path, or `git rm`; `rmdir` for empty dirs |
| Commit work | Commit on an `agent/<task>` branch; prepare protected-branch merges with `git merge --no-commit --no-ff agent/<task>` and let the human commit |
| Install, push, or run `gh`/`sudo` | Ask the user; installs and pushes stay gated for human approval |
| Run remote code | Download to a file, review it, then run it locally; never pipe a download into a shell |

Search note: Bash `grep`/`rg` is the primary file-search path here (the
Grep/Glob tools are not exposed). It is allowed against any relative, workspace,
or `/tmp` path; only out-of-zone absolute scans, bare `~`, and `..` traversal are
held back so a search cannot flood context. A backtick or `$(` inside a
single-quoted pattern is literal and allowed; an unquoted command substitution is
the only grep/find form rejected outright.

## Path existence pre-check

Before evaluating allow or deny rules, the hook stats the target path of `Read`, `Edit`, `MultiEdit`, `Glob`, and `Grep` calls and denies if the path is missing or unusable, immediately catching the common "hallucinated path" failure mode.

### Per-tool semantics

| Tool | Requirement | Failure modes |
| --- | --- | --- |
| `Read` | `file_path` resolves to an existing, non-directory target | missing path; path is a directory; broken symlink |
| `Edit` / `MultiEdit` | `file_path` exists, OR its parent directory exists | both file and parent missing |
| `Glob` | resolved `path` is an existing directory | missing path; file passed where directory expected |
| `Grep` | resolved `path` (when provided) exists as file or directory | missing path |
| `Write` | exempt | n/a -- Write creates new files by design |

Symlinks-to-existing-files are accepted for `Read`. Broken symlinks deny
because `fs::metadata` follows the link and reports the missing target.
Relative paths are resolved against the hook input's `cwd`. When `Glob` or
`Grep` is called without a `path` field, the pre-check is skipped (the
cwd fallback is trusted).

### Reason strings the agent sees

| Condition | Reason |
| --- | --- |
| Read target missing | `Verify the file path before retrying. Read target does not exist: <path>.` |
| Read target is a directory | ``Read targets a file, not a directory. Use `ls <dir>` or `git ls-files <pathspec>` to list directory contents. Path is a directory: <path>.`` |
| Edit / MultiEdit both missing | `Create the parent directory first or choose an existing path. Edit target and parent directory are both missing: <path>; parent: <parent>.` |
| Glob path missing or not a directory | `Choose an existing search directory before retrying. Glob path does not exist as a directory: <path>.` |
| Grep path missing | `Choose an existing file or directory before retrying. Grep path does not exist: <path>.` |
| Stat failed for any reason other than NotFound (permissions, etc.) | `Verify the path before retrying. The hook could not confirm that this path exists: <path>.` |

The pre-check distinguishes `Ok(false)` (path confirmed missing) from
`Err(_)` (could not stat -- permission denied on a parent directory,
malformed path, etc.). Only confirmed-missing emits "does not exist";
errors emit "could not confirm" so the message stays accurate.

### What to do when you see one of these reasons

- Verify the path before retrying. The hook printed exactly which path it
  could not find and, for Edit, which parent directory was also missing.
- If the path was a typo, fix it. If the path belongs to a different
  working directory, set `cwd` correctly or use an absolute path.
- For Read of a directory, use `ls <dir>` or `git ls-files <pathspec>`
  to list contents. For Glob with a file argument, switch to Read for a
  single file or `git ls-files <pathspec>` to list candidates.
- For a brand-new file you intend to create, prefer `Write`; the pre-check
  is exempt for `Write`. `Edit` of a brand-new file is also accepted as long
  as the parent directory already exists.

## Worktrees and protected branches

Agents work on `agent/<task>` branches (often inside a worktree) and prepare
merges into protected branches (`main`, `master` by default) using:

```bash
git merge --no-commit --no-ff agent/<task>
```

This stages the merge result without creating the commit. The human reviews with `git diff HEAD` and runs the final `git commit` and `git push` themselves. Direct `git commit`, `git rebase`, `git reset --hard`, `git cherry-pick`, `git revert`, and pushes targeting protected refs are denied while on a protected branch; the same commands are allowed on feature/agent branches.

## Passthrough (requires user approval)

These commands intentionally require user approval (passthrough) because they have
significant side effects or security implications:

- **npx (non-whitelisted)**: May fetch remote packages from npm registry
- **npm install**: Modifies machine state, adds/updates dependencies
- **pip install**: Modifies machine state, adds/updates Python packages
- **git rebase**: Rewrites repository history
- **deno eval**: Executes arbitrary inline code

## Passthrough (interactive tools)

These tools intentionally passthrough to Claude Code's default permission flow
so the user sees interactive dialogs:

| Tool | Reason |
| --- | --- |
| `AskUserQuestion` | User must see and answer the question dialog |
| `EnterWorktree` | User must consent to worktree creation |
| `ExitWorktree` | User must consent to keep/remove decision |
| `CronCreate` | User should approve scheduled recurring jobs |
| `CronDelete` | User should approve canceling scheduled jobs |
| `CronList` | Kept consistent with other Cron tools |

Do NOT add these tools to any allow rule. Auto-approving them bypasses Claude Code's
interactive UI dialogs, causing blank answers or skipped consent screens.

## Best practices

- Always use `source source_me.sh && python3` for Python execution
- Use the Read tool for file inspection (offset / limit available)
- Search file contents with `grep`/`rg` directly on a relative or workspace path (`grep -rn pat src/`); the Grep tool is not available here
- Use `ls <dir>` or `git ls-files <pathspec>` to list files
- Write scratch code to `_temp.py` or `_temp.sh` (underscore prefix = safe to delete)
- Keep compound commands under 5 chained sub-commands
- Destructive `xargs` pipelines (`xargs rm`, `xargs chmod`, `xargs chown`, `xargs mv`, `xargs sudo`) stay denied
- Use relative paths for project files where possible
- Stage changes and update `docs/CHANGELOG.md`; let the user commit

## Common patterns

Quick rules of thumb (each is detailed in the per-command sections above):
use `Read`/`Edit`/`Write` tool calls, not `cat`/`sed`/`printf`; search with
`grep`/`rg` on a relative or workspace path (not `/etc`, not the `Grep` tool);
list with `ls` or `git ls-files`; run Python via `source source_me.sh &&
python3 script.py` (no `-c`); write loops/inline code to `_temp.py`/`_temp.sh`;
rename with `git mv`; delete only `_temp*`/`/tmp` paths; stage to `/tmp` for
`ffmpeg`/`convert` and prefer `mediainfo` over `ffprobe`.
