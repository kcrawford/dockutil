#!/usr/bin/env python3
"""Prepare a manual GitHub source release from a stable HEAD snapshot.

Releases are manual human decisions. This script never creates tags, never
runs git mutations, and never calls the gh CLI. It validates the working
state, builds reproducible source archives from committed HEAD, verifies the
bundled LICENSE byte-for-byte, and PRINTS the exact commands a human runs to
cut the release.

Dry-run is the default: it reports the planned commands and leaves files as
they are. Pass -w/--write to actually build the archives under output_release/.
With no --notes-file, it instead prints a copy-paste prompt for drafting
release notes with an LLM, then exits.

This module is a sibling of changelog_lib.py and commit_changelog.py in a
consumer repo's devel/ folder; it imports them by module name.
"""

# Standard Library
import os
import time
import shlex
import argparse
import tarfile
import zipfile
import subprocess

# local repo modules
import changelog_lib
import commit_changelog

# Directory (relative to repo root) that receives built release archives.
OUTPUT_DIR_NAME = "output_release"
# Committed pathspec the release LICENSE check and snapshot guarantee.
LICENSE_PATHSPEC = "LICENSE"

#============================================

def parse_args() -> argparse.Namespace:
	"""Parse command-line arguments.

	Returns:
		The parsed argparse namespace.
	"""
	parser = argparse.ArgumentParser(
		description="Prepare a manual GitHub source release from HEAD."
	)
	# Optional positional version; defaults to the VERSION file when omitted.
	parser.add_argument(
		'version', nargs='?', default=None,
		help="release version (defaults to the VERSION file)",
	)
	parser.add_argument(
		'-f', '--notes-file', dest='notes_file', default=None,
		help="path to release notes Markdown; omit to print an LLM prompt",
	)
	# Paired write/dry-run flags share a single dest, defaulting to dry-run.
	parser.add_argument(
		'-w', '--write', dest='dry_run', action='store_false',
		help="build archives and write files",
	)
	parser.add_argument(
		'-n', '--dry-run', dest='dry_run', action='store_true',
		help="report planned commands only (default)",
	)
	parser.set_defaults(dry_run=True)
	args = parser.parse_args()
	return args

#============================================

def check_calver_freshness(version: str) -> None:
	"""Confirm a version string looks like a CalVer YY.MM release.

	A malformed version raises. A well-formed version whose month differs
	from the current calendar month prints a warning but does not raise,
	since back-dated patch releases are legitimate.

	Args:
		version: The release version string to inspect.

	Raises:
		RuntimeError: When the version is not a CalVer-shaped YY.MM string.
	"""
	# Split into dotted segments and validate the leading year/month pair.
	version_parts = version.split(".")
	if len(version_parts) < 2:
		raise RuntimeError(f"Malformed CalVer version: {version!r}")
	year_part = version_parts[0]
	month_part = version_parts[1]
	if not (year_part.isdigit() and month_part.isdigit()):
		raise RuntimeError(f"Malformed CalVer version: {version!r}")
	# Compare the YY.MM prefix against the current calendar month.
	version_month = f"{year_part}.{month_part}"
	current_month = time.strftime("%y.%m")
	if version_month != current_month:
		print(
			f"WARNING: VERSION month {version_month} does not match "
			f"current month {current_month}."
		)

#============================================

def ensure_tag_free(version: str) -> None:
	"""Confirm the v{version} tag does not already exist.

	Args:
		version: The release version string.

	Raises:
		RuntimeError: When a tag named v{version} already exists.
	"""
	tag_name = f"v{version}"
	result = changelog_lib.run_git(["tag", "--list", tag_name])
	if result.returncode != 0:
		raise RuntimeError(
			f"git tag --list {tag_name!r} failed: {result.stderr.strip()}"
		)
	existing = result.stdout.strip()
	if existing == tag_name:
		raise RuntimeError(
			f"Tag {tag_name} already exists; releases are one-shot. "
			f"Bump VERSION or pass a new version."
		)

#============================================

