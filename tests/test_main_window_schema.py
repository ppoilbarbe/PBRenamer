"""Tests for MainWindow — Schema tab, Rename/Renumber buttons, Profile menu."""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

import pbrenamer.settings as _cfg
import pbrenamer.ui.main_window as _mwmod
from pbrenamer import profiles
from pbrenamer.ui.main_window import MainWindow
from pbrenamer.ui.presets import PatternPresets

_SCHEMA_TAB = 1


@pytest.fixture
def window(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    return w


@pytest.fixture
def photos(tmp_path):
    """Source directory with two images, a sidecar and a video."""
    src = tmp_path / "src"
    src.mkdir()
    for name in ("IMG_1.JPG", "IMG_1.xmp", "IMG_2.jpg", "VID_1.mp4"):
        (src / name).write_text(name)
    return src


def _schema_window(window, src, dest, *fields):
    window._ui.tabRules.setCurrentIndex(_SCHEMA_TAB)
    window._files.set_directory(str(src))
    window._schema.edtDest.setText(str(dest))
    window._schema.set_fields(list(fields) + [""] * (6 - len(fields)))
    window._on_preview()


def _answer(monkeypatch, button):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: button)


# ---------------------------------------------------------------------------
# Mode tabs
# ---------------------------------------------------------------------------


class TestModeTabs:
    def test_starts_on_profile_mode(self, qtbot):
        data = profiles.load()
        data["mode"] = "schema"
        profiles.save(data)
        w = MainWindow()
        qtbot.addWidget(w)
        assert w._ui.tabRules.currentIndex() == _SCHEMA_TAB
        assert not w._ui.cmbExtensionMode.isEnabled()

    def test_switch_saves_mode_and_forces_sidecars(self, window, photos):
        window._files.set_directory(str(photos))
        window._ui.chkSidecarMode.setChecked(False)
        window._ui.tabRules.setCurrentIndex(_SCHEMA_TAB)
        assert profiles.load()["mode"] == "schema"
        assert not window._ui.cmbExtensionMode.isEnabled()
        assert not window._ui.chkSidecarMode.isEnabled()
        assert window._files.sidecar_mode_active()
        assert window._extension_mode() == "lower"
        window._ui.tabRules.setCurrentIndex(0)
        assert profiles.load()["mode"] == "pattern"
        assert window._ui.cmbExtensionMode.isEnabled()
        assert not window._files.sidecar_mode_active()

    def test_switch_without_directory(self, window):
        window._files.current_dir = None
        window._ui.tabRules.setCurrentIndex(_SCHEMA_TAB)
        assert profiles.load()["mode"] == "schema"

    def test_renumber_button_visibility(self, window, photos, tmp_path):
        _schema_window(window, photos, tmp_path / "d", "A")
        assert window._ui.btnRenumber.isHidden()
        window._schema.set_fields(["A", "###"])
        assert not window._ui.btnRenumber.isHidden()
        assert window._ui.btnRenumber.isEnabled()

    def test_renumber_disabled_without_preview(self, window, photos, tmp_path):
        """Like Rename, Renumber waits for a preview (7.2 #10)."""
        window._actions.set_auto_preview(False)
        window._ui.tabRules.setCurrentIndex(_SCHEMA_TAB)
        window._files.set_directory(str(photos))
        window._schema.edtDest.setText(str(tmp_path / "d"))
        window._schema.set_fields(["A", "###", "", "", "", ""])
        assert not window._ui.btnRenumber.isHidden()
        assert not window._ui.btnRenumber.isEnabled()
        assert not window._ui.btnRename.isEnabled()
        window._on_preview()
        assert window._ui.btnRenumber.isEnabled()
        assert window._ui.btnRename.isEnabled()
        window._files.clear_preview()
        assert not window._ui.btnRenumber.isEnabled()
        window._on_preview()
        window._files.reload()
        assert not window._ui.btnRenumber.isEnabled()
        window._ui.tabRules.setCurrentIndex(0)
        assert window._ui.btnRenumber.isHidden()


