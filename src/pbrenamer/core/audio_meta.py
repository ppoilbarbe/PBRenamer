"""Audio metadata reading via mutagen."""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

_log = logging.getLogger(__name__)

try:
    import mutagen

    _MUTAGEN = True
except ImportError:
    _MUTAGEN = False
    _log.debug("mutagen not available — {au:…} metadata fields will always be empty")


class FieldType(Enum):
    DATE = "date"
    STRING = "string"
    INTEGER = "integer"


@dataclass(frozen=True)
class FieldInfo:
    description: str
    type: FieldType


FIELD_REGISTRY: dict[str, FieldInfo] = {
    "title": FieldInfo("Track title", FieldType.STRING),
    "artist": FieldInfo("Track artist", FieldType.STRING),
    "albumartist": FieldInfo("Album artist", FieldType.STRING),
    "album": FieldInfo("Album name", FieldType.STRING),
    "tracknumber": FieldInfo("Track number", FieldType.INTEGER),
    "discnumber": FieldInfo("Disc number", FieldType.INTEGER),
    "date": FieldInfo("Release date (YYYY-MM-DD or YYYY)", FieldType.DATE),
    "year": FieldInfo("Release year (extracted from date tag)", FieldType.INTEGER),
    "genre": FieldInfo("Genre", FieldType.STRING),
    "comment": FieldInfo("Comment", FieldType.STRING),
    "composer": FieldInfo("Composer", FieldType.STRING),
    "bpm": FieldInfo("Beats per minute", FieldType.INTEGER),
    "duration": FieldInfo("Duration in seconds", FieldType.INTEGER),
    "bitrate": FieldInfo("Bitrate in kbps", FieldType.INTEGER),
}

# Fields read from mutagen file info (not from tags)
_INFO_FIELDS = frozenset({"duration", "bitrate"})


def _parse_track_int(raw: str) -> int | None:
    """Parse "5" or "5/12" → 5."""
    part = raw.split("/")[0].strip()
    try:
        return int(part)
    except ValueError:
        return None


def _parse_date(raw: str) -> datetime.date | str:
    """Parse YYYY-MM-DD (or variants); return the raw string if unparseable."""
    s = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    return s


def _read_info_field(path: str, key: str) -> int | None:
    """Read duration or bitrate from mutagen file info."""
    try:
        f = mutagen.File(path)
    except Exception as exc:  # noqa: BLE001
        _log.debug("mutagen.File() failed for %s: %s", path, exc)
        return None
    if f is None:
        _log.debug("Unsupported audio format: %s", path)
        return None
    info = getattr(f, "info", None)
    if info is None:
        return None
    if key == "duration":
        length = getattr(info, "length", None)
        return int(round(length)) if length is not None else None
    if key == "bitrate":
        br = getattr(info, "bitrate", None)
        return int(round(br / 1000)) if br is not None else None
    return None


def _read_easy_field(path: str, key: str) -> Any | None:
    """Read a field from mutagen easy tags (format-agnostic)."""
    try:
        f = mutagen.File(path, easy=True)
    except Exception as exc:  # noqa: BLE001
        _log.debug("mutagen easy open failed for %s: %s", path, exc)
        return None
    if f is None:
        _log.debug("Unsupported audio format: %s", path)
        return None

    if key == "year":
        raw_list = f.get("date")
        if not raw_list:
            return None
        try:
            return int(str(raw_list[0]).strip()[:4])
        except (ValueError, IndexError):
            return None

    raw_list = f.get(key)
    if not raw_list:
        return None
    raw = str(raw_list[0])

    info = FIELD_REGISTRY.get(key)
    if info and info.type == FieldType.INTEGER:
        return _parse_track_int(raw)
    if info and info.type == FieldType.DATE:
        return _parse_date(raw)
    return raw.strip() or None


def read_field(path: str, field: str) -> Any | None:
    """Return the value of an audio metadata field for *path*, or None if unavailable.

    *field* is case-insensitive. The returned type depends on the field:
    - DATE fields → datetime.date (when full date available) or str (year-only)
    - INTEGER fields → int
    - STRING fields → str

    Returns None if mutagen is unavailable, the file is not a supported audio
    format, or the field is absent.
    """
    if not _MUTAGEN:
        return None
    key = field.lower()
    _log.debug("Reading audio field %r from %s", key, path)
    if key in _INFO_FIELDS:
        return _read_info_field(path, key)
    return _read_easy_field(path, key)