def ensure_committed_license() -> None:
	"""Confirm a LICENSE blob exists at committed HEAD.

	The snapshot is built from HEAD, so the LICENSE must be committed (not
	merely present in the working tree) to ship inside the archives.

	Raises:
		RuntimeError: When HEAD has no committed LICENSE.
	"""
	result = changelog_lib.run_git(["cat-file", "-e", f"HEAD:{LICENSE_PATHSPEC}"])
	if result.returncode != 0:
		raise RuntimeError(
			"No committed LICENSE at HEAD. Commit a LICENSE file at the "
			"repo root before releasing so it ships inside the archives."
		)

#============================================

def warn_uncommitted_changes() -> None:
	"""Warn when tracked files have uncommitted changes.

	The snapshot captures committed HEAD, so any uncommitted tracked edits
	are silently excluded from the archives. This surfaces that gap.
	"""
	result = changelog_lib.run_git(["status", "--porcelain"])
	# Tracked changes are any porcelain line that is not an untracked "??".
	tracked_changes = []
	for line in result.stdout.splitlines():
		if line.strip() and not line.startswith("??"):
			tracked_changes.append(line)
	if tracked_changes:
		print(
			f"WARNING: {len(tracked_changes)} tracked file(s) have "
			f"uncommitted changes; the snapshot captures committed HEAD only."
		)

#============================================

def read_head_license_bytes() -> bytes:
	"""Read the raw bytes of the LICENSE blob at HEAD.

	Reads in binary mode (not changelog_lib.run_git, which is text mode) so
	the bytes compare exactly against the blob git archive stores.

	Returns:
		The raw LICENSE bytes from HEAD.

	Raises:
		RuntimeError: When the LICENSE blob cannot be read.
	"""
	result = subprocess.run(
		["git", "show", f"HEAD:{LICENSE_PATHSPEC}"],
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
	)
	if result.returncode != 0:
		raise RuntimeError("Unable to read HEAD LICENSE bytes.")
	license_bytes = result.stdout
	return license_bytes

#============================================

def compute_change_range() -> dict:
	"""Compute a best-effort change range for the release notes prompt.

	Returns:
		A dict with keys: prev_tag (str or None), prev_date (str or None),
		log_command (str). When no prior v* tag exists, prev_tag and
		prev_date are None and log_command inspects full history.
	"""
	# Most recent existing v* tag is the previous release, if any.
	result = changelog_lib.run_git(["tag", "--list", "v*", "--sort=-creatordate"])
	tags = [line.strip() for line in result.stdout.splitlines() if line.strip()]
	if tags:
		prev_tag = tags[0]
		date_result = changelog_lib.run_git(["log", "-1", "--format=%cs", prev_tag])
		prev_date = date_result.stdout.strip()
		log_command = f"git log {prev_tag}..HEAD"
	else:
		prev_tag = None
		prev_date = None
		log_command = "git log"
	change_range = {
		"prev_tag": prev_tag,
		"prev_date": prev_date,
		"log_command": log_command,
	}
	return change_range

#============================================

def build_llm_prompt(version: str, repo_name: str) -> str:
	"""Build a copy-paste LLM prompt for drafting release notes.

	Args:
		version: The release version string.
		repo_name: The repository directory name.

	Returns:
		The assembled prompt text.
	"""
	change_range = compute_change_range()
	today = time.strftime("%Y-%m-%d")
	prompt_lines = []
	prompt_lines.append(f"Draft GitHub release notes for {repo_name} v{version}.")
	prompt_lines.append(f"Release date: {today}.")
	# Describe the change window so the notes cover the right commits.
	if change_range["prev_tag"] is not None:
		prompt_lines.append(
			f"Cover changes since the previous release "
			f"{change_range['prev_tag']} (dated {change_range['prev_date']}) "
			f"through today."
		)
	else:
		prompt_lines.append(
			"This is the initial release; inspect the full repo history."
		)
	prompt_lines.append(f"Inspect the change range with: {change_range['log_command']}")
	prompt_lines.append("")
	prompt_lines.append("Audience: users and maintainers of this repository.")
	prompt_lines.append("Tone: clear, factual, present tense. Keep it concise.")
	prompt_lines.append(
		"Group changes into short Markdown sections (Added, Changed, Fixed)."
	)
	prompt_lines.append(
		"Return Markdown only, for: gh release create --notes-file <file>."
	)
	prompt = "\n".join(prompt_lines)
	return prompt

