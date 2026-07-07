#!/usr/bin/env python3
import argparse
import os
import sys


#============================================
def parse_args() -> argparse.Namespace:
	"""
	Parse command-line arguments.

	Returns:
		argparse.Namespace: Parsed arguments.
	"""
	parser = argparse.ArgumentParser(
		description="Check a file for ISO-8859-1/ASCII compliance.",
	)
	parser.add_argument(
		"-i",
		"--input",
		dest="input_file",
		required=True,
		help="Input file to check",
	)
	args = parser.parse_args()
	return args


#============================================
def read_text(input_file: str) -> tuple[str, str]:
	"""
	Read UTF-8 text from a file.

	Args:
		input_file: Path to the file.

	Returns:
		tuple[str, str]: File contents and an error string (empty if ok).
	"""
	content = ""
	error = ""
	try:
		with open(input_file, "rb") as handle:
			raw_bytes = handle.read()
		content = raw_bytes.decode("utf-8")
	except UnicodeDecodeError as exc:
		byte_index = exc.start
		line_number = raw_bytes.count(b"\n", 0, byte_index) + 1
		last_newline = raw_bytes.rfind(b"\n", 0, byte_index)
		if last_newline == -1:
			column_number = byte_index + 1
		else:
			column_number = byte_index - last_newline
		error = (
			f"{input_file}:{line_number}:{column_number}: "
			f"invalid utf-8 sequence at byte {byte_index}"
		)
	return content, error


#============================================
#============================================
def find_non_latin1_chars(text: str) -> list[tuple[int, int, int]]:
	"""
	Find non-ISO-8859-1 characters in text.

	Args:
		text: Input text.

	Returns:
		list[tuple[int, int, int]]: Line, column, and codepoint for each issue.
	"""
	issues = []
	line_number = 1
	column_number = 0
	for char in text:
		if char == "\n":
			line_number += 1
			column_number = 0
			continue
		column_number += 1
		codepoint = ord(char)
		if codepoint > 255:
			issues.append((line_number, column_number, codepoint))
	return issues


#============================================
def check_ascii_compliance(text: str) -> list[tuple[int, int, int]]:
	"""
	Check text for non-ISO-8859-1 characters.

	Args:
		text: Input text.

	Returns:
		list[tuple[int, int, int]]: Line, column, and codepoint for each issue.
	"""
	issues = find_non_latin1_chars(text)
	return issues


#============================================
def main() -> int:
	"""
	Run the ISO-8859-1/ASCII compliance check.

	Returns:
		int: Process exit code.
	"""
	args = parse_args()
	input_file = args.input_file

	if not os.path.isfile(input_file):
		message = f"{input_file}:0:0: file not found"
		print(message, file=sys.stderr)
		return 1

	content, read_error = read_text(input_file)
	if read_error:
		print(read_error, file=sys.stderr)
		return 1

	issues = check_ascii_compliance(content)

	for line_number, column_number, codepoint in issues:
		display_char = chr(codepoint)
		if not display_char.isprintable():
			display_char = "?"
		codepoint_text = f"U+{codepoint:04X}"
		message = (
			f"{input_file}:{line_number}:{column_number}: "
			f"non-ISO-8859-1 character {codepoint_text} {display_char}"
		)
		print(message, file=sys.stderr)

	if issues:
		total = len(issues)
		total_message = f"{input_file}:0:0: found {total} non-ISO-8859-1 characters"
		print(total_message, file=sys.stderr)

	if issues:
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
