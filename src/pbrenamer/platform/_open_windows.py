"""Windows file-open helpers (ported from PBPicat)."""

from __future__ import annotations

import os
from pathlib import Path


def open_default(path: str | Path) -> None:
    os.startfile(str(path))  # type: ignore[attr-defined]


def last_app(path: str | Path) -> str | None:
    """The system "Open with" dialog does not tell the application chosen:
    there is never a last one."""
    return None


def open_with_last(path: str | Path) -> bool:
    return False


def open_with(path: str | Path, parent=None) -> None:
    try:
        os.startfile(str(path), "openas")  # type: ignore[attr-defined]
    except OSError:
        open_default(path)