#============================================

def format_git_archive_command(archive_args: list[str]) -> str:
	"""Format a git archive argument list as a copy-paste shell command.

	Args:
		archive_args: Argument list passed to git (no leading "git").

	Returns:
		The quoted command string.
	"""
	parts = ["git"] + archive_args
	command = " ".join(shlex.quote(part) for part in parts)
	return command

#============================================

def build_archive_arg_lists(prefix: str, zip_path: str, tgz_path: str) -> dict:
	"""Build the git archive argument lists for the zip and tgz snapshots.

	Args:
		prefix: Path prefix stored inside each archive (with trailing slash).
		zip_path: Output path for the zip archive.
		tgz_path: Output path for the gzip-compressed tar archive.

	Returns:
		A dict with keys "zip" and "tgz" mapping to git argument lists.
	"""
	# --prefix nests every entry under {repo}-v{version}/ for clean extraction.
	# tar.gz is emitted directly; modern git supports the compressed format.
	zip_args = ["archive", "--format=zip", f"--prefix={prefix}", "-o", zip_path, "HEAD"]
	tgz_args = ["archive", "--format=tar.gz", f"--prefix={prefix}", "-o", tgz_path, "HEAD"]
	arg_lists = {"zip": zip_args, "tgz": tgz_args}
	return arg_lists

#============================================

def run_git_archive(archive_args: list[str]) -> None:
	"""Run a git archive command, raising on failure.

	Args:
		archive_args: Argument list passed to git (no leading "git").

	Raises:
		RuntimeError: When git archive exits non-zero.
	"""
	result = changelog_lib.run_git(archive_args)
	if result.returncode != 0:
		message = result.stderr.strip() or "git archive failed."
		raise RuntimeError(message)

#============================================

def verify_archive_license(archive_path: str, member_name: str,
		expected_bytes: bytes) -> None:
	"""Verify an archive carries a LICENSE byte-equal to HEAD.

	Args:
		archive_path: Path to the built zip or tgz archive.
		member_name: Archive member path for the LICENSE entry.
		expected_bytes: The expected LICENSE bytes from HEAD.

	Raises:
		RuntimeError: When the archived LICENSE differs from HEAD.
	"""
	# Read the LICENSE member back out of whichever archive format this is.
	if archive_path.endswith(".zip"):
		with zipfile.ZipFile(archive_path) as zip_file:
			archived_bytes = zip_file.read(member_name)
	else:
		with tarfile.open(archive_path, "r:gz") as tar_file:
			member = tar_file.extractfile(member_name)
			# extractfile returns None for non-regular members (dirs, links).
			if member is None:
				raise RuntimeError(f"No regular LICENSE member {member_name} in {archive_path}.")
			archived_bytes = member.read()
	if archived_bytes != expected_bytes:
		raise RuntimeError(
			f"LICENSE in {archive_path} does not match HEAD LICENSE."
		)

#============================================

def build_tag_command(version: str) -> str:
	"""Build the git tag command a human runs to cut the release.

	Args:
		version: The release version string.

	Returns:
		The copy-paste git tag command.
	"""
	tag_name = f"v{version}"
	command = f'git tag -a {tag_name} -m "{tag_name}"'
	return command

#============================================

def build_gh_release_command(version: str, notes_file: str, zip_path: str,
		tgz_path: str) -> str:
	"""Build the gh release create command a human runs to publish.

	Args:
		version: The release version string.
		notes_file: Path to the release notes Markdown file.
		zip_path: Path to the built zip archive.
		tgz_path: Path to the built tgz archive.

	Returns:
		The copy-paste gh release create command.
	"""
	tag_name = f"v{version}"
	command = (
		f'gh release create {tag_name} --title "{tag_name}" '
		f'--notes-file {shlex.quote(notes_file)} -- '
		f'{shlex.quote(zip_path)} {shlex.quote(tgz_path)}'
	)
	return command

