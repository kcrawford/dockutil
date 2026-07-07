import os
import re

import file_utils

REPO_ROOT = file_utils.get_repo_root()
README_PATH = os.path.join(REPO_ROOT, "README.md")
MAX_ABOUT_CHARS = 250

# Inline link or image: optional leading '!', [text](url). Markdown
# images (leading '!') are the syntax used for status badges like
# ![Build](https://img.shields.io/.../badge.svg).
MARKDOWN_LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# Bare autolink: <https://example.com>
AUTOLINK_RE = re.compile(r"<([a-z][a-z0-9+.-]*://[^>]+)>")
# Any inline HTML tag: <tagname ...>, </tagname>, or self-closing
# <tagname .../>. Covers badge wrappers (<img>, <a>) and layout tags
# (<br>, <div>, <p>, <span>). HTML character entities (&amp;, &alpha;,
# etc.) are NOT rejected here: the repo's ASCII-only Markdown rule
# requires entities for non-ASCII glyphs, and the human transcribing
# the About text substitutes the rendered character (e.g. types the
# real & or alpha) rather than copying the entity verbatim.
HTML_TAG_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9-]*\b[^>]*>")


#============================================
def _strip_markdown_links(text: str) -> str:
	"""
	Replace Markdown links with their visible text only.

	Drops the URL portion so a link to a repository or package URL cannot
	smuggle the repo name into the repo-name check. Images (leading '!')
	collapse to their alt text. Autolinks collapse to an empty string.

	Args:
		text: Raw Markdown paragraph content.

	Returns:
		str: Text with link URLs removed, visible text preserved.
	"""
	def link_replacement(match: re.Match) -> str:
		# Keep visible text, drop the URL
		return match.group(1)
	stripped = MARKDOWN_LINK_RE.sub(link_replacement, text)
	stripped = AUTOLINK_RE.sub("", stripped)
	return stripped


#============================================
def _is_badge_only_block(block: str) -> bool:
	"""
	Return True when a block consists only of image badges or links.

	Used to skip leading badge rows that sit between the title heading and
	the real first prose paragraph.

	Args:
		block: A single block of README content (lines joined by newlines).

	Returns:
		bool: True if every non-empty token in the block is a Markdown link
		or image, False if any prose text remains.
	"""
	# Remove every Markdown link and image; if nothing prose-like is left
	# (only whitespace and punctuation glue), treat the block as badges
	residual = MARKDOWN_LINK_RE.sub("", block)
	residual = AUTOLINK_RE.sub("", residual)
	# Allow common badge separators: whitespace, pipes, bullets, dashes
	residual = re.sub(r"[\s|*\-]+", "", residual)
	return residual == ""


#============================================
def _load_first_paragraph() -> str:
	"""
	Load the first prose paragraph of README.md.

	Skips leading heading-only blocks and badge-only blocks, then returns
	the next non-empty block joined with single spaces (GitHub renders
	soft-wrapped lines in a paragraph as space-separated text).

	Returns:
		str: First paragraph text, stripped of surrounding whitespace.
	"""
	# Read README content; missing file raises FileNotFoundError directly
	with open(README_PATH, encoding="utf-8") as handle:
		text = handle.read()
	# Split on blank lines into blocks
	raw_blocks = text.split("\n\n")
	blocks = []
	for raw_block in raw_blocks:
		stripped = raw_block.strip()
		if stripped:
			blocks.append(stripped)
	# Walk blocks, skipping heading-only and badge-only leaders
	paragraph = ""
	for block in blocks:
		# Drop any leading heading lines from this block; some READMEs put
		# the title and first paragraph on adjacent lines with no blank
		# separator, so heading and prose share one block
		lines = block.splitlines()
		prose_lines = []
		dropping = True
		for line in lines:
			if dropping and line.lstrip().startswith("#"):
				continue
			dropping = False
			prose_lines.append(line)
		if not prose_lines:
			continue
		prose_block = "\n".join(prose_lines)
		# Skip blocks composed only of image/link badges
		if _is_badge_only_block(prose_block):
			continue
		# Join soft-wrapped lines with single spaces (GitHub render behavior)
		paragraph = " ".join(line.strip() for line in prose_lines).strip()
		break
	return paragraph


#============================================
def _repo_name_variants() -> list[str]:
	"""
	Return repo name spellings considered "verbatim" for the no-name rule.

	Repo directory names use dashes; Python module names use underscores.
	Both spellings are treated as the repo name.

	Returns:
		list[str]: Lowercase repo name variants to search for.
	"""
	base = os.path.basename(REPO_ROOT).lower()
	variants = [base]
	dash_to_underscore = base.replace("-", "_")
	if dash_to_underscore != base:
		variants.append(dash_to_underscore)
	underscore_to_dash = base.replace("_", "-")
	if underscore_to_dash != base and underscore_to_dash not in variants:
		variants.append(underscore_to_dash)
	return variants


