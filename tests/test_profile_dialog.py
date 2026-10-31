"""Tests for ProfileDialog — configuration of the current profile."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QDialog

from pbrenamer import profiles
from pbrenamer.ui.profile_dialog import ProfileDialog


@pytest.fixture
def dialog(qtbot):
    profiles.set_schema(field_count=3, field_titles=["Place", "Year"])
    ws = MagicMock()
    ws.load_geometry.return_value = None
    dlg = ProfileDialog(ws)
    qtbot.addWidget(dlg)
    return dlg


def _titles(dlg):
    return [e.text() for e in dlg._title_edits]


def test_loads_profile(dialog):
    ui = dialog._ui
    assert dialog.windowTitle() == "Profile configuration — default"
    assert ui.spnFieldCount.value() == 3
    assert _titles(dialog) == ["Place", "Year", "Field 3"]
    assert ui.edtVideoMarker.text() == ""
    assert ui.spnHistoryMax.value() == 20


def test_field_count_keeps_typed_titles(dialog):
    dialog._title_edits[0].setText("City")
    dialog._ui.spnFieldCount.setValue(2)
    assert _titles(dialog) == ["City", "Year"]
    dialog._ui.spnFieldCount.setValue(4)
    assert _titles(dialog) == ["City", "Year", "Field 3", "Field 4"]


def test_marker_rejects_forbidden_chars(dialog, qtbot):
    qtbot.keyClicks(dialog._ui.edtVideoMarker, "v_i{d}")
    assert dialog._ui.edtVideoMarker.text() == "vid"


def test_ok_saves(dialog):
    ui = dialog._ui
    ui.spnFieldCount.setValue(4)
    dialog._title_edits[1].setText("  ")
    ui.edtVideoMarker.setText(" vid ")
    ui.spnHistoryMax.setValue(5)
    ui.buttonBox.accepted.emit()
    assert dialog.result() == QDialog.DialogCode.Accepted
    data = profiles.load()
    assert data["schema"]["field_count"] == 4
    assert data["schema"]["field_titles"] == ["Place", "Field 2", "Field 3", "Field 4"]
    assert data["schema"]["video_marker"] == "vid"
    assert data["display"]["history_max"] == 5


def test_cancel_writes_nothing(dialog):
    dialog._ui.spnFieldCount.setValue(5)
    dialog._ui.buttonBox.rejected.emit()
    assert profiles.get_schema()["field_count"] == 3


class TestDisplayTab:
    def test_loads_defaults(self, dialog):
        ui = dialog._ui
        assert [ui.tabs.tabText(i) for i in range(ui.tabs.count())] == [
            "Schema",
            "Display",
            "Images",
        ]
        assert not ui.chkThumbnails.isChecked()
        assert ui.spnThumbWidth.value() == 128
        assert ui.spnThumbHeight.value() == 128
        assert not ui.chkSidecarColumn.isChecked()
        assert not ui.chkSidecarFilter.isChecked()
        assert ui.edtSidecarExtension.text() == "xmp"
        assert not ui.chkDeleteEmptySidecars.isChecked()

    def test_extension_rejects_separators(self, dialog, qtbot):
        edit = dialog._ui.edtSidecarExtension
        edit.clear()
        qtbot.keyClicks(edit, "pp 3/x")
        assert edit.text() == "pp3x"

    def test_ok_saves(self, dialog):
        ui = dialog._ui
        ui.chkThumbnails.setChecked(True)
        ui.spnThumbWidth.setValue(96)
        ui.spnThumbHeight.setValue(64)
        ui.chkSidecarColumn.setChecked(True)
        ui.chkSidecarFilter.setChecked(True)
        ui.edtSidecarExtension.setText(".prompt.txt")
        ui.chkDeleteEmptySidecars.setChecked(True)
        ui.buttonBox.accepted.emit()
        data = profiles.load()
        assert data["display"] == {
            "thumbnail_max_width": 96,
            "thumbnail_max_height": 64,
            "history_max": 20,
            "thumbnails": True,
            "sidecar_column": True,
            "sidecar_filter": True,
            "sort_by_date": False,
            "sort_reverse": False,
        }
        assert data["images"]["sidecar_new_extension"] == "prompt.txt"
        assert data["images"]["delete_empty_sidecars"] is True


class TestImagesTab:
    def test_loads_defaults(self, dialog):
        ui = dialog._ui
        assert ui.spnZoomStep.value() == 25
        assert ui.spnZoomMax.value() == 400
        assert ui.cmbMetadataSide.currentData() == "right"
        assert ui.chkExifAutoRotate.isChecked()
        assert ui.chkUseTrash.isChecked()
        assert ui.chkConfirmDeletions.isChecked()
        assert ui.spnDeleteListMax.value() == 12

    def test_ok_saves(self, dialog):
        ui = dialog._ui
        ui.spnZoomStep.setValue(50)
        ui.spnZoomMax.setValue(800)
        ui.cmbMetadataSide.setCurrentIndex(ui.cmbMetadataSide.findData("left"))
        ui.chkExifAutoRotate.setChecked(False)
        ui.chkUseTrash.setChecked(False)
        ui.chkConfirmDeletions.setChecked(False)
        ui.spnDeleteListMax.setValue(3)
        ui.buttonBox.accepted.emit()
        images = profiles.load()["images"]
        assert images["zoom_step_percent"] == 50
        assert images["zoom_max_percent"] == 800
        assert images["metadata_panel_side"] == "left"
        assert images["exif_auto_rotate"] is False
        assert images["use_trash"] is False
        assert images["confirm_deletions"] is False
        assert images["delete_list_max_files"] == 3

    def test_unknown_side_falls_back_to_right(self, qtbot):
        data = profiles.load()
        data["images"]["metadata_panel_side"] = "top"
        profiles.save(data)
        dlg = ProfileDialog(MagicMock(**{"load_geometry.return_value": None}))
        qtbot.addWidget(dlg)
        assert dlg._ui.cmbMetadataSide.currentData() == "right"
