"""Tests for pbrenamer.ui.metadata_view — the tree shared by the File
information window and the image viewer."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pbrenamer.core import audio_meta, image_meta, video_meta
from pbrenamer.ui import metadata_view
from pbrenamer.ui.metadata_view import MetadataView


@pytest.fixture
def view(qtbot):
    widget = MetadataView()
    qtbot.addWidget(widget)
    return widget


def _titles(view) -> list[str]:
    return [view.topLevelItem(i).text(0) for i in range(view.topLevelItemCount())]


def test_image_with_raw_sections(view, sample_png):
    raw = [("EXIF", [("Image.Make", "ACME")])]
    with patch.object(image_meta, "read_raw_sections", return_value=raw) as read:
        assert view.show_file(str(sample_png), ["/x/test.xmp"]) == "image"
    read.assert_called_once_with(str(sample_png), ["/x/test.xmp"])
    assert _titles(view)[-1] == "EXIF"
    row = view.topLevelItem(view.topLevelItemCount() - 1).child(0)
    assert (row.text(0), row.text(2)) == ("Image.Make", "ACME")


@pytest.mark.parametrize(
    ("kind", "title"), [("audio", "Audio metadata"), ("video", "Video metadata")]
)
def test_audio_and_video(view, tmp_path, kind, title):
    p = tmp_path / "f.bin"
    p.write_bytes(b"x")
    with (
        patch.object(image_meta, "can_read", return_value=False),
        patch.object(video_meta, "can_read", return_value=kind == "video"),
        patch.object(audio_meta, "can_read", return_value=kind == "audio"),
    ):
        assert view.show_file(str(p)) == kind
    assert title in _titles(view)


def test_raw_rows_are_not_insertable(view, sample_png, qtbot):
    raw = [("EXIF", [("Image.Make", "ACME")])]
    with patch.object(image_meta, "read_raw_sections", return_value=raw):
        view.show_file(str(sample_png))
    received = []
    view.field_requested.connect(received.append)
    raw_row = view.topLevelItem(view.topLevelItemCount() - 1).child(0)
    view._on_item_double_clicked(raw_row, 0)
    field_row = view.topLevelItem(0).child(0)
    view._on_item_double_clicked(field_row, 0)
    assert received == ["{date}"]


def test_context_menu_outside_rows_is_noop(view, monkeypatch):
    monkeypatch.setattr(metadata_view, "QMenu", lambda *_a: pytest.fail("menu shown"))
    view._on_context_menu(view.viewport().rect().center())


def test_context_menu_dismissed(view, tmp_path, monkeypatch):
    p = tmp_path / "f.txt"
    p.write_text("x")
    view.show_file(str(p))
    view.show()
    view.expandAll()
    item = view.topLevelItem(0).child(0)
    pos = view.visualItemRect(item).center()

    class _Menu:
        def __init__(self, _parent):
            pass

        def addAction(self, _text):  # noqa: N802
            return object()

        def exec(self, _pos):
            return None

    monkeypatch.setattr(metadata_view, "QMenu", _Menu)
    received = []
    view.field_requested.connect(received.append)
    view._on_context_menu(pos)
    assert received == []
