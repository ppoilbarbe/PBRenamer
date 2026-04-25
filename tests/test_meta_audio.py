"""Tests for audio metadata reading (audio_meta module)."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

from pbrenamer.core import audio_meta  # noqa: F401 (used in patch.object)
from pbrenamer.core.audio_meta import FieldType, read_field

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_easy_file(tags: dict, length: float = 180.0, bitrate: int = 192000):
    """Return a mock mutagen easy-tag file object."""
    f = MagicMock()
    f.__getitem__ = lambda self, k: tags[k]
    f.get = lambda k, default=None: tags.get(k, default)
    f.info.length = length
    f.info.bitrate = bitrate
    return f


def _make_raw_file(length: float = 180.0, bitrate: int = 192000):
    """Return a mock mutagen raw file object (for info fields)."""
    f = MagicMock()
    f.info.length = length
    f.info.bitrate = bitrate
    return f


# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------


class TestFieldRegistry:
    def test_known_fields_present(self):
        for key in ("title", "artist", "album", "tracknumber", "date", "duration"):
            assert key in audio_meta.FIELD_REGISTRY

    def test_tracknumber_is_integer(self):
        assert audio_meta.FIELD_REGISTRY["tracknumber"].type == FieldType.INTEGER

    def test_date_is_date(self):
        assert audio_meta.FIELD_REGISTRY["date"].type == FieldType.DATE

    def test_title_is_string(self):
        assert audio_meta.FIELD_REGISTRY["title"].type == FieldType.STRING


# ---------------------------------------------------------------------------
# _parse_track_int
# ---------------------------------------------------------------------------


class TestParseTrackInt:
    def test_simple_number(self):
        assert audio_meta._parse_track_int("5") == 5

    def test_number_with_total(self):
        assert audio_meta._parse_track_int("5/12") == 5

    def test_whitespace(self):
        assert audio_meta._parse_track_int("  3 / 10  ") == 3

    def test_non_numeric_returns_none(self):
        assert audio_meta._parse_track_int("abc") is None


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------


class TestParseDate:
    def test_iso_date(self):
        result = audio_meta._parse_date("2021-11-20")
        assert result == datetime.date(2021, 11, 20)

    def test_slash_date(self):
        result = audio_meta._parse_date("2021/11/20")
        assert result == datetime.date(2021, 11, 20)

    def test_dot_date(self):
        result = audio_meta._parse_date("2021.11.20")
        assert result == datetime.date(2021, 11, 20)

    def test_year_only_returns_string(self):
        result = audio_meta._parse_date("2021")
        assert result == "2021"

    def test_year_month_returns_string(self):
        result = audio_meta._parse_date("2021-11")
        assert result == "2021-11"


# ---------------------------------------------------------------------------
# read_field — mutagen unavailable
# ---------------------------------------------------------------------------


class TestReadFieldNoMutagen:
    def test_returns_none_when_mutagen_unavailable(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        with patch.object(audio_meta, "_MUTAGEN", False):
            assert read_field(str(f), "title") is None


# ---------------------------------------------------------------------------
# read_field — easy tag fields
# ---------------------------------------------------------------------------


class TestReadEasyFields:
    def test_title(self, tmp_path):
        f = tmp_path / "song.ogg"
        f.touch()
        mock_file = _make_easy_file({"title": ["My Song"]})
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "title") == "My Song"

    def test_artist(self, tmp_path):
        f = tmp_path / "song.ogg"
        f.touch()
        mock_file = _make_easy_file({"artist": ["The Artist"]})
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "artist") == "The Artist"

    def test_case_insensitive(self, tmp_path):
        f = tmp_path / "song.ogg"
        f.touch()
        mock_file = _make_easy_file({"title": ["My Song"]})
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "Title") == "My Song"
            assert read_field(str(f), "TITLE") == "My Song"

    def test_tracknumber_simple(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        mock_file = _make_easy_file({"tracknumber": ["5"]})
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "tracknumber") == 5

    def test_tracknumber_with_total(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        mock_file = _make_easy_file({"tracknumber": ["3/12"]})
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "tracknumber") == 3

    def test_discnumber(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        mock_file = _make_easy_file({"discnumber": ["2/3"]})
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "discnumber") == 2

    def test_date_full(self, tmp_path):
        f = tmp_path / "song.flac"
        f.touch()
        mock_file = _make_easy_file({"date": ["2021-11-20"]})
        with patch("mutagen.File", return_value=mock_file):
            result = read_field(str(f), "date")
            assert result == datetime.date(2021, 11, 20)

    def test_date_year_only_returns_string(self, tmp_path):
        f = tmp_path / "song.flac"
        f.touch()
        mock_file = _make_easy_file({"date": ["2021"]})
        with patch("mutagen.File", return_value=mock_file):
            result = read_field(str(f), "date")
            assert result == "2021"

    def test_year_field(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        mock_file = _make_easy_file({"date": ["2021-11-20"]})
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "year") == 2021

    def test_year_from_year_only_date(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        mock_file = _make_easy_file({"date": ["1984"]})
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "year") == 1984

    def test_missing_tag_returns_none(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        mock_file = _make_easy_file({})
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "title") is None

    def test_unsupported_format_returns_none(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.touch()
        with patch("mutagen.File", return_value=None):
            assert read_field(str(f), "title") is None

    def test_mutagen_exception_returns_none(self, tmp_path):
        f = tmp_path / "broken.mp3"
        f.touch()
        with patch("mutagen.File", side_effect=Exception("corrupt")):
            assert read_field(str(f), "title") is None

    def test_empty_string_tag_returns_none(self, tmp_path):
        f = tmp_path / "song.ogg"
        f.touch()
        mock_file = _make_easy_file({"title": [""]})
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "title") is None


# ---------------------------------------------------------------------------
# read_field — info fields (duration, bitrate)
# ---------------------------------------------------------------------------


class TestReadInfoFields:
    def test_duration(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        mock_file = _make_raw_file(length=183.7)
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "duration") == 184

    def test_bitrate(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        mock_file = _make_raw_file(bitrate=192000)
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "bitrate") == 192

    def test_duration_unsupported_format(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.touch()
        with patch("mutagen.File", return_value=None):
            assert read_field(str(f), "duration") is None

    def test_duration_mutagen_exception(self, tmp_path):
        f = tmp_path / "broken.mp3"
        f.touch()
        with patch("mutagen.File", side_effect=Exception("corrupt")):
            assert read_field(str(f), "duration") is None
