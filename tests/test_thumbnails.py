"""Tests for the lazy thumbnail loader of the file list."""

from __future__ import annotations

import pytest
from PIL import Image
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from pbrenamer.ui import thumbnails
from pbrenamer.ui.thumbnails import THUMB_COLUMN, ThumbnailLoader, format_size

_IMAGES = frozenset({"png", "jpg"})
_VIDEOS = frozenset({"mp4"})


@pytest.fixture
def tree(qtbot):
    widget = QTreeWidget()
    widget.setColumnCount(4)
    widget.resize(400, 300)
    qtbot.addWidget(widget)
    widget.show()
    return widget


@pytest.fixture
def loader(tree):
    ldr = ThumbnailLoader(tree)
    ldr.configure(True, 32, 32, True, _IMAGES, _VIDEOS)
    yield ldr
    ldr.stop()


def _fill(tree, paths):
    tree.clear()
    for path in paths:
        item = QTreeWidgetItem([path.rsplit("/", 1)[-1], ""])
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        tree.addTopLevelItem(item)


def _images(tmp_path, n, size=(40, 20)):
    paths = []
    for i in range(n):
        p = tmp_path / f"img_{i:03}.png"
        Image.new("RGB", size, "red").save(p)
        paths.append(str(p))
    return paths


def _wait_idle(qtbot, loader):
    qtbot.waitUntil(lambda: all(w.isFinished() for w in loader._workers), timeout=5000)
    qtbot.wait(20)


@pytest.mark.parametrize(
    ("size", "text"),
    [(10, "10 B"), (2048, "2.0 KB"), (3 * 1024**2, "3.0 MB"), (5 * 1024**4, "5.0 TB")],
)
def test_format_size(size, text):
    assert format_size(size) == text


class TestConfigure:
    def test_enabled_shows_column(self, tree, loader):
        assert not tree.isColumnHidden(THUMB_COLUMN)
        assert tree.iconSize() == QSize(32, 32)
        assert tree.columnWidth(THUMB_COLUMN) == 40

    def test_disabled_hides_column_and_loads_nothing(self, tree, tmp_path, qtbot):
        ldr = ThumbnailLoader(tree)
        ldr.configure(False, 32, 32, True, _IMAGES, _VIDEOS)
        _fill(tree, _images(tmp_path, 2))
        ldr.populate()
        assert tree.isColumnHidden(THUMB_COLUMN)
        assert ldr._workers == []
        assert tree.topLevelItem(0).icon(THUMB_COLUMN).isNull()
        assert "\n" not in tree.topLevelItem(0).text(0)


