"""Tests for pbrenamer.ui.file_actions — the File and Images menus, the viewer
wiring, deletion, orphan sidecars, Template and rotations."""

from __future__ import annotations

import io
import os

import pytest
from PIL import Image
from PySide6.QtCore import QItemSelectionModel, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from pbrenamer import profiles
from pbrenamer.core import image_ops
from pbrenamer.core.undo import DeleteEntry, ExifResetEntry, RotationEntry
from pbrenamer.platform import trash as system_trash
from pbrenamer.ui import file_actions, file_list
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

    monkeypatch.setattr(file_actions, "_ask", ask)
    monkeypatch.setattr(
        file_actions,
        "_warn",
        lambda _p, title, text, details="": record["warn"].append(
            (title, text, details)
        ),
    )
    monkeypatch.setattr(file_actions, "_open_path", record["open"].append)
    monkeypatch.setattr(file_list, "_open_path", record["open"].append)
    monkeypatch.setattr(
        file_actions._open_with,
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


def _selected_names(window):
    tree = window._ui.tblFiles
    items = sorted(tree.selectedItems(), key=tree.indexOfTopLevelItem)
    return [item.text(0) for item in items]


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
        assert window._file_actions.targets() == [a]

    def test_current_row_without_selection(self, window, tmp_path):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._ui.tblFiles.clearSelection()
        assert window._file_actions.targets() == [a]

    def test_nothing(self, window):
        window._ui.tblFiles.clear()
        assert window._file_actions.targets() == []

    def test_directories_ignored(self, window, tmp_path):
        (tmp_path / "sub").mkdir()
        window._ui.cmbMode.setCurrentIndex(2)
        _load(window, tmp_path)
        _select(window, "sub")
        assert window._file_actions.targets() == []


class TestUpdateEnabled:
    def test_no_target(self, window):
        window._ui.tblFiles.clear()
        window._file_actions.update_enabled()
        ui = window._ui
        for act in (
            ui.actionFileOpen,
            ui.actionImageView,
            ui.actionFileTemplate,
            ui.actionFileDelete,
            ui.actionRotateLeft,
            ui.actionRotateExif,
        ):
            assert not act.isEnabled()

    def test_one_image(self, window, tmp_path):
        _png(tmp_path / "a.png")
        _load(window, tmp_path)
        _select(window, "a.png")
        ui = window._ui
        assert ui.actionFileOpen.isEnabled()
        assert ui.actionImageView.isEnabled()
        assert ui.actionFileTemplate.isEnabled()
        assert ui.actionRotateLeft.isEnabled()
        assert not ui.actionRotateExif.isEnabled()
        assert not ui.actionResetExif.isEnabled()

    def test_text_file(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / "b.txt").write_text("x")
        _load(window, tmp_path)
        _select(window, "a.txt", "b.txt")
        ui = window._ui
        assert ui.actionFileOpen.isEnabled()
        assert not ui.actionImageView.isEnabled()
        assert not ui.actionFileTemplate.isEnabled()
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
        monkeypatch.setattr(file_actions, "_EXIF_CHECK_MAX", 0)
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
        window._ui.menuFile.aboutToShow.emit()
        assert window._ui.actionFileOrphans.isEnabled()
        os.remove(tmp_path / "lone.xmp")
        window._ui.menuContext.aboutToShow.emit()
        assert not window._ui.actionFileOrphans.isEnabled()


# ---------------------------------------------------------------------------
# Open, Open with
# ---------------------------------------------------------------------------


def test_open_and_open_with(window, tmp_path, calls):
    a = _png(tmp_path / "a.png")
    _load(window, tmp_path)
    _select(window, "a.png")
    window._ui.actionFileOpen.trigger()
    window._ui.actionFileOpenWith.trigger()
    assert calls["open"] == [a]
    assert calls["open_with"] == [a]


class TestOpenWithLast:
    def test_disabled_without_last_application(self, window, tmp_path, monkeypatch):
        monkeypatch.setattr(file_actions._open_with, "last_app", lambda p: None)
        _png(tmp_path / "a.png")
        _load(window, tmp_path)
        _select(window, "a.png")
        window._file_actions._update_open_with_last()
        action = window._ui.actionFileOpenWithLast
        assert not action.isEnabled()
        assert action.text() == "Open with the last application"

    def test_disabled_without_target(self, window, tmp_path):
        _load(window, tmp_path)
        window._file_actions._update_open_with_last()
        assert not window._ui.actionFileOpenWithLast.isEnabled()

    def test_names_the_application_and_opens(self, window, tmp_path, monkeypatch):
        opened = []
        monkeypatch.setattr(file_actions._open_with, "last_app", lambda p: "A&B")
        monkeypatch.setattr(file_actions._open_with, "open_with_last", opened.append)
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        _select(window, "a.png")
        window._ui.menuFile.aboutToShow.emit()
        action = window._ui.actionFileOpenWithLast
        assert action.isEnabled()
        assert action.text() == "Open with A&&B"
        action.trigger()
        assert opened == [a]

    def test_in_file_and_context_menus(self, window):
        ui = window._ui
        for menu in (ui.menuFile, ui.menuContext):
            actions = menu.actions()
            index = actions.index(ui.actionFileOpenWith)
            assert actions[index + 1] is ui.actionFileOpenWithLast


# ---------------------------------------------------------------------------
# Viewer
# ---------------------------------------------------------------------------


class TestViewer:
    def test_view_selection(self, window, tmp_path):
        a = _png(tmp_path / "a.png")
        b = _png(tmp_path / "b.png")
        _load(window, tmp_path)
        _select(window, "a.png", "b.png")
        window._ui.actionImageView.trigger()
        viewer = window._file_actions._viewer
        assert viewer.isVisible()
        assert viewer.current_path == a
        assert viewer._selection_paths == [a, b]

    def test_view_without_media(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        _load(window, tmp_path)
        window._file_actions.view_selected()
        assert window._file_actions._viewer is None

    def test_double_click_reuses_viewer(self, window, tmp_path):
        _png(tmp_path / "a.png")
        b = _png(tmp_path / "b.png")
        _load(window, tmp_path)
        tree = window._ui.tblFiles
        window._files._on_item_double_clicked(tree.topLevelItem(0), 2)
        viewer = window._file_actions._viewer
        window._files._on_item_double_clicked(tree.topLevelItem(1), 2)
        assert window._file_actions._viewer is viewer
        assert viewer.current_path == b
        assert viewer._selection_paths == [b]

    def test_viewer_settings_from_profile(self, window, tmp_path):
        data = profiles.load()
        data["viewer"].update(metadata_panel_side="left", zoom_max_percent=100)
        profiles.save(data)
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._file_actions.show_in_viewer(a)
        viewer = window._file_actions._viewer
        assert viewer._splitter.widget(0) is viewer._metadata_panel
        assert viewer._zoom_max == 1.0

    def test_navigation(self, window, tmp_path):
        a = _png(tmp_path / "a.png")
        (tmp_path / "b.txt").write_text("x")
        c = _png(tmp_path / "c.png")
        _load(window, tmp_path)
        window._file_actions.show_in_viewer(a)
        viewer = window._file_actions._viewer
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
        window._file_actions.show_in_viewer(a)
        viewer = window._file_actions._viewer
        viewer._current_path = str(tmp_path / "elsewhere.png")
        viewer.navigate_next.emit()
        assert viewer.current_path == str(tmp_path / "elsewhere.png")
        viewer._current_path = None
        viewer.navigate_next.emit()

    def test_requests_from_viewer(self, window, tmp_path, calls, monkeypatch):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._file_actions.show_in_viewer(a)
        viewer = window._file_actions._viewer
        viewer.open_requested.emit()
        viewer.open_with_requested.emit()
        assert calls["open"] == [a]
        assert calls["open_with"] == [a]
        templates = []
        monkeypatch.setattr(window._file_actions, "template", templates.append)
        viewer.template_requested.emit()
        assert templates == [a]
        fields = []
        window._files.field_requested.connect(fields.append)
        viewer.field_requested.emit("{date}")
        assert fields == ["{date}"]

    def test_rotate_from_viewer(self, window, tmp_path, monkeypatch):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._file_actions.show_in_viewer(a)
        viewer = window._file_actions._viewer
        done = []
        monkeypatch.setattr(
            window._file_actions, "rotate", lambda p, op: done.append(op)
        )
        monkeypatch.setattr(
            window._file_actions, "reset_exif", lambda p: done.append("r")
        )
        viewer.rotate_requested.emit(90)
        viewer.rotate_requested.emit("reset_exif")
        assert done == [90, "r"]
        viewer._current_path = None
        viewer.rotate_requested.emit(90)
        viewer.open_requested.emit()
        assert done == [90, "r"]

    def test_delete_from_viewer(self, window, tmp_path, calls, monkeypatch):
        monkeypatch.setattr(system_trash, "move_to_trash", lambda p: os.remove(p) or p)
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._file_actions.show_in_viewer(a)
        window._file_actions._viewer.delete_requested.emit()
        assert not os.path.exists(a)

    @pytest.mark.parametrize(
        ("shown", "circular", "expected"),
        [
            ("b.png", False, "c.png"),  # next file of the selection
            ("c.png", True, "a.png"),  # last one, circular: the first
            ("c.png", False, "b.png"),  # last one, linear: the previous
        ],
    )
    def test_delete_from_viewer_selection(
        self, window, tmp_path, calls, monkeypatch, shown, circular, expected
    ):
        monkeypatch.setattr(system_trash, "move_to_trash", lambda p: os.remove(p) or p)
        p = {n: _png(tmp_path / n) for n in ("a.png", "b.png", "c.png")}
        _load(window, tmp_path)
        _select(window, "a.png", "b.png", "c.png")
        window._file_actions.show_in_viewer(p[shown])
        viewer = window._file_actions._viewer
        viewer._circular = circular
        viewer.delete_requested.emit()
        remaining = [p[n] for n in ("a.png", "b.png", "c.png") if n != shown]
        assert viewer.selection_paths == remaining
        assert viewer.current_path == p[expected]
        assert viewer._strip.isVisible()
        current = window._ui.tblFiles.currentItem()
        assert current.data(0, Qt.ItemDataRole.UserRole) == p[expected]

    def test_delete_from_viewer_selection_of_two(
        self, window, tmp_path, calls, monkeypatch
    ):
        monkeypatch.setattr(system_trash, "move_to_trash", lambda p: os.remove(p) or p)
        a, b = _png(tmp_path / "a.png"), _png(tmp_path / "b.png")
        _load(window, tmp_path)
        _select(window, "a.png", "b.png")
        window._file_actions.show_in_viewer(a)
        viewer = window._file_actions._viewer
        viewer.delete_requested.emit()
        assert viewer.selection_paths == [b]
        assert viewer.current_path == b
        assert not viewer._strip.isVisible()

    def test_delete_from_viewer_declined(self, window, tmp_path, calls):
        a, b = _png(tmp_path / "a.png"), _png(tmp_path / "b.png")
        _load(window, tmp_path)
        _select(window, "a.png", "b.png")
        window._file_actions.show_in_viewer(a)
        viewer = window._file_actions._viewer
        calls["answer"]["ask"] = False
        viewer.delete_requested.emit()
        assert os.path.exists(a)
        assert viewer.selection_paths == [a, b]
        assert viewer.current_path == a

    def test_delete_from_viewer_nothing_shown(self, window, tmp_path, calls):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._file_actions.show_in_viewer(a)
        window._file_actions._viewer._current_path = None
        window._file_actions._viewer.delete_requested.emit()
        assert os.path.exists(a)

    def test_reload_refreshes_viewer(self, window, tmp_path, monkeypatch):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._file_actions.show_in_viewer(a)
        refreshed = []
        monkeypatch.setattr(
            window._file_actions._viewer, "refresh_paths", refreshed.append
        )
        window._files.reload()
        assert refreshed == [{a}]

    def test_profile_change_closes_viewer(self, window, tmp_path):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._file_actions.show_in_viewer(a)
        window._file_actions.apply_profile()
        assert window._file_actions._viewer is None
        window._file_actions.apply_profile()  # no viewer: no-op


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

        monkeypatch.setattr(file_actions, "_exec_dialog", accept)
        window._ui.tabRules.setCurrentIndex(0)
        window._ui.actionFileTemplate.trigger()
        assert shown == ["Proposed template"]
        assert window._schema.fields() == ["Nature", "", "", "", "", "###"]
        assert window._ui.tabRules.currentIndex() == _SCHEMA_TAB

    def test_rejected(self, window, tmp_path, monkeypatch):
        self._history()
        a = _png(tmp_path / "Nature_001.png")
        monkeypatch.setattr(
            file_actions, "_exec_dialog", lambda d: QDialog.DialogCode.Rejected
        )
        accepted = []
        window._file_actions.template_accepted.connect(accepted.append)
        window._file_actions.template(a)
        assert accepted == []

    def test_no_match(self, window, tmp_path, calls):
        a = _png(tmp_path / "x.png")
        window._file_actions.template(a)
        assert "x.png" in calls["info"][0]

    def test_needs_one_file(self, window, tmp_path, monkeypatch):
        _png(tmp_path / "a.png")
        _png(tmp_path / "b.png")
        _load(window, tmp_path)
        _select(window, "a.png", "b.png")
        monkeypatch.setattr(window._file_actions, "template", lambda p: pytest.fail(p))
        window._file_actions.template_selected()


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDelete:
    @pytest.fixture
    def trash(self, monkeypatch, tmp_path_factory):
        """Fake freedesktop system trash: files moved to Trash/files."""
        root = tmp_path_factory.mktemp("Trash")
        (root / "files").mkdir()
        (root / "info").mkdir()
        trashed = []

        def move(path):
            trashed.append(path)
            where = root / "files" / f"{len(trashed)}-{os.path.basename(path)}"
            os.rename(path, where)
            (root / "info" / f"{where.name}.trashinfo").write_text("[Trash Info]")
            return str(where)

        monkeypatch.setattr(system_trash, "move_to_trash", move)
        return trashed

    def _set(self, **options):
        data = profiles.load()
        data["files"].update(options)
        profiles.save(data)

    def test_to_trash_with_sidecars(self, window, tmp_path, calls, trash):
        a = _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        b = _png(tmp_path / "b.png")
        window._ui.chkSidecarMode.setChecked(True)
        _load(window, tmp_path)
        _select(window, "a.png")
        window._ui.actionFileDelete.trigger()
        assert trash == [a, str(tmp_path / "a.xmp")]
        assert calls["ask"] == ["Move to trash:\na.png\na.xmp"]
        assert _names(window) == ["b.png"]
        assert window._ui.tblFiles.currentItem().data(0, Qt.ItemDataRole.UserRole) == b

    def test_sidecars_independent_outside_sidecar_mode(
        self, window, tmp_path, calls, trash
    ):
        # The sidecar is left behind, orphaned: outside sidecar mode it is
        # an ordinary file, deleted only when selected itself.
        a = _png(tmp_path / "a.png")
        _png(tmp_path / "b.png")
        (tmp_path / "a.xmp").write_text("x")
        _load(window, tmp_path)
        _select(window, "a.png")
        window._ui.actionFileDelete.trigger()
        assert trash == [a]
        assert calls["ask"] == ["Move to trash:\na.png"]
        assert sorted(_names(window)) == ["a.xmp", "b.png"]

    @staticmethod
    def _selected(window):
        return [n.split("\n")[0] for n in _selected_names(window)]

    @pytest.mark.parametrize(
        ("deleted", "expected"),
        [("b.png", "c.png"), ("c.png", "b.png")],  # next, or previous at the end
    )
    def test_selects_neighbour(self, window, tmp_path, calls, trash, deleted, expected):
        for name in ("a.png", "b.png", "c.png"):
            _png(tmp_path / name)
        _load(window, tmp_path)
        _select(window, deleted)
        window._ui.actionFileDelete.trigger()
        assert self._selected(window) == [expected]

    def test_viewer_follows_list_deletion(self, window, tmp_path, calls, trash):
        a = _png(tmp_path / "a.png")
        (tmp_path / "b.txt").write_text("x")
        c = _png(tmp_path / "c.png")
        _load(window, tmp_path)
        _select(window, "a.png")
        window._file_actions.show_in_viewer(a)
        viewer = window._file_actions._viewer
        window._ui.actionFileDelete.trigger()
        # b.txt is selected, but the viewer shows the nearest media file.
        assert self._selected(window) == ["b.txt"]
        assert viewer.current_path == c

    @pytest.mark.parametrize(
        ("deleted", "expected"),
        [("a.png", "c.png"), ("c.png", "a.png")],  # b.txt is no media
    )
    def test_from_viewer_selects_neighbour_media(
        self, window, tmp_path, calls, trash, deleted, expected
    ):
        p = {n: _png(tmp_path / n) for n in ("a.png", "c.png")}
        (tmp_path / "b.txt").write_text("x")
        _load(window, tmp_path)
        _select(window, deleted)
        window._file_actions.show_in_viewer(p[deleted])
        viewer = window._file_actions._viewer
        viewer.delete_requested.emit()
        assert self._selected(window) == [expected]
        assert viewer.current_path == p[expected]
        assert viewer.isVisible()

    def test_from_viewer_navigation_still_works(self, window, tmp_path, calls, trash):
        p = {n: _png(tmp_path / n) for n in ("a.png", "b.png", "c.png")}
        _load(window, tmp_path)
        _select(window, "a.png")
        window._file_actions.show_in_viewer(p["a.png"])
        viewer = window._file_actions._viewer
        viewer.delete_requested.emit()
        assert viewer.current_path == p["b.png"]
        viewer.navigate_next.emit()
        assert viewer.current_path == p["c.png"]
        viewer.navigate_prev.emit()
        assert viewer.current_path == p["b.png"]

    def test_from_viewer_keeps_keyboard(
        self, window, qtbot, tmp_path, trash, monkeypatch
    ):
        """Through the real confirmation box: once it is closed, the viewer
        is the active window again, so its arrow keys still work."""

        def accept_box():
            box = QApplication.activeModalWidget()
            if isinstance(box, QMessageBox):
                box.button(QMessageBox.StandardButton.Yes).click()
            else:
                QTimer.singleShot(20, accept_box)

        real_ask = file_actions._ask

        def ask(*args):
            QTimer.singleShot(20, accept_box)
            return real_ask(*args)

        monkeypatch.setattr(file_actions, "_ask", ask)
        p = {n: _png(tmp_path / n) for n in ("a.png", "b.png", "c.png")}
        _load(window, tmp_path)
        _select(window, "a.png")
        window._file_actions.show_in_viewer(p["a.png"])
        viewer = window._file_actions._viewer
        viewer.activateWindow()
        qtbot.waitUntil(viewer.isActiveWindow)
        QTest.keyClick(viewer, Qt.Key.Key_Delete)
        assert viewer.current_path == p["b.png"]
        qtbot.waitUntil(viewer.isActiveWindow)
        QTest.keyClick(viewer, Qt.Key.Key_Right)
        assert viewer.current_path == p["c.png"]

    def test_from_viewer_without_confirmation(self, window, tmp_path, calls, trash):
        """The viewer's button skips the question, the profile is unchanged."""
        a, _b = _png(tmp_path / "a.png"), _png(tmp_path / "b.png")
        _load(window, tmp_path)
        _select(window, "a.png")
        window._file_actions.show_in_viewer(a)
        viewer = window._file_actions._viewer
        assert viewer.confirm_deletions is True
        viewer._act_toggle_confirm()
        viewer.delete_requested.emit()
        assert trash == [a]
        assert calls["ask"] == []
        assert profiles.load()["files"]["confirm_deletions"] is True

    def test_from_viewer_confirmation_without_profile_one(
        self, window, tmp_path, calls, trash
    ):
        self._set(confirm_deletions=False)
        a = _png(tmp_path / "a.png")
        _png(tmp_path / "b.png")
        _load(window, tmp_path)
        _select(window, "a.png")
        window._file_actions.show_in_viewer(a)
        viewer = window._file_actions._viewer
        assert viewer.confirm_deletions is False
        viewer._act_toggle_confirm()
        viewer.delete_requested.emit()
        assert calls["ask"] == ["Move to trash:\na.png"]
        assert profiles.load()["files"]["confirm_deletions"] is False

    def test_from_viewer_selection_without_confirmation(
        self, window, tmp_path, calls, trash
    ):
        a = _png(tmp_path / "a.png")
        _png(tmp_path / "b.png")
        _load(window, tmp_path)
        _select(window, "a.png", "b.png")
        window._file_actions.show_in_viewer(a)
        viewer = window._file_actions._viewer
        viewer.set_confirm_deletions(False)
        viewer.delete_requested.emit()
        assert trash == [a]
        assert calls["ask"] == []

    def test_viewer_confirmation_reset_on_reopen(self, window, tmp_path, calls):
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._file_actions.show_in_viewer(a)
        viewer = window._file_actions._viewer
        viewer.set_confirm_deletions(False)
        window._file_actions.show_in_viewer(a)  # still open: kept
        assert viewer.confirm_deletions is False
        viewer.close()
        window._file_actions.show_in_viewer(a)
        assert window._file_actions._viewer is viewer
        assert viewer.confirm_deletions is True

    def test_from_viewer_last_media_closes_it(self, window, tmp_path, calls, trash):
        a = _png(tmp_path / "a.png")
        (tmp_path / "b.txt").write_text("x")
        _load(window, tmp_path)
        _select(window, "a.png")
        window._file_actions.show_in_viewer(a)
        viewer = window._file_actions._viewer
        viewer.delete_requested.emit()
        assert not viewer.isVisible()
        assert self._selected(window) == ["b.txt"]

    def test_declined(self, window, tmp_path, calls, trash):
        a = _png(tmp_path / "a.png")
        calls["answer"]["ask"] = False
        _load(window, tmp_path)
        window._file_actions.delete([a])
        assert trash == []
        assert os.path.exists(a)

    def test_without_confirmation(self, window, tmp_path, calls, trash):
        self._set(confirm_deletions=False)
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._file_actions.delete([a])
        assert trash == [a]
        assert calls["ask"] == []

    def test_count_only_above_limit(self, window, tmp_path, calls, trash):
        self._set(delete_list_max_files=1)
        paths = [_png(tmp_path / "a.png"), _png(tmp_path / "b.png")]
        _load(window, tmp_path)
        window._file_actions.delete(paths)
        assert calls["ask"] == ["Move 2 files to trash?"]

    def test_trash_failure(self, window, tmp_path, calls, monkeypatch):
        monkeypatch.setattr(system_trash, "move_to_trash", lambda p: None)
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._file_actions.delete([a])
        assert calls["warn"][0][1] == "Could not move to trash: a.png"

    def test_permanent(self, window, tmp_path, calls):
        self._set(deletion_mode="delete")
        sub = tmp_path / "sub"
        sub.mkdir()
        a = _png(sub / "a.png")
        window._ui.chkRecursive.setChecked(True)
        _load(window, tmp_path)
        window._file_actions.delete([a])
        assert calls["ask"] == ["Permanently delete:\na.png"]
        assert not os.path.exists(a)
        assert sub.is_dir()  # empty folders kept by default

    @pytest.mark.parametrize("mode", ["delete", "system", "session"])
    @pytest.mark.parametrize(("parents", "kept"), [(False, True), (True, False)])
    def test_emptied_folders_removed(
        self, window, tmp_path, calls, trash, mode, parents, kept
    ):
        self._set(
            deletion_mode=mode, prune_dirs_on_delete=True, prune_parent_dirs=parents
        )
        deep = tmp_path / "sub" / "deep"
        deep.mkdir(parents=True)
        other = tmp_path / "other"
        other.mkdir()
        a = _png(deep / "a.png")
        b = _png(other / "b.png")
        _png(other / "c.png")
        window._ui.chkRecursive.setChecked(True)
        _load(window, tmp_path)
        window._file_actions.delete([a, b])
        assert not deep.exists()
        assert (tmp_path / "sub").exists() is kept
        assert other.is_dir()  # not empty
        assert tmp_path.is_dir()  # not empty

    @pytest.mark.parametrize(("parents", "shown"), [(False, "top"), (True, "")])
    def test_emptied_displayed_folder_removed(
        self, window, tmp_path, calls, parents, shown
    ):
        self._set(
            deletion_mode="delete", prune_dirs_on_delete=True, prune_parent_dirs=parents
        )
        folder = tmp_path / "top" / "shown"
        folder.mkdir(parents=True)
        (tmp_path / "keep").touch()
        a = _png(folder / "a.png")
        _load(window, folder)
        window._file_actions.delete([a])
        assert not folder.exists()
        assert window._files.current_dir == str(tmp_path / shown)

    def test_emptied_folder_restored_by_undo(self, window, tmp_path, calls, trash):
        self._set(deletion_mode="session", prune_dirs_on_delete=True)
        sub = tmp_path / "sub"
        sub.mkdir()
        a = _png(sub / "a.png")
        window._ui.chkRecursive.setChecked(True)
        _load(window, tmp_path)
        window._file_actions.delete([a])
        assert not sub.exists()
        window._on_undo()
        assert os.path.isfile(a)

    def test_permanent_count_and_error(self, window, tmp_path, calls, monkeypatch):
        self._set(deletion_mode="delete", delete_list_max_files=1)
        paths = [_png(tmp_path / "a.png"), _png(tmp_path / "b.png")]
        (tmp_path / "keep.txt").write_text("x")
        _load(window, tmp_path)
        real_remove = os.remove

        def remove(path):
            if path.endswith("b.png"):
                raise OSError("busy")
            real_remove(path)

        monkeypatch.setattr(file_actions.os, "remove", remove)
        window._file_actions.delete(paths)
        assert calls["ask"] == ["Permanently delete 2 files?"]
        assert calls["warn"][0][1] == "b.png: busy"
        assert _names(window) == ["b.png", "keep.txt"]

    def test_nothing(self, window, calls):
        window._file_actions.delete([])
        assert calls["ask"] == []

    def test_permanent_not_undoable(self, window, tmp_path, calls):
        self._set(deletion_mode="delete")
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._file_actions.delete([a])
        assert not window._undo.can_undo()

    def test_system_trash_undo(self, window, tmp_path, calls, trash):
        a = _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        _load(window, tmp_path)
        window._file_actions.delete([a])
        assert not os.path.exists(a)
        assert window._ui.btnUndo.isEnabled()
        window._on_undo()
        assert os.path.exists(a)
        assert (tmp_path / "a.xmp").exists()
        assert _names(window) == ["a.png", "a.xmp"]
        assert calls["warn"] == []

    def test_session_trash_undo(self, window, tmp_path, calls):
        self._set(deletion_mode="session")
        a = _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        window._ui.chkSidecarMode.setChecked(True)
        _load(window, tmp_path)
        window._file_actions.delete([a])
        assert calls["ask"] == ["Move to the session trash:\na.png\na.xmp"]
        trash_dir = window._trash.directory
        assert sorted(p.name for p in trash_dir.iterdir()) == [
            "000001.cache",
            "000002.cache",
        ]
        entry = window._undo._history[-1]
        assert isinstance(entry, DeleteEntry) and not entry.system
        window._on_undo()
        assert os.path.exists(a)
        assert (tmp_path / "a.xmp").read_text() == "x"
        assert list(trash_dir.iterdir()) == []

    def test_session_trash_removed_on_close(self, window, tmp_path, calls):
        self._set(deletion_mode="session", confirm_deletions=False)
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)
        window._file_actions.delete([a])
        trash_dir = window._trash.directory
        assert trash_dir.exists()
        window.close()
        assert not trash_dir.exists()
        assert not window._undo.can_undo()

    @pytest.mark.parametrize("accept", [True, False])
    def test_session_trash_other_filesystem(
        self, window, tmp_path, calls, monkeypatch, accept
    ):
        self._set(deletion_mode="session", confirm_deletions=False)
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)

        def put(path):
            raise file_actions.CrossDeviceError(18, "cross-device", path)

        monkeypatch.setattr(window._trash, "put", put)
        monkeypatch.setattr(file_actions, "_ask", lambda p, t, text: accept)
        deleted = window._file_actions.delete_files([a], window)
        assert deleted == ([a] if accept else [])
        assert os.path.exists(a) is not accept
        assert not window._undo.can_undo()

    def test_session_trash_error(self, window, tmp_path, calls, monkeypatch):
        self._set(deletion_mode="session", confirm_deletions=False)
        a = _png(tmp_path / "a.png")
        _load(window, tmp_path)

        def put(path):
            raise OSError("busy")

        monkeypatch.setattr(window._trash, "put", put)
        assert window._file_actions.delete_files([a], window) == []
        assert calls["warn"][0][1] == "a.png: busy"
        assert not window._undo.can_undo()

    def test_session_trash_other_filesystem_text(self):
        images = {"delete_list_max_files": 1}
        text = file_actions.FileActions._foreign_text(["/x/a.png"], images)
        assert "a.png" in text and "cannot be undone" in text
        text = file_actions.FileActions._foreign_text(["/a", "/b"], images)
        assert text.startswith("2 files")

    def test_session_count_only_above_limit(self):
        images = {"delete_list_max_files": 1, "deletion_mode": "session"}
        text = file_actions.FileActions._confirm_text(["a", "b"], images)
        assert text == "Move 2 files to the session trash?"


