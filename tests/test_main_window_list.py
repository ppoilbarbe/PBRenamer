"""Tests for MainWindow — enriched file list (thumbnails, sidecar options,
selection after renaming)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

import pbrenamer.ui.main_window as _mwmod
from pbrenamer import profiles
from pbrenamer.ui.main_window import MainWindow

_SCHEMA_TAB = 1


@pytest.fixture
def window(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    return w


def _selected(window):
    return sorted(i.text(0) for i in window._ui.tblFiles.selectedItems())


def _current(window):
    return window._ui.tblFiles.currentItem().text(0)


class TestThumbnailsCheckbox:
    def test_toggle_saves_profile(self, window, tmp_path):
        window._files.set_directory(str(tmp_path))
        window._ui.chkThumbnails.setChecked(True)
        assert profiles.load()["display"]["thumbnails"] is True
        assert not window._ui.tblFiles.isColumnHidden(2)
        window._ui.chkThumbnails.setChecked(False)
        assert profiles.load()["display"]["thumbnails"] is False
        assert window._ui.tblFiles.isColumnHidden(2)

    def test_profile_switch_applies_display(self, window):
        profiles.create("photos")
        profiles.use("photos", remember=False)
        data = profiles.load()
        data["display"].update(thumbnails=True, sidecar_column=True)
        profiles.save(data)
        profiles.use("default", remember=False)
        window._switch_profile("photos")
        assert window._ui.chkThumbnails.isChecked()
        assert not window._ui.tblFiles.isColumnHidden(3)
        window._switch_profile("default")
        assert not window._ui.chkThumbnails.isChecked()
        assert window._ui.tblFiles.isColumnHidden(3)


class TestDialogsApplyDisplay:
    def test_profile_config(self, window, monkeypatch):
        def accept(dialog):
            data = profiles.load()
            data["display"]["sidecar_filter"] = True
            profiles.save(data)
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(_mwmod.ProfileDialog, "exec", accept)
        window._on_profile_config()
        assert not window._ui.cmbSidecarFilter.isHidden()

    def test_sidecar_dialog(self, window, monkeypatch):
        called = []
        monkeypatch.setattr(_mwmod.SidecarDialog, "exec", lambda d: 0)
        monkeypatch.setattr(window._files, "apply_display", lambda: called.append(True))
        window._on_sidecar_files()
        assert called == [True]

    def test_history_reloads_filter(self, window, monkeypatch):
        monkeypatch.setattr(_mwmod.HistoryDialog, "exec", lambda d: 0)
        profiles.set_history("sidecar_filter", ["paris"])
        window._on_history()
        assert window._ui.cmbSidecarFilter.itemText(0) == "paris"


class TestSelectionAfterRename:
    def test_pattern_selects_renamed_files(self, window, tmp_path):
        for name in ("a.txt", "b.txt", "c.txt"):
            (tmp_path / name).write_text(name)
        window._files.set_directory(str(tmp_path))
        assert window._execute(
            [(str(tmp_path / "a.txt"), str(tmp_path / "z.txt"))], "t"
        )
        assert _selected(window) == ["z.txt"]
        assert _current(window) == "z.txt"

    def test_schema_makes_next_row_current(self, window, tmp_path, monkeypatch):
        src = tmp_path / "src"
        src.mkdir()
        for name in ("a.jpg", "b.jpg", "c.jpg"):
            (src / name).write_text(name)
        window._ui.tabRules.setCurrentIndex(_SCHEMA_TAB)
        window._files.set_directory(str(src))
        window._files.select_paths([str(src / "a.jpg")])
        window._schema.edtDest.setText(str(tmp_path / "dest"))
        window._schema.set_fields(["Paris", "", "", "", "", ""])
        window._on_preview()
        window._on_rename()
        assert not (src / "a.jpg").exists()
        assert window._ui.tblFiles.selectedItems() == []
        assert _current(window) == "b.jpg"

    def test_failure_keeps_list(self, window, tmp_path, monkeypatch):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        window._files.set_directory(str(tmp_path))
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
        assert not window._execute(
            [(str(tmp_path / "a.txt"), str(tmp_path / "b.txt"))], "t"
        )
        assert _current(window) == "a.txt"
