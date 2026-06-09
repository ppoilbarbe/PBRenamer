"""Normalise PO headers after pybabel update.

- Resets POT-Creation-Date to a fixed sentinel (the .pot is untracked, so its
  timestamp would otherwise generate a spurious diff on every run).
- Strips the version number from Project-Id-Version so it never needs updating.
- Removes obsolete entries (lines starting with #~) left by pybabel update.

Called by `make translate` immediately after `pybabel update`.
"""

import re
import sys
from pathlib import Path

POT_DATE_SENTINEL = "2001-01-01 00:00+0000"
locale_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("src/pbrenamer/locale")

# In PO files the header strings use literal \n (two chars: backslash + n).
# re.sub replacement strings also interpret \n, so we must use a callable to
# prevent double interpretation.
_DATE_RE = re.compile(r'"POT-Creation-Date: [^\\"]+\\n"')
_VER_RE = re.compile(r'"Project-Id-Version: [^\\"]+\\n"')
# Obsolete entries: one or more consecutive lines beginning with #~, plus the
# blank line that separates them from the next block.
_OBSOLETE_RE = re.compile(r"(?:^#~[^\n]*\n)+\n?", re.MULTILINE)

for po in sorted(locale_dir.glob("*/LC_MESSAGES/*.po")):
    text = po.read_text(encoding="utf-8")
    new = _DATE_RE.sub(lambda _: f'"POT-Creation-Date: {POT_DATE_SENTINEL}\\n"', text)
    new = _VER_RE.sub(lambda _: '"Project-Id-Version: PBRenamer\\n"', new)
    new = _OBSOLETE_RE.sub("", new)
    new = new.rstrip("\n") + "\n"
    if new != text:
        po.write_text(new, encoding="utf-8")
