"""Settings dialog — language, log level, and extension normalization table."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QListWidgetItem

from pbrenamer import i18n, settings
from pbrenamer.ui.geometry_mixin import GeometryMixin
from pbrenamer.ui.settings_dialog_ui import Ui_SettingsDialog


class SettingsDialog(GeometryMixin, QDialog):
    """Application settings dialog."""

    def __init__(self, window_state, parent=None) -> None:
        super().__init__(parent)
        self._ui = Ui_SettingsDialog()
        self._ui.setupUi(self)
        self._init_geometry(window_state, "settings_dialog")

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

        self._ui.chkRestoreLastDir.setChecked(settings.get_restore_last_dir())
        self._ui.chkRestoreToolbarState.setChecked(settings.get_restore_toolbar_state())
        self._ui.spnPreviewDelay.setValue(settings.get_preview_delay())

        self._ui.buttonBox.accepted.connect(self._save_and_accept)

        self._ui.btnExtensionAdd.clicked.connect(self._on_add_extension)
        self._ui.edtExtensionFrom.returnPressed.connect(self._on_add_extension)
        self._ui.edtExtensionTo.returnPressed.connect(self._on_add_extension)
        self._ui.btnExtensionRemove.clicked.connect(self._on_remove_extension)
        self._ui.btnExtensionClear.clicked.connect(self._on_clear_extension)
        self._reload_extension_pairs()

    def _save_and_accept(self) -> None:
        i18n.set_language_override(self._ui.cmbLanguage.currentData())
        level = self._ui.cmbLogLevel.currentText()
        settings.set_log_level(level)
        settings.apply_log_level(level)
        settings.set_restore_last_dir(self._ui.chkRestoreLastDir.isChecked())
        settings.set_restore_toolbar_state(self._ui.chkRestoreToolbarState.isChecked())
        settings.set_preview_delay(self._ui.spnPreviewDelay.value())
        self.accept()

    # ── Extension normalization tab ──────────────────────────────────────────

    def _reload_extension_pairs(self) -> None:
        self._ui.lstExtensionPairs.clear()
        for from_ext, to_ext in settings.get_extension_normalization():
            item = QListWidgetItem(f"{from_ext}  →  {to_ext}")
            item.setData(Qt.ItemDataRole.UserRole, (from_ext, to_ext))
            self._ui.lstExtensionPairs.addItem(item)

    def _on_add_extension(self) -> None:
        from_ext = self._ui.edtExtensionFrom.text().strip().lstrip(".")
        to_ext = self._ui.edtExtensionTo.text().strip().lstrip(".")
        if not from_ext or not to_ext:
            return
        pairs = settings.get_extension_normalization()
        pairs.append((from_ext, to_ext))
        settings.set_extension_normalization(pairs)
        self._ui.edtExtensionFrom.clear()
        self._ui.edtExtensionTo.clear()
        self._reload_extension_pairs()

    def _on_remove_extension(self) -> None:
        selected_rows = {
            self._ui.lstExtensionPairs.row(it)
            for it in self._ui.lstExtensionPairs.selectedItems()
        }
        pairs = settings.get_extension_normalization()
        settings.set_extension_normalization(
            [p for i, p in enumerate(pairs) if i not in selected_rows]
        )
        self._reload_extension_pairs()

    def _on_clear_extension(self) -> None:
        settings.set_extension_normalization([])
        self._reload_extension_pairs()
