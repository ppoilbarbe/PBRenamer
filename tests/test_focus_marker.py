"""Tests for focus_marker — which of the tree and the file list has the focus."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QFocusEvent, QPalette
from PySide6.QtWidgets import QApplication, QTreeWidget

from pbrenamer.ui.focus_marker import FocusMarker, _mix, mark_focus
from pbrenamer.ui.main_window import MainWindow

_HIGHLIGHT = QPalette.ColorRole.Highlight
_HIGHLIGHTED_TEXT = QPalette.ColorRole.HighlightedText


@pytest.fixture
def view(qtbot):
    w = QTreeWidget()
    qtbot.addWidget(w)
    return w


def _focus(view, kind, reason=Qt.FocusReason.TabFocusReason):
    QApplication.sendEvent(view, QFocusEvent(kind, reason))


def _app_color(view, role):
    return QApplication.palette(view).color(role)


def test_mix():
    grey = _mix(QColor("white"), QColor("black"), 0.25)
    assert grey.name() == "#bfbfbf"


def test_starts_inactive(view):
    marker = mark_focus(view)
    assert isinstance(marker, FocusMarker)
    assert not marker.active
    assert view.objectName() == "QTreeWidget"
    assert "transparent" in view.styleSheet()
    assert view.palette().color(_HIGHLIGHT) != _app_color(view, _HIGHLIGHT)
    assert view.palette().color(_HIGHLIGHTED_TEXT) == _app_color(
        view, QPalette.ColorRole.Text
    )


def test_keeps_object_name(view):
    view.setObjectName("files")
    mark_focus(view)
    assert view.styleSheet().startswith("#files {")


def test_focus_in_and_out(view):
    marker = mark_focus(view)
    _focus(view, QEvent.Type.FocusIn)
    assert marker.active
    highlight = _app_color(view, _HIGHLIGHT)
    assert highlight.name() in view.styleSheet()
    assert "2px solid" in view.styleSheet()
    assert view.palette().color(_HIGHLIGHT) == highlight
    _focus(view, QEvent.Type.FocusOut)
    assert not marker.active
    assert "transparent" in view.styleSheet()
    assert view.palette().color(_HIGHLIGHT) != highlight
    _focus(view, QEvent.Type.FocusIn)
    assert view.palette().color(_HIGHLIGHT) == highlight


@pytest.mark.parametrize(
    "reason",
    [Qt.FocusReason.PopupFocusReason, Qt.FocusReason.ActiveWindowFocusReason],
)
def test_popup_or_other_window_keeps_marker(view, reason):
    marker = mark_focus(view)
    _focus(view, QEvent.Type.FocusIn)
    _focus(view, QEvent.Type.FocusOut, reason)
    assert marker.active


def test_application_palette_change(view, monkeypatch):
    marker = mark_focus(view)
    calls = []
    monkeypatch.setattr(marker, "_update", lambda: calls.append(1))
    QApplication.sendEvent(view, QEvent(QEvent.Type.ApplicationPaletteChange))
    assert calls == [1]
    _focus(view, QEvent.Type.FocusIn)
    _focus(view, QEvent.Type.FocusIn)
    assert calls == [1, 1]


def test_main_window_views(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    tree, files = w._ui.treeDirectory, w._ui.tblFiles
    _focus(tree, QEvent.Type.FocusIn)
    assert w._ui.treeFocusMarker.active
    assert not w._ui.filesFocusMarker.active
    _focus(tree, QEvent.Type.FocusOut)
    _focus(files, QEvent.Type.FocusIn)
    assert not w._ui.treeFocusMarker.active
    assert w._ui.filesFocusMarker.active
