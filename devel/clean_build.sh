#!/usr/bin/env bash
# clean_build.sh - light clean: wipe build output, tool caches, and test
# artifacts while KEEPING dependency installs (node_modules, Rust target/) so no
# reinstall or full recompile is needed afterward.
#
# Front door: this is the everyday build cleaner, wired to `npm run clean` in
# TypeScript repos. Run directly as ./devel/clean_build.sh. For a deep reset that
# also removes node_modules and Rust target/ (a distribution-clean checkout), use
# devel/dist_clean.sh instead. Both keep the committed package-lock.json.
#
# Universal across repo types (python, typescript, rust). Patterns that do not
# exist in a given repo are silently skipped via `nullglob` + an existence
# check, so no false-positive output.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

DELETED=()

delete_path() {
	local p="$1"
	if [ -e "$p" ] || [ -L "$p" ]; then
		rm -rf "$p"
		DELETED+=("$p")
	fi
}

delete_find_matches() {
	local label="$1"
	shift
	local match
	while IFS= read -r -d '' match; do
		rm -rf "$match"
		DELETED+=("${match#./}")
	done < <(find . "$@" -print0)
}

# Generic build outputs (any language).
delete_path dist
delete_path dist-single
delete_path _site
delete_path build
delete_path out

# TypeScript / JS build artifacts and bundler metadata.
delete_path _bundle.js
delete_path meta.json
delete_path stats.html
delete_find_matches tsbuildinfo -type f -name '*.tsbuildinfo'

# JS/TS tool caches.
delete_path .cache
delete_path .eslintcache
delete_path .prettiercache
delete_path .nyc_output

# Xcode / Swift build outputs and metadata.
delete_path .build
delete_path .swiftpm
delete_path DerivedData
delete_find_matches xcresult -type d -name '*.xcresult'
delete_find_matches xcuserdata -type d -name 'xcuserdata'

# Test outputs (Playwright, coverage).
delete_path test-results
delete_path playwright-report
delete_path blob-report
delete_path coverage

# Python bytecode and tool caches (any depth).
delete_find_matches pycache -type d -name '__pycache__'
delete_find_matches pytest_cache -type d -name '.pytest_cache'
delete_find_matches mypy_cache -type d -name '.mypy_cache'
delete_find_matches ruff_cache -type d -name '.ruff_cache'

# Dependency installs (node_modules, Rust target/) and the committed
# package-lock.json are intentionally KEPT here. Use devel/dist_clean.sh for a
# full reset that also removes node_modules and target/.

if [ "${#DELETED[@]}" -eq 0 ]; then
	echo "Nothing to clean."
else
	echo "Cleaned ${#DELETED[@]} path(s):"
	for p in "${DELETED[@]}"; do
		echo "  $p"
	done
fi