# ---------------------------------------------------------------------------
# Schema preview and rename
# ---------------------------------------------------------------------------


class TestSchemaRename:
    def test_preview_relative_to_destination(self, window, photos, tmp_path):
        _schema_window(window, photos, tmp_path / "dest", "Paris", "###")
        texts = {
            window._ui.tblFiles.topLevelItem(i).text(
                0
            ): window._ui.tblFiles.topLevelItem(i).text(1)
            for i in range(window._ui.tblFiles.topLevelItemCount())
        }
        assert texts == {
            "IMG_1.JPG": "Paris/Paris_001.jpg",
            "IMG_1.xmp": "Paris/Paris_001.xmp",
            "IMG_2.jpg": "Paris/Paris_002.jpg",
            "VID_1.mp4": "Paris/Paris_001.mp4",
        }
        assert window._ui.btnRename.text() == "Rename (4)"
        assert window._ui.btnRename.isEnabled()

    def test_invalid_schema_clears_preview(self, window, photos, tmp_path):
        _schema_window(window, photos, tmp_path / "dest", "A", "###")
        assert window._ui.btnRename.isEnabled()
        window._schema.edtDest.setText("")
        window._on_preview()
        assert window._ui.tblFiles.topLevelItem(0).text(1) == ""
        assert not window._ui.btnRename.isEnabled()

    def test_rename_moves_files_records_history_and_undoes(
        self, window, photos, tmp_path
    ):
        dest = tmp_path / "dest"
        _schema_window(window, photos, dest, "Paris", "2024", "###")
        window._on_rename()
        assert sorted(p.name for p in (dest / "Paris" / "2024").iterdir()) == [
            "Paris_2024_001.jpg",
            "Paris_2024_001.mp4",
            "Paris_2024_001.xmp",
            "Paris_2024_002.jpg",
        ]
        assert list(photos.iterdir()) == []
        assert profiles.get_history("field_0")[0] == "Paris"
        assert profiles.get_history("field_2")[0] == "###"
        assert profiles.get_schema()["dest"] == str(dest)
        assert "4 file(s) renamed" in window.statusBar().currentMessage()

        window._on_undo()
        assert sorted(p.name for p in photos.iterdir()) == [
            "IMG_1.JPG",
            "IMG_1.xmp",
            "IMG_2.jpg",
            "VID_1.mp4",
        ]

    def test_rename_selection_only(self, window, photos, tmp_path):
        window._ui.tabRules.setCurrentIndex(_SCHEMA_TAB)
        window._files.set_directory(str(photos))
        for i in range(window._ui.tblFiles.topLevelItemCount()):
            item = window._ui.tblFiles.topLevelItem(i)
            item.setSelected(item.text(0) == "IMG_2.jpg")
        window._schema.edtDest.setText(str(tmp_path / "dest"))
        window._schema.set_fields(["A"])
        window._on_preview()
        assert window._ui.btnRename.text() == "Rename (1)"
        window._on_rename()
        assert (tmp_path / "dest" / "A" / "A.jpg").exists()
        assert (photos / "IMG_1.JPG").exists()

    def test_conflict_reported(self, window, photos, tmp_path, monkeypatch):
        dest = tmp_path / "dest"
        _schema_window(window, photos, dest, "A", "###")
        monkeypatch.setattr(window._files, "refresh_conflicts", lambda: None)
        (dest / "A").mkdir(parents=True)
        (dest / "A" / "A_001.jpg").write_text("taken")
        warnings = []
        monkeypatch.setattr(
            QMessageBox, "warning", lambda *a, **k: warnings.append(a[2])
        )
        window._on_rename()
        assert warnings and "Nothing was renamed" in warnings[0]
        assert (photos / "IMG_1.JPG").exists()
        assert profiles.get_history("field_0") == []


# ---------------------------------------------------------------------------
# Renumber
# ---------------------------------------------------------------------------


@pytest.fixture
def numbered(tmp_path):
    src = tmp_path / "num"
    src.mkdir()
    for name in ("A_003.jpg", "A_003.xmp", "A_007.jpg"):
        (src / name).write_text(name)
    return src


