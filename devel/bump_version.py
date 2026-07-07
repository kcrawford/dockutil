#!/usr/bin/env python3

# Standard Library
import os
import re
import sys
import tomllib
import argparse
import datetime

BASE_VERSION_PATTERN = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")
PEP440_PATTERN = re.compile(
	r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?P<tag>a|b|rc)(?P<num>\d+)$"
)
SHORT_PEP440_PATTERN = re.compile(
	r"^(?P<major>\d+)\.(?P<minor>\d+)(?P<tag>a|b|rc)(?P<num>\d+)$"
)
DASH_PATTERN = re.compile(
	r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)-(?P<tag>alpha|beta|rc)"
	r"(?:[\\.-]?(?P<num>\d+))?$"
)
YY_MM_PATCH_PATTERN = re.compile(
	r"^(?P<major>\d{2})\.(?P<minor>\d{2})\.(?P<patch>\d+)"
	r"(?:(?P<tag>a|b|rc)(?P<num>\d+))?$"
)
YY_MM_SHORT_PATTERN = re.compile(
	r"^(?P<major>\d{2})\.(?P<minor>\d{2})(?P<tag>a|b|rc)(?P<num>\d+)$"
)
YY_MM_BARE_PATTERN = re.compile(r"^(?P<major>\d{2})\.(?P<minor>\d{2})$")
SIMPLE_VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+(?:[A-Za-z0-9\.-]+)?")
ASSIGNMENT_PATTERN = re.compile(
	r"^(?P<indent>\s*)(?P<name>__version__|VERSION|version)\s*=\s*"
	r"(?P<quote>['\"])(?P<version>[^'\"]+)(?P=quote)(?P<rest>.*)$"
)
SECTION_HEADER_PATTERN = re.compile(r"^\[(?P<section>[^\]]+)\]\s*$")
VERSION_LINE_PATTERN = re.compile(
	r"^(?P<indent>\s*)version\s*=\s*(?P<quote>['\"])(?P<version>[^'\"]+)(?P=quote)(?P<rest>.*)$"
)
SKIP_DIRS = {
	".git",
	".venv",
	"venv",
	"env",
	"build",
	"dist",
	"__pycache__",
	"node_modules",
	"site-packages",
}
CANDIDATE_FILENAMES = {
	"pyproject.toml",
	"VERSION",
	"version",
	"version.txt",
	"version.py",
}
SHORT_BUMP_ALIASES = {
	"M": "major",
	"m": "minor",
	"p": "patch",
	"a": "alpha",
	"b": "beta",
	"r": "rc",
}
ADVANCED_HELP = argparse.SUPPRESS

#============================================