#============================================
def _read_readme_text() -> str:
	"""
	Return the full README.md text.

	Returns:
		str: README file contents.
	"""
	with open(README_PATH, encoding="utf-8") as handle:
		return handle.read()


#============================================
def test_readme_exists() -> None:
	# README.md must be present at the repo root
	assert os.path.isfile(README_PATH), (
		f"README.md is missing at the repo root: {README_PATH}"
	)


#============================================
def test_readme_has_single_h1_title() -> None:
	# First Markdown heading must be a single '# Title' line, and there
	# must be exactly one level-one heading in the file.
	text = _read_readme_text()
	heading_lines = []
	in_fence = False
	for raw_line in text.splitlines():
		stripped = raw_line.strip()
		# Skip content inside fenced code blocks
		if stripped.startswith("```") or stripped.startswith("~~~"):
			in_fence = not in_fence
			continue
		if in_fence:
			continue
		if stripped.startswith("#"):
			heading_lines.append(stripped)
	assert heading_lines, f"README.md has no Markdown headings: {README_PATH}"
	first = heading_lines[0]
	assert first.startswith("# ") and not first.startswith("## "), (
		f"First README heading must be a level-one '# Project Name' line, got: {first!r}"
	)
	title_text = first[2:].strip()
	assert title_text, "First README heading is '#' with no title text after it."
	h1_count = 0
	for heading in heading_lines:
		if heading.startswith("# ") and not heading.startswith("## "):
			h1_count += 1
	assert h1_count == 1, (
		f"README.md must contain exactly one '# Title' heading, found {h1_count}."
	)


#============================================
def test_first_paragraph_exists() -> None:
	# First paragraph must be present and non-empty
	paragraph = _load_first_paragraph()
	assert paragraph, (
		f"README.md has no first prose paragraph after the title and any badge rows: "
		f"{README_PATH}"
	)


#============================================
def test_first_paragraph_at_most_250_chars() -> None:
	# GitHub About field hard-caps at 250 Python characters (len()).
	paragraph = _load_first_paragraph()
	length = len(paragraph)
	assert length <= MAX_ABOUT_CHARS, (
		f"First paragraph must be 250 Python characters or fewer "
		f"(len(paragraph)). Actual: {length} characters; limit: {MAX_ABOUT_CHARS}. "
		f"Paragraph text:\n{paragraph}"
	)


#============================================
def test_first_paragraph_no_repo_name() -> None:
	# Repo name should not appear verbatim in the About text.
	# Strip Markdown link URLs first so a link to the repo or package URL
	# does not trip a false positive; only visible link text is checked.
	paragraph = _load_first_paragraph()
	visible = _strip_markdown_links(paragraph)
	# Strip backticks so a code-formatted name still counts as verbatim
	haystack = visible.replace("`", "").lower()
	variants = _repo_name_variants()
	hits = []
	for variant in variants:
		if variant in haystack:
			hits.append(variant)
	assert not hits, (
		f"First paragraph contains the repo name verbatim ({hits}); "
		f"rewrite it to describe the project without naming it. "
		f"Paragraph text:\n{paragraph}"
	)


#============================================
def test_first_paragraph_is_plain_prose() -> None:
	# Paragraph must be readable prose, not a bullet list, badge row, or
	# pure link row. Checks two things: no line begins with a bullet
	# marker, and the paragraph still has real text after Markdown links
	# and images are stripped.
	paragraph = _load_first_paragraph()
	# Bullet/numbered markers at the start of any joined line
	bullet_re = re.compile(r"(?:^|\s)(?:[-*+]|\d+\.)\s")
	assert not bullet_re.search(" " + paragraph), (
		f"First paragraph looks like a bullet or numbered list, not prose. "
		f"Paragraph text:\n{paragraph}"
	)
	# Reject any Markdown link, image, autolink, or HTML tag in the
	# paragraph. The GitHub About field shows raw Markdown (not
	# rendered), so links, badges, and HTML tags waste characters
	# without rendering. HTML entities are allowed because the repo
	# requires them for non-ASCII glyphs and the human transcribing
	# the About text substitutes the rendered character.
	link_hits = MARKDOWN_LINK_RE.findall(paragraph)
	autolink_hits = AUTOLINK_RE.findall(paragraph)
	html_tag_hits = HTML_TAG_RE.findall(paragraph)
	assert not (link_hits or autolink_hits or html_tag_hits), (
		f"First paragraph must be plain prose with no Markdown links, "
		f"images, autolinks, badges, or HTML tags (they waste characters "
		f"in the GitHub About field). "
		f"Found links: {link_hits}; autolinks: {autolink_hits}; "
		f"HTML tags: {html_tag_hits}. "
		f"Paragraph text:\n{paragraph}"
	)
