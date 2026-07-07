#!/usr/bin/env python3
import argparse
import os
import re
import sys
import unicodedata


#============================================
def parse_args() -> argparse.Namespace:
	"""
	Parse command-line arguments.

	Returns:
		argparse.Namespace: Parsed arguments.
	"""
	parser = argparse.ArgumentParser(
		description="Fix a file for ISO-8859-1/ASCII compliance.",
	)
	parser.add_argument(
		"-i",
		"--input",
		dest="input_file",
		required=True,
		help="Input file to fix",
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
def normalize_line_endings(text: str) -> str:
	"""
	Normalize line endings to LF.

	Args:
		text: Input text.

	Returns:
		str: Text with LF line endings.
	"""
	normalized = text.replace("\r\n", "\n")
	normalized = normalized.replace("\r", "\n")
	return normalized


#============================================
def remove_combining_marks(text: str) -> str:
	"""
	Remove Unicode combining marks.

	Args:
		text: Input text.

	Returns:
		str: Text without combining marks.
	"""
	chars = []
	for char in text:
		if unicodedata.combining(char):
			continue
		chars.append(char)
	result = "".join(chars)
	return result


#============================================
def apply_simple_fixes(text: str) -> tuple[str, bool]:
	"""
	Apply simple replacements for ASCII/ISO-8859-1 compliance.

	Args:
		text: Input text.

	Returns:
		tuple[str, bool]: Updated text and a change flag.
	"""
	original = text

	# Normalize line endings to a consistent LF style.
	fixed_text = normalize_line_endings(original)

	# Remove accents by decomposing and stripping combining marks.
	normalized_text = unicodedata.normalize("NFD", fixed_text)
	fixed_text = remove_combining_marks(normalized_text)

	# Replace non-breaking spaces with regular spaces.
	fixed_text = fixed_text.replace("\u00A0", " ")
	fixed_text = fixed_text.replace("\u2004", " ")
	fixed_text = fixed_text.replace("\u2005", " ")
	fixed_text = fixed_text.replace("\uFEFF", " ")

	# Replace curly quotes and apostrophes with straight equivalents.
	fixed_text = re.sub(r"[\u201C\u201D]", '"', fixed_text)
	fixed_text = re.sub(r"[\u2018\u2019]", "'", fixed_text)

	# Replace angle quotes with straight double quotes.
	fixed_text = re.sub(r"[\u00AB\u00BB]", '"', fixed_text)

	# Replace dash-like characters with a simple hyphen.
	fixed_text = re.sub(
		r"[\u2010-\u2015\u2212\u2043\u2E3A\u2E3B\uFE58\uFE63\uFF0D]",
		"-",
		fixed_text,
	)

	# Replace ellipsis with three dots.
	fixed_text = fixed_text.replace("\u2026", "...")

	# Replace arrow characters with ASCII or HTML-entity equivalents.
	fixed_text = fixed_text.replace("\u2192", "->")        # rightwards arrow
	fixed_text = fixed_text.replace("\u2190", "<-")        # leftwards arrow
	fixed_text = fixed_text.replace("\u2194", "<->")       # left-right arrow
	fixed_text = fixed_text.replace("\u21C4", "<->")       # rightwards arrow over leftwards arrow
	fixed_text = fixed_text.replace("\u21C6", "<~>")       # leftwards arrow over rightwards arrow
	fixed_text = fixed_text.replace("\u21D0", "<=")        # leftwards double arrow
	fixed_text = fixed_text.replace("\u21D2", "=>")        # rightwards double arrow
	fixed_text = fixed_text.replace("\u21D4", "<=>")       # left-right double arrow
	fixed_text = fixed_text.replace("\u2191", "&uarr;")    # upwards arrow
	fixed_text = fixed_text.replace("\u2193", "&darr;")    # downwards arrow

	# Replace bullet points and middot with an asterisk.
	fixed_text = fixed_text.replace("\u2022", "*")
	fixed_text = fixed_text.replace("\u00B7", "*")

	# Replace checkmarks and crosses. The two-token forms come first so
	# "<check> Yes" -> "Yes" wins over the bare-checkmark rule below.
	# Bare-form replacements follow docs/MARKDOWN_STYLE.md alternatives:
	# checkmark -> "[OK]" (or "OK"/"YES"), cross -> "[x]" (or "NO"/"FAIL"/"[ ]").
	fixed_text = fixed_text.replace("\u2713 Yes", "Yes")
	fixed_text = fixed_text.replace("\u2717 No", "No")
	fixed_text = fixed_text.replace("\u2713", "[OK]")   # check mark
	fixed_text = fixed_text.replace("\u2705", "[OK]")   # white heavy check mark
	fixed_text = fixed_text.replace("\u2611", "[OK]")   # ballot box with check
	fixed_text = fixed_text.replace("\u2717", "[x]")    # ballot x
	fixed_text = fixed_text.replace("\u274C", "[x]")    # cross mark
	fixed_text = fixed_text.replace("\u2610", "[x]")    # ballot box

	# Greek capital letters as HTML entities (matches the &micro; convention).
	fixed_text = fixed_text.replace("\u0391", "&Alpha;")
	fixed_text = fixed_text.replace("\u0392", "&Beta;")
	fixed_text = fixed_text.replace("\u0393", "&Gamma;")
	fixed_text = fixed_text.replace("\u0394", "&Delta;")
	fixed_text = fixed_text.replace("\u0395", "&Epsilon;")
	fixed_text = fixed_text.replace("\u0396", "&Zeta;")
	fixed_text = fixed_text.replace("\u0397", "&Eta;")
	fixed_text = fixed_text.replace("\u0398", "&Theta;")
	fixed_text = fixed_text.replace("\u0399", "&Iota;")
	fixed_text = fixed_text.replace("\u039A", "&Kappa;")
	fixed_text = fixed_text.replace("\u039B", "&Lambda;")
	fixed_text = fixed_text.replace("\u039C", "&Mu;")
	fixed_text = fixed_text.replace("\u039D", "&Nu;")
	fixed_text = fixed_text.replace("\u039E", "&Xi;")
	fixed_text = fixed_text.replace("\u039F", "&Omicron;")
	fixed_text = fixed_text.replace("\u03A0", "&Pi;")
	fixed_text = fixed_text.replace("\u03A1", "&Rho;")
	fixed_text = fixed_text.replace("\u03A3", "Sum()")
	fixed_text = fixed_text.replace("\u03A4", "&Tau;")
	fixed_text = fixed_text.replace("\u03A5", "&Upsilon;")
	fixed_text = fixed_text.replace("\u03A6", "&Phi;")
	fixed_text = fixed_text.replace("\u03A7", "&Chi;")
	fixed_text = fixed_text.replace("\u03A8", "&Psi;")
	fixed_text = fixed_text.replace("\u03A9", "&Omega;")

	# Greek lowercase letters as HTML entities. \u03BC stays mapped to
	# &micro; (SI-prefix convention); &mu; would also render correctly.
	fixed_text = fixed_text.replace("\u03B1", "&alpha;")
	fixed_text = fixed_text.replace("\u03B2", "&beta;")
	fixed_text = fixed_text.replace("\u03B3", "&gamma;")
	fixed_text = fixed_text.replace("\u03B4", "&delta;")
	fixed_text = fixed_text.replace("\u03B5", "&epsilon;")
	fixed_text = fixed_text.replace("\u03B6", "&zeta;")
	fixed_text = fixed_text.replace("\u03B7", "&eta;")
	fixed_text = fixed_text.replace("\u03B8", "&theta;")
	fixed_text = fixed_text.replace("\u03B9", "&iota;")
	fixed_text = fixed_text.replace("\u03BA", "&kappa;")
	fixed_text = fixed_text.replace("\u03BB", "&lambda;")
	fixed_text = fixed_text.replace("\u03BC", "&micro;")
	fixed_text = fixed_text.replace("\u03BD", "&nu;")
	fixed_text = fixed_text.replace("\u03BE", "&xi;")
	fixed_text = fixed_text.replace("\u03BF", "&omicron;")
	fixed_text = fixed_text.replace("\u03C0", "&pi;")
	fixed_text = fixed_text.replace("\u03C1", "&rho;")
	fixed_text = fixed_text.replace("\u03C2", "&sigmaf;")
	fixed_text = fixed_text.replace("\u03C3", "&sigma;")
	fixed_text = fixed_text.replace("\u03C4", "&tau;")
	fixed_text = fixed_text.replace("\u03C5", "&upsilon;")
	fixed_text = fixed_text.replace("\u03C6", "&phi;")
	fixed_text = fixed_text.replace("\u03C7", "&chi;")
	fixed_text = fixed_text.replace("\u03C8", "&psi;")
	fixed_text = fixed_text.replace("\u03C9", "&omega;")

	# Currency and trademark symbols.
	fixed_text = fixed_text.replace("\u20AC", "&euro;")
	fixed_text = fixed_text.replace("\u2122", "&trade;")

	# Subscripts and superscripts as numeric HTML entities.
	fixed_text = fixed_text.replace("\u2080", "&#x2080;") # subscript 0
	fixed_text = fixed_text.replace("\u2081", "&#x2081;") # subscript 1
	fixed_text = fixed_text.replace("\u2082", "&#x2082;") # subscript 2
	fixed_text = fixed_text.replace("\u2083", "&#x2083;") # subscript 3
	fixed_text = fixed_text.replace("\u2084", "&#x2084;") # subscript 4
	fixed_text = fixed_text.replace("\u2085", "&#x2085;") # subscript 5
	fixed_text = fixed_text.replace("\u2086", "&#x2086;") # subscript 6
	fixed_text = fixed_text.replace("\u2087", "&#x2087;") # subscript 7
	fixed_text = fixed_text.replace("\u2088", "&#x2088;") # subscript 8
	fixed_text = fixed_text.replace("\u2089", "&#x2089;") # subscript 9
	fixed_text = fixed_text.replace("\u00B2", "&sup2;")   # superscript 2 (ISO-8859-1, kept for clarity)
	fixed_text = fixed_text.replace("\u00B3", "&sup3;")   # superscript 3 (ISO-8859-1, kept for clarity)
	fixed_text = fixed_text.replace("\u2070", "&#x2070;") # superscript 0
	fixed_text = fixed_text.replace("\u2074", "&#x2074;") # superscript 4
	fixed_text = fixed_text.replace("\u2075", "&#x2075;") # superscript 5
	fixed_text = fixed_text.replace("\u2076", "&#x2076;") # superscript 6
	fixed_text = fixed_text.replace("\u2077", "&#x2077;") # superscript 7
	fixed_text = fixed_text.replace("\u2078", "&#x2078;") # superscript 8
	fixed_text = fixed_text.replace("\u2079", "&#x2079;") # superscript 9

	# Replace multiplication and division signs.
	fixed_text = fixed_text.replace("\u00D7", "x")
	fixed_text = fixed_text.replace("\u00F7", "/")

	# Replace common mathematical symbols.
	fixed_text = fixed_text.replace("\u2260", "!=")
	fixed_text = fixed_text.replace("\u2264", "<=")
	fixed_text = fixed_text.replace("\u2265", ">=")
	fixed_text = fixed_text.replace("\u00B1", "+/-")
	fixed_text = fixed_text.replace("\u2248", "~")
	fixed_text = fixed_text.replace("\u2261", "&equiv;")   # identical to
	fixed_text = fixed_text.replace("\u2245", "&cong;")    # approximately equal to
	fixed_text = fixed_text.replace("\u221D", "&prop;")    # proportional to
	fixed_text = fixed_text.replace("\u221E", "&infin;")   # infinity
	fixed_text = fixed_text.replace("\u221A", "&radic;")   # square root
	fixed_text = fixed_text.replace("\u2211", "&sum;")     # n-ary summation
	fixed_text = fixed_text.replace("\u220F", "&prod;")    # n-ary product
	fixed_text = fixed_text.replace("\u2202", "&part;")    # partial differential
	fixed_text = fixed_text.replace("\u2207", "&nabla;")   # nabla / del
	fixed_text = fixed_text.replace("\u222B", "&int;")     # integral

	# Set theory operators.
	fixed_text = fixed_text.replace("\u2208", "&isin;")    # element of
	fixed_text = fixed_text.replace("\u2209", "&notin;")   # not an element of
	fixed_text = fixed_text.replace("\u220B", "&ni;")      # contains as member
	fixed_text = fixed_text.replace("\u2229", "&cap;")     # intersection
	fixed_text = fixed_text.replace("\u222A", "&cup;")     # union
	fixed_text = fixed_text.replace("\u2282", "&sub;")     # subset of
	fixed_text = fixed_text.replace("\u2283", "&sup;")     # superset of
	fixed_text = fixed_text.replace("\u2286", "&sube;")    # subset of or equal to
	fixed_text = fixed_text.replace("\u2287", "&supe;")    # superset of or equal to
	fixed_text = fixed_text.replace("\u2205", "&empty;")   # empty set

	# Logical quantifiers and operators.
	fixed_text = fixed_text.replace("\u2200", "&forall;")  # for all
	fixed_text = fixed_text.replace("\u2203", "&exist;")   # there exists
	fixed_text = fixed_text.replace("\u2227", "&and;")     # logical and
	fixed_text = fixed_text.replace("\u2228", "&or;")      # logical or
	fixed_text = fixed_text.replace("\u22A5", "&perp;")    # perpendicular / up tack

	# Replace box-drawing characters with ASCII equivalents.
	fixed_text = fixed_text.replace("\u2500", "-")   # horizontal line
	fixed_text = fixed_text.replace("\u2502", "|")   # vertical line
	fixed_text = fixed_text.replace("\u250C", "+")   # top-left corner
	fixed_text = fixed_text.replace("\u2510", "+")   # top-right corner
	fixed_text = fixed_text.replace("\u2514", "+")   # bottom-left corner
	fixed_text = fixed_text.replace("\u2518", "+")   # bottom-right corner
	fixed_text = fixed_text.replace("\u251C", "+")   # left tee
	fixed_text = fixed_text.replace("\u2524", "+")   # right tee
	fixed_text = fixed_text.replace("\u252C", "+")   # top tee
	fixed_text = fixed_text.replace("\u2534", "+")   # bottom tee
	fixed_text = fixed_text.replace("\u253C", "+")   # cross

	# Replace or drop additional symbol-like characters.
	fixed_text = fixed_text.replace("\u037C", "(c)")
	fixed_text = fixed_text.replace("\u200E", "")
	fixed_text = fixed_text.replace("\u200F", "")

	# Remove object replacement characters.
	fixed_text = fixed_text.replace("\uFFFC", "")

	changed = fixed_text != original
	return fixed_text, changed


#============================================
def fix_ascii_compliance(text: str) -> tuple[str, bool]:
	"""
	Fix text for ISO-8859-1 compliance using simple replacements.

	Args:
		text: Input text.

	Returns:
		tuple[str, bool]: Updated text and a change flag.
	"""
	fixed_text, changed = apply_simple_fixes(text)
	return fixed_text, changed


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
def write_text(output_file: str, text: str) -> None:
	"""
	Write UTF-8 text back to a file.

	Args:
		output_file: Path to write.
		text: Text to write.
	"""
	with open(output_file, "w", encoding="utf-8", newline="\n") as handle:
		handle.write(text)


#============================================
def main() -> int:
	"""
	Run the ISO-8859-1/ASCII compliance fixer.

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

	fixed_text, changed = fix_ascii_compliance(content)
	issues = find_non_latin1_chars(fixed_text)

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

	if changed:
		write_text(input_file, fixed_text)

	if issues:
		return 1
	if changed:
		return 2
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
