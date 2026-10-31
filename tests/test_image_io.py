"""Tests for core/image_io.py and the JPEG helpers of core/image_ops.py.

Ports PBPicat's ``tests/test_image_io.py`` and its ``is_jpeg`` cases.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from PySide6.QtGui import QImage, QPixmap

from pbrenamer.core.image_io import (
    _pillow_to_qimage,
    image_size,
    load_pixmap,
    load_qimage,
)
from pbrenamer.core.image_ops import is_jpeg, repair_jpeg_sos


def _null_reader():
    reader = MagicMock()
    reader.read.return_value = QImage()
    reader.size.return_value = MagicMock(isValid=lambda: False)
    return reader


def _baseline_jpeg(w: int = 16, h: int = 16) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def _sos_se_offset(data: bytes) -> int:
    i = data.index(b"\xff\xda")
    ns = data[i + 4]
    return i + 6 + 2 * ns


# ---------------------------------------------------------------------------
# is_jpeg, repair_jpeg_sos
# ---------------------------------------------------------------------------


class TestIsJpeg:
    @pytest.mark.parametrize("name", ["a.jpg", "a.jpeg", "a.jpe", "a.JPG"])
    def test_true(self, name):
        assert is_jpeg(Path(name))
        assert is_jpeg(name)

    @pytest.mark.parametrize("name", ["a.png", "a.tiff", "jpg"])
    def test_false(self, name):
        assert not is_jpeg(Path(name))


class TestRepairSos:
    def test_not_jpeg_unchanged(self):
        assert repair_jpeg_sos(b"\x89PNG....") == b"\x89PNG...."

    def test_valid_jpeg_unchanged(self):
        data = _baseline_jpeg()
        assert repair_jpeg_sos(data) == data

    def test_malformed_se_repaired(self):
        data = _baseline_jpeg()
        offset = _sos_se_offset(data)
        assert data[offset] == 0x3F
        broken = bytearray(data)
        broken[offset] = 0
        assert repair_jpeg_sos(bytes(broken)) == data

    def test_progressive_unchanged(self):
        buf = io.BytesIO()
        Image.new("RGB", (16, 16)).save(buf, format="JPEG", progressive=True)
        data = buf.getvalue()
        assert repair_jpeg_sos(data) == data

    def test_truncated_without_sos(self):
        data = _baseline_jpeg()
        head = data[: data.index(b"\xff\xda")]
        assert repair_jpeg_sos(head) == head

    def test_padding_bytes_skipped(self):
        assert repair_jpeg_sos(b"\xff\xd8\x00\x00\xff\xd9\x00\x00") == (
            b"\xff\xd8\x00\x00\xff\xd9\x00\x00"
        )


# ---------------------------------------------------------------------------
# _pillow_to_qimage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "size"), [("RGBA", (10, 10)), ("RGB", (8, 6)), ("P", (4, 4))]
)
def test_pillow_to_qimage(qapp, mode, size):
    result = _pillow_to_qimage(Image.new(mode, size))
    assert not result.isNull()
    assert (result.width(), result.height()) == size


# ---------------------------------------------------------------------------
# load_qimage
# ---------------------------------------------------------------------------


class TestLoadQImage:
    def test_qt_succeeds(self, qapp, sample_png):
        img = load_qimage(sample_png)
        assert img.width() == 100

    def test_str_path(self, qapp, sample_png):
        assert not load_qimage(str(sample_png)).isNull()

    def test_scaled(self, qapp, sample_png):
        img = load_qimage(sample_png, max_w=32, max_h=32)
        assert img.width() <= 32
        assert img.height() <= 32

    def test_no_scale_when_zero(self, qapp, sample_png):
        assert load_qimage(sample_png, max_w=0, max_h=0).width() == 100

    def test_jpeg(self, qapp, tmp_path):
        f = tmp_path / "a.jpg"
        f.write_bytes(_baseline_jpeg(40, 20))
        img = load_qimage(f, 20, 20)
        assert (img.width(), img.height()) == (20, 10)

    def test_malformed_jpeg_repaired(self, qapp, tmp_path):
        data = bytearray(_baseline_jpeg(40, 20))
        data[_sos_se_offset(bytes(data))] = 0
        f = tmp_path / "a.jpg"
        f.write_bytes(bytes(data))
        assert not load_qimage(f).isNull()

    def test_unreadable_jpeg(self, qapp, tmp_path):
        assert load_qimage(tmp_path / "missing.jpg").isNull()

    def test_pillow_fallback(self, qapp, tmp_path):
        f = tmp_path / "test.png"
        Image.new("RGB", (20, 20), "red").save(str(f))
        with patch("pbrenamer.core.image_io.QImageReader", return_value=_null_reader()):
            img = load_qimage(f)
        assert img.width() == 20

    def test_pillow_fallback_scaled(self, qapp, tmp_path):
        f = tmp_path / "big.png"
        Image.new("RGB", (200, 200), "blue").save(str(f))
        with patch("pbrenamer.core.image_io.QImageReader", return_value=_null_reader()):
            img = load_qimage(f, max_w=32, max_h=32)
        assert img.width() <= 32

    def test_both_fail(self, qapp, tmp_path):
        f = tmp_path / "test.xyz"
        f.write_text("not an image")
        assert load_qimage(f).isNull()

    def test_pillow_exception(self, qapp, tmp_path):
        f = tmp_path / "bad.png"
        f.write_bytes(b"\x89PNG corrupted")
        with patch("pbrenamer.core.image_io.QImageReader", return_value=_null_reader()):
            assert load_qimage(f).isNull()


# ---------------------------------------------------------------------------
# image_size
# ---------------------------------------------------------------------------


def test_image_size(qapp, sample_png):
    size = image_size(sample_png)
    assert (size.width(), size.height()) == (100, 80)


def test_image_size_invalid_file_returns_none(qapp, tmp_path):
    f = tmp_path / "test.xyz"
    f.write_text("not an image")
    assert image_size(f) is None


# ---------------------------------------------------------------------------
# load_pixmap
# ---------------------------------------------------------------------------


class TestLoadPixmap:
    def test_qt_succeeds(self, qapp, sample_png):
        assert load_pixmap(sample_png).width() == 100

    def test_auto_rotate_false(self, qapp, sample_png):
        assert load_pixmap(sample_png, auto_rotate=False).width() == 100

    def test_pillow_fallback(self, qapp, tmp_path):
        f = tmp_path / "test.png"
        Image.new("RGB", (15, 15), "green").save(str(f))
        with patch("pbrenamer.core.image_io.QImageReader", return_value=_null_reader()):
            pix = load_pixmap(f)
        assert pix.width() == 15

    def test_pillow_returns_null(self, qapp, tmp_path):
        f = tmp_path / "test.png"
        Image.new("RGB", (15, 15), "green").save(str(f))
        with (
            patch("pbrenamer.core.image_io.QImageReader", return_value=_null_reader()),
            patch("pbrenamer.core.image_io._pillow_to_qimage", return_value=QImage()),
        ):
            assert load_pixmap(f).isNull()

    def test_both_fail(self, qapp, tmp_path):
        f = tmp_path / "test.xyz"
        f.write_text("not an image")
        pix = load_pixmap(f)
        assert isinstance(pix, QPixmap)
        assert pix.isNull()