def parse_args() -> argparse.Namespace:
	"""Parse command line arguments.

	Returns:
		argparse.Namespace: Parsed arguments.
	"""
	show_advanced = "--help-advanced" in sys.argv[1:]
	parser = argparse.ArgumentParser(
		description=(
			"Bump or set version numbers across common version files. "
			"Defaults to dry-run mode."
		),
	)
	parser.add_argument(
		"--help-advanced",
		action="help",
		help="Show advanced options and exit.",
	)

	parser.add_argument(
		"-b", "--base-dir",
		dest="base_dir",
		default=".",
		help=advanced_help(show_advanced, "Base directory to scan."),
	)
	parser.add_argument(
		"-s", "--source",
		dest="source",
		default="",
		help=advanced_help(show_advanced, "Source file to anchor version selection."),
	)
	parser.add_argument(
		"-m", "--max-depth",
		dest="max_depth",
		type=int,
		default=4,
		help=advanced_help(show_advanced, "Max directory depth to scan."),
	)

	parser.add_argument(
		"action",
		nargs="?",
		default="",
		help="Version to set, such as 26.05.",
	)
	parser.add_argument(
		"--bump",
		dest="bump",
		default="",
		choices=["major", "minor", "patch", "alpha", "beta", "rc"],
		help=advanced_help(show_advanced, "Bump by major, minor, patch, alpha, beta, or rc."),
	)
	parser.add_argument(
		"-v", "--set-version",
		dest="set_version",
		default="",
		help="Set an explicit version, such as 26.05.",
	)
	parser.add_argument(
		"-c", "--calver",
		dest="calver",
		action="store_true",
		help="Use the current YY.MM CalVer value.",
	)

	parser.add_argument(
		"-A", "--apply",
		dest="apply",
		action="store_true",
		help="Write changes to disk.",
	)
	parser.add_argument(
		"-n", "--dry-run",
		dest="apply",
		action="store_false",
		help=advanced_help(show_advanced, "Only print planned changes."),
	)
	parser.set_defaults(apply=False)

	parser.add_argument(
		"-u", "--update-all",
		dest="update_all",
		action="store_true",
		help=advanced_help(show_advanced, "Update all discovered versions, even if they differ."),
	)
	parser.add_argument(
		"--pre-style",
		dest="pre_style",
		choices=["pep440", "dash"],
		default="pep440",
		help=advanced_help(show_advanced, "Prerelease style when adding alpha/beta/rc."),
	)
	parser.add_argument(
		"--no-enforce-yy-mm",
		dest="enforce_yy_mm",
		action="store_false",
		help=advanced_help(show_advanced, "Disable YY.MM.PATCH enforcement."),
	)
	parser.set_defaults(enforce_yy_mm=True)

	args = parser.parse_args()
	if args.calver and args.set_version:
		parser.error("Use either --calver or --set-version, not both.")
	if args.action:
		if args.action in SHORT_BUMP_ALIASES:
			if args.bump:
				parser.error("Use either positional bump shortcut or --bump, not both.")
			if args.set_version or args.calver:
				parser.error(
					"Use either positional bump shortcut or version source, not both."
				)
			args.bump = SHORT_BUMP_ALIASES[args.action]
		else:
			if args.set_version or args.calver:
				parser.error("Use either positional version or version flag, not both.")
			args.set_version = args.action
	if args.calver:
		args.set_version = current_calver_month()
	if not args.bump and not args.set_version:
		args.set_version = current_calver_month()
	return args

#============================================

def advanced_help(show_advanced: bool, help_text: str) -> str:
	"""Return help text only when advanced help was requested.

	Args:
		show_advanced (bool): Whether advanced help is visible.
		help_text (str): Help text for the argument.

	Returns:
		str: Help text or argparse suppression marker.
	"""
	if show_advanced:
		return help_text
	return ADVANCED_HELP

#============================================

def current_calver_month() -> str:
	"""Return the current month in repo CalVer format.

	Returns:
		str: Current YY.MM value.
	"""
	today = datetime.date.today()
	return f"{today.year % 100:02d}.{today.month:02d}"

#============================================

def is_version_candidate(text: str) -> bool:
	"""Check whether a string looks like a version.

	Args:
		text (str): Version candidate.

	Returns:
		bool: True if it looks like a version.
	"""
	value = text.strip()
	if not value:
		return False
	try:
		parse_version_details(value)
		return True
	except ValueError:
		pass
	if SIMPLE_VERSION_PATTERN.fullmatch(value):
		return True
	return False

#============================================

def normalize_base_dir(base_dir: str) -> str:
	"""Normalize a base directory path.

	Args:
		base_dir (str): Base directory.

	Returns:
		str: Normalized absolute path.
	"""
	resolved = os.path.abspath(os.path.expanduser(base_dir))
	if not os.path.isdir(resolved):
		raise FileNotFoundError(f"Base directory not found: {resolved}")
	return resolved

#============================================

def normalize_base_version_override(value: str) -> str:
	"""Normalize a base version override string.

	Args:
		value (str): Base version override.

	Returns:
		str: Normalized base version.
	"""
	candidate = value.strip()
	if re.fullmatch(r"\d{2}\.\d{2}", candidate):
		return f"{candidate}.0"
	return candidate

#============================================

def iter_candidate_files(base_dir: str, max_depth: int) -> list[str]:
	"""Find candidate version files.

	Args:
		base_dir (str): Base directory.
		max_depth (int): Max depth to search.

	Returns:
		list[str]: Candidate file paths.
	"""
	base_depth = base_dir.rstrip(os.sep).count(os.sep)
	matches = []
	for root, dirs, files in os.walk(base_dir):
		depth = root.rstrip(os.sep).count(os.sep) - base_depth
		if depth > max_depth:
			dirs[:] = []
			continue

		dirs[:] = [
			d for d in dirs
			if d not in SKIP_DIRS and not d.startswith(".")
		]

		for filename in files:
			if filename in CANDIDATE_FILENAMES:
				matches.append(os.path.join(root, filename))

	matches.sort()
	return matches

