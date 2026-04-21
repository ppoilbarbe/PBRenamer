"""Smoke tests for the main window."""

import pytest
from pytestqt.qtbot import QtBot

from pbrenamer.ui.main_window import MainWindow


def test_window_title(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "PBRenamer"


def test_window_minimum_size(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.minimumWidth() >= 800
    assert window.minimumHeight() >= 400


def test_rename_button_initially_disabled(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert not window._btn_rename.isEnabled()
