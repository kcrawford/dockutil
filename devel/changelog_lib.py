"""Shared helpers for changelog-oriented developer scripts.

Originally a parser/serializer-only library; expanded by user decision
to absorb the small helper trios (git invocation, console + prompt
primitives) that the three changelog scripts -- devel/commit_changelog.py,
devel/rotate_changelog.py, devel/query_changelog.py -- would otherwise
duplicate. Consolidation into one sibling module is preferred over a
separate git_helpers.py / console_helpers.py to keep moving parts low.

Sections, in order:

- ``# Changelog parsing and serialization`` -- DayBlock / Entry
  dataclasses, regex constants, ``read_changelog`` / ``write_changelog``,
  ``parse_day_blocks`` / ``split_day_block`` / ``parse_file``,
  ``newest_date`` / ``find_duplicate_dates``.
- ``# Git helpers`` -- ``run_git`` / ``get_git_root`` /
  ``ensure_in_git_repo``.
- ``# Console and prompt helpers`` -- ``build_choice_prompt`` /
  ``confirm`` / ``print_warning`` / ``print_error`` plus the
  module-level ``CONSOLE`` and ``ERR_CONSOLE`` rich consoles they
  print through.

Out of scope (stays in calling scripts): CLI argument parsing,
query-side filtering, and script-specific business logic. Library
parsers return warnings as ``list[str]``, never printed; the caller
controls presentation.

This is a library module: no shebang, no executable bit, no
``if __name__ == '__main__'`` guard.
"""

# Standard Library
import os
import re
import dataclasses
import subprocess

# PIP3 modules
import rich.console

#============================================
#============================================
# Changelog parsing and serialization
#============================================
#============================================

#============================================
# Module constants

# DATE_RE matches structurally well-formed YYYY-MM-DD headings only;
# calendrical validation (e.g. 2026-13-99) is performed in
# parse_day_blocks via datetime.date.fromisoformat().
DATE_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")
CATEGORY_RE = re.compile(r"^###\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^-\s+(.*)$")

CANONICAL_CATEGORIES = [
	"Additions and New Features",
	"Behavior or Interface Changes",
	"Fixes and Maintenance",
	"Removals and Deprecations",
	"Decisions and Failures",
	"Developer Tests and Notes",
]

#============================================
# Dataclasses

@dataclasses.dataclass
class DayBlock:
	"""One ``## YYYY-MM-DD`` day block from a changelog file.

	Attributes:
		date: ISO date string in YYYY-MM-DD form. Calendrically valid
			(passes ``datetime.date.fromisoformat``).
		raw_text: The verbatim slice of the source file, including the
			``## YYYY-MM-DD`` heading line and any trailing newlines
			up to (but not including) the next accepted day heading.
		source: File path the block came from. ``"<unknown>"`` when the
			caller did not supply a source path.
		lineno: 1-based line number of the ``## YYYY-MM-DD`` heading in
			``source``.
		lead_text: Concatenation of non-blank, non-bullet, non-heading
			lines that appear AFTER the ``## YYYY-MM-DD`` heading and
			BEFORE the first ``### Category`` heading or first ``- ``
			bullet. Captures author-attribution lines such as
			``Neil Voss <vossman77@yahoo.com>`` or ``OpenAI Codex``
			that would otherwise be silently dropped by entry-view
			consumers. Empty string when no such line exists. NOT the
			same as the file-level "preamble" returned by
			``parse_day_blocks``, which is text BEFORE the first day
			block.
	"""
	date: str
	raw_text: str
	source: str
	lineno: int
	lead_text: str = ""

#============================================

@dataclasses.dataclass
class Entry:
	"""A single bullet inside a day block.

	Attributes:
		date: ISO date string of the parent day block.
		source: File path of the parent day block.
		category: The ``### Category`` heading the bullet sits under, or
			``"Uncategorized"`` when the bullet appears before any
			category heading.
		title: First line of the bullet, with the leading ``- `` removed
			and trailing whitespace stripped.
		body: Continuation lines joined with ``"\n"``, trailing
			whitespace stripped. Empty string when the bullet is a
			single line.
		text: ``f"{title}. {body}"`` when ``body`` is non-empty,
			otherwise just ``title``. This is the value keyword search
			hits.
		lineno: 1-based line number of the bullet's ``- `` line in
			``source``.
	"""
	date: str
	source: str
	category: str
	title: str
	body: str
	text: str
	lineno: int