#============================================

def parse_pyproject(path: str) -> dict | None:
	"""Parse a pyproject.toml version.

	Args:
		path (str): pyproject.toml path.

	Returns:
		dict | None: Entry describing the version, or None if missing.
	"""
	with open(path, "rb") as handle:
		data = tomllib.load(handle)

	project_version = None
	poetry_version = None

	project_data = data.get("project", {})
	if project_data:
		project_version = project_data.get("version")

	tool_data = data.get("tool", {})
	poetry_data = tool_data.get("poetry", {})
	if poetry_data:
		poetry_version = poetry_data.get("version")

	versions = []
	if project_version:
		versions.append(str(project_version))
	if poetry_version:
		versions.append(str(poetry_version))

	if not versions:
		return None

	unique_versions = sorted(set(versions))
	if len(unique_versions) > 1:
		raise ValueError(
			f"Conflicting versions in {path}: {', '.join(unique_versions)}"
		)

	entry = {
		"path": path,
		"kind": "pyproject",
		"version": unique_versions[0],
		"sections": [],
	}
	if project_version:
		entry["sections"].append("project")
	if poetry_version:
		entry["sections"].append("tool.poetry")

	return entry

#============================================

def parse_simple_version_file(path: str, force_update: bool=False) -> dict | None:
	"""Parse a simple version file (VERSION, version.txt, version).

	Args:
		path (str): File path.
		force_update (bool): Treat the first non-empty line as a version.

	Returns:
		dict | None: Entry describing the version, or None if missing.
	"""
	with open(path, "r", encoding="utf-8") as handle:
		lines = handle.read().splitlines()

	for line in lines:
		strip_line = line.strip()
		if not strip_line or strip_line.startswith("#"):
			continue
		if force_update or is_version_candidate(strip_line):
			entry = {
				"path": path,
				"kind": "simple",
				"version": strip_line,
				"force_update": force_update,
			}
			return entry
		return None

	if force_update:
		entry = {
			"path": path,
			"kind": "simple",
			"version": "",
			"force_update": True,
			"create": False,
		}
		return entry

	return None

#============================================

def build_version_file_entry(base_dir: str, version: str="", create: bool=True) -> dict:
	"""Build a VERSION-file entry.

	Args:
		base_dir (str): Base directory.
		version (str): Current version value.
		create (bool): Whether the VERSION file needs to be created.

	Returns:
		dict: Version entry.
	"""
	return {
		"path": os.path.join(base_dir, "VERSION"),
		"kind": "simple",
		"version": version,
		"force_update": True,
		"create": create,
	}

#============================================

def parse_version_py(path: str) -> dict | None:
	"""Parse a version.py file with assignment patterns.

	Args:
		path (str): File path.

	Returns:
		dict | None: Entry describing the version, or None if missing.
	"""
	with open(path, "r", encoding="utf-8") as handle:
		lines = handle.read().splitlines()

	versions = []
	for line in lines:
		match = ASSIGNMENT_PATTERN.match(line)
		if not match:
			continue
		versions.append(match.group("version"))

	if not versions:
		return None

	unique_versions = sorted(set(versions))
	if len(unique_versions) > 1:
		raise ValueError(
			f"Conflicting versions in {path}: {', '.join(unique_versions)}"
		)

	entry = {
		"path": path,
		"kind": "version_py",
		"version": unique_versions[0],
	}
	return entry

#============================================

def parse_versions(base_dir: str, max_depth: int) -> list[dict]:
	"""Scan the repo for version sources.

	Args:
		base_dir (str): Base directory.
		max_depth (int): Max depth to scan.

	Returns:
		list[dict]: List of version entries.
	"""
	entries = []
	for path in iter_candidate_files(base_dir, max_depth):
		filename = os.path.basename(path)
		if filename == "pyproject.toml":
			entry = parse_pyproject(path)
		elif filename == "version.py":
			entry = parse_version_py(path)
		else:
			force_update = filename == "VERSION"
			entry = parse_simple_version_file(path, force_update=force_update)
		if entry:
			entries.append(entry)

	return entries

