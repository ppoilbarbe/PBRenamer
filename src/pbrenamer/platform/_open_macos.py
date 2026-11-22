"""macOS file-open helpers (ported from PBPicat)."""

from __future__ import annotations

import mimetypes
import subprocess
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog


def open_default(path: str | Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def _type_key(path: str | Path) -> str:
    """Key of the remembered application: the MIME type guessed from the
    extension, else the lower-case extension."""
    mime, _encoding = mimetypes.guess_type(str(path))
    return mime or Path(path).suffix.lower()


def open_with(path: str | Path, parent=None) -> None:
    app, ok = QInputDialog.getText(
        parent, _("Open with"), _("Application name:"), text=last_app(path) or ""
    )
    if ok and app.strip():
        _remember(path, app.strip())
        subprocess.Popen(["open", "-a", app.strip(), str(path)])
    else:
        open_default(path)


def _remember(path: str | Path, app: str) -> None:
    key = _type_key(path)
    if not key:
        return
    from pbrenamer import settings

    data = settings.get_open_with_lru()
    data[key] = [app] + [a for a in data.get(key, []) if a != app]
    try:
        settings.set_open_with_lru(data)
    except OSError:
        pass


def last_app(path: str | Path) -> str | None:
    """Application last chosen with "Open with" for the type of *path*."""
    key = _type_key(path)
    if not key:
        return None
    from pbrenamer import settings

    apps = settings.get_open_with_lru().get(key, [])
    return apps[0] if apps else None


def open_with_last(path: str | Path) -> bool:
    app = last_app(path)
    if app is None:
        return False
    subprocess.Popen(["open", "-a", app, str(path)])
    return True