#============================================
# File I/O

def read_changelog(path: str) -> str:
	"""Return the full text of a changelog file.

	Args:
		path: Path to the file to read.

	Returns:
		The file contents as a single string.

	Raises:
		FileNotFoundError: When ``path`` does not exist. The caller
			decides whether a missing file is fatal.
	"""
	# open in text mode with explicit utf-8 encoding for cross-platform consistency
	with open(path, "r", encoding="utf-8") as handle:
		text = handle.read()
	return text

#============================================

def write_changelog(path: str, preamble: str, blocks: list) -> None:
	"""Write a changelog file from a preamble and a list of day blocks.

	The day-block ``raw_text`` is preserved byte-for-byte. The final
	file ending is normalized to exactly one trailing newline: zero
	newlines become one; two or more become one; one is left alone.
	No other rewriting is performed.

	Args:
		path: Destination file path.
		preamble: Verbatim text written before the first day block.
		blocks: Ordered list of ``DayBlock`` records whose
			``raw_text`` is written in order.
	"""
	# assemble verbatim: preamble first, then each block's raw text in order
	parts = [preamble]
	for block in blocks:
		parts.append(block.raw_text)
	assembled = "".join(parts)

	# normalize file ending to exactly one trailing newline
	# strip every trailing newline, then add exactly one back
	trimmed = assembled.rstrip("\n")
	normalized = trimmed + "\n"

	# ensure the parent directory exists in case the caller did not pre-create it
	parent = os.path.dirname(path)
	if parent:
		os.makedirs(parent, exist_ok=True)

	with open(path, "w", encoding="utf-8") as handle:
		handle.write(normalized)

#============================================
# Parsing

def _is_valid_iso_date(date_str: str) -> bool:
	"""Return True if ``date_str`` is a calendrically valid YYYY-MM-DD.

	Rejects impossible dates such as ``2026-13-99``. Avoids try/except
	per the repo style guide by validating shape and calendar ranges
	manually.
	"""
	# regex-matched dates are shape-valid YYYY-MM-DD; the only remaining
	# failure mode is calendrical (e.g. month or day out of range).
	# Re-implement the calendar check inline to comply with the
	# no-try/except rule.
	parts = date_str.split("-")
	if len(parts) != 3:
		return False
	year_str, month_str, day_str = parts
	if not (year_str.isdigit() and month_str.isdigit() and day_str.isdigit()):
		return False
	year = int(year_str)
	month = int(month_str)
	day = int(day_str)
	if month < 1 or month > 12:
		return False
	if day < 1 or day > 31:
		return False
	# walk a hardcoded month-length table (with leap-year adjustment for
	# February) so no exception-raising constructor is needed.
	month_lengths = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
	# leap-year adjustment for February
	if month == 2:
		is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
		max_day = 29 if is_leap else 28
	else:
		max_day = month_lengths[month - 1]
	if day > max_day:
		return False
	return True

#============================================