class TestOrphanSidecars:
    """Schema mode leaves the orphan sidecars alone: numbered like a base
    file they would get attached to another one (7.2 #13)."""

    def _texts(self, window):
        return {
            os.path.basename(i.data(0, Qt.ItemDataRole.UserRole)): i.text(1)
            for i in window._files.all_items()
        }

    def test_not_renamed(self, window, photos, tmp_path):
        (photos / "lost.xmp").write_text("x")
        _schema_window(window, photos, tmp_path / "d", "A", "###")
        assert self._texts(window)["lost.xmp"] == "⚠ orphan sidecar, not renamed"
        assert window._ui.btnRename.isEnabled()
        pending = [src for src, _dst in window._files.pending_renames()]
        assert str(photos / "lost.xmp") not in pending
        assert len(pending) == 4
        window._on_rename()
        assert sorted(p.name for p in photos.iterdir()) == ["lost.xmp"]

    def test_not_renumbered(self, window, photos, monkeypatch):
        (photos / "lost.xmp").write_text("x")
        _schema_window(window, photos, "/unused", "A", "###")
        _answer(monkeypatch, QMessageBox.StandardButton.Yes)
        window._on_renumber()
        assert (photos / "lost.xmp").read_text() == "x"
        assert (photos / "A_001.xmp").read_text() == "IMG_1.xmp"

    def test_pattern_mode_unchanged(self, window, photos):
        (photos / "lost.xmp").write_text("x")
        window._files.set_directory(str(photos))
        assert window._files.listed_orphan_sidecars() == set()
        window._ui.chkSidecarMode.setChecked(True)
        assert window._files.listed_orphan_sidecars() == {str(photos / "lost.xmp")}
        window._on_preview()
        assert "orphan" not in self._texts(window)["lost.xmp"]


class TestRenumber:
    def test_confirmed(self, window, numbered, monkeypatch):
        _schema_window(window, numbered, "/unused", "A", "###")
        _answer(monkeypatch, QMessageBox.StandardButton.Yes)
        window._on_renumber()
        assert sorted(p.name for p in numbered.iterdir()) == [
            "A_001.jpg",
            "A_001.xmp",
            "A_002.jpg",
        ]
        window._on_undo()
        assert sorted(p.name for p in numbered.iterdir()) == [
            "A_003.jpg",
            "A_003.xmp",
            "A_007.jpg",
        ]

    def test_records_field_history(self, window, numbered, monkeypatch):
        """A renumber records the schema fields like a rename (7.2 #11)."""
        _schema_window(window, numbered, "/unused", "Bx", "###")
        _answer(monkeypatch, QMessageBox.StandardButton.Yes)
        window._on_renumber()
        assert profiles.get_history("field_0")[0] == "Bx"
        assert profiles.get_history("field_1")[0] == "###"

    def test_preview_stays_empty_with_auto_preview(self, window, numbered, monkeypatch):
        """After a renumber the preview is empty, auto-preview or not
        (7.2 #12)."""
        _schema_window(window, numbered, "/unused", "A", "###")
        window._actions.set_auto_preview(True)
        _answer(monkeypatch, QMessageBox.StandardButton.Yes)
        window._on_renumber()
        assert [i.text(1) for i in window._files.all_items()] == ["", "", ""]
        assert not window._ui.btnRename.isEnabled()
        assert not window._ui.btnRenumber.isEnabled()
        window._schema.set_fields(["B", "###", "", "", "", ""])
        window._actions.request_auto_preview()
        assert all(i.text(1) for i in window._files.all_items())
        window._actions.set_auto_preview(False)

    def test_declined(self, window, numbered, monkeypatch):
        _schema_window(window, numbered, "/unused", "A", "###")
        _answer(monkeypatch, QMessageBox.StandardButton.No)
        window._on_renumber()
        assert (numbered / "A_007.jpg").exists()

    def test_already_numbered(self, window, tmp_path, monkeypatch):
        src = tmp_path / "ok"
        src.mkdir()
        (src / "A_001.jpg").write_text("x")
        _schema_window(window, src, "/unused", "A", "###")
        asked = []
        monkeypatch.setattr(QMessageBox, "question", lambda *a: asked.append(a))
        window._on_renumber()
        assert not asked
        assert "already" in window.statusBar().currentMessage()

    def test_invalid_schema(self, window, numbered, monkeypatch):
        _schema_window(window, numbered, "/unused", "A")
        warnings = []
        monkeypatch.setattr(
            QMessageBox, "warning", lambda *a, **k: warnings.append(a[2])
        )
        window._on_renumber()
        assert "numeric" in warnings[0]

    def test_no_directory(self, window):
        window._files.current_dir = None
        window._on_renumber()

    def test_failure_reported(self, window, numbered, monkeypatch):
        from pbrenamer.core import filetools

        _schema_window(window, numbered, "/unused", "A", "###")
        _answer(monkeypatch, QMessageBox.StandardButton.Yes)

        def fail(*_a, **_k):
            raise filetools.RenameError("disk full")

        monkeypatch.setattr(filetools, "execute_renames", fail)
        warnings = []
        monkeypatch.setattr(
            QMessageBox, "warning", lambda *a, **k: warnings.append(a[1:3])
        )
        window._on_renumber()
        assert warnings[0][0] == "Renumber errors"
        assert "disk full" in warnings[0][1]


