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


# ---------------------------------------------------------------------------
# _rational_to_str
# ---------------------------------------------------------------------------


class TestRationalToStr:
    def test_integer_value(self):
        assert image_meta._rational_to_str(4.0) == "4"

    def test_fraction_less_than_one(self):
        result = image_meta._rational_to_str(1 / 125)
        assert result == "1/125"

    def test_decimal_value(self):
        result = image_meta._rational_to_str(2.8)
        assert result in ("2.8", "2.80")

    def test_zero_division_returns_str(self):
        class BadRational:
            def __float__(self):
                raise ZeroDivisionError

        result = image_meta._rational_to_str(BadRational())
        assert isinstance(result, str)

    def test_type_error_returns_str(self):
        class BadRational:
            def __float__(self):
                raise TypeError

        result = image_meta._rational_to_str(BadRational())
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _decode_bytes
# ---------------------------------------------------------------------------


class TestDecodeBytes:
    def test_bytes_decoded_as_utf8(self):
        assert image_meta._decode_bytes(b"hello") == "hello"

    def test_bytearray_decoded(self):
        assert image_meta._decode_bytes(bytearray(b"world")) == "world"

    def test_null_bytes_stripped(self):
        assert image_meta._decode_bytes(b"abc\x00\x00") == "abc"

    def test_non_bytes_stringified(self):
        assert image_meta._decode_bytes(42) == "42"


# ---------------------------------------------------------------------------
# _fix_str_encoding
# ---------------------------------------------------------------------------


class TestFixStrEncoding:
    def test_mojibake_repaired(self):
        # "é" encoded as UTF-8 (b'\xc3\xa9') then decoded as latin-1 → "Ã©"
        mojibake = "é".encode().decode("latin-1")
        assert image_meta._fix_str_encoding(mojibake) == "é"

    def test_clean_ascii_unchanged(self):
        assert image_meta._fix_str_encoding("Canon") == "Canon"

    def test_genuine_latin1_kept_as_is(self):
        # bytes that aren't valid UTF-8 can't be repaired — keep original
        genuine_latin1 = "\xe9"  # latin-1 "é" not as mojibake
        result = image_meta._fix_str_encoding(genuine_latin1)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# read_field — INTEGER and RATIONAL EXIF fields (mocked)
# ---------------------------------------------------------------------------

_ISO_TAG = 34855  # ISOSpeedRatings tag ID
_FNUMBER_TAG = 33437  # FNumber tag ID


class TestReadExifIntegerField:
    def test_iso_returns_int(self):
        exif = _FakeExif({_ISO_TAG: "400"})
        with patch("PIL.Image.open", return_value=_make_image(exif)):
            result = image_meta.read_field("dummy.jpg", "ISOSpeedRatings")
        assert result == 400

    def test_iso_non_numeric_returns_str(self):
        exif = _FakeExif({_ISO_TAG: "N/A"})
        with patch("PIL.Image.open", return_value=_make_image(exif)):
            result = image_meta.read_field("dummy.jpg", "ISOSpeedRatings")
        assert isinstance(result, str)


class TestReadExifRationalField:
    def test_fnumber_returns_formatted_string(self):
        exif = _FakeExif({_FNUMBER_TAG: 2.8})
        with patch("PIL.Image.open", return_value=_make_image(exif)):
            result = image_meta.read_field("dummy.jpg", "FNumber")
        assert isinstance(result, str)


class TestReadExifUnknownKey:
    def test_unknown_key_returns_none(self):
        exif = _FakeExif({})
        with patch("PIL.Image.open", return_value=_make_image(exif)):
            result = image_meta.read_field("dummy.jpg", "NonExistentTag")
        assert result is None


# ---------------------------------------------------------------------------
# _parse_exif_datetime
# ---------------------------------------------------------------------------


class TestParseExifDatetime:
    def test_malformed_string_returns_none(self):
        assert image_meta._parse_exif_datetime("not-a-date") is None

    def test_none_input_returns_none(self):
        assert image_meta._parse_exif_datetime(None) is None


# ---------------------------------------------------------------------------
# _read_iptc (mocked)
# ---------------------------------------------------------------------------


def _make_iptc_image(iptc_data: dict | None):
    img = MagicMock()
    img.__enter__ = lambda s: s
    img.__exit__ = MagicMock(return_value=False)
    return img, iptc_data