#============================================

def ensure_version_file_entry(entries: list[dict], base_dir: str) -> list[dict]:
	"""Ensure the root VERSION file is represented.

	Args:
		entries (list[dict]): Discovered version entries.
		base_dir (str): Base directory.

	Returns:
		list[dict]: Entries with root VERSION appended when missing.
	"""
	version_path = os.path.join(base_dir, "VERSION")
	for entry in entries:
		if os.path.abspath(entry["path"]) == os.path.abspath(version_path):
			return entries
	if os.path.exists(version_path):
		return entries
	return entries + [build_version_file_entry(base_dir)]

#============================================

def resolve_source_entry(entries: list[dict], source: str) -> dict:
	"""Resolve a source entry by path.

	Args:
		entries (list[dict]): Version entries.
		source (str): Source path.

	Returns:
		dict: Matching entry.
	"""
	if not source:
		raise ValueError("Source path is empty.")

	normalized = os.path.abspath(os.path.expanduser(source))
	for entry in entries:
		if os.path.abspath(entry["path"]) == normalized:
			return entry

	paths = "\n".join(sorted(entry["path"] for entry in entries))
	raise ValueError(f"Source path not found. Known paths:\n{paths}")

#============================================

def choose_base_version(entries: list[dict], source: str) -> str:
	"""Choose a base version.

	Args:
		entries (list[dict]): Version entries.
		source (str): Optional source path.

	Returns:
		str: Base version string.
	"""
	if source:
		source_entry = resolve_source_entry(entries, source)
		return source_entry["version"]

	versions = sorted(set(entry["version"] for entry in entries))
	if len(versions) == 1:
		return versions[0]

	joined = ", ".join(versions)
	raise ValueError(f"Multiple versions found: {joined}. Use --source or --set-version.")

#============================================

def bump_version(version: str, bump: str, pre_style: str) -> str:
	"""Bump a semantic version.

	Args:
		version (str): Current version string.
		bump (str): major, minor, patch, alpha, beta, or rc.
		pre_style (str): pep440 or dash.

	Returns:
		str: New version string.
	"""
	details = parse_version_details(version)
	if bump in ("major", "minor", "patch"):
		if details["pre_tag"] or details["pre_num"] is not None:
			raise ValueError(f"Remove prerelease suffix before bumping: {version}")
		if bump == "major":
			details["major"] += 1
			details["minor"] = 0
			details["patch"] = 0
		elif bump == "minor":
			details["minor"] += 1
			details["patch"] = 0
		else:
			details["patch"] += 1
		details["pre_tag"] = None
		details["pre_num"] = None
		return format_version(details)

	if bump in ("alpha", "beta", "rc"):
		return bump_prerelease(details, bump, pre_style)

	raise ValueError(f"Unsupported bump mode: {bump}")

#============================================