# ---------------------------------------------------------------------------
# Profile menu
# ---------------------------------------------------------------------------


def _text(monkeypatch, name, ok=True):
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: (name, ok))


class TestProfileMenu:
    def test_title(self, window):
        assert window.windowTitle() == "PBRenamer"

    def test_new_profile(self, window, monkeypatch):
        _text(monkeypatch, " photos ")
        window._ui.actionProfileNew.trigger()
        assert profiles.current() == "photos"
        assert window.windowTitle() == "PBRenamer [photos]"
        assert "photos" in window.statusBar().currentMessage()

    @pytest.mark.parametrize(("name", "ok"), [("", True), ("x", False)])
    def test_new_cancelled(self, window, monkeypatch, name, ok):
        _text(monkeypatch, name, ok)
        window._ui.actionProfileNew.trigger()
        assert profiles.list_profiles() == ["default"]

    @pytest.mark.parametrize("name", ["a b", ".hidden", "a.b", "default"])
    def test_new_invalid_or_existing(self, window, monkeypatch, name):
        _text(monkeypatch, name)
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a))
        window._ui.actionProfileNew.trigger()
        assert warnings
        assert profiles.current() == "default"
        assert profiles.list_profiles(include_hidden=True) == ["default"]

    def test_duplicate(self, window, monkeypatch, tmp_path):
        window._schema.edtDest.setText(str(tmp_path))
        _text(monkeypatch, "copy")
        window._ui.actionProfileDuplicate.trigger()
        assert profiles.current() == "copy"
        assert profiles.get_schema()["dest"] == str(tmp_path)

    @pytest.mark.parametrize("name", ["copy", ".copy"])
    def test_duplicate_existing_or_invalid(self, window, monkeypatch, name):
        profiles.create("copy")
        _text(monkeypatch, name)
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a))
        window._ui.actionProfileDuplicate.trigger()
        assert warnings
        assert profiles.current() == "default"
        assert profiles.list_profiles(include_hidden=True) == ["copy", "default"]

    def test_duplicate_cancelled(self, window, monkeypatch):
        _text(monkeypatch, "copy", ok=False)
        window._ui.actionProfileDuplicate.trigger()
        assert not profiles.exists("copy")

    def test_delete_nothing(self, window, monkeypatch):
        profiles.create(".hidden")
        infos = []
        monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a))
        window._ui.actionProfileDelete.trigger()
        assert infos
        assert profiles.list_profiles(include_hidden=True) == [".hidden", "default"]

    def test_delete_current_default_falls_back(self, window, monkeypatch):
        profiles.create("b")
        profiles.create("a")
        self._delete(window, monkeypatch, "default", QMessageBox.StandardButton.Yes)
        assert profiles.list_profiles() == ["a", "b"]
        assert profiles.current() == "a"
        assert window.windowTitle() == "PBRenamer [a]"

    def _delete(self, window, monkeypatch, name, answer, ok=True):
        seen = {}

        def get_item(_parent, _title, _label, names, index, _editable):
            seen.update(names=names, index=index)
            return name, ok

        monkeypatch.setattr(QInputDialog, "getItem", get_item)
        _answer(monkeypatch, answer)
        window._ui.actionProfileDelete.trigger()
        return seen

    def test_delete_current(self, window, monkeypatch):
        profiles.create(".hidden")
        profiles.create("a")
        profiles.create("p")
        window._switch_profile("p")
        seen = self._delete(window, monkeypatch, "p", QMessageBox.StandardButton.Yes)
        assert seen == {"names": ["a", "default", "p"], "index": 2}
        assert not profiles.exists("p")
        assert profiles.current() == "default"
        assert window.windowTitle() == "PBRenamer"

    def test_delete_never_offers_hidden(self, window, monkeypatch):
        profiles.create(".hidden")
        profiles.create("p")
        window._switch_profile(".hidden")
        seen = self._delete(window, monkeypatch, "p", QMessageBox.StandardButton.Yes)
        assert seen == {"names": ["default", "p"], "index": 0}
        assert profiles.exists(".hidden")
        assert profiles.current() == ".hidden"

    def test_delete_other(self, window, monkeypatch):
        profiles.create("p")
        self._delete(window, monkeypatch, "p", QMessageBox.StandardButton.Yes)
        assert not profiles.exists("p")

    def test_delete_declined(self, window, monkeypatch):
        profiles.create("p")
        self._delete(window, monkeypatch, "p", QMessageBox.StandardButton.No)
        assert profiles.exists("p")

    def test_delete_cancelled(self, window, monkeypatch):
        profiles.create("p")
        self._delete(window, monkeypatch, "p", None, ok=False)
        assert profiles.exists("p")

    def _rename(self, window, monkeypatch, name, ok=True):
        seen = []

        def get_text(_parent, _title, _label, _mode, text):
            seen.append(text)
            return name, ok

        monkeypatch.setattr(QInputDialog, "getText", get_text)
        window._ui.actionProfileRename.trigger()
        return seen

    def test_rename_current(self, window, monkeypatch):
        PatternPresets().add_replace("kept")
        seen = self._rename(window, monkeypatch, " photos ")
        assert seen == ["default"]
        assert profiles.list_profiles() == ["photos"]
        assert profiles.current() == "photos"
        assert window.windowTitle() == "PBRenamer [photos]"
        assert "photos" in window.statusBar().currentMessage()
        # Presets follow the renamed directory
        assert window._ui.cmbPatternDest.findText("kept") >= 0
        assert window._presets._dir.parent == profiles.profile_dir("photos")

    @pytest.mark.parametrize(("name", "ok"), [("default", True), ("x", False)])
    def test_rename_unchanged(self, window, monkeypatch, name, ok):
        self._rename(window, monkeypatch, name, ok)
        assert profiles.list_profiles() == ["default"]

    @pytest.mark.parametrize("name", [".x", "a.b", "p", "-p", "a b"])
    def test_rename_rejected(self, window, monkeypatch, name):
        profiles.create("p")
        profiles.create("-p")
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a))
        self._rename(window, monkeypatch, name)
        assert warnings
        assert profiles.list_profiles(include_hidden=True) == ["-p", "default", "p"]
        assert profiles.current() == "default"

    def test_rename_hiding_last_visible_rejected(self, window, monkeypatch):
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a))
        self._rename(window, monkeypatch, "-old")
        assert "last visible" in warnings[0][2]
        assert profiles.list_profiles() == ["default"]

    def test_menu_lists_profiles(self, window):
        profiles.create("b")
        profiles.create(".h")
        window._build_profile_menu()
        names = [a.text() for a in window._profile_actions]
        assert names == ["b", "default"]
        assert [a.isChecked() for a in window._profile_actions] == [False, True]
        window._switch_profile(".h")
        window._build_profile_menu()
        assert [a.text() for a in window._profile_actions] == [".h", "b", "default"]
        assert window._ui.menuProfile.actions().count(window._profile_actions[0]) == 1

    def test_menu_action_switches(self, window):
        profiles.create("b")
        window._build_profile_menu()
        window._profile_actions[0].trigger()
        assert profiles.current() == "b"