class TestReadIptc:
    def _call(self, key: str, iptc_data: dict | None) -> object:
        img = MagicMock()
        img.__enter__ = lambda s: s
        img.__exit__ = MagicMock(return_value=False)
        with patch("PIL.Image.open", return_value=img):
            with patch("PIL.IptcImagePlugin.getiptcinfo", return_value=iptc_data):
                return image_meta.read_field("dummy.jpg", key)

    def test_caption_returns_string(self):
        result = self._call("caption", {(2, 120): b"A caption"})
        assert result == "A caption"

    def test_keywords_list_joined_with_semicolon(self):
        result = self._call("keywords", {(2, 25): [b"nature", b"landscape"]})
        assert result == "nature; landscape"

    def test_datecreated_returns_date(self):
        import datetime

        result = self._call("datecreated", {(2, 55): b"20211120"})
        assert result == datetime.date(2021, 11, 20)

    def test_datecreated_invalid_falls_back_to_string(self):
        result = self._call("datecreated", {(2, 55): b"not-a-date"})
        assert isinstance(result, str)

    def test_absent_dataset_returns_none(self):
        result = self._call("caption", {(2, 80): b"something_else"})
        assert result is None

    def test_no_iptc_data_returns_none(self):
        result = self._call("caption", None)
        assert result is None

    def test_iptc_exception_returns_none(self):
        img = MagicMock()
        img.__enter__ = lambda s: s
        img.__exit__ = MagicMock(return_value=False)
        with patch("PIL.Image.open", return_value=img):
            with patch(
                "PIL.IptcImagePlugin.getiptcinfo",
                side_effect=Exception("corrupt IPTC"),
            ):
                result = image_meta.read_field("dummy.jpg", "caption")
        assert result is None

    def test_non_iptc_key_goes_to_exif(self):
        exif = _FakeExif({_MAKE_TAG: "Nikon"})
        with patch("PIL.Image.open", return_value=_make_image(exif)):
            result = image_meta.read_field("dummy.jpg", "Make")
        assert result == "Nikon"

    def test_unknown_iptc_key_returns_none_without_opening_file(self):
        # Key not in _IPTC_DATASETS → early return before any file I/O
        result = image_meta._read_iptc("dummy.jpg", "not_an_iptc_key")
        assert result is None


# ---------------------------------------------------------------------------
# can_read
# ---------------------------------------------------------------------------


class TestCanRead:
    def test_returns_false_when_pillow_unavailable(self, monkeypatch):
        monkeypatch.setattr(image_meta, "_PILLOW", False)
        assert image_meta.can_read("dummy.jpg") is False

    def test_returns_true_for_valid_image(self, tmp_path):
        f = tmp_path / "img.jpg"
        f.touch()
        img_mock = MagicMock()
        img_mock.__enter__ = lambda s: s
        img_mock.__exit__ = MagicMock(return_value=False)
        with patch("PIL.Image.open", return_value=img_mock):
            assert image_meta.can_read(str(f)) is True

    def test_returns_false_for_unidentified_image(self, tmp_path):
        from PIL import UnidentifiedImageError

        f = tmp_path / "not_an_image.txt"
        f.write_text("not an image")
        with patch("PIL.Image.open", side_effect=UnidentifiedImageError):
            assert image_meta.can_read(str(f)) is False

    def test_returns_false_on_os_error(self, tmp_path):
        f = tmp_path / "missing.jpg"
        with patch("PIL.Image.open", side_effect=OSError("no such file")):
            assert image_meta.can_read(str(f)) is False

    def test_returns_false_on_generic_exception(self, tmp_path):
        f = tmp_path / "broken.jpg"
        f.touch()
        with patch("PIL.Image.open", side_effect=Exception("unexpected")):
            assert image_meta.can_read(str(f)) is False


# ---------------------------------------------------------------------------
# field_type
# ---------------------------------------------------------------------------


class TestFieldType:
    def test_known_datetime_field(self):
        from pbrenamer.core.meta_common import FieldType

        assert image_meta.field_type("DateTimeOriginal") == FieldType.DATETIME

    def test_known_integer_field(self):
        from pbrenamer.core.meta_common import FieldType

        assert image_meta.field_type("ISOSpeedRatings") == FieldType.INTEGER

    def test_unknown_field_defaults_to_string(self):
        from pbrenamer.core.meta_common import FieldType

        assert image_meta.field_type("totally_unknown") == FieldType.STRING

    def test_case_insensitive(self):
        assert image_meta.field_type("datetimeoriginal") == image_meta.field_type(
            "DateTimeOriginal"
        )