def parse_day_blocks(text: str, source: str = "<unknown>",
		duplicate_policy: str = "warn"
		) -> tuple:
	"""Parse changelog text into a preamble and a list of day blocks.

	A day block runs from a ``## YYYY-MM-DD`` heading up to (but not
	including) the next ``## YYYY-MM-DD`` heading or end of file.
	The ``raw_text`` field on each ``DayBlock`` preserves the source
	bytes verbatim, including all trailing newlines.

	Tolerance:

	- A ``## YYYY-MM-DD`` heading that matches ``DATE_RE`` but whose
	  date is calendrically invalid (rejected by
	  ``datetime.date.fromisoformat``) causes the entire block under
	  that heading to be skipped. A warning of the form
	  ``"{source}:{lineno}: invalid date '{date_str}', skipping block"``
	  is appended. A leading bad-date block is folded into the preamble
	  of the first accepted block, because the preamble is defined as
	  "everything before the first accepted heading".
	- ``duplicate_policy='warn'`` (default) keeps the first occurrence
	  of any date and emits a warning of the form
	  ``"{source}:{lineno}: duplicate date '{date_str}', skipping block"``
	  for each later duplicate.
	- ``duplicate_policy='raise'`` raises ``ValueError`` on the first
	  duplicate, naming the date and the duplicate heading lineno.
	- ``duplicate_policy='keep'`` retains every accepted block, including
	  duplicates, without emitting warnings. Suitable for callers that
	  want to detect duplicates themselves via ``find_duplicate_dates``.

	Args:
		text: Full changelog file contents.
		source: File path used in warning messages and on each
			resulting ``DayBlock.source``. Defaults to ``"<unknown>"``.
		duplicate_policy: ``"warn"``, ``"raise"``, or ``"keep"``.

	Returns:
		A tuple ``(preamble, blocks, warnings)`` where ``preamble`` is
		a string, ``blocks`` is a list of ``DayBlock`` records, and
		``warnings`` is a list of warning strings.

	Raises:
		ValueError: When ``duplicate_policy='raise'`` and a duplicate
			date is encountered.
	"""
	# validate the policy argument at the function boundary; this is input
	# validation, not exception-handling business logic
	if duplicate_policy not in ("warn", "raise", "keep"):
		raise ValueError("duplicate_policy must be 'warn', 'raise', or 'keep'")
	warnings: list = []
	# split with keepends so each line carries its own newline character;
	# joining preserves the original file bytes
	lines = text.splitlines(keepends=True)

	# first pass: find heading positions so we can carve raw_text slices
	# each entry: (lineno_1based, date_str, is_valid_iso)
	heading_positions: list = []
	for index, line in enumerate(lines):
		match = DATE_RE.match(line)
		if not match:
			continue
		date_str = match.group(1)
		lineno = index + 1
		is_valid = _is_valid_iso_date(date_str)
		heading_positions.append((lineno, date_str, is_valid, index))

	# if no headings at all, the entire file is preamble
	if not heading_positions:
		preamble = "".join(lines)
		return (preamble, [], warnings)

	# find the line_index of the first accepted (valid-date) heading; the
	# preamble spans every line before that heading
	first_accepted_index = None
	for pos in heading_positions:
		hp_lineno, hp_date, hp_valid, hp_line_index = pos
		if hp_valid:
			first_accepted_index = hp_line_index
			break

	if first_accepted_index is None:
		# no accepted headings at all: every heading is bad-date; whole file is preamble
		preamble = "".join(lines)
		# emit a warning for each bad heading
		for bad_pos in heading_positions:
			bad_lineno, bad_date_str, bad_valid, bad_line_index = bad_pos
			warning = f"{source}:{bad_lineno}: invalid date '{bad_date_str}', skipping block"
			warnings.append(warning)
		return (preamble, [], warnings)

	preamble = "".join(lines[:first_accepted_index])

	# build blocks, walking heading positions and slicing raw_text up to the
	# next heading (good or bad)
	blocks: list = []
	seen_dates: dict = {}
	# precompute total line count for the trailing-slice case
	total = len(lines)
	for hp_idx, pos in enumerate(heading_positions):
		lineno, date_str, is_valid, line_index = pos
		# end of slice: next heading's line_index, or total
		if hp_idx + 1 < len(heading_positions):
			end_index = heading_positions[hp_idx + 1][3]
		else:
			end_index = total
		# skip headings whose date is before the first accepted heading;
		# their text already lives in the preamble
		if line_index < first_accepted_index:
			# emit a warning for the bad-date heading (the text is in preamble)
			warning = f"{source}:{lineno}: invalid date '{date_str}', skipping block"
			warnings.append(warning)
			continue
		if not is_valid:
			# bad-date block in the middle or end: discard the slice entirely
			warning = f"{source}:{lineno}: invalid date '{date_str}', skipping block"
			warnings.append(warning)
			continue
		# duplicate detection on accepted (valid-date) headings only
		if date_str in seen_dates:
			if duplicate_policy == "raise":
				raise ValueError(
					f"duplicate date '{date_str}' at {source}:{lineno} "
					f"(first seen at line {seen_dates[date_str]})"
				)
			if duplicate_policy == "warn":
				# warn policy: append warning and skip this block
				warning = f"{source}:{lineno}: duplicate date '{date_str}', skipping block"
				warnings.append(warning)
				continue
			# keep policy: fall through and append the duplicate block
		else:
			seen_dates[date_str] = lineno
		raw_text = "".join(lines[line_index:end_index])
		# compute lead_text: non-blank, non-bullet, non-heading lines between
		# the ## heading (lines[line_index]) and the first ### or - line. This
		# captures author-attribution day-block annotations that would
		# otherwise be silently dropped by entry-view consumers.
		lead_text_parts: list = []
		for scan_idx in range(line_index + 1, end_index):
			scan_line = lines[scan_idx]
			if BULLET_RE.match(scan_line) or CATEGORY_RE.match(scan_line):
				break
			if DATE_RE.match(scan_line):
				break
			scan_stripped = scan_line.strip()
			if scan_stripped:
				lead_text_parts.append(scan_stripped)
		lead_text = "\n".join(lead_text_parts)
		if lead_text:
			# excerpt: first line only, truncated, for the warning preview
			first_line = lead_text.split("\n", 1)[0]
			excerpt = first_line if len(first_line) <= 80 else first_line[:77] + "..."
			warning = (
				f"{source}:{lineno}: lead text under day heading: "
				f"{excerpt}"
			)
			warnings.append(warning)
		block = DayBlock(
			date=date_str, raw_text=raw_text, source=source, lineno=lineno,
			lead_text=lead_text,
		)
		blocks.append(block)

	return (preamble, blocks, warnings)

