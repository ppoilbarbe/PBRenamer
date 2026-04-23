"""Settings dialog — language override and other preferences."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from pbrenamer import i18n


class SettingsDialog(QDialog):
    """Application settings dialog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Settings"))
        self.setMinimumWidth(340)

        self._combo = QComboBox()
        self._combo.addItem(_("System default"), userData="")
        for code, name in i18n.available_languages():
            self._combo.addItem(f"{name} ({code})", userData=code)

        saved = i18n.get_language_override()
        if saved:
            idx = self._combo.findData(saved)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)

        notice = QLabel(
            _("A restart is required for the language change to take effect.")
        )
        notice.setWordWrap(True)

        form = QFormLayout()
        form.addRow(_("Language:"), self._combo)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(notice)
        layout.addWidget(buttons)

    def _save_and_accept(self) -> None:
        i18n.set_language_override(self._combo.currentData())
        self.accept()