class TestSwitchProfile:
    def test_same_profile_is_noop(self, window, monkeypatch):
        monkeypatch.setattr(profiles, "use", lambda *a: pytest.fail("switched"))
        window._switch_profile("default")

    def test_loads_profile_settings(self, window, photos, tmp_path):
        window._files.set_directory(str(photos))
        PatternPresets().add_replace("from-default")
        window._schema.edtDest.setText(str(tmp_path / "d1"))
        window._undo.add_batch([(str(photos / "x"), str(photos / "y"))])

        profiles.create("photos")
        profiles.use("photos", remember=False)
        other = tmp_path / "other"
        other.mkdir()
        data = profiles.load()
        data["mode"] = "schema"
        data["last_dir"] = str(other)
        data["schema"]["field_count"] = 3
        profiles.save(data)
        profiles.use("default", remember=False)

        window._switch_profile("photos")
        assert window._ui.tabRules.currentIndex() == _SCHEMA_TAB
        assert len(window._schema.fields()) == 3
        assert window._files.current_dir == str(other)
        assert window._ui.cmbPatternDest.findText("from-default") == -1
        assert len(window._undo) == 1
        assert window._presets is window._pattern._presets

        window._switch_profile("default")
        assert profiles.get_schema()["dest"] == str(tmp_path / "d1")
        assert window._ui.tabRules.currentIndex() == 0
        assert window._ui.cmbPatternDest.findText("from-default") >= 0
        photos_dir = profiles.profile_dir("photos")
        assert profiles.read_profile(photos_dir)["last_dir"] == str(other)

    def test_toolbar_state_restored(self, window):
        _cfg.set_restore_toolbar_state(True)
        profiles.create("p")
        profiles.use("p", remember=False)
        _cfg.set_toolbar_state({"recursive": True})
        profiles.use("default", remember=False)
        window._switch_profile("p")
        assert window._ui.chkRecursive.isChecked()