#============================================

def split_day_block(block: DayBlock, strict: bool = False) -> tuple:
	"""Split one ``DayBlock`` into ``Entry`` records.

	Walks the block's raw text and emits one ``Entry`` per ``- ``
	bullet. Bullets are grouped by the most recent ``### Category``
	heading; bullets that appear before any category heading are
	classified ``"Uncategorized"``.

	Two warning shapes are emitted, at most one per block:

	- ``LEGACY_FLAT`` -- ``"legacy flat block (no category heading)"``
	  fires once when the block contains zero ``### Category`` headings
	  AND at least one bullet. ``parse_file`` post-processes these into
	  a single per-file summary line.
	- ``ORPHAN_BULLETS`` -- ``"orphan bullets before first category
	  heading"`` fires once when the block has at least one ``###``
	  heading but a bullet appears before the first one. Per-block
	  actionable; never collapsed.

	The third warning shape (``"lead text under day heading"``) is
	emitted by ``parse_day_blocks`` when it captures ``DayBlock.lead_text``;
	this function does not emit it.

	Bullet body collection rule: a bullet starts at a line matching
	``BULLET_RE``. Continuation lines belong to the bullet if they
	are indented (start with whitespace) or blank. A new bullet
	(``- `` at column 0), a new ``### `` heading, or a new ``## ``
	heading ends the current bullet.

	Args:
		block: The ``DayBlock`` to split.
		strict: When True, emit a warning for any category heading
			that is not in ``CANONICAL_CATEGORIES``.

	Returns:
		A tuple ``(entries, warnings)`` where ``entries`` is a list
		of ``Entry`` records (in source order) and ``warnings`` is a
		list of warning strings.
	"""
	warnings: list = []
	entries: list = []

	# split into lines without keepends; we are emitting structured data, not bytes
	raw_lines = block.raw_text.splitlines()

	# pre-scan: count categories and find first-category vs first-bullet positions
	# so we can decide which uncategorized warning shape (if any) to emit
	pre_first_cat_idx = None
	pre_first_bullet_idx = None
	pre_cat_count = 0
	for pre_idx, pre_line in enumerate(raw_lines):
		if pre_idx == 0 and DATE_RE.match(pre_line):
			continue
		if CATEGORY_RE.match(pre_line):
			pre_cat_count += 1
			if pre_first_cat_idx is None:
				pre_first_cat_idx = pre_idx
		elif BULLET_RE.match(pre_line):
			if pre_first_bullet_idx is None:
				pre_first_bullet_idx = pre_idx

	# state machine: current_category, current_bullet
	current_category: str | None = None
	bullet_title: str | None = None
	bullet_body_lines: list = []
	bullet_lineno: int = 0
	uncategorized_warned = False

	# the block's ## heading is raw_lines[0]; bullets and ### headings begin at
	# raw_lines[1]; file lineno for raw_lines[offset] is block.lineno + offset
	def flush_bullet(title: str | None, body_lines: list, lineno: int) -> None:
		"""Build and append an Entry from the bullet state. Returns nothing."""
		if title is None:
			return
		# strip trailing whitespace on the joined body, preserve internal whitespace
		body_joined = "\n".join(body_lines)
		body = body_joined.rstrip()
		if body:
			text = f"{title}. {body}"
		else:
			text = title
		entry = Entry(
			date=block.date,
			source=block.source,
			category=current_category if current_category is not None else "Uncategorized",
			title=title,
			body=body,
			text=text,
			lineno=lineno,
		)
		entries.append(entry)

	for offset, line in enumerate(raw_lines):
		file_lineno = block.lineno + offset

		# the ## heading itself is skipped from entry collection
		if offset == 0 and DATE_RE.match(line):
			continue

		cat_match = CATEGORY_RE.match(line)
		if cat_match:
			# flush any pending bullet before switching category
			flush_bullet(bullet_title, bullet_body_lines, bullet_lineno)
			bullet_title = None
			bullet_body_lines = []
			heading = cat_match.group(1).strip()
			current_category = heading
			if strict and heading not in CANONICAL_CATEGORIES:
				warnings.append(
					f"{block.source}:{file_lineno}: non-canonical category '{heading}'"
				)
			continue

		bullet_match = BULLET_RE.match(line)
		if bullet_match:
			# flush previous bullet
			flush_bullet(bullet_title, bullet_body_lines, bullet_lineno)
			bullet_title = bullet_match.group(1).rstrip()
			bullet_body_lines = []
			bullet_lineno = file_lineno
			# emit a single per-block uncategorized warning at the first such bullet.
			# warning text depends on whether ANY ### Category exists in the block:
			#   - zero categories -> LEGACY_FLAT (collapsed per-file by parse_file)
			#   - at least one category -> ORPHAN_BULLETS (per-block actionable)
			if current_category is None and not uncategorized_warned:
				uncategorized_warned = True
				if pre_cat_count == 0:
					warnings.append(
						f"{block.source}:{block.lineno}: "
						f"legacy flat block (no category heading)"
					)
				else:
					warnings.append(
						f"{block.source}:{block.lineno}: "
						f"orphan bullets before first category heading"
					)
			continue

		# continuation candidate for the current bullet
		if bullet_title is None:
			# nothing to attach to; skip
			continue

		# blank line: soft separator inside the bullet body
		stripped = line.strip()
		if stripped == "":
			bullet_body_lines.append("")
			continue

		# indented continuation: append the stripped form
		if line.startswith(" ") or line.startswith("\t"):
			bullet_body_lines.append(stripped)
			continue

		# non-indented, non-bullet, non-heading content terminates the bullet
		flush_bullet(bullet_title, bullet_body_lines, bullet_lineno)
		bullet_title = None
		bullet_body_lines = []

	# flush a trailing bullet at end of block
	flush_bullet(bullet_title, bullet_body_lines, bullet_lineno)
	return (entries, warnings)

