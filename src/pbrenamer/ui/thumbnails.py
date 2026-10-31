"""Lazy thumbnail loading for the file list (ported from PBPicat).

Only the visible rows, plus one screenful on each side, are decoded, by up to
four background threads.  Scrolling and resizing are debounced; nothing is
loaded while the scrollbar handle is held.
"""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QTreeWidget

from pbrenamer.core.image_io import image_size, load_qimage
from pbrenamer.resources import path as _resource

_log = logging.getLogger(__name__)

THUMB_COLUMN = 2
_NAME_COLUMN = 0
_DEBOUNCE_MS = 400
_MAX_WORKERS = 4


def format_size(num_bytes: int) -> str:
    """Human-readable file size."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class ThumbnailWorker(QThread):
    """Decode the thumbnails of *paths* in a background thread."""

    thumbnail_ready = Signal(int, str, QImage, QSize)  # row, path, image, size

    def __init__(
        self,
        rows: list[int],
        paths: list[str],
        width: int,
        height: int,
        auto_rotate: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._rows = rows
        self._paths = paths
        self._w = width
        self._h = height
        self._auto_rotate = auto_rotate
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        for row, path in zip(self._rows, self._paths, strict=True):
            if self._cancelled:
                break
            image = load_qimage(path, self._w, self._h, auto_rotate=self._auto_rotate)
            size = image_size(path, auto_rotate=self._auto_rotate) or QSize()
            self.thumbnail_ready.emit(row, path, image, size)


class ThumbnailLoader(QObject):
    """Fill the thumbnail column of *tree* (top-level items, path in
    ``UserRole`` of column 0) for the visible rows."""

    def __init__(self, tree: QTreeWidget, parent=None) -> None:
        super().__init__(parent)
        self._tree = tree
        self.enabled = False
        self._w = self._h = 128
        self._auto_rotate = True
        self._image_exts: frozenset[str] = frozenset()
        self._video_exts: frozenset[str] = frozenset()
        self._paths: list[str] = []
        self._loaded: set[str] = set()
        self._workers: list[ThumbnailWorker] = []
        self._placeholder = QIcon()
        self._video_icon = QIcon()

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._on_debounce)
        bar = tree.verticalScrollBar()
        bar.valueChanged.connect(self._schedule)
        bar.sliderReleased.connect(self.load_visible)
        tree.viewport().installEventFilter(self)

    def configure(
        self,
        enabled: bool,
        width: int,
        height: int,
        auto_rotate: bool,
        image_exts: frozenset[str],
        video_exts: frozenset[str],
    ) -> None:
        """Apply the display settings; call populate() afterwards."""
        self.stop()
        self.enabled = enabled
        self._w, self._h = width, height
        self._auto_rotate = auto_rotate
        self._image_exts = image_exts
        self._video_exts = video_exts
        placeholder = QPixmap(width, height)
        placeholder.fill(Qt.GlobalColor.lightGray)
        self._placeholder = QIcon(placeholder)
        self._video_icon = QIcon(_resource("movie.svg"))
        self._tree.setIconSize(QSize(width, height) if enabled else QSize())
        self._tree.setColumnHidden(THUMB_COLUMN, not enabled)
        if enabled:
            self._tree.setColumnWidth(THUMB_COLUMN, width + 8)

    def _kind(self, path: str) -> str | None:
        ext = os.path.splitext(path)[1][1:].lower()
        if ext in self._image_exts:
            return "image"
        if ext in self._video_exts:
            return "video"
        return None

    # ── Table life cycle ──────────────────────────────────────────────────────

    def stop(self) -> None:
        """Cancel the workers and wait for them: the rows are about to change."""
        self._debounce.stop()
        for worker in self._workers:
            worker.cancel()
            worker.wait()
        self._workers = []

    def populate(self) -> None:
        """Set placeholders after the tree was (re)filled, then load the
        visible thumbnails."""
        self.stop()
        self._loaded = set()
        root = self._tree.invisibleRootItem()
        self._paths = [
            root.child(i).data(_NAME_COLUMN, Qt.ItemDataRole.UserRole)
            for i in range(root.childCount())
        ]
        if not self.enabled:
            return
        for i, path in enumerate(self._paths):
            item = root.child(i)
            kind = self._kind(path)
            if kind == "image":
                item.setIcon(THUMB_COLUMN, self._placeholder)
            elif kind == "video":
                item.setIcon(THUMB_COLUMN, self._video_icon)
            if kind is not None:
                try:
                    info = format_size(os.path.getsize(path))
                except OSError:
                    continue
                item.setText(_NAME_COLUMN, f"{item.text(_NAME_COLUMN)}\n{info}")
        self.load_visible()

    # ── Visible rows ──────────────────────────────────────────────────────────

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Resize:
            self._schedule()
        return False

    def _schedule(self) -> None:
        if self.enabled:
            self._debounce.start()

    def _on_debounce(self) -> None:
        # Dragging the handle emits valueChanged all along the way: wait for
        # sliderReleased.  Wheel and keyboard scrolling still load here.
        if self._tree.verticalScrollBar().isSliderDown():
            return
        self.load_visible()

    def visible_rows(self) -> tuple[int, int]:
        """Return (first, last) visible rows, widened by one screenful on
        each side so that paging finds thumbnails already loaded."""
        n = len(self._paths)
        if n == 0:
            return (0, -1)
        viewport = self._tree.viewport()
        top = self._tree.indexAt(QPoint(1, 1)).row()
        top = max(top, 0)
        bottom = self._tree.indexAt(QPoint(1, max(0, viewport.height() - 2))).row()
        if bottom < 0:
            bottom = n - 1
        margin = bottom - top + 1
        return (max(0, top - margin), min(n - 1, bottom + margin))

    def load_visible(self) -> None:
        """Start loading the not yet loaded thumbnails of the visible rows."""
        if not self.enabled or not self._paths:
            return
        first, last = self.visible_rows()
        pending = [
            (row, self._paths[row])
            for row in range(first, last + 1)
            if self._paths[row] not in self._loaded
            and self._kind(self._paths[row]) == "image"
        ]
        if not pending:
            return
        self._cancel_async()
        n_workers = min(len(pending), max(1, min(_MAX_WORKERS, os.cpu_count() or 1)))
        chunk = (len(pending) + n_workers - 1) // n_workers
        for i in range(0, len(pending), chunk):
            part = pending[i : i + chunk]
            worker = ThumbnailWorker(
                [row for row, _ in part],
                [path for _, path in part],
                self._w,
                self._h,
                self._auto_rotate,
                self,
            )
            worker.thumbnail_ready.connect(self._on_ready)
            self._workers.append(worker)
            worker.start()

    def _cancel_async(self) -> None:
        """Cancel the running workers without waiting for their current
        decode (it would stall scrolling).  The rows are unchanged, so a
        late signal still lands on the right row."""
        for worker in self._workers:
            worker.cancel()
            worker.finished.connect(worker.deleteLater)
        self._workers = []

    def is_loaded(self, path: str) -> bool:
        return path in self._loaded

    def _fit_name_column(self, item) -> None:
        """Widen the name column for the longer second line, without the
        cost of resizeColumnToContents() on every thumbnail."""
        metrics = self._tree.fontMetrics()
        width = max(
            metrics.horizontalAdvance(line)
            for line in item.text(_NAME_COLUMN).split("\n")
        )
        width += (
            2
            * self._tree.style().pixelMetric(
                self._tree.style().PixelMetric.PM_FocusFrameHMargin
            )
            + 16
        )
        if width > self._tree.columnWidth(_NAME_COLUMN):
            self._tree.setColumnWidth(_NAME_COLUMN, width)

    def _on_ready(self, row: int, path: str, image: QImage, size: QSize) -> None:
        """Show a decoded thumbnail, unless the tree was refilled since: a
        signal queued before stop() would otherwise paint another
        directory's image on the file now at that row, and mark it loaded."""
        if row >= len(self._paths) or self._paths[row] != path:
            return
        item = self._tree.topLevelItem(row)
        if item is None or item.data(_NAME_COLUMN, Qt.ItemDataRole.UserRole) != path:
            return
        self._loaded.add(path)
        if size.isValid():
            name, _sep, info = item.text(_NAME_COLUMN).partition("\n")
            parts = [f"{size.width()}×{size.height()}"] + ([info] if info else [])
            item.setText(_NAME_COLUMN, f"{name}\n{'  ·  '.join(parts)}")
            self._fit_name_column(item)
        if image.isNull():
            item.setIcon(THUMB_COLUMN, QIcon())
            item.setText(THUMB_COLUMN, "?")
            return
        item.setIcon(THUMB_COLUMN, QIcon(QPixmap.fromImage(image)))
