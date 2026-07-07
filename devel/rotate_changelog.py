#!/usr/bin/env python3
"""Rotate docs/CHANGELOG.md per docs/REPO_STYLE.md changelog rotation rules.

Reads the active changelog, keeps the two most recent day blocks in place, and
moves older day blocks into docs/CHANGELOG-YYYY-MM[a-z].md. Never invokes git;
the human stages and commits the resulting files.
"""

# Standard Library
import os
import re
import glob
import argparse

# local repo modules
import changelog_lib

THRESHOLD_DEFAULT = 1000
CHANGELOG_PATH = "docs/CHANGELOG.md"
ARCHIVE_GLOB = "docs/CHANGELOG-*.md"
ARCHIVE_NAME_RE = re.compile(r"^CHANGELOG-(\d{4}-\d{2})([a-z])\.md$")

#============================================

def split_active_archive(
		blocks: list[changelog_lib.DayBlock],
		) -> tuple[list[changelog_lib.DayBlock], list[changelog_lib.DayBlock]]:
	"""Split blocks into active (first two) and archive (the rest)."""
	active = blocks[:2]
	archive = blocks[2:]
	return active, archive

#============================================

def compute_archive_path(
		archive_blocks: list[changelog_lib.DayBlock],
		docs_dir: str,
		) -> str:
	"""Compute the next-unused archive path for the archive set.

	Naming follows REPO_STYLE.md: name the archive after the most recent
	month included in the range (the YYYY-MM of the first/newest date in
	the archive set). Letter suffix starts at 'a' and increments to the
	first unused letter when prior archives for the same YYYY-MM exist.

	Args:
		archive_blocks: Non-empty list of DayBlock records being archived.
		docs_dir: Path to the docs directory to scan for existing archives.

	Returns:
		Absolute or relative path to the chosen archive filename.
	"""
	if not archive_blocks:
		raise RuntimeError("compute_archive_path called with empty archive set.")
	newest_archive_date = archive_blocks[0].date
	yyyy_mm = newest_archive_date[:7]

	# scan existing archives in docs_dir, find used letter suffixes for this YYYY-MM
	used_letters: set[str] = set()
	pattern = os.path.join(docs_dir, "CHANGELOG-*.md")
	for existing in glob.glob(pattern):
		base = os.path.basename(existing)
		match = ARCHIVE_NAME_RE.match(base)
		if not match:
			continue
		if match.group(1) != yyyy_mm:
			continue
		used_letters.add(match.group(2))

	# pick the first unused letter starting at 'a'
	for code in range(ord("a"), ord("z") + 1):
		letter = chr(code)
		if letter not in used_letters:
			chosen = letter
			break
	else:
		raise RuntimeError(f"All archive letters a-z used for {yyyy_mm}.")

	archive_name = f"CHANGELOG-{yyyy_mm}{chosen}.md"
	archive_path = os.path.join(docs_dir, archive_name)
	return archive_path

#============================================

def find_boundary_conflict(
		active_blocks: list[changelog_lib.DayBlock],
		docs_dir: str,
		) -> tuple[str, str] | None:
	"""Detect a boundary-date conflict against existing archives.

	Per REPO_STYLE.md, a date heading appears in exactly one file. If the
	oldest active-set heading already lives in an existing archive, that
	date must be dropped from the active set rather than copied.

	Args:
		active_blocks: The active block list (first two day blocks).
		docs_dir: Docs directory to scan for archives.

	Returns:
		(date, archive_path) when a conflict is found; None otherwise.
	"""
	if len(active_blocks) < 1:
		return None
	# oldest active heading is the last block in the active set
	oldest_active_date = active_blocks[-1].date
	pattern = os.path.join(docs_dir, "CHANGELOG-*.md")
	for existing in sorted(glob.glob(pattern)):
		base = os.path.basename(existing)
		if not ARCHIVE_NAME_RE.match(base):
			continue
		# skip files that exist as a glob match but are not actually present
		if not os.path.isfile(existing):
			continue
		archive_text = changelog_lib.read_changelog(existing)
		# duplicate-warn policy here is fine: we only inspect the newest date
		_pre, archive_blocks, _warnings = changelog_lib.parse_day_blocks(
			archive_text, source=existing,
		)
		newest_in_existing = changelog_lib.newest_date(archive_blocks)
		if newest_in_existing == oldest_active_date:
			return (oldest_active_date, existing)
	return None

