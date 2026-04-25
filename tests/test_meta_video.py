"""Tests for video metadata reading (video_meta module)."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pbrenamer.core import video_meta
from pbrenamer.core.meta_common import FieldType
from pbrenamer.core.video_meta import read_field

# Real MP4 generated with ffmpeg (320x240, AVC+AAC, 2 s, ultrafast/crf40).
# Fields present: width, height, duration, framerate, videocodec, audiocodec,
#                 audiochannels, bitrate, title, encodeddate.
SAMPLE_VIDEO = Path(__file__).parent / "data" / "sample_video.mp4"

# Expected values derived from pymediainfo on the generated file.
_EXPECTED_ENCODED_DATE = datetime.datetime(2024, 6, 15, 8, 30, 0)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_track(track_type: str, **attrs):
    t = MagicMock()
    t.track_type = track_type
    for k, v in attrs.items():
        setattr(t, k, v)
    return t


def _make_mediainfo(*tracks):
    mi = MagicMock()
    mi.tracks = list(tracks)
    return mi


def _read(field: str, *, general=None, video=None, audio=None) -> object:
    """Call read_field with a mocked MediaInfo.parse() result."""
    tracks = []
    if general is not None:
        tracks.append(_make_track("General", **general))
    if video is not None:
        tracks.append(_make_track("Video", **video))
    if audio is not None:
        tracks.append(_make_track("Audio", **audio))
    mi = _make_mediainfo(*tracks)
    with patch("pbrenamer.core.video_meta.MediaInfo") as mock_cls:
        mock_cls.parse.return_value = mi
        with patch.object(video_meta, "_MEDIAINFO", True):
            return read_field("/fake/video.mp4", field)


# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------


class TestFieldRegistry:
    def test_known_fields_present(self):
        for key in ("duration", "width", "height", "videocodec", "framerate"):
            assert key in video_meta.FIELD_REGISTRY

    def test_duration_is_integer(self):
        assert video_meta.FIELD_REGISTRY["duration"].type == FieldType.INTEGER

    def test_videocodec_is_string(self):
        assert video_meta.FIELD_REGISTRY["videocodec"].type == FieldType.STRING

    def test_encodeddate_is_datetime(self):
        assert video_meta.FIELD_REGISTRY["encodeddate"].type == FieldType.DATETIME


# ---------------------------------------------------------------------------
# _parse_encoded_date
# ---------------------------------------------------------------------------


class TestParseEncodedDate:
    def test_utc_prefix(self):
        result = video_meta._parse_encoded_date("UTC 2023-07-14 10:30:00")
        assert result == datetime.datetime(2023, 7, 14, 10, 30, 0)

    def test_no_prefix(self):
        result = video_meta._parse_encoded_date("2023-07-14 10:30:00")
        assert result == datetime.datetime(2023, 7, 14, 10, 30, 0)

    def test_iso_t_separator(self):
        result = video_meta._parse_encoded_date("2023-07-14T10:30:00")
        assert result == datetime.datetime(2023, 7, 14, 10, 30, 0)

    def test_date_only(self):
        result = video_meta._parse_encoded_date("2023-07-14")
        assert result == datetime.datetime(2023, 7, 14, 0, 0, 0)

    def test_garbage_returns_none(self):
        result = video_meta._parse_encoded_date("not a date")
        assert result is None


# ---------------------------------------------------------------------------
# _get_track
# ---------------------------------------------------------------------------


class TestGetTrack:
    def test_returns_first_matching(self):
        g = _make_track("General")
        v = _make_track("Video")
        assert video_meta._get_track([g, v], "Video") is v

    def test_returns_none_when_absent(self):
        g = _make_track("General")
        assert video_meta._get_track([g], "Video") is None


# ---------------------------------------------------------------------------
# read_field — library unavailable
# ---------------------------------------------------------------------------


class TestReadFieldNoLibrary:
    def test_returns_none_when_no_mediainfo(self):
        with patch.object(video_meta, "_MEDIAINFO", False):
            assert read_field("/any/file.mp4", "width") is None


# ---------------------------------------------------------------------------
# read_field — General track fields
# ---------------------------------------------------------------------------


class TestDuration:
    def test_milliseconds_converted_to_seconds(self):
        assert _read("duration", general={"duration": 125_400}) == 125

    def test_fractional_rounded(self):
        assert _read("duration", general={"duration": 1500}) == 2

    def test_none_when_absent(self):
        assert _read("duration", general={"duration": None}) is None

    def test_none_when_no_general_track(self):
        assert _read("duration") is None

    def test_case_insensitive(self):
        assert _read("DURATION", general={"duration": 60_000}) == 60


class TestBitrate:
    def test_bits_per_second_to_kbps(self):
        assert _read("bitrate", general={"overall_bit_rate": 4_000_000}) == 4000

    def test_none_when_absent(self):
        assert _read("bitrate", general={"overall_bit_rate": None}) is None


class TestTitle:
    def test_returns_title(self):
        assert _read("title", general={"title": "My Movie"}) == "My Movie"

    def test_strips_whitespace(self):
        assert _read("title", general={"title": "  Clip  "}) == "Clip"

    def test_none_when_empty(self):
        assert _read("title", general={"title": ""}) is None

    def test_none_when_absent(self):
        assert _read("title", general={"title": None}) is None


class TestEncodedDate:
    def test_parses_utc_date(self):
        result = _read(
            "encodeddate", general={"encoded_date": "UTC 2022-03-15 08:00:00"}
        )
        assert result == datetime.datetime(2022, 3, 15, 8, 0, 0)

    def test_none_when_absent(self):
        result = _read(
            "encodeddate",
            general={"encoded_date": None, "tagged_date": None},
        )
        assert result is None


# ---------------------------------------------------------------------------
# read_field — Video track fields
# ---------------------------------------------------------------------------


class TestWidth:
    def test_returns_int(self):
        assert _read("width", video={"width": 1920}) == 1920

    def test_none_when_no_video_track(self):
        assert _read("width", general={"duration": 1000}) is None


class TestHeight:
    def test_returns_int(self):
        assert _read("height", video={"height": 1080}) == 1080


class TestFramerate:
    def test_returns_string(self):
        assert _read("framerate", video={"frame_rate": "29.970"}) == "29.970"

    def test_none_when_empty(self):
        assert _read("framerate", video={"frame_rate": ""}) is None


class TestVideoCodec:
    def test_returns_format(self):
        assert _read("videocodec", video={"format": "AVC"}) == "AVC"

    def test_none_when_no_video_track(self):
        assert _read("videocodec") is None


# ---------------------------------------------------------------------------
# read_field — Audio track fields
# ---------------------------------------------------------------------------


class TestAudioCodec:
    def test_returns_format(self):
        assert _read("audiocodec", audio={"format": "AAC"}) == "AAC"

    def test_none_when_no_audio_track(self):
        assert _read("audiocodec") is None


class TestAudioChannels:
    def test_returns_int(self):
        assert _read("audiochannels", audio={"channel_s": 2}) == 2

    def test_none_when_absent(self):
        assert _read("audiochannels", audio={"channel_s": None}) is None


# ---------------------------------------------------------------------------
# read_field — unknown field
# ---------------------------------------------------------------------------


class TestUnknownField:
    def test_unknown_field_returns_none(self):
        assert _read("nonexistent", general={"duration": 1000}) is None


# ---------------------------------------------------------------------------
# read_field — parse failure
# ---------------------------------------------------------------------------


class TestParseFailure:
    def test_exception_returns_none(self):
        with patch("pbrenamer.core.video_meta.MediaInfo") as mock_cls:
            mock_cls.parse.side_effect = Exception("read error")
            with patch.object(video_meta, "_MEDIAINFO", True):
                assert read_field("/bad/file.mp4", "width") is None


# ---------------------------------------------------------------------------
# Integration tests (real MP4 file)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SAMPLE_VIDEO.exists(), reason="sample_video.mp4 not found")
class TestRealFile:
    path = str(SAMPLE_VIDEO)

    def test_width(self):
        assert read_field(self.path, "width") == 320

    def test_height(self):
        assert read_field(self.path, "height") == 240

    def test_duration(self):
        assert read_field(self.path, "duration") == 2

    def test_framerate(self):
        assert read_field(self.path, "framerate") == "25.000"

    def test_videocodec(self):
        assert read_field(self.path, "videocodec") == "AVC"

    def test_audiocodec(self):
        assert read_field(self.path, "audiocodec") == "AAC"

    def test_audiochannels(self):
        assert read_field(self.path, "audiochannels") == 1

    def test_bitrate(self):
        assert read_field(self.path, "bitrate") == 111

    def test_title(self):
        assert read_field(self.path, "title") == "PBRenamer test clip"

    def test_encodeddate(self):
        assert read_field(self.path, "encodeddate") == _EXPECTED_ENCODED_DATE

    def test_case_insensitive(self):
        assert read_field(self.path, "WIDTH") == read_field(self.path, "width")
