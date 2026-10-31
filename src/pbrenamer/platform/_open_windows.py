"""Windows file-open helpers (ported from PBPicat)."""

from __future__ import annotations

import os
from pathlib import Path


def open_default(path: str | Path) -> None:
    os.startfile(str(path))  # type: ignore[attr-defined]


def open_with(path: str | Path, parent=None) -> None:
    try:
        os.startfile(str(path), "openas")  # type: ignore[attr-defined]
    except OSError:
        open_default(path)