#============================================

def print_loud_warning(date_str: str, archive_path: str) -> None:
	"""Print a bold-red warning about a boundary-date conflict."""
	banner = "!" * 60
	changelog_lib.ERR_CONSOLE.print(banner, style="bold red")
	changelog_lib.ERR_CONSOLE.print(
		f"BOUNDARY-DATE CONFLICT: date {date_str} already exists in {archive_path}.",
		style="bold red",
	)
	changelog_lib.ERR_CONSOLE.print(
		"REPO_STYLE.md requires each date heading to appear in exactly one file.",
		style="bold red",
	)
	changelog_lib.ERR_CONSOLE.print(
		f"This rotation would DROP the {date_str} block from {CHANGELOG_PATH}.",
		style="bold red",
	)
	changelog_lib.ERR_CONSOLE.print(banner, style="bold red")

#============================================

def print_duplicate_error(dups: list[str]) -> None:
	"""Print a bold-red error listing duplicate dates in the active file."""
	banner = "!" * 60
	changelog_lib.ERR_CONSOLE.print(banner, style="bold red")
	changelog_lib.ERR_CONSOLE.print(
		f"DUPLICATE DATE HEADINGS in {CHANGELOG_PATH}:",
		style="bold red",
	)
	for date_str in dups:
		changelog_lib.ERR_CONSOLE.print(f"  - duplicate date: {date_str}", style="bold red")
	changelog_lib.ERR_CONSOLE.print(
		"Rotation refuses to operate on a duplicate-date active file; "
		"writing back could lose data. Fix the duplicates and retry.",
		style="bold red",
	)
	changelog_lib.ERR_CONSOLE.print(banner, style="bold red")

#============================================

def print_plan(
		line_count: int,
		threshold: int,
		archive_path: str,
		active_blocks: list[changelog_lib.DayBlock],
		archive_blocks: list[changelog_lib.DayBlock],
		) -> None:
	"""Print a plan summary describing what the rotation will do."""
	changelog_lib.CONSOLE.print(f"Active file: {CHANGELOG_PATH} ({line_count} lines)", style="bold")
	changelog_lib.CONSOLE.print(f"Threshold: {threshold} lines")
	changelog_lib.CONSOLE.print(f"Archive path (new): {archive_path}", style="bold")
	active_dates = ", ".join(b.date for b in active_blocks) if active_blocks else "(none)"
	changelog_lib.CONSOLE.print(f"Active blocks kept: {active_dates}")
	archive_dates = ", ".join(b.date for b in archive_blocks) if archive_blocks else "(none)"
	changelog_lib.CONSOLE.print(f"Archive blocks moved: {archive_dates}")

#============================================

def parse_args() -> argparse.Namespace:
	"""Parse command-line arguments."""
	parser = argparse.ArgumentParser(
		description=(
			"Rotate docs/CHANGELOG.md per REPO_STYLE.md: keep the two most "
			"recent day blocks in place, move older ones into "
			"docs/CHANGELOG-YYYY-MM[a-z].md."
		),
	)
	parser.add_argument(
		"-n", "--dry-run", dest="dry_run",
		action="store_true",
		help="Print the rotation plan without writing any files.",
	)
	parser.add_argument(
		"-f", "--force", dest="force",
		action="store_true",
		help="Rotate regardless of the line-count threshold.",
	)
	parser.add_argument(
		"-t", "--threshold", dest="threshold",
		type=int,
		help=f"Override the default trigger threshold (default {THRESHOLD_DEFAULT} lines).",
	)
	parser.add_argument(
		"-y", "--yes", dest="yes",
		action="store_true",
		help="Skip the interactive y/N confirmation.",
	)
	parser.set_defaults(
		dry_run=False,
		force=False,
		threshold=THRESHOLD_DEFAULT,
		yes=False,
	)
	args = parser.parse_args()
	return args

#============================================

