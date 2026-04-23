"""System locale detection, cross-platform."""

from __future__ import annotations

import locale
import os


def system_language() -> str:
    """Return the primary BCP-47 language tag for the running system.

    Tries environment variables first (Unix convention), then falls back to
    the ``locale`` module (reliable on Windows and macOS when env vars are
    absent).
    """
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        if val:
            first = val.split(":")[0]
            lang = first.split("_")[0].split(".")[0]
            if lang and lang not in ("", "C", "POSIX"):
                return lang

    loc, _ = locale.getlocale()
    if loc:
        return loc.split("_")[0]

    return "en"
