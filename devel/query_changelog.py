#!/usr/bin/env python3

"""Query the CHANGELOG corpus by date range, category, and keywords.

Primary use case is release archaeology: filter entries across the active
docs/CHANGELOG.md (default) or the active changelog plus all archives
(--archives). Outputs text, json, or csv records.
"""

# Standard Library
import io
import os
import csv
import sys
import glob
import json
import fnmatch
import argparse
import datetime
import dataclasses

# PIP3 modules
import rich.console

# local repo modules
import changelog_lib

#============================================
# Module constants

CATEGORY_ALIASES = {
	"add": "Additions and New Features",
	"behavior": "Behavior or Interface Changes",
	"fix": "Fixes and Maintenance",
	"remove": "Removals and Deprecations",
	"decision": "Decisions and Failures",
	"test": "Developer Tests and Notes",
	# legacy flat changelogs assign Uncategorized to bullets that appear under
	# a day heading with no preceding ### Category. Surface them as a
	# first-class --category target.
	"uncategorized": "Uncategorized",
	"uncat": "Uncategorized",
}

ERR_CONSOLE = rich.console.Console(stderr=True, highlight=False)

#============================================

def today_or(today: datetime.date = None) -> datetime.date:
	"""Return the supplied date, or today's date if none given.

	Injection point for tests so date math can be pinned.
	"""
	if today is None:
		return datetime.date.today()
	return today

#============================================

def parse_iso_date(text: str, field_name: str) -> datetime.date:
	"""Parse an ISO YYYY-MM-DD string into a date or raise a CLI error."""
	# avoid try/except: validate shape first, then construct
	parts = text.split("-")
	if len(parts) != 3 or not all(p.isdigit() for p in parts):
		raise SystemExit(f"{field_name} must be ISO YYYY-MM-DD, got: {text}")
	year, month, day = (int(p) for p in parts)
	# constructor will raise ValueError for impossible dates; that is an
	# invalid-CLI hard-raise per the plan, allowed to propagate
	return datetime.date(year, month, day)

#============================================

def resolve_categories(raw_values: list[str], parser: argparse.ArgumentParser) -> list[str]:
	"""Resolve --category values: aliases map to canonical headings.

	Other values are treated as case-insensitive substring matches against
	canonical category headings. Returns the list of canonical strings to
	match against (or substring patterns when no alias resolves).
	"""
	if not raw_values:
		return []
	canonical = changelog_lib.CANONICAL_CATEGORIES
	resolved = []
	for raw in raw_values:
		key = raw.strip().lower()
		# alias path: exact lowercase alias name
		if key in CATEGORY_ALIASES:
			resolved.append(CATEGORY_ALIASES[key])
			continue
		# substring path: must match at least one canonical heading
		matches = [c for c in canonical if key in c.lower()]
		if not matches:
			# split error messages by shape: a short single-word token reads
			# as an alias typo; anything else reads as a substring miss.
			# Both are hard errors so the user notices the typo.
			if " " not in raw and len(raw) <= 12:
				parser.error(f"unknown --category alias or substring: {raw}")
			parser.error(f"--category substring matched no canonical heading: {raw}")
		resolved.extend(matches)
	# de-duplicate preserving order
	seen = set()
	unique = []
	for item in resolved:
		if item not in seen:
			seen.add(item)
			unique.append(item)
	return unique

#============================================

def collect_files(corpus_dir: str, archives: bool, source_filter: str,
		quiet: bool) -> list[str]:
	"""Return the list of changelog files to read, newest-first."""
	active = os.path.join(corpus_dir, "CHANGELOG.md")
	files = []
	active_exists = os.path.isfile(active)
	if active_exists:
		files.append(active)
	if archives:
		if not active_exists and not quiet:
			ERR_CONSOLE.print(
				f"[yellow]warn:[/yellow] active changelog missing: {active}"
			)
		# archives sorted newest-first by filename
		archive_glob = os.path.join(corpus_dir, "CHANGELOG-*.md")
		archive_files = sorted(glob.glob(archive_glob), reverse=True)
		files.extend(archive_files)
	if source_filter:
		# allow either a full path or a glob-tail like "CHANGELOG-2026-04a.md"
		filtered = []
		for path in files:
			base = os.path.basename(path)
			if path == source_filter or base == source_filter:
				filtered.append(path)
				continue
			# glob-tail match against basename
			if fnmatch.fnmatch(base, source_filter):
				filtered.append(path)
		files = filtered
	return files

#============================================

