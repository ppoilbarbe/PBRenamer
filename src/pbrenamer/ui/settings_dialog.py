"""Settings dialog — language override and log level."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from pbrenamer import i18n, settings
from pbrenamer.ui.settings_dialog_ui import Ui_SettingsDialog


class SettingsDialog(QDialog):
    """Application settings dialog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ui = Ui_SettingsDialog()
        self._ui.setupUi(self)

        self._ui.cmbLanguage.addItem(_("System default"), userData="")
        for code, name in i18n.available_languages():
            self._ui.cmbLanguage.addItem(f"{name} ({code})", userData=code)
        saved_lang = i18n.get_language_override()
        if saved_lang:
            idx = self._ui.cmbLanguage.findData(saved_lang)
            if idx >= 0:
                self._ui.cmbLanguage.setCurrentIndex(idx)

        for level in settings.LEVELS:
            self._ui.cmbLogLevel.addItem(level)
        saved_level = settings.get_log_level()
        idx = self._ui.cmbLogLevel.findText(saved_level)
        if idx >= 0:
            self._ui.cmbLogLevel.setCurrentIndex(idx)

        self._ui.buttonBox.accepted.connect(self._save_and_accept)

    def _save_and_accept(self) -> None:
        i18n.set_language_override(self._ui.cmbLanguage.currentData())
        level = self._ui.cmbLogLevel.currentText()
        settings.set_log_level(level)
        settings.apply_log_level(level)
        self.accept()
