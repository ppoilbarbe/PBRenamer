"""Normalise PO files after pybabel update.

- Resets POT-Creation-Date to a fixed sentinel (the .pot is untracked, so its
  timestamp would otherwise generate a spurious diff on every run).
- Strips the version number from Project-Id-Version so it never needs updating.
- Removes obsolete entries (lines starting with #~) left by pybabel update.
- Removes trailing comment-only lines (e.g. # AUTO markers) left at EOF.

Called by `make translate` immediately after `pybabel update`, and with
`--docs` by `make docs-translate` after `sphinx-intl update`: the user guide
catalogs live in subdirectories of docs/locale/<lang>/LC_MESSAGES/, one per
documentation page, and get the same normalisation.
"""

import argparse
import re
from pathlib import Path

POT_DATE_SENTINEL = "2001-01-01 00:00+0000"

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument(
    "locale_dir", nargs="?", type=Path, default=Path("src/pbrenamer/locale")
)
parser.add_argument(
    "--docs",
    action="store_true",
    help="Sphinx documentation catalogs: also look into subdirectories",
)
args = parser.parse_args()
locale_dir: Path = args.locale_dir
pattern = "*/LC_MESSAGES/**/*.po" if args.docs else "*/LC_MESSAGES/*.po"

# In PO files the header strings use literal \n (two chars: backslash + n).
# re.sub replacement strings also interpret \n, so we must use a callable to
# prevent double interpretation.
_DATE_RE = re.compile(r'"POT-Creation-Date: [^\\"]+\\n"')
_VER_RE = re.compile(r'"Project-Id-Version: [^\\"]+\\n"')
# Obsolete entries: one or more consecutive lines beginning with #~, plus the
# blank line that separates them from the next block.
_OBSOLETE_RE = re.compile(r"(?:^#~[^\n]*\n)+\n?", re.MULTILINE)
# Location comments (#: file.py:line) injected by pybabel when --no-location is omitted.
_LOCATION_RE = re.compile(r"^#:[ \t][^\n]*\n", re.MULTILINE)

for po in sorted(locale_dir.glob(pattern)):
    text = po.read_text(encoding="utf-8")
    new = _DATE_RE.sub(lambda _: f'"POT-Creation-Date: {POT_DATE_SENTINEL}\\n"', text)
    new = _VER_RE.sub(lambda _: '"Project-Id-Version: PBRenamer\\n"', new)
    new = _OBSOLETE_RE.sub("", new)
    new = _LOCATION_RE.sub("", new)
    # Strip trailing comment-only and blank lines (e.g. # AUTO markers left by pybabel).
    lines = new.splitlines()
    while lines and (lines[-1].lstrip().startswith("#") or lines[-1].strip() == ""):
        lines.pop()
    new = "\n".join(lines).rstrip("\n") + "\n"
    if new != text:
        po.write_text(new, encoding="utf-8")
