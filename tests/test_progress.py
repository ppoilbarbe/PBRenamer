"""Tests for pbrenamer.ui.progress — the modal progress window."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from pbrenamer.ui.progress import PROGRESS_THRESHOLD, FileProgress


def test_threshold_is_50():
    assert PROGRESS_THRESHOLD == 50


def test_no_window_below_threshold(qtbot):
    with FileProgress(None, "Work", PROGRESS_THRESHOLD - 1) as progress:
        assert not progress.visible
        assert all(progress.step() for _ in range(PROGRESS_THRESHOLD - 1))


def test_window_from_threshold(qtbot):
    with FileProgress(None, "Work", PROGRESS_THRESHOLD) as progress:
        assert progress.visible
        dialog = progress._dialog
        assert dialog.maximum() == PROGRESS_THRESHOLD
        assert progress.step()
        assert progress.step()
        assert dialog.value() == 1
        assert "1 / 50 file(s)" in dialog.labelText()
        assert dialog.labelText().startswith("Work\n")
    assert not progress.visible


def test_custom_threshold(qtbot):
    with FileProgress(None, "Work", 3, threshold=3) as progress:
        assert progress.visible


def test_cancel_button_stops(qtbot):
    with FileProgress(None, "Work", 60) as progress:
        assert progress.step()
        progress._dialog.findChild(QPushButton).click()
        assert progress.cancelled
        assert not progress.step()


def test_cancel_without_window(qtbot):
    progress = FileProgress(None, "Work", 2)
    progress.cancel()
    assert not progress.step()
    progress.close()
