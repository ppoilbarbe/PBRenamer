"""Tests for pbrenamer.ui.image_actions — the Images menu, the viewer
wiring, deletion, orphan sidecars, Template and rotations."""

from __future__ import annotations

import io
import os

import pytest
from PIL import Image
from PySide6.QtCore import QFile, QItemSelectionModel, Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from pbrenamer import profiles
from pbrenamer.core import image_ops
from pbrenamer.core.undo import ExifResetEntry, RotationEntry
from pbrenamer.ui import image_actions
from pbrenamer.ui.main_window import MainWindow

_SCHEMA_TAB = 1

needs_jpegtran = pytest.mark.skipif(
    not image_ops.jpegtran_available(), reason="jpegtran not installed"
)
needs_pyexiv2 = pytest.mark.skipif(
    not image_ops.pyexiv2_available(), reason="pyexiv2 not installed"
)


@pytest.fixture
def window(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    return w


@pytest.fixture
def calls(monkeypatch):
    """Record the modal helpers instead of showing them."""
    record = {"ask": [], "warn": [], "open": [], "open_with": [], "info": []}
    answer = {"ask": True}

    def ask(_parent, title, text):
        record["ask"].append(text)
        return answer["ask"]

    monkeypatch.setattr(image_actions, "_ask", ask)
    monkeypatch.setattr(
        image_actions,
        "_warn",
        lambda _p, title, text, details="": record["warn"].append(
            (title, text, details)
        ),
    )
    monkeypatch.setattr(image_actions, "_open_path", record["open"].append)
    monkeypatch.setattr(
        image_actions._open_with,
        "open_with",
        lambda p, _w: record["open_with"].append(p),
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda _p, _t, text: record["info"].append(text)
    )
    record["answer"] = answer
    return record


def _png(path, size=(40, 20)):
    Image.new("RGB", size, "red").save(path)
    return str(path)


def _jpeg(path, orientation=None, size=(160, 96)):
    img = Image.new("RGB", size, (100, 150, 200))
    buf = io.BytesIO()
    if orientation is None:
        img.save(buf, format="JPEG")
    else:
        exif = Image.Exif()
        exif[274] = orientation
        img.save(buf, format="JPEG", exif=exif)
    path.write_bytes(buf.getvalue())
    return str(path)


def _load(window, directory):
    window._files.set_directory(str(directory))


def _select(window, *names):
    tree = window._ui.tblFiles
    tree.clearSelection()
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        if item.text(0).split("\n")[0] in names:
            item.setSelected(True)


def _names(window):
    tree = window._ui.tblFiles
    return [
        tree.topLevelItem(i).text(0).split("\n")[0]
        for i in range(tree.topLevelItemCount())
    ]


def _size(path):
    with Image.open(path) as img:
        return img.size


# ---------------------------------------------------------------------------
# Targets and enabled state
# ---------------------------------------------------------------------------


class TestTargets:
    def test_selection(self, window, tmp_path):
        a = _png(tmp_path / "a.png")
        _png(tmp_path / "b.png")
        _load(window, tmp_path)
        _select(window, "a.png")
        assert window._images.targets() == [a]

    def test_current_row_without_selection(self, window, tmp_path):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._ui.tblFiles.clearSelection()
        assert window._images.targets() == [a]

    def test_nothing(self, window):
        window._ui.tblFiles.clear()
        assert window._images.targets() == []

    def test_directories_ignored(self, window, tmp_path):
        (tmp_path / "sub").mkdir()
        window._ui.cmbMode.setCurrentIndex(2)
        _load(window, tmp_path)
        _select(window, "sub")
        assert window._images.targets() == []


class TestUpdateEnabled:
    def test_no_target(self, window):
        window._ui.tblFiles.clear()
        window._images.update_enabled()
        ui = window._ui
        for act in (
            ui.actionImgOpen,
            ui.actionImgView,
            ui.actionImgTemplate,
            ui.actionImgDelete,
            ui.actionRotateLeft,
            ui.actionRotateExif,
        ):
            assert not act.isEnabled()

    def test_one_image(self, window, tmp_path):
        _png(tmp_path / "a.png")
        _load(window, tmp_path)
        _select(window, "a.png")
        ui = window._ui
        assert ui.actionImgOpen.isEnabled()
        assert ui.actionImgView.isEnabled()
        assert ui.actionImgTemplate.isEnabled()
        assert ui.actionRotateLeft.isEnabled()
        assert not ui.actionRotateExif.isEnabled()
        assert not ui.actionResetExif.isEnabled()

    def test_text_file(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / "b.txt").write_text("x")
        _load(window, tmp_path)
        _select(window, "a.txt", "b.txt")
        ui = window._ui
        assert ui.actionImgOpen.isEnabled()
        assert not ui.actionImgView.isEnabled()
        assert not ui.actionImgTemplate.isEnabled()
        assert not ui.actionRotateLeft.isEnabled()

    @needs_pyexiv2
    def test_exif_orientation(self, window, tmp_path):
        _jpeg(tmp_path / "a.jpg", 6)
        _load(window, tmp_path)
        _select(window, "a.jpg")
        assert window._ui.actionRotateExif.isEnabled()
        assert window._ui.actionResetExif.isEnabled()

    def test_many_images_not_read(self, window, tmp_path, monkeypatch):
        for i in range(3):
            _png(tmp_path / f"{i}.png")
        monkeypatch.setattr(image_actions, "_EXIF_CHECK_MAX", 0)
        _load(window, tmp_path)
        monkeypatch.setattr(
            image_ops, "get_exif_orientation", lambda _p: pytest.fail("read")
        )
        _select(window, "0.png", "1.png", "2.png")
        assert window._ui.actionRotateExif.isEnabled()

    def test_without_pillow(self, window, tmp_path, monkeypatch):
        _png(tmp_path / "a.png")
        monkeypatch.setattr(image_ops, "pillow_available", lambda: False)
        _load(window, tmp_path)
        _select(window, "a.png")
        assert not window._ui.actionRotateLeft.isEnabled()

    def test_jpeg_without_jpegtran(self, window, tmp_path, monkeypatch):
        _jpeg(tmp_path / "a.jpg")
        _png(tmp_path / "b.png")
        monkeypatch.setattr(image_ops, "jpegtran_available", lambda: False)
        _load(window, tmp_path)
        _select(window, "a.jpg")
        assert not window._ui.actionRotateLeft.isEnabled()
        _select(window, "a.jpg", "b.png")
        assert window._ui.actionRotateLeft.isEnabled()

    def test_orphans_on_menu_show(self, window, tmp_path):
        (tmp_path / "lone.xmp").write_text("x")
        _load(window, tmp_path)
        window._ui.menuImages.aboutToShow.emit()
        assert window._ui.actionImgOrphans.isEnabled()
        os.remove(tmp_path / "lone.xmp")
        window._ui.menuImages.aboutToShow.emit()
        assert not window._ui.actionImgOrphans.isEnabled()


# ---------------------------------------------------------------------------
# Open, Open with
# ---------------------------------------------------------------------------


def test_open_and_open_with(window, tmp_path, calls):
    a = _png(tmp_path / "a.png")
    _load(window, tmp_path)
    _select(window, "a.png")
    window._ui.actionImgOpen.trigger()
    window._ui.actionImgOpenWith.trigger()
    assert calls["open"] == [a]
    assert calls["open_with"] == [a]


# ---------------------------------------------------------------------------
# Viewer
# ---------------------------------------------------------------------------


class TestViewer:
    def test_view_selection(self, window, tmp_path):
        a = _png(tmp_path / "a.png")
        b = _png(tmp_path / "b.png")
        _load(window, tmp_path)
        _select(window, "a.png", "b.png")
        window._ui.actionImgView.trigger()
        viewer = window._images._viewer
        assert viewer.isVisible()
        assert viewer.current_path == a
        assert viewer._selection_paths == [a, b]

    def test_view_without_media(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        _load(window, tmp_path)
        window._images.view_selected()
        assert window._images._viewer is None

    def test_double_click_reuses_viewer(self, window, tmp_path):
        _png(tmp_path / "a.png")
        b = _png(tmp_path / "b.png")
        _load(window, tmp_path)
        tree = window._ui.tblFiles
        window._files._on_item_double_clicked(tree.topLevelItem(0), 2)
        viewer = window._images._viewer
        window._files._on_item_double_clicked(tree.topLevelItem(1), 2)
        assert window._images._viewer is viewer
        assert viewer.current_path == b
        assert viewer._selection_paths == [b]

    def test_viewer_settings_from_profile(self, window, tmp_path):
        data = profiles.load()
        data["images"].update(metadata_panel_side="left", zoom_max_percent=100)
        profiles.save(data)
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._images.show_in_viewer(a)
        viewer = window._images._viewer
        assert viewer._splitter.widget(0) is viewer._metadata_panel
        assert viewer._zoom_max == 1.0

    def test_navigation(self, window, tmp_path):
        a = _png(tmp_path / "a.png")
        (tmp_path / "b.txt").write_text("x")
        c = _png(tmp_path / "c.png")
        _load(window, tmp_path)
        window._images.show_in_viewer(a)
        viewer = window._images._viewer
        viewer.navigate_next.emit()
        assert viewer.current_path == c
        assert window._files.selected_paths() == [c]
        viewer.navigate_next.emit()  # linear: stays on the last one
        assert viewer.current_path == c
        viewer._circular = True
        viewer.navigate_next.emit()
        assert viewer.current_path == a
        viewer.navigate_prev.emit()
        assert viewer.current_path == c

    def test_navigation_file_gone_from_list(self, window, tmp_path):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._images.show_in_viewer(a)
        viewer = window._images._viewer
        viewer._current_path = str(tmp_path / "elsewhere.png")
        viewer.navigate_next.emit()
        assert viewer.current_path == str(tmp_path / "elsewhere.png")
        viewer._current_path = None
        viewer.navigate_next.emit()

    def test_requests_from_viewer(self, window, tmp_path, calls, monkeypatch):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._images.show_in_viewer(a)
        viewer = window._images._viewer
        viewer.open_requested.emit()
        viewer.open_with_requested.emit()
        assert calls["open"] == [a]
        assert calls["open_with"] == [a]
        templates = []
        monkeypatch.setattr(window._images, "template", templates.append)
        viewer.template_requested.emit()
        assert templates == [a]
        fields = []
        window._files.field_requested.connect(fields.append)
        viewer.field_requested.emit("{date}")
        assert fields == ["{date}"]

    def test_rotate_from_viewer(self, window, tmp_path, monkeypatch):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._images.show_in_viewer(a)
        viewer = window._images._viewer
        done = []
        monkeypatch.setattr(window._images, "rotate", lambda p, op: done.append(op))
        monkeypatch.setattr(window._images, "reset_exif", lambda p: done.append("r"))
        viewer.rotate_requested.emit(90)
        viewer.rotate_requested.emit("reset_exif")
        assert done == [90, "r"]
        viewer._current_path = None
        viewer.rotate_requested.emit(90)
        viewer.open_requested.emit()
        assert done == [90, "r"]

    def test_delete_from_viewer(self, window, tmp_path, calls, monkeypatch):
        monkeypatch.setattr(QFile, "moveToTrash", lambda p: os.remove(p) or True)
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._images.show_in_viewer(a)
        window._images._viewer.delete_requested.emit()
        assert not os.path.exists(a)

    def test_reload_refreshes_viewer(self, window, tmp_path, monkeypatch):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._images.show_in_viewer(a)
        refreshed = []
        monkeypatch.setattr(window._images._viewer, "refresh_paths", refreshed.append)
        window._files.reload()
        assert refreshed == [{a}]

    def test_profile_change_closes_viewer(self, window, tmp_path):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._images.show_in_viewer(a)
        window._images.apply_profile()
        assert window._images._viewer is None
        window._images.apply_profile()  # no viewer: no-op


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------


class TestTemplate:
    def _history(self):
        profiles.set_history("field_0", ["Nature"])
        profiles.set_history("field_5", ["###"])

    def test_accepted_fills_schema(self, window, tmp_path, monkeypatch):
        self._history()
        _png(tmp_path / "Nature_001.png")
        _load(window, tmp_path)
        _select(window, "Nature_001.png")
        shown = []

        def accept(dialog):
            shown.append(dialog.windowTitle())
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(image_actions, "_exec_dialog", accept)
        window._ui.tabRules.setCurrentIndex(0)
        window._ui.actionImgTemplate.trigger()
        assert shown == ["Proposed template"]
        assert window._schema.fields() == ["Nature", "", "", "", "", "###"]
        assert window._ui.tabRules.currentIndex() == _SCHEMA_TAB

    def test_rejected(self, window, tmp_path, monkeypatch):
        self._history()
        a = _png(tmp_path / "Nature_001.png")
        monkeypatch.setattr(
            image_actions, "_exec_dialog", lambda d: QDialog.DialogCode.Rejected
        )
        accepted = []
        window._images.template_accepted.connect(accepted.append)
        window._images.template(a)
        assert accepted == []

    def test_no_match(self, window, tmp_path, calls):
        a = _png(tmp_path / "x.png")
        window._images.template(a)
        assert "x.png" in calls["info"][0]

    def test_needs_one_file(self, window, tmp_path, monkeypatch):
        _png(tmp_path / "a.png")
        _png(tmp_path / "b.png")
        _load(window, tmp_path)
        _select(window, "a.png", "b.png")
        monkeypatch.setattr(window._images, "template", lambda p: pytest.fail(p))
        window._images.template_selected()


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDelete:
    @pytest.fixture
    def trash(self, monkeypatch):
        trashed = []

        def move(path):
            trashed.append(path)
            os.remove(path)
            return True

        monkeypatch.setattr(QFile, "moveToTrash", move)
        return trashed

    def _set(self, **images):
        data = profiles.load()
        data["images"].update(images)
        profiles.save(data)

    def test_to_trash_with_sidecars(self, window, tmp_path, calls, trash):
        a = _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        b = _png(tmp_path / "b.png")
        _load(window, tmp_path)
        _select(window, "a.png")
        window._ui.actionImgDelete.trigger()
        assert trash == [a, str(tmp_path / "a.xmp")]
        assert calls["ask"] == ["Move to trash:\na.png\na.xmp"]
        assert _names(window) == ["b.png"]
        assert window._ui.tblFiles.currentItem().data(0, Qt.ItemDataRole.UserRole) == b

    def test_declined(self, window, tmp_path, calls, trash):
        a = _png(tmp_path / "a.png")
        calls["answer"]["ask"] = False
        _load(window, tmp_path)
        window._images.delete([a])
        assert trash == []
        assert os.path.exists(a)

    def test_without_confirmation(self, window, tmp_path, calls, trash):
        self._set(confirm_deletions=False)
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._images.delete([a])
        assert trash == [a]
        assert calls["ask"] == []

    def test_count_only_above_limit(self, window, tmp_path, calls, trash):
        self._set(delete_list_max_files=1)
        paths = [_png(tmp_path / "a.png"), _png(tmp_path / "b.png")]
        _load(window, tmp_path)
        window._images.delete(paths)
        assert calls["ask"] == ["Move 2 files to trash?"]

    def test_trash_failure(self, window, tmp_path, calls, monkeypatch):
        monkeypatch.setattr(QFile, "moveToTrash", lambda p: False)
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._images.delete([a])
        assert calls["warn"][0][1] == "Could not move to trash: a.png"

    def test_permanent(self, window, tmp_path, calls):
        self._set(use_trash=False)
        sub = tmp_path / "sub" / "deeper"
        sub.mkdir(parents=True)
        a = _png(sub / "a.png")
        window._ui.chkRecursive.setChecked(True)
        _load(window, tmp_path)
        window._images.delete([a])
        assert calls["ask"] == ["Permanently delete:\na.png"]
        assert not (tmp_path / "sub").exists()
        assert tmp_path.exists()

    def test_permanent_count_and_error(self, window, tmp_path, calls, monkeypatch):
        self._set(use_trash=False, delete_list_max_files=1)
        paths = [_png(tmp_path / "a.png"), _png(tmp_path / "b.png")]
        (tmp_path / "keep.txt").write_text("x")
        _load(window, tmp_path)
        real_remove = os.remove

        def remove(path):
            if path.endswith("b.png"):
                raise OSError("busy")
            real_remove(path)

        monkeypatch.setattr(image_actions.os, "remove", remove)
        window._images.delete(paths)
        assert calls["ask"] == ["Permanently delete 2 files?"]
        assert calls["warn"][0][1] == "b.png: busy"
        assert _names(window) == ["b.png", "keep.txt"]

    def test_nothing(self, window, calls):
        window._images.delete([])
        assert calls["ask"] == []


# ---------------------------------------------------------------------------
# Orphan sidecars
# ---------------------------------------------------------------------------


class TestOrphans:
    def test_delete_all(self, window, tmp_path, calls, monkeypatch):
        monkeypatch.setattr(QFile, "moveToTrash", lambda p: os.remove(p) or True)
        _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        (tmp_path / "lone.xmp").write_text("x")
        _load(window, tmp_path)
        shown = []

        def run(dialog):
            shown.append(dialog._list.count())
            dialog._delete_all()
            return dialog.result()

        monkeypatch.setattr(image_actions, "_exec_dialog", run)
        window._ui.actionImgOrphans.setEnabled(True)
        window._ui.actionImgOrphans.trigger()
        assert shown == [1]
        assert not (tmp_path / "lone.xmp").exists()
        assert (tmp_path / "a.xmp").exists()
        assert "lone.xmp" not in _names(window)

    def test_dialog_delete_selected(self, qtbot, tmp_path):
        from pbrenamer.ui.orphan_sidecars_dialog import OrphanSidecarsDialog
        from pbrenamer.ui.window_state import WindowState

        orphans = [str(tmp_path / "a.xmp"), str(tmp_path / "b.xmp")]
        asked = []

        def delete(files):
            asked.append(files)
            return files[:1]

        dialog = OrphanSidecarsDialog(orphans, delete, WindowState())
        qtbot.addWidget(dialog)
        dialog._delete_selected()  # nothing selected
        assert asked == []
        dialog._list.item(1).setSelected(True)
        dialog._delete_selected()
        assert asked == [[orphans[1]]]
        assert dialog._label.text() == "1 orphan sidecar file(s):"
        assert dialog._list.item(0).text() == "a.xmp"

    def test_no_directory(self, window):
        window._files.current_dir = None
        assert window._files.orphan_sidecars() == []


# ---------------------------------------------------------------------------
# Rotations and EXIF orientation
# ---------------------------------------------------------------------------


class TestRotate:
    def test_rotate_and_undo(self, window, tmp_path, qtbot):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        _select(window, "a.png")
        window._ui.actionRotateRight.trigger()
        assert _size(a) == (20, 40)
        assert isinstance(window._undo._history[-1], RotationEntry)
        assert window._ui.btnUndo.isEnabled()
        assert window._files.selected_paths() == [a]
        window._on_undo()
        assert _size(a) == (40, 20)

    @pytest.mark.parametrize(
        ("action", "size"),
        [("actionRotateLeft", (20, 40)), ("actionRotate180", (40, 20))],
    )
    def test_other_rotations(self, window, tmp_path, action, size):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        _select(window, "a.png")
        getattr(window._ui, action).trigger()
        assert _size(a) == size

    def test_failure_reported(self, window, tmp_path, calls, monkeypatch):
        a = _jpeg(tmp_path / "a.jpg")

        def fail(_path, _op):
            raise RuntimeError("jpegtran: broken")

        monkeypatch.setattr(image_ops, "rotate_lossless", fail)
        window._images.rotate([a], 90)
        title, text, details = calls["warn"][0]
        assert text == "1 file(s) could not be rotated."
        assert "jpegtran: broken" in details
        assert len(window._undo) == 0

    @needs_jpegtran
    @needs_pyexiv2
    def test_apply_exif(self, window, tmp_path):
        a = _jpeg(tmp_path / "a.jpg", 6)
        b = _jpeg(tmp_path / "b.jpg")
        _load(window, tmp_path)
        _select(window, "a.jpg", "b.jpg")
        window._ui.actionRotateExif.trigger()
        assert _size(a) == (96, 160)
        assert _size(b) == (160, 96)
        assert window._undo._history[-1].items[0][2] == 6
        window._on_undo()
        assert image_ops.get_exif_orientation(a) == 6

    @needs_pyexiv2
    def test_reset_exif_and_undo(self, window, tmp_path):
        a = _jpeg(tmp_path / "a.jpg", 6)
        _jpeg(tmp_path / "b.jpg")
        _load(window, tmp_path)
        _select(window, "a.jpg", "b.jpg")
        window._ui.actionResetExif.trigger()
        assert image_ops.get_exif_orientation(a) is None
        assert isinstance(window._undo._history[-1], ExifResetEntry)
        assert window._undo._history[-1].items == [(a, 6)]
        window._on_undo()
        assert image_ops.get_exif_orientation(a) == 6

    def test_reset_exif_nothing(self, window, tmp_path):
        a = _png(tmp_path / "a.png")
        window._images.reset_exif([a])
        assert len(window._undo) == 0


def test_refresh_action_reloads(window, tmp_path):
    _png(tmp_path / "a.png")
    _load(window, tmp_path)
    _png(tmp_path / "b.png")
    window._ui.actionRefresh.trigger()
    assert _names(window) == ["a.png", "b.png"]


class TestSidecarGroupTargets:
    """A selected sidecar group targets its base file only (7.2 #2)."""

    def test_group_is_one_target(self, window, tmp_path, calls):
        _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        window._ui.chkSidecarMode.setChecked(True)
        _load(window, tmp_path)
        _select(window, "a.xmp")
        assert window._images.targets() == [str(tmp_path / "a.png")]
        assert window._ui.actionImgTemplate.isEnabled()
        window._images.open_selected()
        assert calls["open"] == [str(tmp_path / "a.png")]


class TestOpenSidecarMenu:
    """ "Open sidecar" submenu: one entry per suffix (7.2 #3)."""

    def _entries(self, window):
        window._images._fill_open_sidecar_menu()
        return [a.text() for a in window._ui.menuOpenSidecar.actions()]

    def test_disabled_without_sidecar(self, window, tmp_path):
        _png(tmp_path / "a.png")
        _load(window, tmp_path)
        _select(window, "a.png")
        assert self._entries(window) == []
        assert not window._ui.menuOpenSidecar.menuAction().isEnabled()

    def test_one_entry_per_suffix(self, window, tmp_path, calls):
        _png(tmp_path / "a.png")
        _png(tmp_path / "b.png")
        for name in ("a.xmp", "a.info", "b.xmp"):
            (tmp_path / name).write_text("x")
        _load(window, tmp_path)
        _select(window, "a.png", "b.png")
        assert self._entries(window) == ["info", "xmp (2)"]
        assert window._ui.menuOpenSidecar.menuAction().isEnabled()
        window._ui.menuOpenSidecar.actions()[1].trigger()
        assert calls["open"] == [str(tmp_path / "a.xmp"), str(tmp_path / "b.xmp")]

    def test_sidecar_selected_in_sidecar_mode(self, window, tmp_path, calls):
        _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        window._ui.chkSidecarMode.setChecked(True)
        _load(window, tmp_path)
        _select(window, "a.xmp")
        assert self._entries(window) == ["xmp"]

    def test_filled_when_menu_shown(self, window, tmp_path):
        _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        _load(window, tmp_path)
        _select(window, "a.png")
        window._ui.menuImages.aboutToShow.emit()
        assert window._ui.menuOpenSidecar.menuAction().isEnabled()

    def test_in_images_menu(self, window):
        actions = window._ui.menuImages.actions()
        assert window._ui.menuOpenSidecar.menuAction() in actions


class TestViewerFollowsSelection:
    """The open viewer follows the selection of the main window (7.2 #8)."""

    def _open(self, window, tmp_path, *names):
        paths = {n: _png(tmp_path / n) for n in names}
        (tmp_path / "t.txt").write_text("x")
        _load(window, tmp_path)
        window._images.show_in_viewer(paths[names[0]])
        return window._images._viewer, paths

    def _current(self, window, name):
        tree = window._ui.tblFiles
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            if item.text(0) == name:
                tree.setCurrentItem(item, 0, QItemSelectionModel.SelectionFlag.NoUpdate)

    def test_other_file_selected(self, window, tmp_path):
        viewer, p = self._open(window, tmp_path, "a.png", "b.png")
        window._files.select_paths([p["b.png"]])
        assert viewer.current_path == p["b.png"]
        assert viewer.selection_paths == [p["b.png"]]

    def test_selection_extended_and_reduced(self, window, tmp_path):
        viewer, p = self._open(window, tmp_path, "a.png", "b.png", "c.png")
        _select(window, "a.png")
        self._current(window, "c.png")
        _select(window, "a.png", "c.png")
        assert viewer.selection_paths == [p["a.png"], p["c.png"]]
        assert viewer.current_path == p["c.png"]  # the file just added
        assert viewer._strip.isVisible()
        self._current(window, "b.png")
        _select(window, "a.png", "b.png", "c.png")
        assert viewer.current_path == p["b.png"]
        self._current(window, "t.txt")
        _select(window, "b.png", "c.png")
        assert viewer.selection_paths == [p["b.png"], p["c.png"]]
        assert viewer.current_path == p["b.png"]  # kept: still selected
        _select(window, "c.png")
        assert viewer.selection_paths == [p["c.png"]]
        assert viewer.current_path == p["c.png"]
        assert not viewer._strip.isVisible()

    def test_empty_or_media_less_selection_ignored(self, window, tmp_path):
        viewer, p = self._open(window, tmp_path, "a.png", "b.png")
        _select(window, "b.png")
        _select(window)
        _select(window, "t.txt")
        assert viewer.selection_paths == [p["b.png"]]

    def test_unchanged_selection_not_reloaded(self, window, tmp_path, monkeypatch):
        viewer, p = self._open(window, tmp_path, "a.png", "b.png")
        _select(window, "a.png", "b.png")
        monkeypatch.setattr(viewer, "set_selection", pytest.fail)
        window._ui.actionRefresh.trigger()

    def test_hidden_viewer_untouched(self, window, tmp_path):
        viewer, p = self._open(window, tmp_path, "a.png", "b.png")
        viewer.hide()
        _select(window, "b.png")
        assert viewer.current_path == p["a.png"]

    def test_sidecar_group_gives_its_base(self, window, tmp_path):
        window._ui.chkSidecarMode.setChecked(True)
        viewer, p = self._open(window, tmp_path, "a.png", "b.png")
        (tmp_path / "b.xmp").write_text("x")
        window._ui.actionRefresh.trigger()
        self._current(window, "b.xmp")
        _select(window, "b.xmp")
        assert viewer.selection_paths == [p["b.png"]]
        assert viewer.current_path == p["b.png"]

    def test_arrow_with_single_file_moves_selection(self, window, tmp_path):
        viewer, p = self._open(window, tmp_path, "a.png", "b.png")
        window._files.select_paths([p["a.png"]])
        viewer._act_next()
        assert window._files.selected_paths() == [p["b.png"]]
        assert viewer.current_path == p["b.png"]
