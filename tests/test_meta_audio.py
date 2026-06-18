"""Tests for audio metadata reading (audio_meta module)."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pbrenamer.core import audio_meta  # noqa: F401 (used in patch.object)
from pbrenamer.core.audio_meta import read_field
from pbrenamer.core.meta_common import FieldType

# Real OGG with known tags (Georges Brassens — La Cane de Jeanne, 1991).
# Fields present: title, artist, album, albumartist, tracknumber, discnumber,
#                 date, genre, duration, bitrate.
SAMPLE_AUDIO = Path(__file__).parent / "data" / "sample_audio.ogg"
SAMPLE_VIDEO = Path(__file__).parent / "data" / "sample_video.mp4"

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


# ---------------------------------------------------------------------------
# Integration tests (real OGG file)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SAMPLE_AUDIO.exists(), reason="sample_audio.ogg not found")
class TestRealFile:
    path = str(SAMPLE_AUDIO)

    def test_title(self):
        assert read_field(self.path, "title") == "La Cane de Jeanne"

    def test_artist(self):
        assert read_field(self.path, "artist") == "Georges Brassens"

    def test_album(self):
        assert read_field(self.path, "album") == (
            "Intégrale 1991, Volume 01: La Mauvaise Réputation"
        )

    def test_albumartist(self):
        assert read_field(self.path, "albumartist") == "Georges Brassens"

    def test_tracknumber(self):
        assert read_field(self.path, "tracknumber") == 12

    def test_discnumber(self):
        assert read_field(self.path, "discnumber") == 1

    def test_date_year_only(self):
        assert read_field(self.path, "date") == "1991"

    def test_year(self):
        assert read_field(self.path, "year") == 1991

    def test_genre(self):
        assert read_field(self.path, "genre") == "Chanson"

    def test_duration(self):
        assert read_field(self.path, "duration") == 3

    def test_bitrate(self):
        assert read_field(self.path, "bitrate") == 160

    def test_case_insensitive(self):
        assert read_field(self.path, "TITLE") == read_field(self.path, "title")


# ---------------------------------------------------------------------------
# Regression: video containers must not be treated as audio
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SAMPLE_VIDEO.exists(), reason="sample_video.mp4 not found")
class TestVideoRejected:
    path = str(SAMPLE_VIDEO)

    def test_can_read_returns_false(self):
        assert audio_meta.can_read(self.path) is False

    def test_read_field_returns_none(self):
        # Mutagen can read MP4 tags; read_field must still return None for video files.
        assert read_field(self.path, "title") is None

    def test_read_field_duration_returns_none(self):
        assert read_field(self.path, "duration") is None


# ---------------------------------------------------------------------------
# _read_info_field edge cases
# ---------------------------------------------------------------------------


class TestReadInfoFieldEdgeCases:
    def test_info_attribute_is_none_returns_none(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        mock_file = MagicMock()
        mock_file.info = None
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "duration") is None

    def test_unknown_info_key_returns_none(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        mock_file = _make_raw_file()
        with patch("mutagen.File", return_value=mock_file):
            # Call internal helper directly with a key outside _INFO_FIELDS
            result = audio_meta._read_info_field(str(f), "unknown_key")
        assert result is None


# ---------------------------------------------------------------------------
# _read_easy_field year edge cases
# ---------------------------------------------------------------------------


class TestReadEasyFieldYearEdgeCases:
    def test_year_field_no_date_tag_returns_none(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        mock_file = _make_easy_file({})
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "year") is None

    def test_year_field_non_numeric_value_returns_none(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        mock_file = _make_easy_file({"date": ["not-a-year"]})
        with patch("mutagen.File", return_value=mock_file):
            assert read_field(str(f), "year") is None


# ---------------------------------------------------------------------------
# can_read
# ---------------------------------------------------------------------------


def _mock_mediainfo(has_video: bool):
    """Return a mock _MediaInfo whose parse() result has or lacks a video track."""
    mock_track = MagicMock()
    mock_track.track_type = "Video" if has_video else "Audio"
    mock_info = MagicMock()
    mock_info.tracks = [mock_track]
    mock_cls = MagicMock()
    mock_cls.parse.return_value = mock_info
    return mock_cls


class TestCanRead:
    def test_returns_false_when_mutagen_unavailable(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        with patch.object(audio_meta, "_MUTAGEN", False):
            assert audio_meta.can_read(str(f)) is False

    def test_returns_true_for_pure_audio_format(self, tmp_path):
        f = tmp_path / "song.ogg"
        f.touch()
        with (
            patch.object(audio_meta, "_MUTAGEN", True),
            patch("mutagen.File", return_value=MagicMock()),
            patch.object(audio_meta, "_MEDIAINFO", True),
            patch.object(audio_meta, "_MediaInfo", _mock_mediainfo(has_video=False)),
        ):
            assert audio_meta.can_read(str(f)) is True

    def test_returns_false_for_video_container(self, tmp_path):
        # MP4 with a video track: mutagen reads it, but it is NOT an audio file.
        f = tmp_path / "clip.mp4"
        f.touch()
        with (
            patch.object(audio_meta, "_MUTAGEN", True),
            patch("mutagen.File", return_value=MagicMock()),
            patch.object(audio_meta, "_MEDIAINFO", True),
            patch.object(audio_meta, "_MediaInfo", _mock_mediainfo(has_video=True)),
        ):
            assert audio_meta.can_read(str(f)) is False

    def test_returns_true_when_mediainfo_unavailable(self, tmp_path):
        # pymediainfo not installed: fall back to mutagen-only probe.
        f = tmp_path / "song.mp3"
        f.touch()
        with (
            patch.object(audio_meta, "_MUTAGEN", True),
            patch("mutagen.File", return_value=MagicMock()),
            patch.object(audio_meta, "_MEDIAINFO", False),
        ):
            assert audio_meta.can_read(str(f)) is True

    def test_returns_true_when_mediainfo_raises(self, tmp_path):
        # pymediainfo present but parse() fails: fall back to mutagen result.
        f = tmp_path / "song.flac"
        f.touch()
        mock_cls = MagicMock()
        mock_cls.parse.side_effect = Exception("parse error")
        with (
            patch.object(audio_meta, "_MUTAGEN", True),
            patch("mutagen.File", return_value=MagicMock()),
            patch.object(audio_meta, "_MEDIAINFO", True),
            patch.object(audio_meta, "_MediaInfo", mock_cls),
        ):
            assert audio_meta.can_read(str(f)) is True

    def test_returns_false_for_unsupported_format(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.touch()
        with patch.object(audio_meta, "_MUTAGEN", True):
            with patch("mutagen.File", return_value=None):
                assert audio_meta.can_read(str(f)) is False

    def test_returns_false_on_exception(self, tmp_path):
        f = tmp_path / "broken.mp3"
        f.touch()
        with patch.object(audio_meta, "_MUTAGEN", True):
            with patch("mutagen.File", side_effect=Exception("corrupt")):
                assert audio_meta.can_read(str(f)) is False