class TestPopulate:
    def test_images_loaded_with_info(self, tree, loader, tmp_path, qtbot):
        paths = _images(tmp_path, 3)
        _fill(tree, paths)
        loader.populate()
        _wait_idle(qtbot, loader)
        item = tree.topLevelItem(0)
        assert loader.is_loaded(paths[0])
        assert not item.icon(THUMB_COLUMN).isNull()
        name, info = item.text(0).split("\n")
        assert name == "img_000.png"
        assert info.startswith("40×20  ·  ")
        assert info.endswith(" B")

    def test_video_icon_and_other_files(self, tree, loader, tmp_path, qtbot):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"x" * 10)
        text = tmp_path / "notes.txt"
        text.write_text("x")
        _fill(tree, [str(video), str(text), str(tmp_path / "gone.png")])
        loader.populate()
        _wait_idle(qtbot, loader)
        assert not tree.topLevelItem(0).icon(THUMB_COLUMN).isNull()
        assert tree.topLevelItem(0).text(0) == "clip.mp4\n10 B"
        assert not loader.is_loaded(str(video))
        assert tree.topLevelItem(1).icon(THUMB_COLUMN).isNull()
        assert tree.topLevelItem(1).text(0) == "notes.txt"
        # A missing image keeps its name only and shows "?" once tried.
        assert tree.topLevelItem(2).text(0) == "gone.png"
        assert tree.topLevelItem(2).text(THUMB_COLUMN) == "?"

    def test_only_visible_rows_loaded(self, tree, loader, tmp_path, qtbot):
        paths = _images(tmp_path, 200, size=(4, 4))
        _fill(tree, paths)
        loader.populate()
        _wait_idle(qtbot, loader)
        first, last = loader.visible_rows()
        assert first == 0
        assert last < 199
        assert loader.is_loaded(paths[last])
        assert not loader.is_loaded(paths[199])

    def test_scroll_loads_after_debounce(self, tree, loader, tmp_path, qtbot):
        paths = _images(tmp_path, 200, size=(4, 4))
        _fill(tree, paths)
        loader.populate()
        _wait_idle(qtbot, loader)
        tree.scrollToBottom()
        assert loader._debounce.isActive()
        qtbot.waitUntil(lambda: loader.is_loaded(paths[199]), timeout=5000)

    def test_slider_held_defers_loading(self, tree, loader, tmp_path, qtbot):
        paths = _images(tmp_path, 200, size=(4, 4))
        _fill(tree, paths)
        loader.populate()
        _wait_idle(qtbot, loader)
        bar = tree.verticalScrollBar()
        bar.setSliderDown(True)
        bar.setValue(bar.maximum())
        loader._on_debounce()
        assert not loader.is_loaded(paths[199])
        bar.setSliderDown(False)
        bar.sliderReleased.emit()
        qtbot.waitUntil(lambda: loader.is_loaded(paths[199]), timeout=5000)

    def test_resize_schedules(self, tree, loader):
        tree.resize(500, 400)
        assert loader._debounce.isActive()

    def test_disabled_does_not_schedule(self, tree, loader):
        loader._debounce.stop()
        loader.enabled = False
        loader._schedule()
        assert not loader._debounce.isActive()

    def test_empty_tree(self, tree, loader):
        loader.populate()
        assert loader.visible_rows() == (0, -1)
        loader.load_visible()
        assert loader._workers == []

    def test_nothing_pending(self, tree, loader, tmp_path, qtbot):
        _fill(tree, _images(tmp_path, 1))
        loader.populate()
        _wait_idle(qtbot, loader)
        before = list(loader._workers)
        loader.load_visible()
        assert loader._workers == before

    def test_restart_cancels_running_workers(self, tree, loader, tmp_path, qtbot):
        paths = _images(tmp_path, 3)
        _fill(tree, paths)
        loader.populate()
        running = list(loader._workers)
        loader._loaded.clear()
        loader.load_visible()
        assert all(w._cancelled for w in running)
        _wait_idle(qtbot, loader)


class TestStaleSignals:
    def test_rejected_when_row_changed(self, tree, loader, tmp_path):
        paths = _images(tmp_path, 2)
        _fill(tree, paths)
        loader.populate()
        loader.stop()
        image = QImage(4, 4, QImage.Format.Format_RGB32)
        loader._on_ready(0, paths[1], image, QSize(4, 4))
        loader._on_ready(5, paths[0], image, QSize(4, 4))
        assert not loader.is_loaded(paths[1])
        assert not loader.is_loaded(paths[0])

    def test_rejected_when_tree_refilled(self, tree, loader, tmp_path):
        paths = _images(tmp_path, 2)
        _fill(tree, paths)
        loader.populate()
        loader.stop()
        _fill(tree, list(reversed(paths)))
        image = QImage(4, 4, QImage.Format.Format_RGB32)
        loader._on_ready(0, paths[0], image, QSize(4, 4))
        assert not loader.is_loaded(paths[0])

    def test_invalid_size_keeps_text(self, tree, loader, tmp_path):
        paths = _images(tmp_path, 1)
        _fill(tree, paths)
        loader.populate()
        loader.stop()
        before = tree.topLevelItem(0).text(0)
        image = QImage(4, 4, QImage.Format.Format_RGB32)
        loader._on_ready(0, paths[0], image, QSize())
        assert tree.topLevelItem(0).text(0) == before
        assert loader.is_loaded(paths[0])


class TestWorker:
    def test_cancelled_emits_nothing(self, tmp_path, qtbot):
        paths = _images(tmp_path, 2)
        worker = thumbnails.ThumbnailWorker([0, 1], paths, 8, 8, True)
        received = []
        worker.thumbnail_ready.connect(lambda *a: received.append(a))
        worker.cancel()
        worker.run()
        assert received == []

    def test_emits_each_image(self, tmp_path):
        paths = _images(tmp_path, 2)
        worker = thumbnails.ThumbnailWorker([3, 4], paths, 8, 8, False)
        received = []
        worker.thumbnail_ready.connect(lambda *a: received.append(a[:2]))
        worker.run()
        assert received == [(3, paths[0]), (4, paths[1])]
