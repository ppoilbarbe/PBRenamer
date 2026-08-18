"""Tests for HiDPI-aware drag'n'drop cursor pixmaps."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbrenamer.ui import dnd_cursors


class _FakeScreen:
    def __init__(self, dpr: float) -> None:
        self._dpr = dpr

    def devicePixelRatio(self) -> float:  # noqa: N802
        return self._dpr


class _FakeDrag:
    def __init__(self) -> None:
        self.cursors: list[tuple] = []

    def setDragCursor(self, pixmap, action) -> None:  # noqa: N802
        self.cursors.append((pixmap, action))


class TestScreenScale:
    def test_defaults_to_1x_when_no_screen(self, monkeypatch):
        monkeypatch.setattr(
            dnd_cursors.QApplication, "primaryScreen", staticmethod(lambda: None)
        )
        assert dnd_cursors._screen_scale() == 1

    def test_1x_for_standard_dpr(self, monkeypatch):
        monkeypatch.setattr(
            dnd_cursors.QApplication,
            "primaryScreen",
            staticmethod(lambda: _FakeScreen(1.0)),
        )
        assert dnd_cursors._screen_scale() == 1

    def test_2x_for_retina_dpr(self, monkeypatch):
        monkeypatch.setattr(
            dnd_cursors.QApplication,
            "primaryScreen",
            staticmethod(lambda: _FakeScreen(2.0)),
        )
        assert dnd_cursors._screen_scale() == 2

    def test_3x_for_high_dpr(self, monkeypatch):
        monkeypatch.setattr(
            dnd_cursors.QApplication,
            "primaryScreen",
            staticmethod(lambda: _FakeScreen(3.0)),
        )
        assert dnd_cursors._screen_scale() == 3


class TestDragCursor:
    def test_returns_pixmap_with_matching_device_pixel_ratio(self, qtbot, monkeypatch):
        monkeypatch.setattr(dnd_cursors, "_screen_scale", lambda: 2)
        pixmap = dnd_cursors.drag_cursor("copy")
        assert not pixmap.isNull()
        assert pixmap.devicePixelRatio() == 2.0

    def test_result_is_cached(self, qtbot, monkeypatch):
        monkeypatch.setattr(dnd_cursors, "_screen_scale", lambda: 1)
        first = dnd_cursors.drag_cursor("move")
        second = dnd_cursors.drag_cursor("move")
        assert first is second

    def test_each_cursor_state_loads(self, qtbot, monkeypatch):
        monkeypatch.setattr(dnd_cursors, "_screen_scale", lambda: 1)
        for name in ("copy", "move", "alias", "not-allowed"):
            assert not dnd_cursors.drag_cursor(name).isNull()


class TestSetDragCursors:
    def test_assigns_all_four_actions(self, qtbot, monkeypatch):
        monkeypatch.setattr(dnd_cursors, "_screen_scale", lambda: 1)
        drag = _FakeDrag()
        dnd_cursors.set_drag_cursors(drag)

        actions = [action for _pixmap, action in drag.cursors]
        assert actions == [
            Qt.DropAction.CopyAction,
            Qt.DropAction.MoveAction,
            Qt.DropAction.LinkAction,
            Qt.DropAction.IgnoreAction,
        ]
        for pixmap, _action in drag.cursors:
            assert not pixmap.isNull()