#============================================
# Convenience

def parse_text(text: str, source: str = "<unknown>", strict: bool = False,
		duplicate_policy: str = "warn") -> tuple:
	"""Parse and split a changelog from an in-memory string.

	Same return shape as ``parse_file``. Use this when the source text
	comes from somewhere other than a filesystem path (for example
	``git show <sha>:docs/CHANGELOG.md`` output).

	Args:
		text: Full changelog file contents.
		source: Label used in warning messages and on each resulting
			record. Defaults to ``"<unknown>"``.
		strict: Passed to ``split_day_block``.
		duplicate_policy: Passed to ``parse_day_blocks``.

	Returns:
		A tuple ``(blocks, entries, warnings)``. ``warnings`` is the
		concatenation of the parse-time warnings and every block's
		split-time warnings. Legacy-flat per-block warnings are
		collapsed into a single per-source summary line.

	Raises:
		ValueError: Passthrough from ``parse_day_blocks`` when
			``duplicate_policy='raise'`` and a duplicate
			``## YYYY-MM-DD`` heading is encountered.
	"""
	_preamble, blocks, parse_warnings = parse_day_blocks(
		text, source=source, duplicate_policy=duplicate_policy,
	)
	entries: list = []
	split_warnings: list = []
	for block in blocks:
		block_entries, block_warnings = split_day_block(block, strict=strict)
		entries.extend(block_entries)
		split_warnings.extend(block_warnings)
	# collapse per-block LEGACY_FLAT warnings into one per-file summary line.
	# the dominant corpus shape (94%+ of the old "bullets before any category"
	# warnings) is legacy flat changelogs; surfacing one summary per file keeps
	# signal-to-noise reasonable. Other warning shapes survive untouched.
	legacy_marker = "legacy flat block (no category heading)"
	non_legacy = [w for w in split_warnings if legacy_marker not in w]
	legacy_count = len(split_warnings) - len(non_legacy)
	combined_warnings = parse_warnings + non_legacy
	if legacy_count > 0:
		combined_warnings.append(
			f"{source}: legacy flat changelog: {legacy_count} day blocks have "
			f"bullets with no category heading (treated as Uncategorized)"
		)
	return (blocks, entries, combined_warnings)

