#!/usr/bin/env python3
import argparse
import glob
import os
import sys


#============================================
def parse_args() -> argparse.Namespace:
	"""Parse command-line arguments.

	Returns:
		argparse.Namespace: Parsed arguments.
	"""
	parser = argparse.ArgumentParser(
		description="Fix whitespace issues (line endings, trailing whitespace, final newline, BOM).",
	)
	parser.add_argument(
		"-i",
		"--input",
		dest="input_files",
		nargs="+",
		required=True,
		help="Input file(s) or glob(s) to fix",
	)
	args = parser.parse_args()
	return args


#============================================
def expand_inputs(inputs: list[str]) -> tuple[list[str], list[str]]:
	"""Expand input paths and globs into files.

	Args:
		inputs: Input paths or glob patterns.

	Returns:
		tuple[list[str], list[str]]: (resolved files, missing inputs)
	"""
	resolved = []
	missing = []
	seen = set()
	for entry in inputs:
		matches = glob.glob(entry, recursive=True)
		if matches:
			candidates = matches
		else:
			candidates = [entry]

		found_any = False
		for candidate in candidates:
			if os.path.isfile(candidate):
				if candidate not in seen:
					resolved.append(candidate)
					seen.add(candidate)
				found_any = True
			elif os.path.exists(candidate):
				found_any = True
		if not found_any:
			missing.append(entry)
	return resolved, missing


#============================================
def read_bytes(input_file: str) -> bytes:
	"""Read file bytes.

	Args:
		input_file: Path to the file.

	Returns:
		bytes: File contents.
	"""
	with open(input_file, "rb") as handle:
		data = handle.read()
	return data


#============================================
def normalize_line_endings(data: bytes) -> bytes:
	"""Normalize CRLF and CR line endings to LF.

	Args:
		data: File bytes.

	Returns:
		bytes: Bytes with LF line endings.
	"""
	normalized = data.replace(b"\r\n", b"\n")
	normalized = normalized.replace(b"\r", b"\n")
	return normalized


#============================================
def strip_utf8_bom(data: bytes) -> tuple[bytes, bool]:
	"""Strip a UTF-8 BOM if present.

	Args:
		data: File bytes.

	Returns:
		tuple[bytes, bool]: Updated bytes and a change flag.
	"""
	bom = b"\xef\xbb\xbf"
	if data.startswith(bom):
		return data[len(bom):], True
	return data, False


#============================================
def strip_trailing_whitespace(data: bytes) -> tuple[bytes, bool]:
	"""Strip trailing spaces and tabs from each line.

	Args:
		data: File bytes with LF line endings.

	Returns:
		tuple[bytes, bool]: Updated bytes and a change flag.
	"""
	original = data
	lines = data.split(b"\n")
	fixed_lines = []
	for line in lines:
		fixed_lines.append(line.rstrip(b" \t"))
	fixed = b"\n".join(fixed_lines)
	changed = fixed != original
	return fixed, changed


#============================================
def ensure_final_newline(data: bytes) -> tuple[bytes, bool]:
	"""Ensure the file ends with a single LF if non-empty.

	Args:
		data: File bytes with LF line endings.

	Returns:
		tuple[bytes, bool]: Updated bytes and a change flag.
	"""
	if not data:
		return data, False
	if data.endswith(b"\n"):
		return data, False
	return data + b"\n", True


#============================================
def fix_whitespace_bytes(data: bytes) -> tuple[bytes, bool]:
	"""Apply whitespace fixes.

	Args:
		data: Input bytes.

	Returns:
		tuple[bytes, bool]: Updated bytes and a change flag.
	"""
	original = data

	data, _ = strip_utf8_bom(data)
	data = normalize_line_endings(data)
	data, _ = strip_trailing_whitespace(data)
	data, _ = ensure_final_newline(data)

	changed = data != original
	return data, changed


#============================================
def write_bytes(output_file: str, data: bytes) -> None:
	"""Write bytes back to a file.

	Args:
		output_file: Path to write.
		data: Bytes to write.
	"""
	with open(output_file, "wb") as handle:
		handle.write(data)


#============================================
def main() -> int:
	"""Run the whitespace fixer.

	Returns:
		int: Process exit code.
	"""
	args = parse_args()
	input_files, missing = expand_inputs(args.input_files)
	if missing:
		for entry in missing:
			message = f"{entry}:0:0: file not found"
			print(message, file=sys.stderr)
		return 1
	if not input_files:
		print("No files matched inputs.", file=sys.stderr)
		return 1

	exit_code = 0
	for input_file in input_files:
		data = read_bytes(input_file)
		fixed, changed = fix_whitespace_bytes(data)
		if changed:
			write_bytes(input_file, fixed)
	return exit_code


if __name__ == "__main__":
	raise SystemExit(main())