def parse_version_details(version: str) -> dict:
	"""Parse a version string into parts.

	Args:
		version (str): Version string.

	Returns:
		dict: Parsed version parts.
	"""
	match = PEP440_PATTERN.match(version)
	if match:
		major_text = match.group("major")
		minor_text = match.group("minor")
		patch_text = match.group("patch")
		tag = match.group("tag")
		tag_map = {"a": "alpha", "b": "beta", "rc": "rc"}
		details = {
			"major": int(major_text),
			"minor": int(minor_text),
			"patch": int(patch_text),
			"major_width": len(major_text),
			"minor_width": len(minor_text),
			"patch_width": len(patch_text),
			"pre_tag": tag_map[tag],
			"pre_num": int(match.group("num")),
			"style": "pep440",
		}
		return details

	match = SHORT_PEP440_PATTERN.match(version)
	if match:
		major_text = match.group("major")
		minor_text = match.group("minor")
		tag = match.group("tag")
		tag_map = {"a": "alpha", "b": "beta", "rc": "rc"}
		details = {
			"major": int(major_text),
			"minor": int(minor_text),
			"patch": 0,
			"major_width": len(major_text),
			"minor_width": len(minor_text),
			"patch_width": 1,
			"pre_tag": tag_map[tag],
			"pre_num": int(match.group("num")),
			"style": "pep440",
			"patch_optional": True,
		}
		return details

	match = DASH_PATTERN.match(version)
	if match:
		major_text = match.group("major")
		minor_text = match.group("minor")
		patch_text = match.group("patch")
		num_text = match.group("num")
		pre_num = int(num_text) if num_text else 0
		details = {
			"major": int(major_text),
			"minor": int(minor_text),
			"patch": int(patch_text),
			"major_width": len(major_text),
			"minor_width": len(minor_text),
			"patch_width": len(patch_text),
			"pre_tag": match.group("tag"),
			"pre_num": pre_num,
			"style": "dash",
		}
		return details

	match = YY_MM_PATCH_PATTERN.match(version)
	if match:
		major_text = match.group("major")
		minor_text = match.group("minor")
		patch_text = match.group("patch")
		details = {
			"major": int(major_text),
			"minor": int(minor_text),
			"patch": int(patch_text),
			"major_width": len(major_text),
			"minor_width": len(minor_text),
			"patch_width": len(patch_text),
			"pre_tag": match.group("tag"),
			"pre_num": int(match.group("num")) if match.group("num") else None,
			"style": "pep440",
			"patch_optional": False,
		}
		return details

	match = YY_MM_SHORT_PATTERN.match(version)
	if match:
		major_text = match.group("major")
		minor_text = match.group("minor")
		tag = match.group("tag")
		details = {
			"major": int(major_text),
			"minor": int(minor_text),
			"patch": 0,
			"major_width": len(major_text),
			"minor_width": len(minor_text),
			"patch_width": 1,
			"pre_tag": tag,
			"pre_num": int(match.group("num")),
			"style": "pep440",
			"patch_optional": True,
		}
		return details

	match = YY_MM_BARE_PATTERN.match(version)
	if match:
		major_text = match.group("major")
		minor_text = match.group("minor")
		details = {
			"major": int(major_text),
			"minor": int(minor_text),
			"patch": 0,
			"major_width": len(major_text),
			"minor_width": len(minor_text),
			"patch_width": 1,
			"pre_tag": None,
			"pre_num": None,
			"style": "pep440",
			"patch_optional": True,
		}
		return details

	match = BASE_VERSION_PATTERN.match(version)
	if match:
		major_text = match.group("major")
		minor_text = match.group("minor")
		patch_text = match.group("patch")
		details = {
			"major": int(major_text),
			"minor": int(minor_text),
			"patch": int(patch_text),
			"major_width": len(major_text),
			"minor_width": len(minor_text),
			"patch_width": len(patch_text),
			"pre_tag": None,
			"pre_num": None,
			"style": "none",
			"patch_optional": False,
		}
		return details

	raise ValueError(f"Unsupported version format: {version}")

#============================================

def validate_yy_mm_patch(version: str) -> None:
	"""Validate YY.MM.PATCH format with optional PEP 440 prerelease suffix.

	Args:
		version (str): Version string.
	"""
	match = YY_MM_PATCH_PATTERN.match(version)
	match_short = YY_MM_SHORT_PATTERN.match(version)
	match_bare = YY_MM_BARE_PATTERN.match(version)
	if not match and not match_short and not match_bare:
		raise ValueError(
			f"Version must be YY.MM, YY.MM.PATCH, or YY.MM prerelease: {version}"
		)

	month_text = (match or match_short or match_bare).group("minor")
	month = int(month_text)
	if month < 1 or month > 12:
		raise ValueError(f"Invalid month in version: {version}")

#============================================

def format_version(details: dict) -> str:
	"""Format a version string from parts.

	Args:
		details (dict): Version parts.

	Returns:
		str: Formatted version.
	"""
	major = format_number(details["major"], details.get("major_width"))
	minor = format_number(details["minor"], details.get("minor_width"))
	patch = format_number(details["patch"], details.get("patch_width"))
	base = f"{major}.{minor}.{patch}"
	if not details["pre_tag"]:
		return base

	pre_num = details["pre_num"] if details["pre_num"] is not None else 1
	if details["style"] == "pep440":
		tag_map = {"alpha": "a", "beta": "b", "rc": "rc"}
		return f"{base}{tag_map[details['pre_tag']]}{pre_num}"

	return f"{base}-{details['pre_tag']}.{pre_num}"

