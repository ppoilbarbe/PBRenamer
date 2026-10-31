"""Tests for FileListController, instantiated on its own."""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QTreeWidgetItem

from pbrenamer.core.undo import UndoManager
from pbrenamer.ui.file_list import FileListController, PreviewEntry
from pbrenamer.ui.main_window_ui import Ui_MainWindow
from pbrenamer.ui.window_state import WindowState


@pytest.fixture
def files(qtbot):
    win = QMainWindow()
    qtbot.addWidget(win)
    ui = Ui_MainWindow()
    ui.setupUi(win)
    ext_mode = {"value": "keep"}
    ctrl = FileListController(
        ui, UndoManager(), WindowState(), lambda: ext_mode["value"], win
    )
    yield ctrl, ui, ext_mode
    win.close()


def _paths(ui):
    root = ui.tblFiles.invisibleRootItem()
    return [
        root.child(i).data(0, Qt.ItemDataRole.UserRole)
        for i in range(root.childCount())
    ]


def test_set_directory_lists_files_and_signals(files, tmp_path, qtbot):
    ctrl, ui, _ = files
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.txt").write_text("x")
    with qtbot.waitSignal(ctrl.files_reloaded, timeout=1000):
        ctrl.set_directory(str(tmp_path))
    assert ctrl.current_dir == str(tmp_path)
    assert sorted(_paths(ui)) == [str(tmp_path / "a.txt"), str(tmp_path / "b.txt")]


def test_show_previews_allows_rename(files, tmp_path, qtbot):
    ctrl, _ui, _ = files
    (tmp_path / "a.txt").write_text("x")
    ctrl.set_directory(str(tmp_path))
    items = ctrl.active_items()
    with qtbot.waitSignal(ctrl.rename_count_changed, check_params_cb=lambda n: n == 1):
        ctrl.show_previews(items, [PreviewEntry("z.txt")])
    assert ctrl.pending_renames() == [
        (str(tmp_path / "a.txt"), str(tmp_path / "z.txt"))
    ]


def test_show_previews_conflict_blocks_rename(files, tmp_path, qtbot):
    ctrl, _ui, _ = files
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.txt").write_text("x")
    ctrl.set_directory(str(tmp_path))
    items = ctrl.active_items()
    with qtbot.waitSignal(ctrl.rename_count_changed, check_params_cb=lambda n: n == 0):
        ctrl.show_previews(items, [PreviewEntry("c.txt"), PreviewEntry("c.txt")])


def test_error_entry_is_not_renamed(files, tmp_path):
    ctrl, _ui, _ = files
    (tmp_path / "a.txt").write_text("x")
    ctrl.set_directory(str(tmp_path))
    ctrl.show_previews(ctrl.active_items(), [PreviewEntry("⚠ boom", error=True)])
    assert ctrl.pending_renames() == []


def test_clear_preview_disallows_rename(files, tmp_path, qtbot):
    ctrl, ui, _ = files
    (tmp_path / "a.txt").write_text("x")
    ctrl.set_directory(str(tmp_path))
    ctrl.show_previews(ctrl.active_items(), [PreviewEntry("z.txt")])
    with qtbot.waitSignal(ctrl.rename_count_changed, check_params_cb=lambda n: n == 0):
        ctrl.clear_preview()
    assert ui.tblFiles.topLevelItem(0).text(1) == ""


def test_sidecar_mode_follows_extension_mode(files):
    ctrl, ui, ext_mode = files
    ui.chkSidecarMode.setChecked(True)
    assert ctrl.sidecar_mode_active()
    ext_mode["value"] = "normalize"
    ctrl.update_sidecar_checkbox_state()
    assert not ui.chkSidecarMode.isEnabled()
    assert not ctrl.sidecar_mode_active()


# ---------------------------------------------------------------------------
# Phase 5: display options, sidecar column, content filter, selection, drops
# ---------------------------------------------------------------------------

from PySide6.QtGui import QDesktopServices  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402

from pbrenamer import profiles  # noqa: E402
from pbrenamer.ui import file_list as file_list_mod  # noqa: E402


def _display(ctrl, **values):
    data = profiles.load()
    for key, value in values.items():
        section = "images" if key in data["images"] else "display"
        data[section][key] = value
    profiles.save(data)
    ctrl.apply_display()


