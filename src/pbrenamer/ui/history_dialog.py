"""History management dialog — pattern presets and schema field histories."""

from __future__ import annotations

import functools
import unicodedata

from PySide6.QtCore import QCollator, QLocale, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pbrenamer import i18n, profiles
from pbrenamer.ui.geometry_mixin import GeometryMixin
from pbrenamer.ui.history_dialog_ui import Ui_HistoryDialog
from pbrenamer.ui.presets import PatternPresets
from pbrenamer.ui.rule_panel_schema import field_title

_MODE_LABEL = {"pattern": "pat", "regex": "RE", "plain": "txt"}
_LIGATURES = str.maketrans({"Œ": "OE", "œ": "oe", "Æ": "AE", "æ": "ae"})


def sort_fold(text: str) -> str:
    """Fold *text* for a case- and diacritic-insensitive comparison
    (O = o = Ô = Ǫ, Œ = OE = œ)."""
    text = unicodedata.normalize("NFKD", text.translate(_LIGATURES))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.casefold()


def sorted_history(items: list[str], *, reverse: bool = False) -> list[str]:
    """Return *items* sorted with the collation of the current language,
    ignoring case and accents; empty strings stay at the end."""
    collator = QCollator(QLocale(i18n.current_language() or "C"))
    collator.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    non_empty = sorted(
        (s for s in items if s),
        key=functools.cmp_to_key(
            lambda a, b: collator.compare(sort_fold(a), sort_fold(b))
        ),
        reverse=reverse,
    )
    return non_empty + [s for s in items if not s]


class FieldHistoryWidget(QWidget):
    """Editor of one history of the current profile (``history.json`` key):
    reorder, sort, delete.  Every change is saved at once."""

    def __init__(self, key: str, parent=None) -> None:
        super().__init__(parent)
        self.key = key

        root = QHBoxLayout(self)
        self.list = QListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list.addItems(profiles.get_history(key))
        self.list.model().rowsMoved.connect(lambda *_: self._save())
        root.addWidget(self.list, 1)

        buttons = QVBoxLayout()
        buttons.addStretch()
        self.btnUp = self._button(_("▲ Move up"), self._move_up, buttons)
        self.btnDown = self._button(_("▼ Move down"), self._move_down, buttons)
        buttons.addSpacing(12)
        self.btnSortAsc = self._button(_("Sort ↓"), self._sort_ascending, buttons)
        self.btnSortAsc.setToolTip(_("Sort the list in ascending order"))
        self.btnSortDesc = self._button(_("Sort ↑"), self._sort_descending, buttons)
        self.btnSortDesc.setToolTip(_("Sort the list in descending order"))
        buttons.addSpacing(12)
        self.btnDelete = self._button(_("Delete"), self._delete_selected, buttons)
        self.btnClear = self._button(_("Clear all"), self._clear_all, buttons)
        buttons.addStretch()
        root.addLayout(buttons)

        self.list.currentRowChanged.connect(self._update_buttons)
        self._update_buttons(self.list.currentRow())

    def _button(self, text, slot, layout) -> QPushButton:
        button = QPushButton(text, self)
        button.clicked.connect(slot)
        layout.addWidget(button)
        return button

    def items(self) -> list[str]:
        return [self.list.item(i).text() for i in range(self.list.count())]

    def _set_items(self, items: list[str], current: int = -1) -> None:
        self.list.clear()
        self.list.addItems(items)
        self.list.setCurrentRow(current)
        self._save()

    def _save(self) -> None:
        profiles.set_history(self.key, self.items())
        self._update_buttons(self.list.currentRow())

    def _move(self, offset: int) -> None:
        row = self.list.currentRow()
        items = self.items()
        items.insert(row + offset, items.pop(row))
        self._set_items(items, row + offset)

    def _move_up(self) -> None:
        if self.list.currentRow() > 0:
            self._move(-1)

    def _move_down(self) -> None:
        if 0 <= self.list.currentRow() < self.list.count() - 1:
            self._move(1)

    def _sort_ascending(self) -> None:
        self._set_items(sorted_history(self.items()))

    def _sort_descending(self) -> None:
        self._set_items(sorted_history(self.items(), reverse=True))

    def _delete_selected(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            items = self.items()
            del items[row]
            self._set_items(items, min(row, len(items) - 1))

    def _clear_all(self) -> None:
        if not self.list.count():
            return
        reply = QMessageBox.question(
            self,
            _("Clear history"),
            _("Clear all values from this history?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._set_items([])

    def _update_buttons(self, row: int) -> None:
        count = self.list.count()
        self.btnUp.setEnabled(row > 0)
        self.btnDown.setEnabled(0 <= row < count - 1)
        self.btnDelete.setEnabled(row >= 0)
        self.btnClear.setEnabled(count > 0)
        self.btnSortAsc.setEnabled(count >= 2)
        self.btnSortDesc.setEnabled(count >= 2)


class HistoryDialog(GeometryMixin, QDialog):
    """Dialog for viewing, adding, and removing search/replace history entries,
    and for editing the history of each schema field of the current profile."""

    def __init__(self, presets: PatternPresets, window_state, parent=None) -> None:
        super().__init__(parent)
        self._ui = Ui_HistoryDialog()
        self._ui.setupUi(self)
        self._presets = presets
        self._init_geometry(window_state, "history_dialog")

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

        schema_cfg = profiles.get_schema()
        self.field_widgets: list[FieldHistoryWidget] = []
        for i in range(max(1, schema_cfg["field_count"])):
            title = field_title(schema_cfg["field_titles"], i)
            widget = FieldHistoryWidget(f"field_{i}", self._ui.tabs)
            self.field_widgets.append(widget)
            self._ui.tabs.addTab(widget, title)
        self.filter_widget = FieldHistoryWidget("sidecar_filter", self._ui.tabs)
        self._ui.tabs.addTab(self.filter_widget, _("Sidecar filter"))

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
        mode = self._ui.cmbSearchMode.currentData()
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
