## Coding Style
See Python coding style in docs/PYTHON_STYLE.md.
See Markdown style in docs/MARKDOWN_STYLE.md.
See repo style in docs/REPO_STYLE.md.
When making edits, document them in docs/CHANGELOG.md.
Agents may run programs in the tests folder, including smoke tests and pyflakes/mypy runner scripts.
When in doubt, implement the changes the user asked for rather than waiting for a response; the user is not the best reader and will likely miss your request and then be confused why it was not implemented or fixed.
When changing code always run tests, documentation does not require tests.

## Environment
Codex must run Python using `/opt/homebrew/opt/python@3.12/bin/python3.12` (use Python 3.12 only).
On this user's macOS (Homebrew Python 3.12), Python modules are installed to `/opt/homebrew/lib/python3.12/site-packages/`.
