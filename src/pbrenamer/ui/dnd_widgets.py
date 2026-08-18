"""Drag-and-drop-enabled tree/list widgets for the main window.

These subclasses only handle Qt drag-and-drop mechanics (accepting or
ignoring events, extracting dropped URLs, resolving the target directory).
All filesystem mutation and user-facing confirmation lives in
``MainWindow._on_files_dropped``, connected to the ``files_dropped`` signal
both classes emit.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtCore import QMimeData, Qt, QUrl, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QAbstractItemView,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
)

from pbrenamer.ui.dnd_cursors import set_drag_cursors


class DirectoryTreeView(QTreeView):
    """Directory tree with drag-out (via QFileSystemModel) and drag-in support."""

    files_dropped = Signal(list, str, bool)  # paths, target_dir, is_move

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

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
    """File list with drag-out (real file URLs) and drag-in support."""

    files_dropped = Signal(list, str, bool)  # paths, target_dir, is_move

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.current_dir_getter: Callable[[], str | None] | None = None
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def mimeData(self, items: list[QTreeWidgetItem]) -> QMimeData:  # noqa: N802
        urls = [
            QUrl.fromLocalFile(item.data(0, Qt.ItemDataRole.UserRole)) for item in items
        ]
        mime = QMimeData()
        mime.setUrls(urls)
        return mime

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