#============================================
# Release-doc writers: prepend an entry to RELEASE_HISTORY.md and NEWS.md.
# Both run under --write after the archive build; dry-run reports would-be entries.

def _prepend_release_doc(repo_root: str, rel_name: str, version: str,
		notes_path: str) -> None:
	"""Prepend a release entry to a docs/ release doc, preserving older content.

	Reads the --notes-file body and inserts a ## v{version} - YYYY-MM-DD block
	immediately above the first existing ## heading, preserving all older content
	byte-for-byte. On a repeat version heading, reports the file path and
	1-based line number then raises so the caller knows to choose a new VERSION
	or edit that entry directly.

	Args:
		repo_root: Absolute path to the repository root.
		rel_name: Release doc filename under docs/ (e.g. RELEASE_HISTORY.md).
		version: The release version string.
		notes_path: Path to the release notes Markdown file.

	Raises:
		RuntimeError: When a ## v{version} heading already exists in the file.
	"""
	target_path = os.path.join(repo_root, "docs", rel_name)
	today = time.strftime("%Y-%m-%d")
	heading = f"## v{version} - {today}"
	# Read the notes body from the --notes-file the human authored.
	with open(notes_path, "r", encoding="utf-8") as notes_file:
		notes_body = notes_file.read()
	# Read the existing doc content to detect duplicates.
	with open(target_path, "r", encoding="utf-8") as doc_file:
		existing_content = doc_file.read()
	# Detect a repeat version heading; report file + 1-based line, then stop.
	version_prefix = f"## v{version} "
	for line_idx, line in enumerate(existing_content.splitlines()):
		if line.startswith(version_prefix):
			line_number = line_idx + 1
			raise RuntimeError(
				f"v{version} already has an entry in {target_path}:{line_number}. "
				f"Choose a new VERSION or edit that entry directly."
			)
	# Build the new heading block with the verbatim notes body.
	new_block = heading + "\n\n" + notes_body.rstrip("\n") + "\n\n"
	# Find the position just before the first ## heading to insert the new block.
	first_h2_pos = existing_content.find("\n## ")
	if first_h2_pos == -1:
		# No existing ## heading; append after any trailing content.
		updated_content = existing_content.rstrip("\n") + "\n\n" + new_block
	else:
		# Insert immediately before the first ## heading line, after its preceding \n.
		prefix = existing_content[:first_h2_pos + 1]
		suffix = existing_content[first_h2_pos + 1:]
		updated_content = prefix + new_block + suffix
	with open(target_path, "w", encoding="utf-8") as doc_file:
		doc_file.write(updated_content)
	print(f"Prepended {heading} to {target_path}")

#============================================

def prepend_release_history(repo_root: str, version: str, notes_path: str) -> None:
	"""Prepend a release entry to docs/RELEASE_HISTORY.md.

	Thin wrapper over _prepend_release_doc targeting RELEASE_HISTORY.md.

	Args:
		repo_root: Absolute path to the repository root.
		version: The release version string.
		notes_path: Path to the release notes Markdown file.

	Raises:
		RuntimeError: When a ## v{version} heading already exists in the file.
	"""
	_prepend_release_doc(repo_root, "RELEASE_HISTORY.md", version, notes_path)

#============================================

def prepend_news(repo_root: str, version: str, notes_path: str) -> None:
	"""Prepend a release highlight to docs/NEWS.md.

	Thin wrapper over _prepend_release_doc targeting NEWS.md.

	Args:
		repo_root: Absolute path to the repository root.
		version: The release version string.
		notes_path: Path to the release notes Markdown file.

	Raises:
		RuntimeError: When a ## v{version} heading already exists in the file.
	"""
	_prepend_release_doc(repo_root, "NEWS.md", version, notes_path)

#============================================