#============================================

def format_number(value: int, width: int | None) -> str:
	"""Format a number with optional zero padding.

	Args:
		value (int): Numeric value.
		width (int | None): Minimum width to preserve.

	Returns:
		str: Formatted number.
	"""
	text = str(value)
	if width and len(text) < width:
		return text.zfill(width)
	return text

def bump_prerelease(details: dict, tag: str, pre_style: str) -> str:
	"""Bump or add a prerelease suffix.

	Args:
		details (dict): Parsed version details.
		tag (str): alpha, beta, or rc.
		pre_style (str): pep440 or dash.

	Returns:
		str: Updated version.
	"""
	style = details["style"]
	if style == "none":
		style = pre_style
	details = dict(details)
	details["style"] = style
	if details["pre_tag"] == tag:
		if details["pre_num"] is None:
			details["pre_num"] = 1
		else:
			details["pre_num"] += 1
	else:
		details["pre_tag"] = tag
		details["pre_num"] = 1
	return format_version(details)

#============================================

def update_pyproject(text: str, sections: list[str], new_version: str) -> tuple[str, bool]:
	"""Update version lines in a pyproject.toml string.

	Args:
		text (str): File contents.
		sections (list[str]): Sections to update.
		new_version (str): New version.

	Returns:
		tuple[str, bool]: Updated text and changed flag.
	"""
	lines = text.splitlines(keepends=True)
	changed = False

	active_section = None
	for index, line in enumerate(lines):
		match = SECTION_HEADER_PATTERN.match(line.strip())
		if match:
			active_section = match.group("section")
			continue

		if active_section not in sections:
			continue

		match = VERSION_LINE_PATTERN.match(line)
		if not match:
			continue

		indent = match.group("indent")
		quote = match.group("quote")
		rest = match.group("rest")
		newline = "\n" if line.endswith("\n") else ""
		lines[index] = f"{indent}version = {quote}{new_version}{quote}{rest}{newline}"
		changed = True

	return "".join(lines), changed

#============================================

def normalize_target_version(entry: dict, new_version: str) -> str:
	"""Normalize the target version for entries without a patch segment.

	Args:
		entry (dict): Version entry metadata.
		new_version (str): Target version.

	Returns:
		str: Adjusted version string.
	"""
	if entry.get("patch_optional") and new_version.endswith(".0"):
		short_version = new_version.replace(".0", "", 1)
		if SHORT_PEP440_PATTERN.match(short_version):
			return short_version
	return new_version

#============================================

def update_simple_version(text: str, new_version: str, force_update: bool=False) -> tuple[str, bool]:
	"""Update a simple version file.

	Args:
		text (str): File contents.
		new_version (str): New version.
		force_update (bool): Update first non-empty line even if not a version.

	Returns:
		tuple[str, bool]: Updated text and changed flag.
	"""
	lines = text.splitlines(keepends=True)
	for index, line in enumerate(lines):
		strip_line = line.strip()
		if not strip_line or strip_line.startswith("#"):
			continue
		if not is_version_candidate(strip_line) and not force_update:
			break
		newline = "\n" if line.endswith("\n") else ""
		lines[index] = f"{new_version}{newline}"
		return "".join(lines), True

	if force_update:
		return f"{new_version}\n", True

	return text, False

#============================================

def update_version_py(text: str, new_version: str) -> tuple[str, bool]:
	"""Update version assignments in version.py.

	Args:
		text (str): File contents.
		new_version (str): New version.

	Returns:
		tuple[str, bool]: Updated text and changed flag.
	"""
	lines = text.splitlines(keepends=True)
	changed = False
	for index, line in enumerate(lines):
		match = ASSIGNMENT_PATTERN.match(line)
		if not match:
			continue
		indent = match.group("indent")
		name = match.group("name")
		quote = match.group("quote")
		rest = match.group("rest")
		newline = "\n" if line.endswith("\n") else ""
		lines[index] = f"{indent}{name} = {quote}{new_version}{quote}{rest}{newline}"
		changed = True

	return "".join(lines), changed

