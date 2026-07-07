# PYTHON_STYLE.md

Language Model guide to Neil python3 programming

## Common misconceptions

AI agents frequently get these wrong. Read the full sections below for details.

- **Fix the design, not the symptom.** When something behaves wrong, fix the design before adding a fallback. See [Design philosophy](REPO_STYLE.md#core-philosophies).
- **Tabs not spaces.** Always indent with tabs. See [USE TABS](#use-tabs).
- **Avoid try/except.** Do not wrap code in try/except blocks. See [CODE STRUCTURE](#code-structure).
- **Do not hide bugs with defaults.** Use `dict[key]` when the key must exist, not `dict.get(key, fallback)`. See [DO NOT HIDE BUGS WITH DEFAULTS](#do-not-hide-bugs-with-defaults).
- **Shebangs only on runnable scripts.** No shebangs on library modules, test files, or helpers. See [CODE STRUCTURE](#code-structure).
- **Argparse minimalism.** Only add flags users frequently change between runs. See [ARGPARSE](#argparse).
- **Import the module, not names from it.** Prefer `import os` over `from os import path`. See [IMPORTING](#importing).
- **No relative imports.** Never use `from . import` or `from ..module import`. See [IMPORTING](#importing).
- **Declare all third-party imports.** Every non-stdlib, non-local import must be in `pip_requirements.txt`. See [IMPORT REQUIREMENTS](#import-requirements).
- **No brittle pytest assertions.** Do not assert on dates, collection sizes, required key lists, hardcoded defaults, or function names. See [PYTEST_STYLE.md](PYTEST_STYLE.md).
- **No `assert` in plain scripts.** All `assert` statements live in `tests/test_*.py`, `tests/playwright/` (browser tests), or `tests/e2e/` (shell/Python E2E). Module-level asserts run on every import and slow script startup. See [ASSERT](#assert).

## Python version

* I like using one of the latest versions of python, but not the latest, of python3, currently **3.12**.
* In this repo, run python commands through the bootstrap pattern:
* `source source_me.sh && python ...`

## FILENAMES
* Prefer snake_case for Python filenames and module names.
* Avoid CamelCase in filenames. Reserve CamelCase for class names.
* Keep filenames descriptive, and consistent with the primary thing the file provides.
* Use only lowercase letters, numbers, and underscores in filenames.

## USE TABS

* Always use tabs for indentation in python3 code, never spaces!
* I disagree with PEP 8 requirement of spaces. Using spaces causes a lot more deleting and formatting work.
* I use tabs exclusively.
* Tabs provide flexibility, because I can change the tab size to 2, 3, 4, or 8 spaces depending on the complexity of the code.

## CODE STRUCTURE

- Use a `def main()` for the backbone of the code, have a `if __name__ == '__main__': main()` to run main
- I prefer single task sub-functions over one large function.
- `args` is reserved for the `argparse.Namespace` returned by `parse_args()`; do not attach derived runtime state to `args` (use local variables, module-level caches, or explicit parameters instead).
- Prefer to avoid module-level global state; when a generator needs expensive precomputed data (lists, parsed files) and the framework requires `write_question(N, args)`, it is acceptable to cache that data in a module-level constant-like variable (ALL_CAPS) initialized in `main()` and treated as read-only during question generation.
- Whenever making a URL or API internet request, add a time.sleep(random.random()) to avoid overloading the server, unless the official API specifies otherwise.
- For error handling, avoid try/except block if you can, I find they cause more problems than they solve.
- Use try/except rarely, and if needed use for at most two lines
- Avoid using `sys.exit(1)` prefer to raise Errors.
- Use f-strings, in older code I used `.format()` or `'%'` system, update to f-strings.
- I prefer string concatenation `'+='` over multiline strings.
- Shebangs apply ONLY to executable scripts - files with a `if __name__ == '__main__':` guard that are meant to be run directly from the command line.
- The required shebang is `#!/usr/bin/env python3` and it must be the very first line. The module docstring comes after it.
- Do NOT add shebangs to library modules, helper files, `__init__.py` files, or test files. These are imported, not executed directly.
- Do not hard-code interpreter paths in shebangs (bad: `#!/opt/homebrew/.../python3.12`).
- Do not use `/usr/bin/python` or `/usr/bin/python3` in shebangs.
- Files with a shebang must also have the executable bit set, and vice versa. See `tests/test_shebangs.py` for enforcement.
- Return statements should be simple and should not perform calculations, fill out a dict, or build strings. Store computed values and assembled strings in variables first, including any multiline HTML or text, then return the variable.
- add comments within the code to describe what different lines are doing, to make for better readability later. especially for complex lines!
- Please only use ascii characters in the script, if utf characters are need they should be escape e.g. `&alpha;` `&lrarr;`

## DO NOT HIDE BUGS WITH DEFAULTS

This section is the Python expression of "fix the design, not the symptom" (see [Design philosophy](REPO_STYLE.md#core-philosophies)). Defensive coding patterns that silently supply fallback values hide bugs instead of exposing them. If a key, attribute, or value is required, access it directly so missing data fails loudly.

- Use `dict[key]` when the key must exist. Do not use `dict.get(key, default)` to paper over missing data.
- Use `dict.get(key, default)` only when the key is genuinely optional and the default is intentional.
- Do not use `value or fallback` to silently replace None, empty strings, or zero. If the value should never be None, fix the source.
- Do not catch broad exceptions to continue silently. `except Exception: pass` hides every possible bug.

### Bad (hides missing keys)

```python
name = config.get("name", "Unknown")
count = data.get("count", 0)
```

### Good (fails on missing required keys)

```python
name = config["name"]
count = data["count"]
```

### Good (genuinely optional with intentional default)

```python
# verbose flag is optional, defaults to off
verbose = config.get("verbose", False)
```

## `__init__.py` FILES

`__init__.py` is not where coders look for bugs, so hiding logic there disguises problems. Keep these files minimal.

- Keep `__init__.py` empty or limited to a one-line docstring.
- No implementation code belongs in `__init__.py`.
- No hardcoded import lines or re-export facades.
- No manually curated lists (`__all__`, `_EXPORTED_MODULES`, etc.).
- No class or function maps (`_MODE_CLASS_MAP`, `_FUNCTION_MAP`, etc.).
- No auto-discovery or registrar logic (put that in a dedicated loader module).
- No aliases except as temporary migration shims (mark with a removal date comment).
- No global variables -- they disguise bugs in a file coders rarely inspect.
- No `__version__` assignments. Version lives in `pyproject.toml` as the single source of truth. Scattering `__version__` across `__init__.py` files is a maintenance nightmare when upgrading.
- No `importlib`-based lazy loaders inline. If a package needs lazy loading for startup performance, put the loader in a dedicated module, not in `__init__.py`.
- Do not add re-exports to satisfy type-checker public API inference. Type checkers that expect names in `__init__.py` can be configured with `py.typed` markers or explicit stubs. Convenience for tooling does not justify cluttering `__init__.py`.
- Every caller should import from submodules directly.

Good:
```python
# __init__.py
"""Package docstring."""
```

Bad:
```python
# __init__.py
from .widget import Widget
from .parser import parse_input
__all__ = ["Widget", "parse_input"]
_CLASS_MAP = {"widget": Widget}
```

Good (caller imports from the submodule):
```python
import mypackage.widget
w = mypackage.widget.Widget()
```

Bad (caller relies on re-exports in `__init__.py`):
```python
import mypackage
w = mypackage.Widget()
```

## QUOTING
* Avoid backslash escaping quotes inside strings when possible.
* Prefer alternating quote styles instead:
* Use double quotes on the outside with single quotes inside.
* Or use single quotes on the outside with double quotes inside.
* This is especially useful for HTML like "<span style='...'>text</span>".

## LAMBDA FUNCTIONS
* Be conservative with lambda. Prefer def for anything more than a simple key or one-liner callback.
* lambda is allowed when used as key= for sorted(), .sort(), min(), or max() and the expression is short and obvious.
* Avoid lambda bodies that call major helper functions or hide important logic. If the lambda is doing real work, name it with def so it is readable, commentable, and testable.
* If the lambda expression would be hard to understand without a comment, replace it with a named function.

Allowed:
gel_set = sorted(gel_set, key=lambda k: k["MW"])
i = max(range(n), key=lambda k: values[k])
villages_sorted = sorted(villages, key=lambda v: totals[v])

Avoid:
choices = sorted(choices, key=lambda k: -compare_sequence(k, consensus_sequence))

Preferred rewrite:
def score_choice(choice: str) -> int:
score = -compare_sequence(choice, consensus_sequence)
return score
choices = sorted(choices, key=score_choice)

## HTML UNITS IN MONOSPACE
* When generating HTML for lab problems, render numeric values and their units in monospace for readability and alignment.
* Use a span like:

volume_text = f"<span style='font-family: monospace;'>{vol1:.1f} mL</span>"

## TESTING

- I like to test the code with **pyflakes** and **mypy**
- create a folder in most projects called tests for storing test scripts
- a good repo-wide pyflakes gate is `tests/test_pyflakes_code_lint.py` (run with pytest)
- For pytest-specific style, test design, and command usage, see [PYTEST_STYLE.md](PYTEST_STYLE.md).
- For slow end-to-end tests run outside pytest, see [E2E_TESTS.md](E2E_TESTS.md).
```bash
pytest tests/test_pyflakes_code_lint.py
```

## DO NOT USE HEREDOCS

* Do not use shell heredocs to run inline Python code.
* Avoid patterns like `python3 - <<EOF`.
* Python code should live in `.py` files or be passed explicitly as files or modules.
* Heredocs make code harder to read, harder to lint, and harder to test.

## ENVIRONMENT VARIABLES

The program should not require custom environment variables to function. Configuration must be explicit and visible via config files or command line arguments. Environment variables may be read only when they are standard OS or ecosystem variables, not variables invented to control program behavior.

### Allowed

```python
home_dir = os.environ["HOME"]
editor = os.environ.get("EDITOR", "nano")
tmp_dir = os.environ.get("TMPDIR", "/tmp")
is_ci = os.environ.get("CI") == "true"
```

### Disallowed

```python
api_key = os.environ["API_KEY"]
preserve_temp = os.environ.get("PRESERVE_TEMP_FILES") == "1"
debug_mode = os.environ.get("DEBUG_MODE") == "true"
```

For api keys, mode settings, or temp variables use argparse, config files, or function arguments instead. Rule of thumb: If a variable exists only because the script exists, it does not belong in the environment.

### Shell defaults

When running Python scripts locally, export these to get unbuffered output and to avoid writing `.pyc` / `__pycache__` garbage files (scripts must still work without them):

```bash
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
```

## COMMENTING

- Assume all import statements have been made at the top of the script file
- Visually separate function with comment of only equal signs. It makes it easier to visually see the functions in the code. For example:
```python
#============================================
```

* Use Google style documentation style for functions. https://github.com/google/styleguide
* I prefer to keep line lengths less than 100 characters
* Comments should be on a line of their own before the code they are commenting
* No emoji or special characters in comments, only ascii characters

## ASSERT

* Do not put `assert` statements in plain `.py` scripts or library modules. All asserts live in `tests/test_*.py`, `tests/playwright/` (browser tests), or `tests/e2e/` (shell/Python E2E).
* Reason: module-level asserts run at import time, which slows CLI startup. Tests pay the cost once, in the test suite.
* Do not assert in functions that require user input or read/write to files; cover those with end-to-end checks instead. See [E2E_TESTS.md](E2E_TESTS.md).
* Keep individual asserts short: under 4 lines and under 100 characters.
* For pytest test structure and good/brittle assert patterns, see [PYTEST_STYLE.md](PYTEST_STYLE.md).

## TYPE HINTING

Type hints are enforced repo-wide by `tests/test_function_typing.py`. Every `def` must carry
type annotations on every parameter (except `self`, `cls`, `*args`, and `**kwargs`) and a
return annotation. For example:

```python
def greater_than(a: int, b: int) -> bool:
	return a > b
```

Use builtin generics (`list`, `dict`, `tuple`, `set`) and PEP 604 unions (`X | None`).
Use `collections.abc` for callable and iterable params (for example `collections.abc.Callable`,
`collections.abc.Iterable`). The `typing` module is not used in this repo.

Good:
```python
def func(arg: dict) -> tuple:
```

Bad (uses `typing` module):
```python
def func(arg: typing.Dict[str, typing.Any]) -> typing.Tuple[str, str, str]:
```

## IMPORTING
* Never use import *
* I prefer to keep the original module names, just import numpy is preferred over import numpy as np.
* This one is flexible but I also prefer to avoid using 'from' in the import statements. 'import PIL.Image' over 'from PIL import Image'. I like to know where commands are coming from.
* Never use relative imports (`from . import`, `from ..module import`). Always use absolute imports so it is clear where every name comes from. See `tests/test_import_dot.py` for enforcement.
* Place import modules in the following order (1) external python/pip modules vs. local repo modules with commented headings (2) length of module name with the shortest first, (3) alphabetical 'os' comes before 're'. For example:

```python
# Standard Library
import os
import re
import sys
import time
import random
import argparse

# PIP3 modules
import numpy
import PIL.Image #python-pillow

# local repo modules
import bptools
import aminoacidlib
```

## IMPORT REQUIREMENTS

Every import in the repo must come from one of three sources:

- **Python standard library** (os, sys, re, etc.)
- **Repo-local modules** (other `.py` files tracked in the same repo)
- **Declared pip dependencies** listed in `pip_requirements.txt` or `pip_requirements-dev.txt`

If you add a new third-party import, add the package to the appropriate requirements file. Some pip packages use a different import name than their package name (e.g., `import yaml` comes from `pyyaml`, `import cv2` comes from `opencv-python`). Known aliases are maintained in `tests/test_import_requirements.py` under `IMPORT_REQUIREMENT_ALIASES`. See `tests/test_import_requirements.py` for enforcement.

## ARGPARSE

### ARGPARSE MINIMALISM

Be conservative. Only add arguments users frequently need to change between runs.

**Good candidates:**
- Input/output file paths
- Mode switches (--dry-run, --verbose, --format)
- Behavior toggles (--recursive, --force)

**Hardcode instead:**
- Backup suffixes, timeout durations, buffer sizes
- Retry counts, column widths, formatting details
- Any "what if someone wants to..." parameters

**Rule:** If you added it thinking "someone might want to configure this", remove it.

#### Over-engineered (bad):
```python
parser.add_argument('-t', '--timeout', type=int, default=30)
parser.add_argument('-r', '--retries', type=int, default=3)
parser.add_argument('-s', '--suffix', default='.bak')
```

#### Minimal (good):
```python
parser.add_argument('-i', '--input', dest='input_file', required=True)
parser.add_argument('-o', '--output', dest='output_file', required=True)
parser.add_argument('-n', '--dry-run', dest='dry_run', action='store_true')
```

### ARGPARSE DETAILS

* Argparse value should have both a single letter cli flag and a full word cli flag. You should always specify the destination for the value, dest='flag_name'. See example below.
* When doing an argparse boolean value. Provide both on and off flags and set the default with a different command, For example,
```python
	parser.add_argument('-e', '--send-email', dest='dry_run', help='send emails', action='store_false')
	parser.add_argument('-n', '--dry-run', dest='dry_run', help='only display email', action='store_true')
	parser.set_defaults(dry_run=True)
```
* I like using argparse groups
```python
	question_group = parser.add_mutually_exclusive_group(required=True)
	question_group.add_argument(
		'-f', '--format', dest='question_format', type=str,
		choices=('num', 'mc'),
	)
	question_group.add_argument(
		'-m', '--mc', dest='question_format', action='store_const', const='mc',
	)
	question_group.add_argument(
		'-n', '--num', dest='question_format', action='store_const', const='num',
		help='Set question format to numeric'
	)
	parser.set_defaults(question_format='mc')
```
* Use a separate function for argparse that returns args to the main() function at start
```python
def parse_args():
	"""
	Parse command-line arguments.
	"""
	parser = argparse.ArgumentParser(description="<replace with script function>")
	parser.add_argument('-i', '--input', dest='input_file', required=True, help="Input file")
	args = parser.parse_args()
	return args
```

## DATA FILES
* YAML favorite, readable, editable
* CSV spreadsheet input/output
* JSON good for large, wordy data
* PNG images, graphics, figures, pixel data

## AVAILABLE MODULES

I keep several pip3 modules installed on all my systems that are available for use

```bash
% cat pip_requirements.txt
accelerate  # Hugging Face helper for running PyTorch training
biopython  # Bioinformatics tools for sequences, structures
brickse  # Brickset related utilities or API client for LEGO set date
crcmod  # Fast CRC checksum functions (CRC-32, CRC-16)
curl_cffi  # HTTP client using libcurl via cffi, for browser-like TLS
einops  # Clean tensor reshaping and rearranging (works with numpy, torch, etc.)
face_recognition  # Simple face detection and recognition built on dlib
google-api-python-client  # Official Google API client for many Google services
gtts  # Google Text-to-Speech client for generating speech audio
imagehash  # Perceptual image hashing for similarity and duplicate detection
lxml  # Fast XML and HTML parsing with XPath support
matplotlib  # Plotting and figure generation
mkdocs-include-markdown-plugin  # MkDocs plugin to include markdown files
mkdocs-material  # Material theme for MkDocs documentation sites
mutagen  # Read and write audio metadata tags (MP3, FLAC, etc.)
num2word  # Convert numbers into words (for example 42 to forty two)
numpy  # Core n-dimensional arrays and vectorized numerical computing
ollama  # Client for interacting with a local Ollama model server
opencv-python  # OpenCV bindings for computer vision and image processing
openpyxl  # Read and write Excel .xlsx files
pandas  # DataFrames for tabular data analysis and ETL
pillow  # Image I O and basic image processing (PIL fork)
pillow_heif  # HEIF and HEIC support for Pillow
py-applescript  # Run AppleScript from Python (macOS automation)
pyexiftool  # Python wrapper for exiftool metadata extraction and editing
pyflakes  # Static analysis to find unused imports and simple errors
pygame  # SDL based multimedia and simple game framework
pytesseract  # Python wrapper for Tesseract OCR
pytest
python-bricklink-api  # BrickLink API client for LEGO parts and orders
pyyaml  # YAML parsing and serialization
qrcode  # QR code generation
rebrick  # Rebrickable API client for LEGO set and parts data
rembg[cli]  # Remove image backgrounds using segmentation models
requests  # Simple HTTP library
rich  # Pretty console output, logging, progress bars, and tracebacks
scipy  # Scientific computing
tabulate  # Pretty print tables in plain text
torch  # PyTorch tensor library and deep learning framework
torchvision  # Vision datasets, transforms, and pretrained models for PyTorch
transformers  # Hugging Face transformer models, tokenizers, and pipelines
transliterate  # Convert text between scripts (for example Cyrillic to Latin)
unidecode  # Best effort conversion of Unicode text to ASCII
wikipedia  # Simple Python interface to Wikipedia search and pages
xmltodict  # Convert XML to nested Python dicts and back
yt-dlp[default]  # Video and audio downloader
```
