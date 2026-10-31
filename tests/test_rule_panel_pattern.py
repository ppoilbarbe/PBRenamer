"""Tests for PatternRulePanel, instantiated on its own."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMainWindow

from pbrenamer.core.undo import UndoManager
from pbrenamer.ui.file_list import FileListController, PreviewEntry
from pbrenamer.ui.main_window_ui import Ui_MainWindow
from pbrenamer.ui.presets import PatternPresets
from pbrenamer.ui.rule_panel_pattern import PatternRulePanel, resolve_extension_mode
from pbrenamer.ui.window_state import WindowState


@pytest.fixture
def panel(qtbot):
    win = QMainWindow()
    qtbot.addWidget(win)
    ui = Ui_MainWindow()
    ui.setupUi(win)
    presets = PatternPresets()
    state = WindowState()
    holder = {}
    files = FileListController(
        ui, UndoManager(), state, lambda: holder["panel"].extension_mode(), win
    )
    holder["panel"] = PatternRulePanel(ui, presets, state, files, win)
    yield holder["panel"], ui, presets
    win.close()


def test_preview_none_without_search(panel, tmp_path):
    pattern, ui, _ = panel
    ui.cmbPatternSearch.setCurrentText("")
    assert pattern.preview([str(tmp_path / "a.txt")]) is None


def test_preview_none_with_invalid_regex(panel, tmp_path):
    pattern, ui, _ = panel
    ui.radRegex.setChecked(True)
    ui.cmbPatternSearch.setCurrentText("(")
    assert pattern.preview([str(tmp_path / "a.txt")]) is None


def test_preview_computes_names(panel, tmp_path):
    pattern, ui, _ = panel
    ui.radPlainText.setChecked(True)
    ui.cmbPatternSearch.setCurrentText("a")
    ui.cmbPatternDest.setCurrentText("b")
    entries = pattern.preview([str(tmp_path / "a1.txt"), str(tmp_path / "x.txt")])
    # No match leaves the preview empty
    assert entries == [PreviewEntry("b1.txt"), PreviewEntry("")]


def test_edits_and_changes_emit(panel, qtbot):
    pattern, ui, _ = panel
    with qtbot.waitSignal(pattern.edited, timeout=1000):
        ui.cmbPatternSearch.setCurrentText("foo")
    with qtbot.waitSignal(pattern.changed, timeout=1000):
        ui.chkRemoveAccents.toggle()


def test_record_history_promotes_patterns(panel):
    pattern, ui, presets = panel
    ui.cmbPatternSearch.setCurrentText("{X}")
    ui.cmbPatternDest.setCurrentText("{1}")
    pattern.record_history()
    assert presets.get_search()[0] == ("pattern", "{X}")
    assert presets.get_replace()[0] == "{1}"


def test_insert_field(panel):
    pattern, ui, _ = panel
    ui.cmbPatternDest.setCurrentText("")
    pattern.insert_field("{num}")
    assert ui.cmbPatternDest.currentText() == "{num}"


@pytest.mark.parametrize(
    ("cfg", "expected"),
    [
        ({"extension_mode": "lower"}, "lower"),
        ({"keep_extension": True}, "keep"),
        ({"keep_extension": False}, "modify"),
        ({}, None),
    ],
)
def test_resolve_extension_mode(cfg, expected):
    assert resolve_extension_mode(cfg) == expected


@pytest.mark.parametrize(
    ("reason", "text"),
    [
        ("no_dest", "no destination"),
        ("dest_position", "must start"),
        ("absolute", "absolute path"),
        ("ext_separator", "extension separator removed"),
        ("invalid_component", "invalid path"),
    ],
)
def test_error_text_of_target_errors(reason, text):
    from pbrenamer.core import filetools
    from pbrenamer.ui.rule_panel_pattern import error_text

    assert text in error_text(filetools.TargetPathError(reason, "x"))
