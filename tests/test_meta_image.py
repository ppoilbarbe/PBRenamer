"""Tests for core/image_meta.py — EXIF/IPTC metadata reading."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pbrenamer.core import image_meta

# Real JPEG with known EXIF data (Canon EOS 30D, crafted for PBRenamer tests).
# Fields present: ImageDescription, Make, Model, DateTime, Copyright,
#                 DateTimeOriginal, DateTimeDigitized.
SAMPLE_EXIF = Path(__file__).parent / "data" / "sample_exif.jpg"

_EXPECTED_DT = datetime.datetime(2021, 11, 20, 21, 54, 56)


class _FakeExif(dict):
    """Minimal stand-in for Pillow's Exif object."""

    def __init__(self, main: dict, sub_ifds: dict[int, dict] | None = None):
        super().__init__(main)
        self._sub_ifds = sub_ifds or {}

    def get_ifd(self, ifd_id: int) -> dict:
        return self._sub_ifds.get(ifd_id, {})


def _make_image(exif: _FakeExif) -> MagicMock:
    img = MagicMock()
    img.__enter__ = lambda s: s
    img.__exit__ = MagicMock(return_value=False)
    img.getexif.return_value = exif
    return img


# Tag IDs
_DATETIME_DIGITIZED_TAG = 36868  # Exif.Photo.DateTimeDigitized
_DATETIME_ORIGINAL_TAG = 36867  # Exif.Photo.DateTimeOriginal
_MAKE_TAG = 271  # Exif.Image.Make  (main IFD)
_EXIF_IFD = 0x8769


@pytest.fixture(autouse=True)
def _pillow_available(monkeypatch):
    monkeypatch.setattr(image_meta, "_PILLOW", True)


# ---------------------------------------------------------------------------
# Unit tests (mocked Pillow)
# ---------------------------------------------------------------------------


class TestReadExifMainIFD:
    def test_make_from_main_ifd(self):
        exif = _FakeExif({_MAKE_TAG: "Canon"})
        with patch("PIL.Image.open", return_value=_make_image(exif)):
            assert image_meta.read_field("dummy.jpg", "Make") == "Canon"

    def test_absent_field_returns_none(self):
        exif = _FakeExif({})
        with patch("PIL.Image.open", return_value=_make_image(exif)):
            assert image_meta.read_field("dummy.jpg", "Make") is None


class TestReadExifSubIFD:
    def test_datetime_digitized_in_exif_ifd(self):
        """DateTimeDigitized lives in ExifIFD, not the main IFD."""
        exif = _FakeExif(
            {},
            {_EXIF_IFD: {_DATETIME_DIGITIZED_TAG: "2021:11:20 21:54:56"}},
        )
        with patch("PIL.Image.open", return_value=_make_image(exif)):
            result = image_meta.read_field("dummy.jpg", "DateTimeDigitized")
        assert result == _EXPECTED_DT

    def test_datetime_original_in_exif_ifd(self):
        exif = _FakeExif(
            {},
            {_EXIF_IFD: {_DATETIME_ORIGINAL_TAG: "2021:11:20 21:54:56"}},
        )
        with patch("PIL.Image.open", return_value=_make_image(exif)):
            result = image_meta.read_field("dummy.jpg", "DateTimeOriginal")
        assert result == _EXPECTED_DT

    def test_main_ifd_takes_precedence_over_sub_ifd(self):
        """If a tag exists in both, the main IFD value wins."""
        exif = _FakeExif(
            {_MAKE_TAG: "main"},
            {_EXIF_IFD: {_MAKE_TAG: "sub"}},
        )
        with patch("PIL.Image.open", return_value=_make_image(exif)):
            assert image_meta.read_field("dummy.jpg", "Make") == "main"


class TestReadExifCaseInsensitive:
    def test_field_name_is_case_insensitive(self):
        exif = _FakeExif(
            {},
            {_EXIF_IFD: {_DATETIME_DIGITIZED_TAG: "2021:11:20 21:54:56"}},
        )
        with patch("PIL.Image.open", return_value=_make_image(exif)):
            assert image_meta.read_field(
                "dummy.jpg", "datetimedigitized"
            ) == image_meta.read_field("dummy.jpg", "DateTimeDigitized")


class TestPillowUnavailable:
    def test_returns_none_when_pillow_missing(self, monkeypatch):
        monkeypatch.setattr(image_meta, "_PILLOW", False)
        assert image_meta.read_field("dummy.jpg", "DateTimeDigitized") is None


# ---------------------------------------------------------------------------
# Integration tests (real JPEG file)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SAMPLE_EXIF.exists(), reason="sample_exif.jpg not found")
class TestRealFile:
    path = str(SAMPLE_EXIF)

    # --- main IFD fields ---

    def test_make(self):
        assert image_meta.read_field(self.path, "Make") == "Canon"

    def test_model(self):
        assert image_meta.read_field(self.path, "Model") == "Canon EOS 30D"

    def test_image_description(self):
        assert image_meta.read_field(self.path, "ImageDescription") == (
            "Comment/Description test for PBRenamer"
        )

    def test_copyright(self):
        assert (
            image_meta.read_field(self.path, "Copyright")
            == "Copyright test for PBRenamer"
        )

    def test_datetime(self):
        assert image_meta.read_field(self.path, "DateTime") == _EXPECTED_DT

    # --- ExifIFD (sub-IFD) fields ---

    def test_datetime_original(self):
        assert image_meta.read_field(self.path, "DateTimeOriginal") == _EXPECTED_DT

    def test_datetime_digitized(self):
        assert image_meta.read_field(self.path, "DateTimeDigitized") == _EXPECTED_DT

    # --- absent field ---

    def test_artist(self):
        assert image_meta.read_field(self.path, "Artist") == "©Renamer test suite"

    # --- case-insensitivity on real data ---

    def test_field_name_case_insensitive(self):
        assert image_meta.read_field(self.path, "make") == image_meta.read_field(
            self.path, "Make"
        )
