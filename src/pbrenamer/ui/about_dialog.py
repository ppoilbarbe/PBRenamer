"""About dialog."""

from __future__ import annotations

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

        icon = QApplication.windowIcon()
        if not icon.isNull():
            self._ui.lblIcon.setPixmap(icon.pixmap(64, 64))