def ensure_release_docs_unreleased(repo_root: str, version: str) -> None:
	"""Confirm no release doc already carries a ## v{version} heading.

	Run under --write before any archive is built so a duplicate release stops
	early, leaving no zip/tgz or doc edits behind. A consumer repo may not carry
	every release doc, so absent docs are skipped. Mirrors the in-writer guard in
	_prepend_release_doc but fires before the archive build.

	Args:
		repo_root: Absolute path to the repository root.
		version: The release version string.

	Raises:
		RuntimeError: When a ## v{version} heading already exists in a release doc.
	"""
	version_prefix = f"## v{version} "
	for rel_name in ("RELEASE_HISTORY.md", "NEWS.md"):
		target_path = os.path.join(repo_root, "docs", rel_name)
		# Skip release docs the consumer repo does not ship.
		if not os.path.isfile(target_path):
			continue
		with open(target_path, "r", encoding="utf-8") as doc_file:
			existing_content = doc_file.read()
		for line_idx, line in enumerate(existing_content.splitlines()):
			if line.startswith(version_prefix):
				line_number = line_idx + 1
				raise RuntimeError(
					f"v{version} already has an entry in {target_path}:{line_number}. "
					f"Choose a new VERSION or edit that entry directly."
				)

#============================================

def main() -> None:
	"""Validate state, build or plan the snapshot, and print release commands."""
	args = parse_args()
	repo_root = changelog_lib.get_git_root()
	repo_name = os.path.basename(repo_root)

	# Resolve the version from the positional arg or the VERSION file.
	if args.version is not None:
		version = args.version
	else:
		version = commit_changelog.read_version_file()
	check_calver_freshness(version)

	# Without release notes, the job is to help the human draft them: print
	# the LLM prompt and stop before any release-prep validation or build.
	if args.notes_file is None:
		prompt = build_llm_prompt(version, repo_name)
		print(prompt)
		return

	# Validate all release preconditions up front, before writing any files.
	ensure_tag_free(version)
	ensure_committed_license()
	warn_uncommitted_changes()

	# Resolve snapshot output paths and the in-archive prefix.
	prefix = f"{repo_name}-v{version}/"
	output_dir = os.path.join(repo_root, OUTPUT_DIR_NAME)
	zip_path = os.path.join(output_dir, f"{repo_name}-v{version}.zip")
	tgz_path = os.path.join(output_dir, f"{repo_name}-v{version}.tgz")
	arg_lists = build_archive_arg_lists(prefix, zip_path, tgz_path)
	license_member = f"{prefix}{LICENSE_PATHSPEC}"

	if args.dry_run:
		# Dry-run: report the planned build commands, build nothing.
		print("Planned snapshot build (dry-run; pass -w/--write to build):")
		print("  " + format_git_archive_command(arg_lists["zip"]))
		print("  " + format_git_archive_command(arg_lists["tgz"]))
		# Report the would-be doc writer entries without writing.
		today = time.strftime("%Y-%m-%d")
		rh_path = os.path.join(repo_root, "docs", "RELEASE_HISTORY.md")
		news_path = os.path.join(repo_root, "docs", "NEWS.md")
		print(f"Would prepend ## v{version} - {today} to {rh_path}")
		print(f"Would prepend ## v{version} - {today} to {news_path}")
	else:
		# Precheck duplicate release headings up front, before building anything,
		# so a re-run at an already-released version leaves no archives or doc edits.
		ensure_release_docs_unreleased(repo_root, version)
		# Write: build the archives, then verify each bundled LICENSE.
		os.makedirs(output_dir, exist_ok=True)
		run_git_archive(arg_lists["zip"])
		run_git_archive(arg_lists["tgz"])
		expected_license = read_head_license_bytes()
		verify_archive_license(zip_path, license_member, expected_license)
		verify_archive_license(tgz_path, license_member, expected_license)
		print(f"Built and verified: {zip_path}")
		print(f"Built and verified: {tgz_path}")
		# Write the release-doc entries under --write.
		prepend_release_history(repo_root, version, args.notes_file)
		prepend_news(repo_root, version, args.notes_file)

	# Print the exact commands the human runs to cut the release.
	print("")
	print("Run these to cut the release:")
	print("  " + build_tag_command(version))
	print("  " + build_gh_release_command(version, args.notes_file, zip_path, tgz_path))

#============================================

if __name__ == '__main__':
	main()