# ---------------------------------------------------------------------------
# Orphan sidecars
# ---------------------------------------------------------------------------


class TestOrphans:
    def test_delete_all(self, window, tmp_path, calls, monkeypatch):
        monkeypatch.setattr(system_trash, "move_to_trash", lambda p: os.remove(p) or p)
        _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        (tmp_path / "lone.xmp").write_text("x")
        _load(window, tmp_path)
        shown = []

        def run(dialog):
            shown.append(dialog._list.count())
            dialog._delete_all()
            return dialog.result()

        monkeypatch.setattr(file_actions, "_exec_dialog", run)
        window._ui.actionFileOrphans.setEnabled(True)
        window._ui.actionFileOrphans.trigger()
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
        window._file_actions.rotate([a], 90)
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

    def test_progress_window_cancel(self, window, tmp_path, monkeypatch):
        """From the threshold on, the progress window shows; Cancel keeps the
        files already rotated, undoable."""
        from pbrenamer.ui import progress as progress_mod

        paths = [str(tmp_path / f"{i:03}.png") for i in range(60)]
        shown = []
        rotated = []

        real_step = progress_mod.FileProgress.step

        def step(self):
            shown.append(self.visible)
            if len(rotated) == 5:
                self.cancel()
            return real_step(self)

        monkeypatch.setattr(progress_mod.FileProgress, "step", step)
        monkeypatch.setattr(image_ops, "get_exif_orientation", lambda p: None)
        monkeypatch.setattr(
            image_ops, "rotate_lossless", lambda p, op: rotated.append(p) or -90
        )
        window._file_actions.rotate(paths, 90)
        assert all(shown)
        assert rotated == paths[:5]
        assert window._undo._history[-1].items == [(p, -90, None) for p in paths[:5]]

    def test_no_progress_window_below_threshold(self, window, tmp_path, monkeypatch):
        from pbrenamer.ui import progress as progress_mod

        shown = []
        real_step = progress_mod.FileProgress.step

        def step(self):
            shown.append(self.visible)
            return real_step(self)

        monkeypatch.setattr(progress_mod.FileProgress, "step", step)
        monkeypatch.setattr(image_ops, "get_exif_orientation", lambda p: None)
        monkeypatch.setattr(image_ops, "rotate_lossless", lambda p, op: -90)
        window._file_actions.rotate([str(tmp_path / f"{i}.png") for i in range(49)], 90)
        assert shown == [False] * 49

    def test_reset_exif_cancel(self, window, tmp_path, monkeypatch):
        from pbrenamer.ui import progress as progress_mod

        monkeypatch.setattr(progress_mod.FileProgress, "step", lambda self: False)
        reset = []
        monkeypatch.setattr(
            image_ops, "set_exif_orientation", lambda p, o: reset.append(p)
        )
        window._file_actions.reset_exif([str(tmp_path / f"{i}.jpg") for i in range(60)])
        assert reset == []
        assert len(window._undo) == 0

    def test_reset_exif_nothing(self, window, tmp_path):
        a = _png(tmp_path / "a.png")
        window._file_actions.reset_exif([a])
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
        assert window._file_actions.targets() == [str(tmp_path / "a.png")]
        assert window._ui.actionFileTemplate.isEnabled()
        window._file_actions.open_selected()
        assert calls["open"] == [str(tmp_path / "a.png")]

    def test_deselect_takes_the_group(self, window, tmp_path):
        a = _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        b = _png(tmp_path / "b.png")
        window._ui.chkSidecarMode.setChecked(True)
        _load(window, tmp_path)
        _select(window, "a.png", "a.xmp", "b.png")
        window._files.deselect_paths([a])
        assert window._files.selected_paths() == [b]