def _photos(tmp_path):
    for name in ("a.jpg", "a.xmp", "a.info", "b.jpg", "c.jpg", "c.xmp", "n.txt"):
        (tmp_path / name).write_text("x")
    (tmp_path / "a.xmp").write_text("<subject>Paris</subject>")
    (tmp_path / "c.xmp").write_text("<subject>Lyon</subject>")
    return tmp_path


def _item(ui, name):
    for item in _all(ui):
        if item.data(0, Qt.ItemDataRole.UserRole).endswith("/" + name):
            return item
    raise KeyError(name)


def _all(ui):
    root = ui.tblFiles.invisibleRootItem()
    return [root.child(i) for i in range(root.childCount())]


def _names(ui):
    return [p.rsplit("/", 1)[-1] for p in _paths(ui)]


class TestApplyDisplay:
    def test_defaults_hide_everything(self, files):
        ctrl, ui, _ = files
        ctrl.apply_display()
        assert ui.tblFiles.isColumnHidden(2)
        assert ui.tblFiles.isColumnHidden(3)
        assert ui.cmbSidecarFilter.isHidden()
        assert not ui.chkThumbnails.isChecked()

    def test_options_shown(self, files):
        ctrl, ui, _ = files
        _display(ctrl, thumbnails=True, sidecar_column=True, sidecar_filter=True)
        assert not ui.tblFiles.isColumnHidden(2)
        assert not ui.tblFiles.isColumnHidden(3)
        assert not ui.cmbSidecarFilter.isHidden()
        assert ui.chkThumbnails.isChecked()

    def test_column_order(self, files):
        _ctrl, ui, _ = files
        header = ui.tblFiles.header()
        assert [header.logicalIndex(v) for v in range(4)] == [2, 0, 3, 1]

    def test_hiding_filter_clears_it(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        _display(ctrl, sidecar_filter=True)
        ctrl.set_directory(str(tmp_path))
        ui.cmbSidecarFilter.setEditText("paris")
        ctrl._apply_content_filter()
        assert len(_paths(ui)) == 3
        _display(ctrl, sidecar_filter=False)
        assert ui.cmbSidecarFilter.currentText() == ""
        assert len(_paths(ui)) == 7


class TestSidecarColumn:
    def test_indicators(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        _display(ctrl, sidecar_column=True)
        ctrl.set_directory(str(tmp_path))
        assert _item(ui, "a.jpg").text(3) == "● info  xmp"
        assert _item(ui, "a.jpg").toolTip(3) == "\n".join(
            [str(tmp_path / "a.info"), str(tmp_path / "a.xmp")]
        )
        assert _item(ui, "b.jpg").text(3) == "○"
        assert _item(ui, "a.xmp").text(3) == ""
        assert _item(ui, "n.txt").text(3) == ""
        # Sidecar rows stay in the list.
        assert "a.xmp" in _names(ui)

    def test_hidden_column_not_filled(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.apply_display()
        ctrl.set_directory(str(tmp_path))
        assert _item(ui, "a.jpg").text(3) == ""
        assert ctrl._groups is None

    @pytest.fixture
    def opened(self, monkeypatch):
        urls = []
        monkeypatch.setattr(
            QDesktopServices, "openUrl", staticmethod(lambda u: urls.append(u))
        )
        return urls

    def test_double_click_opens_single_sidecar(self, files, tmp_path, opened):
        ctrl, ui, _ = files
        _photos(tmp_path)
        _display(ctrl, sidecar_column=True)
        ctrl.set_directory(str(tmp_path))
        ctrl._on_item_double_clicked(_item(ui, "c.jpg"), 3)
        assert [u.toLocalFile() for u in opened] == [str(tmp_path / "c.xmp")]

    def test_double_click_thumbnail_requests_viewer(self, files, tmp_path, opened):
        ctrl, ui, _ = files
        _photos(tmp_path)
        _display(ctrl, sidecar_column=True)
        ctrl.set_directory(str(tmp_path))
        requested = []
        ctrl.view_requested.connect(requested.append)
        ctrl._on_item_double_clicked(_item(ui, "c.jpg"), 2)
        assert requested == [str(tmp_path / "c.jpg")]
        assert opened == []

    @pytest.mark.parametrize("column", [0, 1])
    def test_double_click_image_name_opens_it(self, files, tmp_path, opened, column):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        requested = []
        ctrl.view_requested.connect(requested.append)
        ctrl._on_item_double_clicked(_item(ui, "c.jpg"), column)
        assert requested == []
        assert [u.toLocalFile() for u in opened] == [str(tmp_path / "c.jpg")]

    def test_double_click_thumbnail_of_other_file_opens_it(
        self, files, tmp_path, opened
    ):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        ctrl._on_item_double_clicked(_item(ui, "n.txt"), 2)
        assert [u.toLocalFile() for u in opened] == [str(tmp_path / "n.txt")]

    def test_double_click_other_file_opens_it(self, files, tmp_path, opened):
        ctrl, ui, _ = files
        _photos(tmp_path)
        _display(ctrl, sidecar_column=True)
        ctrl.set_directory(str(tmp_path))
        ctrl._on_item_double_clicked(_item(ui, "a.xmp"), 0)
        assert [u.toLocalFile() for u in opened] == [str(tmp_path / "a.xmp")]

    def test_double_click_chooses_among_several(
        self, files, tmp_path, opened, monkeypatch
    ):
        ctrl, ui, _ = files
        _photos(tmp_path)
        _display(ctrl, sidecar_column=True)
        ctrl.set_directory(str(tmp_path))
        shown = []

        def fake_exec(menu, _pos=None):
            actions = menu.actions()
            shown.extend(a.text() for a in actions)
            actions[1].trigger()

        monkeypatch.setattr(file_list_mod, "_exec_menu", fake_exec)
        ctrl._on_item_double_clicked(_item(ui, "a.jpg"), 3)
        assert shown == ["a.info", "a.xmp"]
        assert [u.toLocalFile() for u in opened] == [str(tmp_path / "a.xmp")]

    def test_double_click_creates_sidecar(self, files, tmp_path, opened):
        ctrl, ui, _ = files
        _photos(tmp_path)
        _display(ctrl, sidecar_column=True, sidecar_new_extension="pp3")
        ctrl.set_directory(str(tmp_path))
        ctrl._on_item_double_clicked(_item(ui, "b.jpg"), 3)
        new = tmp_path / "b.pp3"
        assert new.exists()
        assert new.stat().st_size == 0
        assert [u.toLocalFile() for u in opened] == [str(new)]
        assert "b.pp3" in _names(ui)

    def test_no_creation_for_other_files(self, files, tmp_path, opened):
        ctrl, ui, _ = files
        _photos(tmp_path)
        _display(ctrl, sidecar_column=True)
        ctrl.set_directory(str(tmp_path))
        ctrl._on_item_double_clicked(_item(ui, "n.txt"), 3)
        assert not (tmp_path / "n.xmp").exists()
        assert opened == []

    def test_no_creation_without_extension(self, files, tmp_path, opened):
        ctrl, ui, _ = files
        _photos(tmp_path)
        _display(ctrl, sidecar_column=True, sidecar_new_extension="")
        ctrl.set_directory(str(tmp_path))
        ctrl._on_item_double_clicked(_item(ui, "b.jpg"), 3)
        assert opened == []

    def test_creation_error(self, files, tmp_path, opened, monkeypatch):
        ctrl, ui, _ = files
        _photos(tmp_path)
        _display(ctrl, sidecar_column=True)
        ctrl.set_directory(str(tmp_path))
        (tmp_path / "b.xmp").mkdir()  # appears after the listing
        warnings = []
        monkeypatch.setattr(
            QMessageBox, "warning", staticmethod(lambda *a: warnings.append(a[2]))
        )
        ctrl._on_item_double_clicked(_item(ui, "b.jpg"), 3)
        assert warnings and warnings[0].startswith("Cannot create b.xmp: ")
        assert opened == []


class TestEmptySidecars:
    def test_deleted_on_load_when_enabled(self, files, tmp_path):
        ctrl, ui, _ = files
        (tmp_path / "a.jpg").write_text("x")
        (tmp_path / "a.xmp").write_bytes(b"")
        (tmp_path / "orphan.xmp").write_bytes(b"")
        (tmp_path / "empty.txt").write_bytes(b"")
        _display(ctrl, delete_empty_sidecars=True)
        ctrl.set_directory(str(tmp_path))
        assert _names(ui) == ["a.jpg", "empty.txt"]

    def test_kept_when_disabled(self, files, tmp_path):
        ctrl, ui, _ = files
        (tmp_path / "a.xmp").write_bytes(b"")
        ctrl.apply_display()
        ctrl.set_directory(str(tmp_path))
        assert _names(ui) == ["a.xmp"]

    def test_created_sidecar_kept_while_empty(self, files, tmp_path, monkeypatch):
        ctrl, ui, _ = files
        monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda u: None))
        (tmp_path / "a.jpg").write_text("x")
        _display(ctrl, sidecar_column=True, delete_empty_sidecars=True)
        ctrl.set_directory(str(tmp_path))
        ctrl._on_item_double_clicked(_item(ui, "a.jpg"), 3)
        ctrl.reload()
        assert (tmp_path / "a.xmp").exists()
        # Once edited, it is no longer protected; emptied again, it goes.
        (tmp_path / "a.xmp").write_text("x")
        ctrl.reload()
        (tmp_path / "a.xmp").write_bytes(b"")
        ctrl.reload()
        assert not (tmp_path / "a.xmp").exists()

    def test_deletion_error_logged(self, files, tmp_path, monkeypatch, caplog):
        ctrl, ui, _ = files
        (tmp_path / "a.xmp").write_bytes(b"")

        def boom(_path):
            raise OSError("denied")

        monkeypatch.setattr(file_list_mod.os, "remove", boom)
        _display(ctrl, delete_empty_sidecars=True)
        ctrl.set_directory(str(tmp_path))
        assert "Cannot delete empty sidecar" in caplog.text
        assert _names(ui) == ["a.xmp"]

    def test_unreadable_directory(self, files, tmp_path, monkeypatch):
        ctrl, _ui, _ = files
        ctrl.current_dir = str(tmp_path)
        monkeypatch.setattr(
            file_list_mod.os, "listdir", lambda _p: (_ for _ in ()).throw(OSError())
        )
        ctrl._delete_empty_sidecars_now()


class TestContentFilter:
    @pytest.fixture
    def shown(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        _display(ctrl, sidecar_filter=True)
        ctrl.set_directory(str(tmp_path))
        return ctrl, ui

    def test_debounced_filter(self, shown, qtbot):
        ctrl, ui = shown
        ui.cmbSidecarFilter.setEditText("PARIS")
        assert ctrl._filter_timer.isActive()
        qtbot.waitUntil(lambda: len(_paths(ui)) == 3, timeout=2000)
        assert _names(ui) == ["a.info", "a.jpg", "a.xmp"]

    def test_invalid_pattern_marked(self, shown):
        ctrl, ui = shown
        ui.cmbSidecarFilter.setEditText("(")
        assert "red" in ui.cmbSidecarFilter.lineEdit().styleSheet()
        assert not ctrl._filter_timer.isActive()
        ctrl._apply_content_filter()
        assert len(_paths(ui)) == 7
        ui.cmbSidecarFilter.setEditText("(a)")
        assert ui.cmbSidecarFilter.lineEdit().styleSheet() == ""

    def test_unchanged_pattern_no_reload(self, shown, qtbot):
        ctrl, ui = shown
        ui.cmbSidecarFilter.setEditText("lyon")
        ctrl._apply_content_filter()
        with qtbot.assertNotEmitted(ctrl.files_reloaded):
            ctrl._apply_content_filter()

    def test_cleared_shows_all(self, shown):
        ctrl, ui = shown
        ui.cmbSidecarFilter.setEditText("lyon")
        ctrl._apply_content_filter()
        assert _names(ui) == ["c.jpg", "c.xmp"]
        ui.cmbSidecarFilter.setEditText("")
        ctrl._apply_content_filter()
        assert len(_paths(ui)) == 7

    def test_return_records_history(self, shown):
        ctrl, ui = shown
        profiles.set_history("sidecar_filter", ["lyon", "paris"])
        data = profiles.load()
        data["display"]["history_max"] = 2
        profiles.save(data)
        ui.cmbSidecarFilter.setEditText("subject")
        ctrl._on_filter_return()
        assert profiles.get_history("sidecar_filter") == ["subject", "lyon"]
        combo = ui.cmbSidecarFilter
        assert [combo.itemText(i) for i in range(combo.count())] == [
            "subject",
            "lyon",
        ]
        assert combo.currentText() == "subject"

    def test_return_ignores_empty_and_invalid(self, shown):
        ctrl, ui = shown
        ui.cmbSidecarFilter.setEditText("(")
        ctrl._on_filter_return()
        ui.cmbSidecarFilter.setEditText("")
        ctrl._on_filter_return()
        assert profiles.get_history("sidecar_filter") == []

    def test_cleared_on_directory_change(self, shown, tmp_path):
        ctrl, ui = shown
        ui.cmbSidecarFilter.setEditText("lyon")
        ctrl._apply_content_filter()
        other = tmp_path / "sub"
        other.mkdir()
        (other / "x.jpg").write_text("x")
        ctrl.set_directory(str(other))
        assert ui.cmbSidecarFilter.currentText() == ""
        assert _names(ui) == ["x.jpg"]


class TestSelectionState:
    def test_new_directory_current_without_selection(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        assert ui.tblFiles.currentItem() is _all(ui)[0]
        assert ui.tblFiles.selectedItems() == []

    def test_reload_keeps_selection_and_current(self, files, tmp_path, qtbot):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        _item(ui, "b.jpg").setSelected(True)
        _item(ui, "c.jpg").setSelected(True)
        ctrl.set_current_path(str(tmp_path / "c.jpg"))
        with qtbot.assertNotEmitted(ctrl.selection_changed):
            ctrl.reload()
        assert sorted(i.text(0) for i in ui.tblFiles.selectedItems()) == [
            "b.jpg",
            "c.jpg",
        ]
        assert ui.tblFiles.currentItem().text(0) == "c.jpg"

    def test_reload_current_falls_back_to_selection(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        _item(ui, "c.jpg").setSelected(True)
        ctrl.set_current_path(str(tmp_path / "n.txt"))
        (tmp_path / "n.txt").unlink()
        ctrl.reload()
        assert ui.tblFiles.currentItem().text(0) == "c.jpg"

    def test_fs_change_keeps_current(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        ctrl.set_current_path(str(tmp_path / "c.jpg"))
        (tmp_path / "d.jpg").write_text("x")
        ctrl._on_fs_change()
        assert "d.jpg" in _names(ui)
        assert ui.tblFiles.currentItem().text(0) == "c.jpg"

    def test_select_paths(self, files, tmp_path, qtbot):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        with qtbot.waitSignal(ctrl.selection_changed):
            assert ctrl.select_paths([str(tmp_path / "c.jpg"), str(tmp_path / "b.jpg")])
        assert ui.tblFiles.currentItem().text(0) == "b.jpg"
        assert not ctrl.select_paths([str(tmp_path / "gone")])

    def test_next_path_after(self, files, tmp_path):
        ctrl, _ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        p = {n: str(tmp_path / n) for n in _names(_ui)}
        assert ctrl.next_path_after([p["a.jpg"], p["b.jpg"]]) == p["c.jpg"]
        assert ctrl.next_path_after([p["n.txt"]]) == p["c.xmp"]
        assert ctrl.next_path_after(list(p.values())) is None
        assert ctrl.next_path_after(["/elsewhere"]) is None

    def test_select_after_change(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        ctrl.select_after_change(["/moved/away"], str(tmp_path / "c.jpg"))
        assert ui.tblFiles.selectedItems() == []
        assert ui.tblFiles.currentItem().text(0) == "c.jpg"
        ctrl.select_after_change([str(tmp_path / "b.jpg")], None)
        assert [i.text(0) for i in ui.tblFiles.selectedItems()] == ["b.jpg"]

    def test_set_current_path_unknown(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        ctrl.set_current_path(None)
        ctrl.set_current_path("/nowhere")
        assert ui.tblFiles.currentItem() is _all(ui)[0]


class TestDropWithSidecars:
    @pytest.fixture
    def dirs(self, tmp_path):
        src, dst = tmp_path / "src", tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        _photos(src)
        return src, dst

    def test_listed_file_takes_its_sidecars(self, files, dirs):
        ctrl, ui, _ = files
        src, dst = dirs
        _display(ctrl, sidecar_column=True)
        ctrl.set_directory(str(src))
        ctrl._on_files_dropped([str(src / "a.jpg")], str(dst), True)
        assert sorted(p.name for p in dst.iterdir()) == ["a.info", "a.jpg", "a.xmp"]
        assert "a.xmp" not in _names(ui)
        assert ui.tblFiles.currentItem().text(0) == "b.jpg"

    def test_external_file_takes_its_sidecars(self, files, dirs, tmp_path):
        ctrl, _ui, _ = files
        src, dst = dirs
        ctrl.set_directory(str(dst))
        ctrl._on_files_dropped([str(src / "c.jpg")], str(dst), False)
        assert sorted(p.name for p in dst.iterdir()) == ["c.jpg", "c.xmp"]
        assert (src / "c.xmp").exists()

    def test_sidecar_dropped_with_base_not_duplicated(self, files, dirs):
        ctrl, _ui, _ = files
        src, dst = dirs
        ctrl.set_directory(str(src))
        ctrl._on_files_dropped([str(src / "c.xmp"), str(src / "c.jpg")], str(dst), True)
        assert sorted(p.name for p in dst.iterdir()) == ["c.jpg", "c.xmp"]
        assert len(ctrl._undo) == 1

    def test_skip_drops_whole_unit(self, files, dirs, monkeypatch):
        ctrl, _ui, _ = files
        src, dst = dirs
        (dst / "a.xmp").write_text("old")
        ctrl.set_directory(str(src))

        def fake_exec(box):
            box._clicked = [
                b for b in box.buttons() if box.buttonRole(b) == QMessageBox.NoRole
            ][0]

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        monkeypatch.setattr(QMessageBox, "clickedButton", lambda box: box._clicked)
        ctrl._on_files_dropped([str(src / "a.jpg"), str(src / "b.jpg")], str(dst), True)
        assert sorted(p.name for p in dst.iterdir()) == ["a.xmp", "b.jpg"]
        assert (dst / "a.xmp").read_text() == "old"
        assert (src / "a.jpg").exists()

    def test_overwritten_copy_not_undoable(self, files, dirs, monkeypatch):
        ctrl, _ui, _ = files
        src, dst = dirs
        (dst / "b.jpg").write_text("old")
        ctrl.set_directory(str(src))

        def fake_exec(box):
            box._clicked = [
                b for b in box.buttons() if box.buttonRole(b) == QMessageBox.YesRole
            ][0]

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        monkeypatch.setattr(QMessageBox, "clickedButton", lambda box: box._clicked)
        ctrl._on_files_dropped(
            [str(src / "b.jpg"), str(src / "n.txt")], str(dst), False
        )
        assert (dst / "b.jpg").read_text() == "x"
        entry = ctrl._undo._history[-1]
        assert entry.pairs == [(str(src / "n.txt"), str(dst / "n.txt"))]

    def test_sidecars_of_feeds_drag(self, files, dirs):
        ctrl, ui, _ = files
        src, _dst = dirs
        _display(ctrl, sidecar_column=True)
        ctrl.set_directory(str(src))
        mime = ui.tblFiles.mimeData([_item(ui, "a.jpg"), _item(ui, "a.xmp")])
        assert sorted(u.toLocalFile() for u in mime.urls()) == [
            str(src / "a.info"),
            str(src / "a.jpg"),
            str(src / "a.xmp"),
        ]


class TestSort:
    def _files(self, tmp_path):
        for name, mtime in (("a.txt", 300), ("b.txt", 100), ("c.txt", 200)):
            (tmp_path / name).write_text("x")
            os.utime(tmp_path / name, (mtime, mtime))
        for name, mtime in (("d1", 50), ("d2", 10)):
            (tmp_path / name).mkdir()
            os.utime(tmp_path / name, (mtime, mtime))
        return tmp_path

    def test_by_name_default(self, files, tmp_path):
        ctrl, ui, _ = files
        ui.cmbMode.setCurrentIndex(2)
        ctrl.set_directory(str(self._files(tmp_path)))
        assert _names(ui) == ["a.txt", "b.txt", "c.txt", "d1", "d2"]

    def test_by_date_and_reversed_saved(self, files, tmp_path):
        ctrl, ui, _ = files
        ui.cmbMode.setCurrentIndex(2)
        ctrl.set_directory(str(self._files(tmp_path)))
        ui.chkSortByDate.setChecked(True)
        assert _names(ui) == ["d2", "d1", "b.txt", "c.txt", "a.txt"]
        ui.chkSortReverse.setChecked(True)
        assert _names(ui) == ["d1", "d2", "a.txt", "c.txt", "b.txt"]
        assert profiles.load()["display"]["sort_by_date"] is True
        assert profiles.load()["display"]["sort_reverse"] is True
        ui.chkSortByDate.setChecked(False)
        assert _names(ui) == ["d2", "d1", "c.txt", "b.txt", "a.txt"]

    def test_profile_applied(self, files, tmp_path):
        ctrl, ui, _ = files
        ctrl.current_dir = str(self._files(tmp_path))
        _display(ctrl, sort_by_date=True)
        assert ui.chkSortByDate.isChecked()
        assert _names(ui) == ["b.txt", "c.txt", "a.txt"]

    def test_vanished_file_sorts_first(self, files, tmp_path, monkeypatch):
        ctrl, ui, _ = files
        ctrl._sort_by_date = True

        def mtime(path):
            raise OSError("gone")

        monkeypatch.setattr(file_list_mod.os.path, "getmtime", mtime)
        entries = [("b", str(tmp_path / "b")), ("a", str(tmp_path / "a"))]
        assert ctrl._sorted(entries) == entries


class TestAccessors:
    def test_sidecars_map_from_groups_or_disk(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        a, b = str(tmp_path / "a.jpg"), str(tmp_path / "b.jpg")
        assert ctrl._groups is None
        expected = {a: [str(tmp_path / "a.info"), str(tmp_path / "a.xmp")], b: []}
        assert ctrl.sidecars_map([a, b]) == expected
        _display(ctrl, sidecar_column=True)
        assert {k: sorted(v) for k, v in ctrl.sidecars_map([a, b]).items()} == (
            expected
        )

    def test_selected_and_listed_paths(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        _item(ui, "c.jpg").setSelected(True)
        _item(ui, "a.jpg").setSelected(True)
        assert ctrl.selected_paths() == [
            str(tmp_path / "a.jpg"),
            str(tmp_path / "c.jpg"),
        ]
        assert len(ctrl.listed_paths()) == 7

    def test_double_click_row_without_path(self, files, monkeypatch):
        ctrl, ui, _ = files
        monkeypatch.setattr(file_list_mod, "_open_path", pytest.fail)
        item = QTreeWidgetItem(["x"])
        ui.tblFiles.addTopLevelItem(item)
        ctrl._on_item_double_clicked(item, 0)


class TestSidecarModeOrder:
    """Sidecar mode lists each base file's sidecars right after it, sorted by
    suffix; the sort options only order the base files (7.2 #6)."""

    def _files(self, tmp_path):
        for name, mtime in (
            ("a.info", 50),
            ("a.jpg", 30),
            ("a.xmp", 10),
            ("b.jpg", 20),
            ("c.txt", 40),
        ):
            path = tmp_path / name
            path.write_text("x")
            os.utime(path, (mtime, mtime))
        return tmp_path

    def test_without_sidecar_mode_by_name(self, files, tmp_path):
        ctrl, ui, _ = files
        ctrl.set_directory(str(self._files(tmp_path)))
        assert _names(ui) == ["a.info", "a.jpg", "a.xmp", "b.jpg", "c.txt"]

    def test_sidecars_follow_their_base(self, files, tmp_path):
        ctrl, ui, _ = files
        ui.chkSidecarMode.setChecked(True)
        ctrl.set_directory(str(self._files(tmp_path)))
        assert _names(ui) == ["a.jpg", "a.info", "a.xmp", "b.jpg", "c.txt"]

    def test_sort_options_order_base_files_only(self, files, tmp_path):
        ctrl, ui, _ = files
        ui.chkSidecarMode.setChecked(True)
        ctrl.set_directory(str(self._files(tmp_path)))
        ui.chkSortByDate.setChecked(True)
        assert _names(ui) == ["b.jpg", "a.jpg", "a.info", "a.xmp", "c.txt"]
        ui.chkSortReverse.setChecked(True)
        assert _names(ui) == ["c.txt", "a.jpg", "a.info", "a.xmp", "b.jpg"]
        ui.chkSortByDate.setChecked(False)
        assert _names(ui) == ["c.txt", "b.jpg", "a.jpg", "a.info", "a.xmp"]

    def test_base_of(self, files, tmp_path):
        ctrl, ui, _ = files
        ctrl.set_directory(str(self._files(tmp_path)))
        xmp = str(tmp_path / "a.xmp")
        assert ctrl.base_of(xmp) == xmp
        ui.chkSidecarMode.setChecked(True)
        assert ctrl.base_of(xmp) == str(tmp_path / "a.jpg")


class TestSidecarModeSelection:
    """Entering sidecar mode extends the selection to whole groups (7.2 #1)."""

    def _selected(self, ui):
        return sorted(i.text(0) for i in ui.tblFiles.selectedItems())

    def test_base_pulls_its_sidecars(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        _item(ui, "a.jpg").setSelected(True)
        ui.chkSidecarMode.setChecked(True)
        assert self._selected(ui) == ["a.info", "a.jpg", "a.xmp"]

    def test_sidecar_pulls_base_and_siblings(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        _item(ui, "a.xmp").setSelected(True)
        _item(ui, "b.jpg").setSelected(True)
        ui.chkSidecarMode.setChecked(True)
        assert self._selected(ui) == ["a.info", "a.jpg", "a.xmp", "b.jpg"]

    def test_forced_mode_extends_selection(self, qtbot, tmp_path):
        win = QMainWindow()
        qtbot.addWidget(win)
        ui = Ui_MainWindow()
        ui.setupUi(win)
        forced = {"value": False}
        ctrl = FileListController(
            ui,
            UndoManager(),
            WindowState(),
            lambda: "keep",
            win,
            sidecars_forced=lambda: forced["value"],
        )
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        _item(ui, "c.xmp").setSelected(True)
        forced["value"] = True
        ctrl.reload()
        assert self._selected(ui) == ["c.jpg", "c.xmp"]
        assert ctrl._prev_group_selection == {
            str(tmp_path / "c.jpg"),
            str(tmp_path / "c.xmp"),
        }

    def test_leaving_sidecar_mode_keeps_selection(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ui.chkSidecarMode.setChecked(True)
        ctrl.set_directory(str(tmp_path))
        _item(ui, "c.jpg").setSelected(True)
        assert self._selected(ui) == ["c.jpg", "c.xmp"]
        ui.chkSidecarMode.setChecked(False)
        assert self._selected(ui) == ["c.jpg", "c.xmp"]


class TestSelectedBases:
    """A selected sidecar group counts as its main file (7.2 #2)."""

    def test_group_reduced_to_base(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ui.chkSidecarMode.setChecked(True)
        ctrl.set_directory(str(tmp_path))
        _item(ui, "a.xmp").setSelected(True)
        assert len(ui.tblFiles.selectedItems()) == 3
        assert ctrl.selected_bases() == [str(tmp_path / "a.jpg")]

    def test_without_sidecar_mode_every_file(self, files, tmp_path):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ctrl.set_directory(str(tmp_path))
        _item(ui, "a.jpg").setSelected(True)
        _item(ui, "a.xmp").setSelected(True)
        assert len(ctrl.selected_bases()) == 2

    def test_file_info_shows_the_base(self, files, tmp_path, monkeypatch):
        ctrl, ui, _ = files
        _photos(tmp_path)
        ui.chkSidecarMode.setChecked(True)
        ctrl.set_directory(str(tmp_path))
        ctrl.show_file_info()
        shown = []
        monkeypatch.setattr(ctrl._file_info, "update_file", shown.append)
        monkeypatch.setattr(
            ctrl._file_info, "show_multiple", lambda: shown.append("multiple")
        )
        _item(ui, "c.xmp").setSelected(True)
        ctrl._refresh_file_info()
        assert shown[-1] == str(tmp_path / "c.jpg")
        _item(ui, "b.jpg").setSelected(True)
        ctrl._refresh_file_info()
        assert shown[-1] == "multiple"