#============================================

def parse_file(path: str, strict: bool = False,
		duplicate_policy: str = "warn") -> tuple:
	"""Read, parse, and split a changelog file in a single call.

	Thin wrapper around ``parse_text``: reads ``path``, then delegates.

	Args:
		path: Path to the changelog file.
		strict: Passed to ``split_day_block``.
		duplicate_policy: Passed to ``parse_day_blocks``.

	Returns:
		A tuple ``(blocks, entries, warnings)``. ``warnings`` is the
		concatenation of the parse-time warnings and every block's
		split-time warnings.

	Raises:
		FileNotFoundError: When ``path`` does not exist.
		ValueError: Passthrough from ``parse_day_blocks`` when
			``duplicate_policy='raise'`` and a duplicate
			``## YYYY-MM-DD`` heading is encountered.
	"""
	text = read_changelog(path)
	return parse_text(text, source=path, strict=strict,
		duplicate_policy=duplicate_policy)

#============================================

def newest_date(blocks: list) -> str | None:
	"""Return the date of the first day block, or ``None`` if empty.

	This is a pure inspector: it does not read any file. The caller
	composes ``read_changelog`` + ``parse_day_blocks`` + ``newest_date``
	when archive boundary detection is needed.

	Args:
		blocks: List of ``DayBlock`` records, typically the second
			element of a ``parse_day_blocks`` return tuple.

	Returns:
		The date string of ``blocks[0]`` when ``blocks`` is non-empty,
		otherwise ``None``.
	"""
	if not blocks:
		return None
	first = blocks[0]
	return first.date

#============================================

def find_duplicate_dates(blocks: list) -> list:
	"""Return dates that appear two or more times in ``blocks``.

	The returned list is in input order and deduplicated (a date that
	appears three times is reported once). An empty list signals that
	the input is clean. Used as a preflight by rotation so the script
	never needs ``try/except`` around the parser.

	Args:
		blocks: List of ``DayBlock`` records.

	Returns:
		List of duplicated date strings in input order.
	"""
	seen: set = set()
	dup_set: set = set()
	dup_order: list = []
	for block in blocks:
		date_str = block.date
		if date_str in seen and date_str not in dup_set:
			dup_set.add(date_str)
			dup_order.append(date_str)
			continue
		seen.add(date_str)
	return dup_order

#============================================
#============================================
# Git helpers
#============================================
#============================================
#
# Lifted out of devel/commit_changelog.py, devel/rotate_changelog.py,
# and devel/query_changelog.py to eliminate three-way duplication. All
# three scripts already import this module for parser access; sharing
# the git trio here avoids a separate devel/git_helpers.py module per
# user decision.