def apply_filters(entries: list, date_from: datetime.date,
		date_to: datetime.date, categories: list[str], keywords: list[str],
		case_sensitive: bool, any_keyword: bool) -> list:
	"""Apply all filters in sequence; return matching entries."""
	results = []
	for entry in entries:
		# convert ISO string back to date for comparison; library already
		# validated calendrical correctness during parsing
		parts = entry.date.split("-")
		entry_date = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
		if date_from is not None and entry_date < date_from:
			continue
		if date_to is not None and entry_date > date_to:
			continue
		# category filter (OR across the resolved list)
		if categories:
			cat_lower = entry.category.lower()
			if not any(c.lower() in cat_lower or cat_lower in c.lower()
					for c in categories):
				continue
		# keyword filter
		if keywords:
			haystack = entry.text if case_sensitive else entry.text.lower()
			needles = keywords if case_sensitive else [k.lower() for k in keywords]
			if any_keyword:
				if not any(n in haystack for n in needles):
					continue
			else:
				if not all(n in haystack for n in needles):
					continue
		results.append(entry)
	return results

#============================================

def category_sort_key(category: str) -> int:
	"""Return the canonical sort index for a category heading."""
	canonical = changelog_lib.CANONICAL_CATEGORIES
	if category in canonical:
		return canonical.index(category)
	# non-canonical categories sort after canonical ones, alphabetically
	return len(canonical)

#============================================

def format_text(entries: list, lead_text_blocks: list = None) -> str:
	"""Render entries as grouped text, reverse-chron by date, canonical category.

	If ``lead_text_blocks`` is provided (a list of ``DayBlock`` records with
	non-empty ``lead_text``), the captured lead text is rendered as ``>``
	blockquote lines under the matching date heading. Lead text is human
	context (author attributions, etc.) and is intentionally only emitted
	in text output, never in JSON or CSV.
	"""
	if not entries:
		return ""
	# build (date -> [lead_text lines]) map from supplied blocks
	lead_by_date: dict = {}
	if lead_text_blocks:
		for blk in lead_text_blocks:
			if not blk.lead_text:
				continue
			lead_by_date.setdefault(blk.date, []).append(
				(blk.lead_text, blk.source, blk.lineno)
			)
	# group by date desc
	by_date = {}
	for entry in entries:
		by_date.setdefault(entry.date, []).append(entry)
	out_lines = []
	for date_str in sorted(by_date.keys(), reverse=True):
		out_lines.append(f"## {date_str}")
		out_lines.append("")
		# emit captured lead-text lines (if any) as blockquote context
		for lead_text, lead_source, lead_lineno in lead_by_date.get(date_str, []):
			for lead_line in lead_text.split("\n"):
				out_lines.append(f"> {lead_line}")
			out_lines.append(f"> (lead text from {lead_source}:{lead_lineno})")
			out_lines.append("")
		# group by category in canonical order
		day_entries = by_date[date_str]
		by_cat = {}
		for entry in day_entries:
			by_cat.setdefault(entry.category, []).append(entry)
		ordered_cats = sorted(by_cat.keys(),
				key=lambda c: (category_sort_key(c), c))
		for cat in ordered_cats:
			out_lines.append(f"### {cat}")
			out_lines.append("")
			for entry in by_cat[cat]:
				out_lines.append(f"- {entry.title}")
				if entry.body:
					body_lines = entry.body.split("\n")
					for body_line in body_lines:
						if body_line == "":
							out_lines.append("")
						else:
							out_lines.append(f"  {body_line}")
				out_lines.append(f"  (source: {entry.source}:{entry.lineno})")
				out_lines.append("")
		out_lines.append("")
	rendered = "\n".join(out_lines).rstrip() + "\n"
	return rendered

#============================================

def format_json(entries: list) -> str:
	"""Render entries as a JSON array."""
	# serialize dataclass entries via dataclasses.asdict for JSON encoding
	records = [dataclasses.asdict(entry) for entry in entries]
	return json.dumps(records, indent=2, ensure_ascii=True) + "\n"

#============================================

def format_csv(entries: list) -> str:
	"""Render entries as CSV: date,category,source,title,text."""
	# build rows in memory using csv writer for proper quoting
	buffer = io.StringIO()
	writer = csv.writer(buffer)
	writer.writerow(["date", "category", "source", "title", "text"])
	for entry in entries:
		# collapse newlines in text/title for CSV cleanliness
		title_clean = entry.title.replace("\n", " ").replace("\r", " ")
		text_clean = entry.text.replace("\n", " ").replace("\r", " ")
		writer.writerow([
			entry.date, entry.category, entry.source,
			title_clean, text_clean,
		])
	return buffer.getvalue()

#============================================