class TestOpenSidecarMenu:
    """ "Open or create sidecar" submenu: one entry per sidecar suffix of the
    category of the targeted files, existing or not, in any sidecar mode."""

    def _entries(self, window):
        window._file_actions._fill_open_sidecar_menu()
        return [a.text() for a in window._ui.menuOpenSidecar.actions()]

    def test_every_suffix_of_the_category(self, window, tmp_path):
        _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        _load(window, tmp_path)
        _select(window, "a.png")
        assert self._entries(window) == ["info (new)", "xmp"]
        assert window._ui.menuOpenSidecar.menuAction().isEnabled()

    def test_missing_sidecar_created_then_opened(self, window, tmp_path, calls):
        _png(tmp_path / "a.png")
        _load(window, tmp_path)
        _select(window, "a.png")
        self._entries(window)
        window._ui.menuOpenSidecar.actions()[0].trigger()  # info (new)
        created = tmp_path / "a.info"
        assert created.read_text() == ""
        assert calls["open"] == [str(created)]
        assert "a.info" in _names(window)

    def test_existing_sidecar_found_in_any_case(self, window, tmp_path, calls):
        _png(tmp_path / "a.png")
        (tmp_path / "a.XMP").write_text("x")
        _load(window, tmp_path)
        _select(window, "a.png")
        assert self._entries(window) == ["info (new)", "xmp"]
        window._ui.menuOpenSidecar.actions()[1].trigger()
        assert calls["open"] == [str(tmp_path / "a.XMP")]
        assert sorted(p.name for p in tmp_path.iterdir()) == ["a.XMP", "a.png"]

    def test_several_files(self, window, tmp_path, calls):
        _png(tmp_path / "a.png")
        _png(tmp_path / "b.png")
        (tmp_path / "a.xmp").write_text("x")
        _load(window, tmp_path)
        _select(window, "a.png", "b.png")
        assert self._entries(window) == ["info (2)", "xmp (2)"]
        window._ui.menuOpenSidecar.actions()[1].trigger()
        assert calls["open"] == [str(tmp_path / "a.xmp"), str(tmp_path / "b.xmp")]
        assert (tmp_path / "b.xmp").read_text() == ""

    def test_disabled_for_a_sidecar_outside_sidecar_mode(self, window, tmp_path):
        _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        _load(window, tmp_path)
        _select(window, "a.xmp")
        assert self._entries(window) == []
        assert not window._ui.menuOpenSidecar.menuAction().isEnabled()

    def test_disabled_without_sidecar_suffix(self, window, tmp_path):
        # The "other" category has no sidecar suffix by default.
        (tmp_path / "notes.txt").write_text("x")
        _load(window, tmp_path)
        _select(window, "notes.txt")
        assert self._entries(window) == []
        assert not window._ui.menuOpenSidecar.menuAction().isEnabled()

    def test_sidecar_selected_in_sidecar_mode_targets_base(self, window, tmp_path):
        _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        window._ui.chkSidecarMode.setChecked(True)
        _load(window, tmp_path)
        _select(window, "a.xmp")
        assert self._entries(window) == ["info (new)", "xmp"]

    def test_filled_when_menu_shown(self, window, tmp_path):
        _png(tmp_path / "a.png")
        (tmp_path / "a.xmp").write_text("x")
        _load(window, tmp_path)
        _select(window, "a.png")
        window._ui.menuContext.aboutToShow.emit()
        assert window._ui.menuOpenSidecar.menuAction().isEnabled()

    def test_in_file_and_context_menus(self, window):
        sidecar = window._ui.menuOpenSidecar.menuAction()
        assert sidecar in window._ui.menuFile.actions()
        assert sidecar in window._ui.menuContext.actions()
        assert sidecar not in window._ui.menuImages.actions()