# ---------------------------------------------------------------------------
# Profile configuration and history dialogs
# ---------------------------------------------------------------------------


class TestDialogs:
    def test_profile_config_accepted(self, window, monkeypatch, tmp_path):
        window._schema.edtDest.setText(str(tmp_path))
        window._schema.set_fields(["A"])

        def accept(dialog):
            profiles.set_schema(field_count=2)
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(_mwmod.ProfileDialog, "exec", accept)
        window._on_profile_config()
        assert window._schema.fields() == ["A", ""]
        assert window._schema.dest() == str(tmp_path)

    def test_profile_config_rejected(self, window, monkeypatch):
        monkeypatch.setattr(
            _mwmod.ProfileDialog, "exec", lambda d: QDialog.DialogCode.Rejected
        )
        window._schema.set_fields(["A"])
        profiles.set_schema(field_count=2)
        window._on_profile_config()
        assert len(window._schema.fields()) == 6

    def test_history_keeps_field_values(self, window, monkeypatch):
        window._schema.set_fields(["A", "B"])

        def edit(dialog):
            profiles.set_history("field_0", ["X"])
            return QDialog.DialogCode.Rejected

        monkeypatch.setattr(_mwmod.HistoryDialog, "exec", edit)
        window._on_history()
        assert window._schema.fields()[:2] == ["A", "B"]
        combo = window._schema._fields[0].combo
        assert combo.findText("X") >= 0

    def test_close_saves_destination(self, window, tmp_path):
        window._schema.edtDest.setText(str(tmp_path))
        window.close()
        assert profiles.get_schema()["dest"] == str(tmp_path)