#============================================

def update_entry(entry: dict, new_version: str, apply: bool) -> dict:
	"""Update a version entry.

	Args:
		entry (dict): Version entry.
		new_version (str): New version.
		apply (bool): Whether to write changes.

	Returns:
		dict: Result summary.
	"""
	path = entry["path"]
	if entry.get("create"):
		text = ""
	else:
		with open(path, "r", encoding="utf-8") as handle:
			text = handle.read()

	version_value = normalize_target_version(entry, new_version)
	if entry["kind"] == "pyproject":
		updated_text, changed = update_pyproject(text, entry["sections"], version_value)
	elif entry["kind"] == "version_py":
		updated_text, changed = update_version_py(text, version_value)
	else:
		updated_text, changed = update_simple_version(
			text,
			version_value,
			force_update=entry.get("force_update", False),
		)

	if changed and apply:
		with open(path, "w", encoding="utf-8") as handle:
			handle.write(updated_text)

	result = {
		"path": path,
		"changed": changed,
	}
	return result

#============================================

def main() -> None:
	args = parse_args()
	base_dir = normalize_base_dir(args.base_dir)
	entries = parse_versions(base_dir, args.max_depth)

	base_version_override = ""
	explicit_version = ""
	if args.bump and args.set_version:
		base_version_override = normalize_base_version_override(args.set_version)
		if not base_version_override:
			raise SystemExit("--set-version requires a non-empty value.")
	elif args.set_version:
		explicit_version = args.set_version.strip()
		if not explicit_version:
			raise SystemExit("--set-version requires a non-empty value.")

	if explicit_version:
		entries = ensure_version_file_entry(entries, base_dir)

	if not entries:
		raise SystemExit("No version sources found.")

	print("Discovered versions:")
	for entry in entries:
		rel_path = os.path.relpath(entry["path"], base_dir)
		version_display = entry["version"] if entry["version"] else "(empty)"
		if entry.get("create"):
			version_display = "(missing)"
		print(f"- {rel_path}: {version_display} ({entry['kind']})")

	base_version_display = ""
	if base_version_override:
		base_version = base_version_override
		base_version_display = base_version
	elif explicit_version and args.update_all:
		versions = sorted(set(entry["version"] for entry in entries))
		if len(versions) == 1:
			base_version = versions[0]
			base_version_display = base_version
		else:
			base_version = ""
			base_version_display = "multiple"
	else:
		base_version = choose_base_version(entries, args.source)
		base_version_display = base_version

	if base_version_override and not args.update_all:
		known_versions = {entry["version"] for entry in entries}
		if base_version not in known_versions:
			raise SystemExit(
				f"Base version not found: {base_version}. Use --update-all to override."
			)

	if args.enforce_yy_mm and base_version:
		validate_yy_mm_patch(base_version)
	if explicit_version:
		new_version = explicit_version
	else:
		new_version = bump_version(base_version, args.bump, args.pre_style)
	if args.enforce_yy_mm:
		validate_yy_mm_patch(new_version)

	print(f"Base version: {base_version_display}")
	print(f"New version: {new_version}")

	if args.update_all:
		if all(entry["version"] == new_version for entry in entries):
			print("New version matches current version. Nothing to do.")
			return
	else:
		if base_version == new_version:
			print("New version matches current version. Nothing to do.")
			return

	if args.update_all:
		selected = list(entries)
		skipped = []
	else:
		selected = [entry for entry in entries if entry["version"] == base_version]
		skipped = [entry for entry in entries if entry["version"] != base_version]

	if skipped:
		print("Skipping entries with different versions:")
		for entry in skipped:
			rel_path = os.path.relpath(entry["path"], base_dir)
			print(f"- {rel_path}: {entry['version']}")

	print("Planned updates:")
	for entry in selected:
		rel_path = os.path.relpath(entry["path"], base_dir)
		print(f"- {rel_path}")

	changed = 0
	for entry in selected:
		result = update_entry(entry, new_version, args.apply)
		if result["changed"]:
			changed += 1

	if args.apply:
		print(f"Updated {changed} file(s).")
	else:
		print("Dry run only. Use --apply to write changes.")


#============================================
if __name__ == "__main__":
	main()
