"""Non-modal window listing the content of the undo stack, most recent first."""

from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from pbrenamer.core.undo import (
    CopyEntry,
    DeleteEntry,
    ExifResetEntry,
    MoveEntry,
    RenameEntry,
    RotationEntry,
    UndoEntry,
    UndoManager,
)
from pbrenamer.ui.geometry_mixin import GeometryMixin

# Files listed under an entry; the rest is summed up in one line.
MAX_DETAILS = 500


def _pair_text(src: str, dst: str) -> str:
    """“old → new”, with names only when both are in the same folder."""
    if os.path.dirname(src) == os.path.dirname(dst):
        return f"{os.path.basename(src)} → {os.path.basename(dst)}"
    return f"{src} → {dst}"


def describe(entry: UndoEntry) -> tuple[str, list[str]]:
    """Return (label, detail lines) of *entry*."""
    if isinstance(entry, RenameEntry):
        return _("Rename"), [_pair_text(s, d) for s, d in entry.pairs]
    if isinstance(entry, MoveEntry):
        return _("Move"), [_pair_text(s, d) for s, d in entry.pairs]
    if isinstance(entry, CopyEntry):
        return _("Copy"), [_pair_text(s, d) for s, d in entry.pairs]
    if isinstance(entry, RotationEntry):
        return _("Rotation"), [path for path, _op, _orient in entry.items]
    if isinstance(entry, ExifResetEntry):
        return _("EXIF orientation reset"), [path for path, _orient in entry.items]
    if isinstance(entry, DeleteEntry):
        label = (
            _("Move to the system trash")
            if entry.system
            else _("Move to the session trash")
        )
        return label, [original for original, _trashed in entry.items]
    return type(entry).__name__, []


class UndoStackDialog(GeometryMixin, QDialog):
    """Show the undo stack, kept up to date while it changes; use show()."""

    def __init__(self, undo: UndoManager, window_state, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(_("Undo stack"))
        self._init_geometry(window_state, "undo_stack")
        self._undo = undo
        # Entry of each top-level item of the tree, in order.
        self._shown: list[UndoEntry] = []

        self.lblHint = QLabel(
            _("The most recent operation is at the top: Undo reverts it first."),
            self,
        )
        self.lblHint.setWordWrap(True)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels([_("Operation"), _("Time")])
        self.tree.setUniformRowHeights(True)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        self.lblEmpty = QLabel(_("The undo stack is empty."), self)
        self.lblEmpty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addWidget(self.lblHint)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.lblEmpty)
        layout.addWidget(buttons)
        self.resize(640, 420)

        undo.add_listener(self._on_stack_changed)
        self.destroyed.connect(lambda: undo.remove_listener(self._on_stack_changed))
        self.refresh()

    def _on_stack_changed(self) -> None:
        if self.isVisible():
            self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the list from the stack, keeping the expanded entries."""
        expanded = {
            id(entry)
            for i, entry in enumerate(self._shown)
            if self.tree.topLevelItem(i).isExpanded()
        }
        self.tree.clear()
        entries = self._undo.entries()
        self._shown = [entry for entry, _added in entries]
        for entry, added in entries:
            label, details = describe(entry)
            text = _("{label} ({n} file(s))").format(label=label, n=len(details))
            item = QTreeWidgetItem([text, time.strftime("%X", time.localtime(added))])
            item.setToolTip(1, time.strftime("%c", time.localtime(added)))
            for line in details[:MAX_DETAILS]:
                child = QTreeWidgetItem([line])
                child.setToolTip(0, line)
                item.addChild(child)
            if len(details) > MAX_DETAILS:
                item.addChild(
                    QTreeWidgetItem(
                        [_("… and {n} more").format(n=len(details) - MAX_DETAILS)]
                    )
                )
            self.tree.addTopLevelItem(item)
            item.setExpanded(id(entry) in expanded)
        self.tree.setVisible(bool(entries))
        self.lblEmpty.setVisible(not entries)
