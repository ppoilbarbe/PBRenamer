"""Non-modal window showing replacement-field values for a single file."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from pbrenamer.ui.geometry_mixin import GeometryMixin
from pbrenamer.ui.metadata_view import MetadataView


class FileInfoWindow(GeometryMixin, QWidget):
    """Non-modal window showing replacement field values for a selected file."""

    field_requested = Signal(str)

    def __init__(self, window_state, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(_("File information"))
        self.setMinimumSize(600, 460)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._init_geometry(window_state, "file_info")

        self._lbl_info = QLabel()
        self._lbl_info.setWordWrap(True)
        self._lbl_info.hide()

        self._lbl_status = QLabel()
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_status.hide()

        self._tree = MetadataView()
        self._tree.field_requested.connect(self.field_requested)
        self._tree.hide()

        layout = QVBoxLayout(self)
        layout.addWidget(self._lbl_info)
        layout.addWidget(self._lbl_status)
        layout.addWidget(self._tree)

    # ── Public API ────────────────────────────────────────────────────────────

    def update_file(
        self, path: str, sidecars: list[str] | tuple[str, ...] = ()
    ) -> None:
        """Populate the window for *path* (and the XMP of its *sidecars*)."""
        name = os.path.basename(path)
        self.setWindowTitle(_("File information — {name}").format(name=name))
        self._lbl_status.hide()
        file_type = self._tree.show_file(path, sidecars)
        type_label = {
            "image": _("Image"),
            "audio": _("Audio"),
            "video": _("Video"),
            "directory": _("Directory"),
            "other": _("Other"),
        }.get(file_type, _("Other"))
        self._lbl_info.setText(
            f"<b>{_('File:')}</b> {name} &nbsp;&nbsp; <b>{_('Type:')}</b> {type_label}"
        )
        self._lbl_info.show()
        self._tree.show()

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