class TestMenus:
    """File: any file; Images: images and videos; context menu: both."""

    def test_split(self, window):
        ui = window._ui
        file_menu = ui.menuFile.actions()
        images_menu = ui.menuImages.actions()
        context = ui.menuContext.actions()
        for act in (ui.actionFileOpen, ui.actionFileDelete, ui.actionFileOrphans):
            assert act in file_menu
            assert act not in images_menu
            assert act in context
        for act in (ui.actionImageView, ui.actionRotateLeft, ui.actionResetExif):
            assert act in images_menu
            assert act not in file_menu
            assert act in context
        assert ui.actionQuit in file_menu
        assert ui.actionQuit not in context


class TestViewerFollowsSelection:
    """The open viewer follows the selection of the main window (7.2 #8)."""

    def _open(self, window, tmp_path, *names):
        paths = {n: _png(tmp_path / n) for n in names}
        (tmp_path / "t.txt").write_text("x")
        _load(window, tmp_path)
        window._file_actions.show_in_viewer(paths[names[0]])
        return window._file_actions._viewer, paths

    def _current(self, window, name):
        tree = window._ui.tblFiles
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            if item.text(0) == name:
                tree.setCurrentItem(item, 0, QItemSelectionModel.SelectionFlag.NoUpdate)

    def test_ctrl_click_on_thumbnail_deselects(self, window, tmp_path, qtbot):
        viewer, p = self._open(window, tmp_path, "a.png", "b.png", "c.png")
        self._current(window, "a.png")
        _select(window, "a.png", "b.png", "c.png")
        assert viewer.current_path == p["a.png"]
        qtbot.mouseClick(
            viewer._strip._labels[1],
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier,
        )
        assert viewer.selection_paths == [p["a.png"], p["c.png"]]
        assert viewer.current_path == p["a.png"]
        assert window._files.selected_paths() == [p["a.png"], p["c.png"]]

    def test_ctrl_click_on_shown_thumbnail_shows_next(self, window, tmp_path):
        viewer, p = self._open(window, tmp_path, "a.png", "b.png", "c.png")
        self._current(window, "b.png")
        _select(window, "a.png", "b.png", "c.png")
        assert viewer.current_path == p["b.png"]
        viewer._strip.thumbnail_ctrl_clicked.emit(1)
        assert viewer.current_path == p["c.png"]
        assert window._files.selected_paths() == [p["a.png"], p["c.png"]]
        viewer._strip.thumbnail_ctrl_clicked.emit(1)  # the last one: previous
        assert viewer.current_path == p["a.png"]
        assert viewer.selection_paths == [p["a.png"]]
        assert viewer._strip.isHidden()
        assert window._files.selected_paths() == [p["a.png"]]

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
