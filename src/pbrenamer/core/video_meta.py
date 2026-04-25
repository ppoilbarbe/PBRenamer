"""Video metadata reading via pymediainfo."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from pbrenamer.core.meta_common import FieldInfo, FieldType

_log = logging.getLogger(__name__)

try:
    from pymediainfo import MediaInfo

    _MEDIAINFO = True
except ImportError:
    MediaInfo = None  # type: ignore[assignment,misc]
    _MEDIAINFO = False
    _log.debug(
        "pymediainfo not available — {vi:…} metadata fields will always be empty"
    )


FIELD_REGISTRY: dict[str, FieldInfo] = {
    "duration": FieldInfo("Duration in seconds", FieldType.INTEGER),
    "bitrate": FieldInfo("Overall bitrate in kbps", FieldType.INTEGER),
    "width": FieldInfo("Video width in pixels", FieldType.INTEGER),
    "height": FieldInfo("Video height in pixels", FieldType.INTEGER),
    "framerate": FieldInfo("Frame rate (e.g. 29.970)", FieldType.STRING),
    "videocodec": FieldInfo("Video codec name (e.g. AVC, HEVC)", FieldType.STRING),
    "audiocodec": FieldInfo("Audio codec name (e.g. AAC)", FieldType.STRING),
    "audiochannels": FieldInfo("Number of audio channels", FieldType.INTEGER),
    "title": FieldInfo("Title tag", FieldType.STRING),
    "encodeddate": FieldInfo("Encoded date/time", FieldType.DATETIME),
}


def _parse_encoded_date(raw: str) -> datetime.datetime | None:
    s = raw.strip()
    if s.upper().startswith("UTC "):
        s = s[4:]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s[:19], fmt)
        except ValueError:
            pass
    return None


def _get_track(tracks: list, track_type: str):
    for t in tracks:
        if t.track_type == track_type:
            return t
    return None


def _str_attr(track, attr: str) -> str | None:
    v = getattr(track, attr, None)
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _int_attr(track, attr: str) -> int | None:
    v = getattr(track, attr, None)
    if v is None:
        return None
    try:
        return int(float(str(v)))
    except (ValueError, TypeError):
        return None


def read_field(path: str, field: str) -> Any | None:
    """Return the value of a video metadata field for *path*, or None if unavailable.

    *field* is case-insensitive. The returned type depends on the field:
    - DATETIME fields → datetime.datetime
    - INTEGER fields → int
    - STRING fields → str

    Returns None if pymediainfo is unavailable, the file is not a supported video
    format, or the field is absent.
    """
    if not _MEDIAINFO:
        return None
    key = field.lower()
    _log.debug("Reading video field %r from %s", key, path)
    try:
        info = MediaInfo.parse(path)
    except Exception as exc:  # noqa: BLE001
        _log.debug("MediaInfo.parse() failed for %s: %s", path, exc)
        return None

    tracks = info.tracks
    general = _get_track(tracks, "General")

    if key == "duration":
        if general is None:
            return None
        ms = getattr(general, "duration", None)
        if ms is None:
            return None
        try:
            return int(round(float(ms) / 1000))
        except (ValueError, TypeError):
            return None

    if key == "bitrate":
        if general is None:
            return None
        br = getattr(general, "overall_bit_rate", None)
        if br is None:
            return None
        try:
            return int(round(float(br) / 1000))
        except (ValueError, TypeError):
            return None

    if key == "title":
        return _str_attr(general, "title") if general is not None else None

    if key == "encodeddate":
        if general is None:
            return None
        raw = getattr(general, "encoded_date", None) or getattr(
            general, "tagged_date", None
        )
        return _parse_encoded_date(str(raw)) if raw is not None else None

    video = _get_track(tracks, "Video")

    if key == "width":
        return _int_attr(video, "width") if video is not None else None

    if key == "height":
        return _int_attr(video, "height") if video is not None else None

    if key == "framerate":
        return _str_attr(video, "frame_rate") if video is not None else None

    if key == "videocodec":
        return _str_attr(video, "format") if video is not None else None

    audio = _get_track(tracks, "Audio")

    if key == "audiocodec":
        return _str_attr(audio, "format") if audio is not None else None

    if key == "audiochannels":
        return _int_attr(audio, "channel_s") if audio is not None else None

    return None
