"""Tests for ActionBar, instantiated on its own."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMainWindow

from pbrenamer.core.undo import UndoManager
from pbrenamer.ui.action_bar import ActionBar
from pbrenamer.ui.main_window_ui import Ui_MainWindow


@pytest.fixture
def bar(qtbot):
    win = QMainWindow()
    qtbot.addWidget(win)
    ui = Ui_MainWindow()
    ui.setupUi(win)
    undo = UndoManager()
    yield ActionBar(ui, undo, win), ui, undo
    win.close()


def test_buttons_emit_requests(bar, qtbot):
    actions, ui, _undo = bar
    ui.btnRename.setEnabled(True)
    for button, signal in (
        (ui.btnPreview, actions.preview_requested),
        (ui.btnClearPreview, actions.clear_requested),
        (ui.btnRename, actions.rename_requested),
    ):
        with qtbot.waitSignal(signal, timeout=1000):
            button.click()


def test_request_auto_preview_only_when_enabled(bar, qtbot):
    actions, _ui, _undo = bar
    with qtbot.assertNotEmitted(actions.preview_requested):
        actions.request_auto_preview()
    actions.set_auto_preview(True)
    with qtbot.waitSignal(actions.preview_requested, timeout=1000):
        actions.request_auto_preview()


def test_schedule_preview_is_debounced(bar, qtbot):
    actions, _ui, _undo = bar
    actions.schedule_preview()
    assert not actions._preview_timer.isActive()
    actions.set_auto_preview(True)
    with qtbot.waitSignal(actions.preview_requested, timeout=5000):
        actions.schedule_preview()


def test_set_rename_count(bar):
    actions, ui, _undo = bar
    actions.set_rename_count(12)
    assert ui.btnRename.isEnabled()
    assert ui.btnRename.text() == "Rename (12)"
    actions.set_rename_count(0)
    assert not ui.btnRename.isEnabled()
    assert ui.btnRename.text() == "Rename"


def test_rename_shortcut_is_f2(bar):
    _actions, ui, _undo = bar
    assert ui.btnRename.shortcut().toString() == "F2"


def test_refresh_undo_reflects_stack_depth(bar, tmp_path):
    actions, ui, undo = bar
    actions.refresh_undo()
    assert not ui.btnUndo.isEnabled()
    undo.add_batch([(str(tmp_path / "a"), str(tmp_path / "b"))])
    actions.refresh_undo()
    assert ui.btnUndo.isEnabled()
    assert "1" in ui.btnUndo.text()
