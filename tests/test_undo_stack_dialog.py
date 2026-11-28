"""Tests for the undo stack window."""

from __future__ import annotations

from pbrenamer.core.undo import (
    CopyEntry,
    DeleteEntry,
    ExifResetEntry,
    MoveEntry,
    RenameEntry,
    RotationEntry,
    UndoManager,
)
from pbrenamer.ui import undo_stack_dialog
from pbrenamer.ui.main_window import MainWindow
from pbrenamer.ui.undo_stack_dialog import UndoStackDialog, describe
from pbrenamer.ui.window_state import WindowState


def _dialog(qtbot, um):
    dlg = UndoStackDialog(um, WindowState())
    qtbot.addWidget(dlg)
    dlg.show()
    return dlg


def _top_texts(dlg):
    tree = dlg.tree
    return [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]


class TestDescribe:
    def test_rename_same_folder_shows_names(self):
        label, lines = describe(RenameEntry([("/d/a.jpg", "/d/b.jpg")]))
        assert label == "Rename"
        assert lines == ["a.jpg → b.jpg"]

    def test_move_other_folder_shows_paths(self):
        label, lines = describe(MoveEntry([("/d/a.jpg", "/e/a.jpg")]))
        assert label == "Move"
        assert lines == ["/d/a.jpg → /e/a.jpg"]

    def test_other_entries(self):
        assert describe(CopyEntry([("/a", "/b")]))[0] == "Copy"
        assert describe(RotationEntry([("/a.jpg", 90, None)])) == (
            "Rotation",
            ["/a.jpg"],
        )
        assert describe(ExifResetEntry([("/a.jpg", 6)]))[1] == ["/a.jpg"]
        assert "system" in describe(DeleteEntry([("/a", "/t/a")], system=True))[0]
        assert "session" in describe(DeleteEntry([("/a", "/t/a")], system=False))[0]


class TestDialog:
    def test_empty(self, qtbot):
        dlg = _dialog(qtbot, UndoManager())
        assert dlg.tree.isHidden()
        assert not dlg.lblEmpty.isHidden()

    def test_most_recent_on_top(self, qtbot):
        um = UndoManager()
        um.add(CopyEntry([("/a", "/b")]))
        um.add(RenameEntry([("/d/a", "/d/b"), ("/d/c", "/d/e")]))
        dlg = _dialog(qtbot, um)
        assert _top_texts(dlg) == ["Rename (2 file(s))", "Copy (1 file(s))"]
        top = dlg.tree.topLevelItem(0)
        assert [top.child(i).text(0) for i in range(top.childCount())] == [
            "a → b",
            "c → e",
        ]

    def test_updates_while_open(self, qtbot):
        um = UndoManager()
        dlg = _dialog(qtbot, um)
        um.add(CopyEntry([("/a", "/b")]))
        assert _top_texts(dlg) == ["Copy (1 file(s))"]
        um.add(MoveEntry([("/c", "/d")]))
        assert _top_texts(dlg) == ["Move (1 file(s))", "Copy (1 file(s))"]
        um.clear()
        assert _top_texts(dlg) == []
        assert not dlg.lblEmpty.isHidden()

    def test_refreshed_when_shown_again(self, qtbot):
        um = UndoManager()
        dlg = _dialog(qtbot, um)
        dlg.hide()
        um.add(CopyEntry([("/a", "/b")]))
        dlg.show()
        assert _top_texts(dlg) == ["Copy (1 file(s))"]

    def test_keeps_expanded_entries(self, qtbot):
        um = UndoManager()
        um.add(CopyEntry([("/a", "/b")]))
        dlg = _dialog(qtbot, um)
        dlg.tree.topLevelItem(0).setExpanded(True)
        um.add(MoveEntry([("/c", "/d")]))
        assert not dlg.tree.topLevelItem(0).isExpanded()
        assert dlg.tree.topLevelItem(1).isExpanded()

    def test_long_batch_is_truncated(self, qtbot, monkeypatch):
        monkeypatch.setattr(undo_stack_dialog, "MAX_DETAILS", 2)
        um = UndoManager()
        um.add(CopyEntry([(f"/a{i}", f"/b{i}") for i in range(5)]))
        dlg = _dialog(qtbot, um)
        top = dlg.tree.topLevelItem(0)
        assert top.childCount() == 3
        assert top.child(2).text(0) == "… and 3 more"


class TestToolsMenu:
    def test_menu_opens_non_modal_window(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        ui = window._ui
        assert ui.actionUndoStack in ui.menuTools.actions()
        ui.actionUndoStack.trigger()
        dlg = window._undo_stack_dialog
        assert dlg is not None and dlg.isVisible()
        assert not dlg.isModal()
        window._undo.add(CopyEntry([("/a", "/b")]))
        assert _top_texts(dlg) == ["Copy (1 file(s))"]
        ui.actionUndoStack.trigger()
        assert window._undo_stack_dialog is dlg
