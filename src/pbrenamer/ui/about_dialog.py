"""About dialog."""

from __future__ import annotations

import sys
from email.utils import getaddresses
from importlib.metadata import metadata

from PySide6 import __version__ as _pyside_version
from PySide6.QtWidgets import QApplication, QDialog

from pbrenamer import __version__
from pbrenamer.ui.about_dialog_ui import Ui_AboutDialog


class AboutDialog(QDialog):
    """Application About dialog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ui = Ui_AboutDialog()
        self._ui.setupUi(self)

        self._ui.lblVersion.setText(__version__)
        self._ui.lblAuthors.setText(_authors_html())
        py = sys.version_info
        self._ui.lblPythonVersion.setText(f"Python {py.major}.{py.minor}.{py.micro}")
        self._ui.lblPySideVersion.setText(f"PySide6 {_pyside_version}")

        icon = QApplication.windowIcon()
        if not icon.isNull():
            self._ui.lblIcon.setPixmap(icon.pixmap(64, 64))


def _authors_html() -> str:
    try:
        meta = metadata("pbrenamer")
        raw = meta.get_all("Author-email") or []
        pairs = getaddresses(raw)
    except Exception:  # noqa: BLE001
        pairs = []

    parts = []
    for name, addr in pairs:
        label = name or addr
        if addr:
            parts.append(f'<a href="mailto:{addr}">{label}</a>')
        else:
            parts.append(label)
    return ", ".join(parts)
