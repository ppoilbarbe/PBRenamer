"""Dialog for managing user-defined directory shortcuts."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

import pbrenamer.settings as _cfg


class ShortcutsDialog(QDialog):
    """List, reorder and remove user-defined directory shortcuts."""

    def __init__(self, window_state, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Edit Shortcuts"))
        self.setMinimumSize(480, 320)
        self._window_state = window_state

        geo = window_state.load_geometry("shortcuts_dialog")
        if geo:
            self.restoreGeometry(geo)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)

        self._btn_up = QPushButton(_("Move up"))
        self._btn_down = QPushButton(_("Move down"))
        self._btn_remove = QPushButton(_("Remove"))
        for btn in (self._btn_up, self._btn_down, self._btn_remove):
            btn.setEnabled(False)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._btn_up)
        btn_row.addWidget(self._btn_down)
        btn_row.addWidget(self._btn_remove)
        btn_row.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_("Saved shortcuts:")))
        layout.addWidget(self._list)
        layout.addLayout(btn_row)
        layout.addWidget(buttons)

        self._load()

        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        self._btn_up.clicked.connect(self._on_move_up)
        self._btn_down.clicked.connect(self._on_move_down)
        self._btn_remove.clicked.connect(self._on_remove)
        buttons.rejected.connect(self.reject)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._window_state.save_geometry("shortcuts_dialog", self.saveGeometry())
        super().closeEvent(event)

    def _load(self, select_row: int = -1) -> None:
        self._list.clear()
        for name, path in _cfg.get_shortcuts():
            item = QListWidgetItem(f"{name}  —  {path}")
            item.setData(Qt.ItemDataRole.UserRole, (name, path))
            self._list.addItem(item)
        if 0 <= select_row < self._list.count():
            self._list.setCurrentRow(select_row)

    def _on_selection_changed(self) -> None:
        row = self._list.currentRow()
        count = self._list.count()
        has_sel = row >= 0
        self._btn_up.setEnabled(has_sel and row > 0)
        self._btn_down.setEnabled(has_sel and row < count - 1)
        self._btn_remove.setEnabled(has_sel)

    def _on_move_up(self) -> None:
        row = self._list.currentRow()
        if row <= 0:
            return
        shortcuts = _cfg.get_shortcuts()
        shortcuts[row - 1], shortcuts[row] = shortcuts[row], shortcuts[row - 1]
        _cfg.set_shortcuts(shortcuts)
        self._load(row - 1)

    def _on_move_down(self) -> None:
        row = self._list.currentRow()
        shortcuts = _cfg.get_shortcuts()
        if row < 0 or row >= len(shortcuts) - 1:
            return
        shortcuts[row], shortcuts[row + 1] = shortcuts[row + 1], shortcuts[row]
        _cfg.set_shortcuts(shortcuts)
        self._load(row + 1)

    def _on_remove(self) -> None:
        row = self._list.currentRow()
        shortcuts = _cfg.get_shortcuts()
        item = self._list.currentItem()
        if item is None:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry in shortcuts:
            shortcuts.remove(entry)
        _cfg.set_shortcuts(shortcuts)
        self._load(min(row, len(shortcuts) - 1))
