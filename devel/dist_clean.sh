#!/usr/bin/env bash
# dist_clean.sh - deep clean: wipe build artifacts, tool caches, and dependency
# installs to return the repo to a distribution-clean checkout.
#
# Front door: run this directly as ./devel/dist_clean.sh. This is the deep reset,
# used when preparing the repo for distribution or forcing a clean dependency
# reinstall. The lighter everyday build clean is devel/clean_build.sh (wired to
# `npm run clean`), which leaves node_modules intact.
#
# Keeps package-lock.json: it is committed and drives reproducible `npm ci`.
#
# Universal across repo types (python, typescript, rust). Patterns that do
# not exist in a given repo are silently skipped via `nullglob` + an
# existence check, so no false-positive output.
#
# After this runs you may need to reinstall language-specific dependencies
# before the usual gates work again:
#   typescript: npm install
#   python:     pip install -r pip_requirements.txt -r pip_requirements-dev.txt
#   rust:       cargo build (recompiles dependencies on next invocation)
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

# JS dependency installs (forces clean reinstall on next npm install). Keeps
# package-lock.json, which is committed and drives reproducible npm ci.
delete_path node_modules

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
delete_find_matches PackageResolved -type f -path '*/xcshareddata/swiftpm/Package.resolved'
delete_find_matches packageBuild -type d -path './Packages/*/.build'
delete_find_matches packageSwiftpm -type d -path './Packages/*/.swiftpm'
delete_find_matches packageResolved -type f -path './Packages/*/Package.resolved'

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

# Rust build outputs.
delete_path target

if [ "${#DELETED[@]}" -eq 0 ]; then
	echo "Nothing to clean."
else
	echo "Cleaned ${#DELETED[@]} path(s):"
	for p in "${DELETED[@]}"; do
		echo "  $p"
	done
fi
