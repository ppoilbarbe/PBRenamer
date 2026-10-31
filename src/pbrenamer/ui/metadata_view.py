"""Tree of the metadata of one file, shared by the File information window
and the image viewer's side panel.

Sections: universal and batch replacement fields, the ``{im:}``, ``{au:}``
or ``{vi:}`` fields of the file's type, then (images) the raw EXIF, IPTC and
XMP tags and the XMP of the sidecar.  A field row can be inserted into the
replacement pattern (double-click or context menu); raw tag rows cannot.
"""

from __future__ import annotations

import datetime
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHeaderView, QMenu, QTreeWidget, QTreeWidgetItem

from pbrenamer.core import audio_meta, image_meta, video_meta

_INSERTABLE = Qt.ItemDataRole.UserRole


def detect_type(path: str) -> str:
    """Return 'image', 'audio', 'video', 'directory', or 'other'."""
    if os.path.isdir(path):
        return "directory"
    if image_meta.can_read(path):
        return "image"
    if video_meta.can_read(path):
        return "video"
    if audio_meta.can_read(path):
        return "audio"
    return "other"


def fmt(value: object) -> str:
    """Format a field value using its default display format."""
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d_%H%M%S")
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m-%d")
    return str(value)


class MetadataView(QTreeWidget):
    """Read-only tree: Field | Description | Value."""

    field_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHeaderLabels([_("Field"), _("Description"), _("Value")])
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(True)
        hdr = self.header()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    # ── Public API ────────────────────────────────────────────────────────────

    def show_file(self, path: str, sidecars: list[str] | tuple[str, ...] = ()) -> str:
        """Fill the tree for *path*; return its detected type."""
        file_type = detect_type(path)
        self.clear()
        self._fill_universal(path)
        self._fill_batch()
        if file_type == "image":
            self._fill_meta(
                _("Image metadata (EXIF / IPTC)"),
                "im",
                image_meta.FIELD_REGISTRY,
                image_meta.read_field,
                path,
            )
            for title, rows in image_meta.read_raw_sections(path, sidecars):
                sec = self._section(title)
                for key, value in rows:
                    QTreeWidgetItem(sec, [key, "", value])
        elif file_type == "audio":
            self._fill_meta(
                _("Audio metadata"),
                "au",
                audio_meta.FIELD_REGISTRY,
                audio_meta.read_field,
                path,
            )
        elif file_type == "video":
            self._fill_meta(
                _("Video metadata"),
                "vi",
                video_meta.FIELD_REGISTRY,
                video_meta.read_field,
                path,
            )
        return file_type

    # ── Builders ──────────────────────────────────────────────────────────────

    def _fill_universal(self, path: str) -> None:
        sec = self._section(_("Universal fields"))
        now = datetime.datetime.now()
        self._row(sec, "{date}", _("Today's date"), fmt(now.date()))
        self._row(sec, "{datetime}", _("Current date and time"), fmt(now))
        try:
            st = os.stat(path)
        except OSError:
            st = None
        if st is not None:
            mdt = datetime.datetime.fromtimestamp(st.st_mtime)
            cdt = datetime.datetime.fromtimestamp(
                getattr(st, "st_birthtime", st.st_ctime)
            )
            mtime, ctime = fmt(mdt), fmt(cdt)
        else:
            mtime = ctime = _("Missing")
        self._row(sec, "{mdatetime}", _("File modification date/time"), mtime)
        self._row(sec, "{cdatetime}", _("File creation date/time"), ctime)
        parent = os.path.dirname(path)
        dir_name = os.path.basename(parent) if parent else None
        self._row(
            sec,
            "{dir}",
            _("Parent folder name"),
            dir_name if dir_name else _("Missing"),
        )
        sec.setExpanded(True)

    def _fill_batch(self) -> None:
        sec = self._section(_("Batch fields"))
        computed = _("Computed")
        self._row(sec, "{0}", _("Full matched text"), computed)
        self._row(sec, "{1}, {2}…", _("Capture groups"), computed)
        self._row(sec, "{num}", _("Auto-incrementing counter"), computed)
        self._row(sec, "{newnum}", _("Conflict-free counter"), computed)
        self._row(sec, "{re:name}", _("Named regex group"), computed)
        sec.setExpanded(False)

    def _fill_meta(self, title, prefix, registry, reader, path) -> None:
        sec = self._section(title)
        missing = _("Missing")
        for key, info in registry.items():
            val = reader(path, key)
            self._row(
                sec,
                f"{{{prefix}:{key}}}",
                info.description,
                fmt(val) if val is not None else missing,
            )
        sec.setExpanded(True)

    def _section(self, title: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem(self, [title])
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        item.setFirstColumnSpanned(True)
        return item

    def _row(self, parent: QTreeWidgetItem, field: str, desc: str, value: str) -> None:
        item = QTreeWidgetItem(parent, [field, desc, value])
        item.setData(0, _INSERTABLE, True)

    # ── Interaction ───────────────────────────────────────────────────────────

    def _field_of(self, item: QTreeWidgetItem | None) -> str | None:
        if item is None or not item.data(0, _INSERTABLE):
            return None
        return item.text(0) or None

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        field = self._field_of(item)
        if field:
            self.field_requested.emit(field)

    def _on_context_menu(self, pos) -> None:
        field = self._field_of(self.itemAt(pos))
        if not field:
            return
        menu = QMenu(self)
        action = menu.addAction(_("Insert into replacement field"))
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is action:
            self.field_requested.emit(field)