def run_git(args: list[str]) -> subprocess.CompletedProcess:
	"""Run a git command and return the completed process.

	Args:
		args: Argument list passed to git (no leading "git" token).

	Returns:
		The ``subprocess.CompletedProcess`` with text-mode stdout/stderr.
	"""
	result = subprocess.run(
		["git"] + args,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True,
	)
	return result

#============================================

def get_git_root() -> str:
	"""Return the absolute path of the git repository root.

	Returns:
		Absolute path of the git repository root, as reported by
		``git rev-parse --show-toplevel``.

	Raises:
		RuntimeError: When git rev-parse fails or returns an empty path
			(not a git work tree, git binary missing, etc.).
	"""
	result = run_git(["rev-parse", "--show-toplevel"])
	if result.returncode != 0:
		raise RuntimeError("Unable to determine git repository root.")
	root = result.stdout.strip()
	if not root:
		raise RuntimeError("Git repository root is empty.")
	return root

#============================================

def ensure_in_git_repo() -> None:
	"""Raise if the current working directory is not inside a git work tree.

	Raises:
		RuntimeError: When git rev-parse cannot confirm an inside-work-tree
			environment.
	"""
	result = run_git(["rev-parse", "--is-inside-work-tree"])
	if result.returncode != 0:
		raise RuntimeError("Not inside a git repository.")
	if result.stdout.strip() != "true":
		raise RuntimeError("Not inside a git work tree.")

#============================================
#============================================
# Console and prompt helpers
#============================================
#============================================
#
# Lifted out of devel/commit_changelog.py and devel/rotate_changelog.py
# to eliminate duplicated rich-console primitives. The two module-level
# Console instances below are the canonical CONSOLE / ERR_CONSOLE handles
# the helpers below print through; calling scripts that want raw access
# (e.g. CONSOLE.print(...) with their own styles) may either reference
# changelog_lib.CONSOLE directly or keep their own local Console handles.

# highlight=False stops rich from auto-coloring numbers, paths, and
# similar tokens in plain printed text (the "pink lemonade" effect on
# some terminals); markup tags like [bold red] still work because
# markup defaults to True. Per-call markup=False on print_warning /
# print_error keeps literal [brackets] in user-supplied messages from
# being interpreted as markup.
CONSOLE = rich.console.Console(highlight=False)
ERR_CONSOLE = rich.console.Console(stderr=True, highlight=False)

#============================================

def build_choice_prompt(prompt: str) -> str:
	"""Build a colored y/N prompt string.

	Args:
		prompt: Base prompt text.

	Returns:
		The prompt with a colored ``[y/N]`` suffix appended.
	"""
	yes_text = "[bold green]y[/bold green]"
	no_text = "[bold red]N[/bold red]"
	choice_prompt = f"{prompt} [{yes_text}/{no_text}] "
	return choice_prompt

#============================================

def confirm(prompt: str) -> bool:
	"""Ask the user to confirm via a y/N prompt.

	Args:
		prompt: Prompt text shown before the choices.

	Returns:
		True when the answer is ``y`` or ``yes`` (case-insensitive).
	"""
	choice_prompt = build_choice_prompt(prompt)
	ans = CONSOLE.input(choice_prompt).strip().lower()
	confirmed = ans in ("y", "yes")
	return confirmed

#============================================

def print_warning(message: str) -> None:
	"""Print a warning message in yellow on stdout.

	``highlight=False`` and ``markup=False`` keep rich from auto-coloring
	numbers/paths or interpreting ``[brackets]`` in arbitrary user-facing
	text. Matches the unified print-helper convention across devel/.
	"""
	CONSOLE.print(message, style="yellow", highlight=False, markup=False)

#============================================

def print_error(message: str) -> None:
	"""Print an error message in bold red on stderr.

	Same ``highlight=False`` / ``markup=False`` discipline as
	``print_warning``; see that docstring.
	"""
	ERR_CONSOLE.print(message, style="bold red", highlight=False, markup=False)
