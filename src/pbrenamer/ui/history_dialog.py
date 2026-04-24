"""History management dialog — view, add, and remove pattern presets."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QListWidgetItem

from pbrenamer.ui.history_dialog_ui import Ui_HistoryDialog
from pbrenamer.ui.presets import PatternPresets

_MODE_LABEL = {"pattern": "pat", "regex": "RE", "plain": "txt"}


class HistoryDialog(QDialog):
    """Dialog for viewing, adding, and removing search/replace history entries."""

    def __init__(self, presets: PatternPresets, parent=None) -> None:
        super().__init__(parent)
        self._ui = Ui_HistoryDialog()
        self._ui.setupUi(self)
        self._presets = presets

        self._ui.btnAddSearch.clicked.connect(self._on_add_search)
        self._ui.edtSearch.returnPressed.connect(self._on_add_search)
        self._ui.btnRemoveSearch.clicked.connect(self._on_remove_search)
        self._ui.btnClearSearch.clicked.connect(self._on_clear_search)

        self._ui.btnAddReplace.clicked.connect(self._on_add_replace)
        self._ui.edtReplace.returnPressed.connect(self._on_add_replace)
        self._ui.btnRemoveReplace.clicked.connect(self._on_remove_replace)
        self._ui.btnClearReplace.clicked.connect(self._on_clear_replace)

        self._reload_search()
        self._reload_replace()

    # ── Search ────────────────────────────────────────────────────────────────

    def _reload_search(self) -> None:
        self._ui.lstSearch.clear()
        for mode, pattern in self._presets.get_search():
            label = _MODE_LABEL.get(mode, mode)
            item = QListWidgetItem(f"{pattern}  [{label}]")
            item.setData(Qt.ItemDataRole.UserRole, (mode, pattern))
            self._ui.lstSearch.addItem(item)

    def _on_add_search(self) -> None:
        text = self._ui.edtSearch.text()
        if not text:
            return
        if self._ui.radRegex.isChecked():
            mode = "regex"
        elif self._ui.radPlainText.isChecked():
            mode = "plain"
        else:
            mode = "pattern"
        self._presets.add_search(mode, text)
        self._ui.edtSearch.clear()
        self._reload_search()

    def _on_remove_search(self) -> None:
        selected_rows = {
            self._ui.lstSearch.row(it) for it in self._ui.lstSearch.selectedItems()
        }
        entries = self._presets.get_search()
        self._presets.set_search(
            [e for i, e in enumerate(entries) if i not in selected_rows]
        )
        self._reload_search()

    def _on_clear_search(self) -> None:
        self._presets.set_search([])
        self._reload_search()

    # ── Replace ───────────────────────────────────────────────────────────────

    def _reload_replace(self) -> None:
        self._ui.lstReplace.clear()
        for pattern in self._presets.get_replace():
            self._ui.lstReplace.addItem(pattern)

    def _on_add_replace(self) -> None:
        text = self._ui.edtReplace.text()
        if not text:
            return
        self._presets.add_replace(text)
        self._ui.edtReplace.clear()
        self._reload_replace()

    def _on_remove_replace(self) -> None:
        selected_rows = {
            self._ui.lstReplace.row(it) for it in self._ui.lstReplace.selectedItems()
        }
        entries = self._presets.get_replace()
        self._presets.set_replace(
            [e for i, e in enumerate(entries) if i not in selected_rows]
        )
        self._reload_replace()

    def _on_clear_replace(self) -> None:
        self._presets.set_replace([])
        self._reload_replace()
