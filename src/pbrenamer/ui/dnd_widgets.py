"""Drag-and-drop-enabled tree/list widgets for the main window.

These subclasses only handle Qt drag-and-drop mechanics (accepting or
ignoring events, extracting dropped URLs, resolving the target directory).
All filesystem mutation and user-facing confirmation lives in
``FileListController._on_files_dropped``, connected to the ``files_dropped`` signal
both classes emit.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtCore import QEvent, QItemSelectionModel, QMimeData, Qt, QUrl, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QAbstractItemView,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from pbrenamer.ui.dnd_cursors import set_drag_cursors

_TAB_KEYS = (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)


def _toggle_focus(widget, event) -> bool:
    """Send Tab and Shift+Tab to *widget*.tab_partner (tree <-> list);
    return True when the event was consumed."""
    partner: QWidget | None = widget.tab_partner
    if (
        partner is not None
        and event.type() == QEvent.Type.KeyPress
        and event.key() in _TAB_KEYS
    ):
        partner.setFocus(Qt.FocusReason.TabFocusReason)
        return True
    return False


class DirectoryTreeView(QTreeView):
    """Directory tree with drag-out (via QFileSystemModel) and drag-in support."""

    files_dropped = Signal(list, str, bool)  # paths, target_dir, is_move

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.tab_partner: QWidget | None = None
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def event(self, e) -> bool:
        return _toggle_focus(self, e) or super().event(e)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        idx = self.indexAt(event.position().toPoint())
        if idx.isValid() and event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        idx = self.indexAt(event.position().toPoint())
        if not idx.isValid():
            event.ignore()
            return
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return
        paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
        if not paths:
            event.ignore()
            return
        target_dir = self.model().filePath(idx)
        is_move = event.proposedAction() == Qt.DropAction.MoveAction
        event.acceptProposedAction()
        self.files_dropped.emit(paths, target_dir, is_move)

    def startDrag(self, supported_actions) -> None:  # noqa: N802
        indexes = self.selectedIndexes()
        if not indexes:
            return
        mime = self.model().mimeData(indexes)
        if mime is None:
            return
        drag = QDrag(self)
        drag.setMimeData(mime)
        set_drag_cursors(drag)
        drag.exec(supported_actions, self.defaultDropAction())


class FileListWidget(QTreeWidget):
    """File list with drag-out (real file URLs) and drag-in support.

    Dragged files take their sidecars along (*sidecars_of*).  Tab and
    Shift+Tab give the focus back to *tab_partner* (the directory tree).
    """

    files_dropped = Signal(list, str, bool)  # paths, target_dir, is_move

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.current_dir_getter: Callable[[], str | None] | None = None
        self.sidecars_of: Callable[[str], list[str]] = lambda _path: []
        self.tab_partner: QWidget | None = None
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def mimeData(self, items: list[QTreeWidgetItem]) -> QMimeData:  # noqa: N802
        paths: list[str] = []
        for item in items:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            paths.append(path)
            paths.extend(self.sidecars_of(path))
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(p) for p in dict.fromkeys(paths)])
        return mime

    def event(self, e) -> bool:
        return _toggle_focus(self, e) or super().event(e)

    def focusInEvent(self, event) -> None:  # noqa: N802
        # Qt would make the first row current *and selected*; an empty
        # selection means "all files", so only move the current row.
        if (
            event.reason() != Qt.FocusReason.MouseFocusReason
            and self.currentItem() is None
            and self.topLevelItemCount()
        ):
            self.selectionModel().setCurrentIndex(
                self.indexFromItem(self.topLevelItem(0)),
                QItemSelectionModel.SelectionFlag.NoUpdate,
            )
        super().focusInEvent(event)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def _resolve_target_dir(self, pos) -> str | None:
        item = self.itemAt(pos)
        on_item = QAbstractItemView.DropIndicatorPosition.OnItem
        if item is not None and self.dropIndicatorPosition() == on_item:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if os.path.isdir(path):
                return path
            return os.path.dirname(path)
        return self.current_dir_getter() if self.current_dir_getter else None

    def dropEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return
        paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
        if not paths:
            event.ignore()
            return
        target_dir = self._resolve_target_dir(event.position().toPoint())
        if not target_dir:
            event.ignore()
            return
        is_move = event.proposedAction() == Qt.DropAction.MoveAction
        event.acceptProposedAction()
        self.files_dropped.emit(paths, target_dir, is_move)

    def startDrag(self, supported_actions) -> None:  # noqa: N802
        items = self.selectedItems()
        if not items:
            return
        mime = self.mimeData(items)
        drag = QDrag(self)
        drag.setMimeData(mime)
        set_drag_cursors(drag)
        drag.exec(supported_actions, self.defaultDropAction())