def parse_args(argv: list[str] = None) -> argparse.Namespace:
	"""Parse command-line arguments."""
	parser = argparse.ArgumentParser(
		description="Query the CHANGELOG corpus by date, category, and keyword."
	)
	# date range
	date_group = parser.add_mutually_exclusive_group()
	date_group.add_argument(
		"--from", dest="date_from", type=str, default=None,
		help="Inclusive start date (YYYY-MM-DD)."
	)
	date_group.add_argument(
		"--since", dest="since", type=str, default=None,
		help="Look back N days from today (positive integer)."
	)
	parser.add_argument(
		"--to", dest="date_to", type=str, default=None,
		help="Inclusive end date (YYYY-MM-DD)."
	)
	# category
	parser.add_argument(
		"-c", "--category", dest="categories", action="append", default=[],
		help="Category filter; alias or substring (repeatable, OR-combined)."
	)
	# keyword
	parser.add_argument(
		"-k", "--keyword", dest="keywords", action="append", default=[],
		help="Keyword substring (repeatable; AND by default, OR with --any-keyword)."
	)
	parser.add_argument(
		"--case-sensitive", dest="case_sensitive", action="store_true",
		help="Case-sensitive keyword matching (default: case-insensitive)."
	)
	parser.add_argument(
		"--any-keyword", dest="any_keyword", action="store_true",
		help="Combine multiple --keyword values with OR instead of AND."
	)
	# source / archives
	parser.add_argument(
		"--source", dest="source", type=str, default=None,
		help="Limit to a single changelog file (path or filename)."
	)
	parser.add_argument(
		"--archives", "--all", dest="archives", action="store_true",
		help="Search active changelog plus all archive files."
	)
	parser.add_argument(
		"--corpus", dest="corpus", type=str, default=None,
		help="Override docs directory (default: <git-root>/docs)."
	)
	# output
	parser.add_argument(
		"--format", dest="format", type=str, default="text",
		choices=("text", "json", "csv"),
		help="Output format."
	)
	parser.add_argument(
		"--count", dest="count_only", action="store_true",
		help="Print only the count of matching entries."
	)
	parser.add_argument(
		"--strict", dest="strict", action="store_true",
		help="Warn on non-canonical category headings."
	)
	parser.add_argument(
		"--quiet", dest="quiet", action="store_true",
		help="Suppress content warnings (does not silence hard errors)."
	)
	args = parser.parse_args(argv)
	# stash parser for later parser.error() calls in main
	args._parser = parser
	return args

#============================================

def main() -> int:
	"""Orchestrate parse, filter, and emit."""
	args = parse_args()
	parser = args._parser
	# resolve corpus directory
	if args.corpus is not None:
		corpus_dir = args.corpus
	else:
		git_root = changelog_lib.get_git_root()
		corpus_dir = os.path.join(git_root, "docs")
	if not os.path.isdir(corpus_dir):
		parser.error(f"corpus directory not found or not a directory: {corpus_dir}")
	if not os.access(corpus_dir, os.R_OK):
		parser.error(f"corpus directory not readable: {corpus_dir}")

	# date math
	date_from = None
	date_to = None
	if args.date_from is not None:
		date_from = parse_iso_date(args.date_from, "--from")
	if args.date_to is not None:
		date_to = parse_iso_date(args.date_to, "--to")
	if args.since is not None:
		# positive integer required
		if not args.since.isdigit() or int(args.since) <= 0:
			raise SystemExit(f"--since must be a positive integer, got: {args.since}")
		days = int(args.since)
		date_from = today_or() - datetime.timedelta(days=days)

	# resolve categories (aliases / substrings); may parser.error
	resolved_categories = resolve_categories(args.categories, parser)

	# collect files
	active = os.path.join(corpus_dir, "CHANGELOG.md")
	if not args.archives and not os.path.isfile(active):
		raise SystemExit(f"active changelog missing: {active}")
	files = collect_files(corpus_dir, args.archives, args.source, args.quiet)

	# parse all files via the shared library
	all_entries = []
	all_warnings = []
	all_lead_blocks = []
	for path in files:
		_blocks, entries, warnings = changelog_lib.parse_file(
			path, strict=args.strict,
		)
		all_entries.extend(entries)
		all_warnings.extend(warnings)
		# stash blocks with captured lead_text for text rendering
		for blk in _blocks:
			if blk.lead_text:
				all_lead_blocks.append(blk)

	# emit any library warnings to stderr unless suppressed
	if not args.quiet:
		for warning in all_warnings:
			ERR_CONSOLE.print(f"[yellow]warn:[/yellow] {warning}")

	# apply filters
	matched = apply_filters(
		all_entries,
		date_from=date_from,
		date_to=date_to,
		categories=resolved_categories,
		keywords=args.keywords,
		case_sensitive=args.case_sensitive,
		any_keyword=args.any_keyword,
	)

	# emit
	if args.count_only:
		sys.stdout.write(f"{len(matched)}\n")
		return 0
	if args.format == "json":
		sys.stdout.write(format_json(matched))
	elif args.format == "csv":
		sys.stdout.write(format_csv(matched))
	else:
		# pass lead-text blocks for human-context rendering; filter by the
		# dates that survived entry filtering so we don't print lead text
		# for blocks whose entries were filtered out.
		matched_dates = {e.date for e in matched}
		visible_lead_blocks = [b for b in all_lead_blocks if b.date in matched_dates]
		sys.stdout.write(format_text(matched, lead_text_blocks=visible_lead_blocks))
	return 0

#============================================

if __name__ == "__main__":
	sys.exit(main())
