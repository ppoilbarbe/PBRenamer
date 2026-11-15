"""Profile configuration dialog — settings of the current profile."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLineEdit

from pbrenamer import profiles
from pbrenamer.core import schema
from pbrenamer.ui.geometry_mixin import GeometryMixin
from pbrenamer.ui.profile_dialog_ui import Ui_ProfileDialog
from pbrenamer.ui.rule_panel_schema import ForbiddenCharValidator, field_title


class ProfileDialog(GeometryMixin, QDialog):
    """Edit the settings of the current profile; OK saves them."""

    def __init__(self, window_state, parent=None) -> None:
        super().__init__(parent)
        self._ui = Ui_ProfileDialog()
        self._ui.setupUi(self)
        self._init_geometry(window_state, "profile_dialog")
        self.setWindowTitle(
            _("Profile configuration — {name}").format(name=profiles.current())
        )

        self._data = profiles.load()
        schema_cfg = self._data["schema"]
        self._title_edits: list[QLineEdit] = []
        self._saved_titles: list[str] = list(schema_cfg["field_titles"])

        self._ui.edtVideoMarker.setValidator(
            ForbiddenCharValidator(schema.FORBIDDEN_MARKER_CHARS, self)
        )
        self._ui.edtVideoMarker.setText(schema_cfg["video_marker"])
        self._ui.chkRenameDirs.setChecked(schema_cfg["rename_dirs"])
        display, files, viewer = (
            self._data["display"],
            self._data["files"],
            self._data["viewer"],
        )
        self._ui.spnHistoryMax.setValue(display["history_max"])
        self._ui.chkThumbnails.setChecked(display["thumbnails"])
        self._ui.spnThumbWidth.setValue(display["thumbnail_max_width"])
        self._ui.spnThumbHeight.setValue(display["thumbnail_max_height"])
        self._ui.chkSidecarColumn.setChecked(display["sidecar_column"])
        self._ui.chkSidecarFilter.setChecked(display["sidecar_filter"])
        self._ui.edtSidecarExtension.setValidator(ForbiddenCharValidator("/\\ ", self))
        self._ui.edtSidecarExtension.setText(files["sidecar_new_extension"])
        self._ui.chkDeleteEmptySidecars.setChecked(files["delete_empty_sidecars"])
        self._ui.spnZoomStep.setValue(viewer["zoom_step_percent"])
        self._ui.spnZoomMax.setValue(viewer["zoom_max_percent"])
        side = self._ui.cmbMetadataSide.findData(viewer["metadata_panel_side"])
        self._ui.cmbMetadataSide.setCurrentIndex(max(0, side))
        self._ui.chkExifAutoRotate.setChecked(viewer["exif_auto_rotate"])
        mode = self._ui.cmbDeletionMode.findData(files["deletion_mode"])
        self._ui.cmbDeletionMode.setCurrentIndex(max(0, mode))
        self._ui.chkConfirmDeletions.setChecked(files["confirm_deletions"])
        self._ui.spnDeleteListMax.setValue(files["delete_list_max_files"])
        self._ui.chkPruneOnDelete.setChecked(files["prune_dirs_on_delete"])
        self._ui.chkPruneOnRename.setChecked(files["prune_dirs_on_rename"])
        self._ui.chkPruneParents.setChecked(files["prune_parent_dirs"])
        for box in (self._ui.chkPruneOnDelete, self._ui.chkPruneOnRename):
            box.toggled.connect(self._update_prune_parents)
        self._update_prune_parents()
        self._ui.spnFieldCount.setValue(max(1, schema_cfg["field_count"]))
        self._rebuild_titles(self._ui.spnFieldCount.value())
        self._ui.spnFieldCount.valueChanged.connect(self._rebuild_titles)

        self._ui.buttonBox.accepted.connect(self._save_and_accept)

    def _update_prune_parents(self) -> None:
        """The parents option only matters when empty folders are removed."""
        self._ui.chkPruneParents.setEnabled(
            self._ui.chkPruneOnDelete.isChecked()
            or self._ui.chkPruneOnRename.isChecked()
        )

    def _rebuild_titles(self, count: int) -> None:
        """Show *count* title rows, keeping the titles already typed."""
        current = [e.text() for e in self._title_edits]
        layout = self._ui.titlesLayout
        while layout.rowCount():
            layout.removeRow(0)
        self._title_edits.clear()
        for i in range(count):
            if i < len(current):
                text = current[i]
            else:
                text = field_title(self._saved_titles, i)
            edit = QLineEdit(text, self._ui.titlesContainer)
            edit.setPlaceholderText(_("Field {n}").format(n=i + 1))
            layout.addRow(_("Field {n}:").format(n=i + 1), edit)
            self._title_edits.append(edit)

    def _save_and_accept(self) -> None:
        schema_cfg = self._data["schema"]
        schema_cfg["field_count"] = self._ui.spnFieldCount.value()
        schema_cfg["field_titles"] = [
            e.text().strip() or _("Field {n}").format(n=i + 1)
            for i, e in enumerate(self._title_edits)
        ]
        schema_cfg["video_marker"] = self._ui.edtVideoMarker.text().strip()
        schema_cfg["rename_dirs"] = self._ui.chkRenameDirs.isChecked()
        display, files, viewer = (
            self._data["display"],
            self._data["files"],
            self._data["viewer"],
        )
        display["history_max"] = self._ui.spnHistoryMax.value()
        display["thumbnails"] = self._ui.chkThumbnails.isChecked()
        display["thumbnail_max_width"] = self._ui.spnThumbWidth.value()
        display["thumbnail_max_height"] = self._ui.spnThumbHeight.value()
        display["sidecar_column"] = self._ui.chkSidecarColumn.isChecked()
        display["sidecar_filter"] = self._ui.chkSidecarFilter.isChecked()
        files["sidecar_new_extension"] = (
            self._ui.edtSidecarExtension.text().strip().lstrip(".")
        )
        files["delete_empty_sidecars"] = self._ui.chkDeleteEmptySidecars.isChecked()
        viewer["zoom_step_percent"] = self._ui.spnZoomStep.value()
        viewer["zoom_max_percent"] = self._ui.spnZoomMax.value()
        viewer["metadata_panel_side"] = self._ui.cmbMetadataSide.currentData()
        viewer["exif_auto_rotate"] = self._ui.chkExifAutoRotate.isChecked()
        files["deletion_mode"] = self._ui.cmbDeletionMode.currentData()
        files["confirm_deletions"] = self._ui.chkConfirmDeletions.isChecked()
        files["delete_list_max_files"] = self._ui.spnDeleteListMax.value()
        files["prune_dirs_on_delete"] = self._ui.chkPruneOnDelete.isChecked()
        files["prune_dirs_on_rename"] = self._ui.chkPruneOnRename.isChecked()
        files["prune_parent_dirs"] = self._ui.chkPruneParents.isChecked()
        profiles.save(self._data)
        self.accept()
