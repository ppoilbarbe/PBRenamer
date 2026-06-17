"""Non-modal window showing replacement-field values for a single file."""

from __future__ import annotations

import datetime
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pbrenamer.core import audio_meta, image_meta, video_meta

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_type(path: str) -> str:
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


def _fmt(value: object) -> str:
    """Format a field value using its default display format."""
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d_%H%M%S")
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m-%d")
    return str(value)


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------


class FileInfoWindow(QWidget):
    """Non-modal window showing replacement field values for a selected file."""

    field_requested = Signal(str)

    def __init__(self, window_state, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(_("File information"))
        self.setMinimumSize(600, 460)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._window_state = window_state
        self._geometry_restored = False

        self._lbl_info = QLabel()
        self._lbl_info.setWordWrap(True)
        self._lbl_info.hide()

        self._lbl_status = QLabel()
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_status.hide()

        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels([_("Field"), _("Description"), _("Value")])
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        hdr = self._tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self._tree.hide()

        layout = QVBoxLayout(self)
        layout.addWidget(self._lbl_info)
        layout.addWidget(self._lbl_status)
        layout.addWidget(self._tree)

    # ── Public API ────────────────────────────────────────────────────────────

    def update_file(self, path: str) -> None:
        """Populate the window for *path*."""
        name = os.path.basename(path)
        file_type = _detect_type(path)
        type_label = {
            "image": _("Image"),
            "audio": _("Audio"),
            "video": _("Video"),
            "directory": _("Directory"),
            "other": _("Other"),
        }.get(file_type, _("Other"))

        self.setWindowTitle(_("File information — {name}").format(name=name))
        self._lbl_status.hide()
        self._lbl_info.setText(
            f"<b>{_('File:')}</b> {name} &nbsp;&nbsp; <b>{_('Type:')}</b> {type_label}"
        )
        self._lbl_info.show()
        self._tree.show()
        self._tree.clear()

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

    def show_multiple(self) -> None:
        self.setWindowTitle(_("File information"))
        self._lbl_info.hide()
        self._tree.hide()
        self._lbl_status.setText(_("Select a single file to display its information."))
        self._lbl_status.show()

    def show_empty(self) -> None:
        self.setWindowTitle(_("File information"))
        self._lbl_info.hide()
        self._tree.hide()
        self._lbl_status.setText(_("Select a file to display its information."))
        self._lbl_status.show()

    # ── Private builders ──────────────────────────────────────────────────────

    def _fill_universal(self, path: str) -> None:
        sec = self._section(_("Universal fields"))
        now = datetime.datetime.now()
        self._row(sec, "{date}", _("Today's date"), _fmt(now.date()))
        self._row(sec, "{datetime}", _("Current date and time"), _fmt(now))
        try:
            mdt = datetime.datetime.fromtimestamp(os.stat(path).st_mtime)
            self._row(sec, "{mdatetime}", _("File modification date/time"), _fmt(mdt))
        except OSError:
            self._row(
                sec, "{mdatetime}", _("File modification date/time"), _("Missing")
            )
        try:
            st = os.stat(path)
            cdt = datetime.datetime.fromtimestamp(
                getattr(st, "st_birthtime", st.st_ctime)
            )
            self._row(sec, "{cdatetime}", _("File creation date/time"), _fmt(cdt))
        except OSError:
            self._row(sec, "{cdatetime}", _("File creation date/time"), _("Missing"))
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

    def _fill_meta(self, title, prefix, registry, reader, path):
        sec = self._section(title)
        missing = _("Missing")
        for key, info in registry.items():
            val = reader(path, key)
            self._row(
                sec,
                f"{{{prefix}:{key}}}",
                info.description,
                _fmt(val) if val is not None else missing,
            )
        sec.setExpanded(True)

    def _section(self, title: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem(self._tree, [title])
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        item.setFirstColumnSpanned(True)
        return item

    def _row(self, parent: QTreeWidgetItem, field: str, desc: str, value: str) -> None:
        QTreeWidgetItem(parent, [field, desc, value])

    # ── Interaction ───────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._geometry_restored:
            self._geometry_restored = True
            geo = self._window_state.load_geometry("file_info")
            if geo:
                self.restoreGeometry(geo)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._window_state.save_geometry("file_info", self.saveGeometry())
        super().closeEvent(event)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        if item.childCount() > 0:
            return
        field = item.text(0)
        if field:
            self.field_requested.emit(field)

    def _on_tree_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if item is None or item.childCount() > 0:
            return
        field = item.text(0)
        if not field:
            return
        menu = QMenu(self)
        action = menu.addAction(_("Insert into replacement field"))
        chosen = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if chosen is action:
            self.field_requested.emit(field)
