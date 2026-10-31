"""Tests for pbrenamer.core.image_ops — lossless rotation and EXIF orientation.

Ports PBPicat's ``tests/test_image_ops.py`` (``is_jpeg`` and the SOS repair
are covered by ``test_image_io.py``).  EXIF blocks are written with Pillow.
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from pbrenamer.core import image_ops
from pbrenamer.core.image_ops import (
    _find_jpegtran,
    _pil_apply,
    _pil_save_lossless,
    get_exif_orientation,
    rotate_lossless,
    set_exif_orientation,
)
from pbrenamer.core.undo import ExifResetEntry, RotationEntry, UndoError

# MCU-aligned dimensions: no edge trimming by jpegtran
W, H = 160, 96

needs_jpegtran = pytest.mark.skipif(
    not image_ops.jpegtran_available(), reason="jpegtran not installed"
)
needs_pyexiv2 = pytest.mark.skipif(
    not image_ops.pyexiv2_available(), reason="pyexiv2 not installed"
)


def _jpeg(path: Path, orientation: int | None = None) -> Path:
    img = Image.new("RGB", (W, H), color=(100, 150, 200))
    buf = io.BytesIO()
    if orientation is None:
        img.save(buf, format="JPEG")
    else:
        exif = Image.Exif()
        exif[274] = orientation
        img.save(buf, format="JPEG", exif=exif)
    path.write_bytes(buf.getvalue())
    return path


def _image(path: Path, fmt: str) -> Path:
    Image.new("RGB", (W, H), color=(80, 120, 160)).save(path, format=fmt)
    return path


def _size(path: Path) -> tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def _raw_orientation(path: Path) -> int | None:
    with Image.open(path) as img:
        return img.getexif().get(274)


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def test_availability_flags():
    assert image_ops.pillow_available()
    assert image_ops.jpegtran_available() == (_find_jpegtran() is not None)
    assert isinstance(image_ops.pyexiv2_available(), bool)


# ---------------------------------------------------------------------------
# get_exif_orientation
# ---------------------------------------------------------------------------


class TestGetExifOrientation:
    def test_no_exif(self, tmp_path):
        assert get_exif_orientation(_jpeg(tmp_path / "plain.jpg")) is None

    def test_trivial_1_ignored(self, tmp_path):
        assert get_exif_orientation(_jpeg(tmp_path / "o1.jpg", 1)) is None

    @pytest.mark.parametrize("value", [3, 6, 8])
    def test_value(self, tmp_path, value):
        assert get_exif_orientation(_jpeg(tmp_path / "o.jpg", value)) == value

    def test_png(self, tmp_path):
        assert get_exif_orientation(_image(tmp_path / "i.png", "PNG")) is None

    def test_missing_file(self, tmp_path):
        assert get_exif_orientation(tmp_path / "nope.jpg") is None


# ---------------------------------------------------------------------------
# _find_jpegtran
# ---------------------------------------------------------------------------


class TestFindJpegtran:
    def test_not_found(self, monkeypatch):
        monkeypatch.setattr(image_ops.shutil, "which", lambda _name: None)
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        assert _find_jpegtran() is None
        assert not image_ops.jpegtran_available()

    @pytest.mark.parametrize("name", ["jpegtran", "jpegtran.exe"])
    def test_meipass_found(self, tmp_path, monkeypatch, name):
        fake = tmp_path / name
        fake.touch()
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        assert _find_jpegtran() == str(fake)

    def test_meipass_missing_falls_through(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        monkeypatch.setattr(image_ops.shutil, "which", lambda _name: "/bin/jt")
        assert _find_jpegtran() == "/bin/jt"


# ---------------------------------------------------------------------------
# rotate_lossless — JPEG
# ---------------------------------------------------------------------------


@needs_jpegtran
class TestRotateJpeg:
    @pytest.mark.parametrize(
        ("op", "size", "inverse"),
        [
            (90, (H, W), -90),
            (-90, (H, W), 90),
            (180, (W, H), 180),
            ("hflip", (W, H), "hflip"),
            ("vflip", (W, H), "vflip"),
            ("transpose", (H, W), "transpose"),
            ("transverse", (H, W), "transverse"),
        ],
    )
    def test_op(self, tmp_path, op, size, inverse):
        p = _jpeg(tmp_path / "img.jpg")
        assert rotate_lossless(p, op) == inverse
        assert _size(p) == size

    def test_str_path(self, tmp_path):
        p = _jpeg(tmp_path / "img.jpg")
        rotate_lossless(str(p), 90)
        assert _size(p) == (H, W)

    def test_undo_roundtrip(self, tmp_path):
        p = _jpeg(tmp_path / "img.jpg")
        rotate_lossless(p, rotate_lossless(p, 90))
        assert _size(p) == (W, H)

    @pytest.mark.parametrize(
        ("value", "size", "inverse"), [(6, (H, W), -90), (3, (W, H), 180)]
    )
    def test_auto(self, tmp_path, value, size, inverse):
        p = _jpeg(tmp_path / "img.jpg", value)
        assert rotate_lossless(p, "auto") == inverse
        assert get_exif_orientation(p) is None
        assert _size(p) == size

    def test_auto_without_exif(self, tmp_path):
        with pytest.raises(ValueError):
            rotate_lossless(_jpeg(tmp_path / "img.jpg"), "auto")

    def test_auto_unsupported_value(self, tmp_path, monkeypatch):
        p = _jpeg(tmp_path / "img.jpg", 6)
        monkeypatch.setattr(image_ops, "get_exif_orientation", lambda _p: 9)
        with pytest.raises(ValueError, match="9"):
            rotate_lossless(p, "auto")

    @needs_pyexiv2
    def test_plain_rotation_strips_orientation(self, tmp_path):
        p = _jpeg(tmp_path / "img.jpg", 6)
        rotate_lossless(p, 90)
        assert get_exif_orientation(p) is None

    def test_jpegtran_failure(self, tmp_path, monkeypatch):
        p = _jpeg(tmp_path / "img.jpg")
        failed = subprocess.CompletedProcess([], 1, b"", b"jpegtran: some error")
        monkeypatch.setattr(image_ops.subprocess, "run", lambda *a, **k: failed)
        with pytest.raises(RuntimeError, match="jpegtran: some error"):
            rotate_lossless(p, 90)

    def test_jpegtran_failure_with_hint(self, tmp_path, monkeypatch):
        p = _jpeg(tmp_path / "img.jpg")
        failed = subprocess.CompletedProcess([], 1, b"", b"Premature end of JPEG file")
        monkeypatch.setattr(image_ops.subprocess, "run", lambda *a, **k: failed)
        with pytest.raises(RuntimeError, match="truncated"):
            rotate_lossless(p, 90)


def test_rotate_jpeg_without_jpegtran(tmp_path, monkeypatch):
    p = _jpeg(tmp_path / "img.jpg")
    monkeypatch.setattr(image_ops, "_find_jpegtran", lambda: None)
    with pytest.raises(RuntimeError, match="jpegtran"):
        rotate_lossless(p, 90)


# ---------------------------------------------------------------------------
# rotate_lossless — Pillow (non-JPEG)
# ---------------------------------------------------------------------------


class TestRotatePillow:
    @pytest.mark.parametrize(
        ("op", "size", "inverse"),
        [
            (90, (H, W), -90),
            (-90, (H, W), 90),
            (180, (W, H), 180),
            ("hflip", (W, H), "hflip"),
            ("vflip", (W, H), "vflip"),
            ("transpose", (H, W), "transpose"),
            ("transverse", (H, W), "transverse"),
        ],
    )
    def test_png(self, tmp_path, op, size, inverse):
        p = _image(tmp_path / "img.png", "PNG")
        assert rotate_lossless(p, op) == inverse
        assert _size(p) == size

    def test_png_undo_roundtrip(self, tmp_path):
        p = _image(tmp_path / "img.png", "PNG")
        rotate_lossless(p, rotate_lossless(p, 90))
        assert _size(p) == (W, H)

    @pytest.mark.parametrize(
        ("name", "fmt", "op", "size"),
        [
            ("img.tiff", "TIFF", 90, (H, W)),
            ("img.tif", "TIFF", -90, (H, W)),
            ("img.bmp", "BMP", 180, (W, H)),
            ("img.webp", "WEBP", 90, (H, W)),
        ],
    )
    def test_formats(self, tmp_path, name, fmt, op, size):
        p = _image(tmp_path / name, fmt)
        rotate_lossless(p, op)
        assert _size(p) == size

    def test_unknown_op(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown op"):
            _pil_apply(_image(tmp_path / "img.png", "PNG"), "flip_diagonal")

    def test_save_other_format(self, tmp_path):
        p = tmp_path / "img.ppm"
        _pil_save_lossless(Image.new("RGB", (W, H)), p)
        assert _size(p) == (W, H)


# ---------------------------------------------------------------------------
# set_exif_orientation
# ---------------------------------------------------------------------------


@needs_pyexiv2
class TestSetExifOrientation:
    def test_patches_existing_tag(self, tmp_path):
        p = _jpeg(tmp_path / "img.jpg", 1)
        set_exif_orientation(p, 6)
        assert _raw_orientation(p) == 6

    def test_overwrites(self, tmp_path):
        p = _jpeg(tmp_path / "img.jpg", 3)
        set_exif_orientation(p, 8)
        assert _raw_orientation(p) == 8

    def test_to_1(self, tmp_path):
        p = _jpeg(tmp_path / "img.jpg", 6)
        set_exif_orientation(p, 1)
        assert _raw_orientation(p) == 1

    def test_no_exif_block_is_noop(self, tmp_path):
        p = _jpeg(tmp_path / "img.jpg")
        set_exif_orientation(p, 6)
        assert get_exif_orientation(p) is None

    def test_error_is_logged(self, tmp_path, monkeypatch, caplog):
        import pyexiv2

        def boom(*_a):
            raise RuntimeError("pyexiv2 boom")

        p = _jpeg(tmp_path / "img.jpg", 3)
        monkeypatch.setattr(pyexiv2.Image, "modify_exif", boom)
        set_exif_orientation(p, 6)
        assert "Could not set" in caplog.text

    @needs_jpegtran
    def test_undo_restores_orientation(self, tmp_path):
        p = _jpeg(tmp_path / "img.jpg", 6)
        inverse = rotate_lossless(p, "auto")
        rotate_lossless(p, inverse)
        set_exif_orientation(p, 6)
        assert _raw_orientation(p) == 6
        assert _size(p) == (W, H)


def test_set_exif_orientation_without_pyexiv2(tmp_path, monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "pyexiv2", None)
    p = _jpeg(tmp_path / "img.jpg", 3)
    set_exif_orientation(p, 6)
    assert _raw_orientation(p) == 3
    assert "pyexiv2 unavailable" in caplog.text


# ---------------------------------------------------------------------------
# Undo entries
# ---------------------------------------------------------------------------


class TestRotationEntry:
    def test_undo_png(self, tmp_path):
        p = _image(tmp_path / "img.png", "PNG")
        inverse = rotate_lossless(p, 90)
        RotationEntry([(str(p), inverse, None)]).undo()
        assert _size(p) == (W, H)

    @needs_jpegtran
    @needs_pyexiv2
    def test_undo_restores_orientation(self, tmp_path):
        p = _jpeg(tmp_path / "img.jpg", 6)
        inverse = rotate_lossless(p, "auto")
        RotationEntry([(str(p), inverse, 6)]).undo()
        assert _raw_orientation(p) == 6
        assert _size(p) == (W, H)

    def test_errors_collected(self, tmp_path):
        ok = _image(tmp_path / "ok.png", "PNG")
        inverse = rotate_lossless(ok, 90)
        entry = RotationEntry(
            [(str(tmp_path / "gone.png"), 90, None), (str(ok), inverse, None)]
        )
        with pytest.raises(UndoError, match="gone.png"):
            entry.undo()
        assert _size(ok) == (W, H)


@needs_pyexiv2
def test_exif_reset_entry(tmp_path):
    p = _jpeg(tmp_path / "img.jpg", 6)
    set_exif_orientation(p, 1)
    ExifResetEntry([(str(p), 6)]).undo()
    assert get_exif_orientation(p) == 6