def main() -> None:
	"""Orchestrate the rotation."""
	args = parse_args()

	changelog_lib.ensure_in_git_repo()
	repo_root = changelog_lib.get_git_root()
	os.chdir(repo_root)

	if not os.path.isfile(CHANGELOG_PATH):
		raise RuntimeError(f"{CHANGELOG_PATH} not found at repo root.")

	text = changelog_lib.read_changelog(CHANGELOG_PATH)
	line_count = text.count("\n")
	if not text.endswith("\n") and text:
		# count the trailing partial line too
		line_count += 1
	threshold = args.threshold

	if line_count < threshold and not args.force:
		changelog_lib.CONSOLE.print(
			f"Below threshold ({line_count} / {threshold} lines). Nothing to do.",
			style="yellow",
		)
		return

	# preflight: parse with 'keep' so duplicates survive into the block list
	# and find_duplicate_dates can actually see them
	_pre_keep, all_blocks, _warn_keep = changelog_lib.parse_day_blocks(
		text, source=CHANGELOG_PATH, duplicate_policy="keep",
	)
	dups = changelog_lib.find_duplicate_dates(all_blocks)
	if dups:
		print_duplicate_error(dups)
		raise SystemExit(2)

	# re-parse with default 'warn' policy to get the deduped block list
	# and any parser warnings for presentation
	preamble, blocks, warnings = changelog_lib.parse_day_blocks(
		text, source=CHANGELOG_PATH,
	)
	# surface parser warnings to stderr before any rotation work
	for warning in warnings:
		changelog_lib.ERR_CONSOLE.print(warning, style="yellow")

	if len(blocks) <= 2:
		changelog_lib.CONSOLE.print("Only two day blocks; cannot rotate.", style="yellow")
		return

	active_blocks, archive_blocks = split_active_archive(blocks)
	if not archive_blocks:
		changelog_lib.CONSOLE.print("Only two day blocks; cannot rotate.", style="yellow")
		return

	docs_dir = os.path.dirname(CHANGELOG_PATH)
	archive_path = compute_archive_path(archive_blocks, docs_dir)

	# Boundary-date guard: the oldest active-set heading must not already
	# live in an existing archive. If it does, drop it from the active set.
	boundary_conflict = find_boundary_conflict(active_blocks, docs_dir)
	dropped_date: str | None = None
	if boundary_conflict is not None:
		dropped_date, conflicting_archive = boundary_conflict
		print_loud_warning(dropped_date, conflicting_archive)
		if args.dry_run:
			changelog_lib.CONSOLE.print(
				f"Dry run: would drop {dropped_date} from {CHANGELOG_PATH} "
				f"(already archived in {conflicting_archive}). No files written.",
				style="bold yellow",
			)
			return
		if not args.yes:
			changelog_lib.ERR_CONSOLE.print(
				"Refusing to drop a boundary date without explicit --yes. Aborting.",
				style="bold red",
			)
			raise SystemExit(2)
		# drop the boundary date from the active set
		active_blocks = active_blocks[:-1]

	print_plan(line_count, threshold, archive_path, active_blocks, archive_blocks)

	if args.dry_run:
		changelog_lib.CONSOLE.print("Dry run: no files written.", style="yellow")
		return

	if not args.yes:
		if not changelog_lib.confirm("Rotate?"):
			changelog_lib.CONSOLE.print("Aborted.", style="yellow")
			return

	# write archive first, then rewrite the active file
	changelog_lib.write_changelog(archive_path, "", archive_blocks)
	changelog_lib.write_changelog(CHANGELOG_PATH, preamble, active_blocks)

	changelog_lib.CONSOLE.print(
		f"Rotated: wrote {archive_path} and rewrote {CHANGELOG_PATH}.",
		style="bold green",
	)
	moved_dates = ", ".join(b.date for b in archive_blocks)
	changelog_lib.CONSOLE.print(f"Dates moved: {moved_dates}")
	if dropped_date is not None:
		changelog_lib.CONSOLE.print(
			f"Dropped boundary date {dropped_date} from the active file.",
			style="bold yellow",
		)
	changelog_lib.CONSOLE.print(
		"Reminder: add a rotation entry to docs/CHANGELOG.md per AGENTS.md.",
		style="yellow",
	)

#============================================

if __name__ == "__main__":
	main()
