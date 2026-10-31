"""macOS file-open helpers (ported from PBPicat)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog


def open_default(path: str | Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def open_with(path: str | Path, parent=None) -> None:
    app, ok = QInputDialog.getText(parent, _("Open with"), _("Application name:"))
    if ok and app.strip():
        subprocess.Popen(["open", "-a", app.strip(), str(path)])
    else:
        open_default(path)
