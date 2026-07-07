# Exclude both end-to-end tiers from pytest collection. tests/playwright/
# holds browser-driven tests (Playwright), and tests/e2e/ holds heavier
# shell/Python whole-system runners. Both run outside pytest -- see
# docs/PLAYWRIGHT_USAGE.md and docs/E2E_TESTS.md.
collect_ignore = ["e2e", "playwright"]

# REPO_HYGIENE_FILTERS is the repo-local hygiene-exclusion registry (Layer 2).
# file_utils.discover_files reads it from this conftest, which is the right
# home because propagation only merges the collect_ignore block above into this
# file; the rest of conftest survives and may differ per repo. Vendored files
# (file_utils.py and every tests/test_*.py) get overwritten by propagation,
# so they must hold no repo-specific data. Put repo-specific exclusions here.
#
# Shape and rules:
#   - It is a dict: key -> list of repo-relative POSIX glob patterns.
#   - Keys are "all" or a vendored test key. A test key is the test filename
#     stem with the leading "test_" removed (test_pyflakes_code_lint.py ->
#     "pyflakes_code_lint", test_ascii_compliance.py -> "ascii_compliance").
#   - Patterns match repo-relative POSIX paths via fnmatch.fnmatchcase
#     (case-sensitive). A match excludes the file from that test.
#   - "all" patterns apply to every test; a test-key list applies only when
#     that test_key is passed to discover_files.
#   - Recursive directory exclusions need an explicit /** because fnmatch's *
#     does not cross "/". Use "temp_scripts/**" to exclude a whole subtree.
#
# This template has no repo-specific exclusions, so the registry is empty.
# Cross-overlay doc references (a template doc naming a doc that ships from a
# different overlay or the universal docs/ tree) use a backticked name, not a
# markdown link: no single relative link is valid both in the split template
# tree and in the flattened consumer repo.
# Example entries (commented out; this repo needs none):
#   REPO_HYGIENE_FILTERS = {
#       "all": ["temp_scripts/**", "TEMPLATE.py"],
#       "ascii_compliance": ["human_readable-*.html"],
#       "pyflakes_code_lint": ["devel/scratch_*.py"],
#   }
REPO_HYGIENE_FILTERS = {}

# === OPTIONAL_HELPERS_MENU ===
# See meta/docs/PROPAGATION_RULES.md for the managed-block propagation contract.
# This block is an optional helpers menu appended once by propagation and
# never overwritten on subsequent propagation runs. Uncomment a recipe below
# to enable it for this repo. Every line here is a comment by default so an
# untouched consumer behaves exactly as it did before propagation added this
# block.
#
# Note: inserting the repo root onto sys.path is now done unconditionally at the
# top of this file via file_utils.get_repo_root(), so it is no longer a recipe.
#
# --- Recipe 1: redirect matplotlib config dir to a per-repo tmp location ---
# Prevents matplotlib from writing to the home-directory config cache during
# tests, which can cause cross-repo pollution or permission errors in CI.
# Set MPLCONFIGDIR to a writable tmp path before matplotlib is imported.
# Note: PYTHONUNBUFFERED and PYTHONDONTWRITEBYTECODE are handled by
# source_me.sh and belong there, not here.
#
#	import os
#	import tempfile
#	os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="mpl_"))
