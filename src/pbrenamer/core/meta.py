"""EXIF and IPTC metadata reading via Pillow."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Any

try:
    from PIL import Image, IptcImagePlugin
    from PIL.ExifTags import TAGS as _EXIF_TAGS

    _PILLOW = True
except ImportError:
    _PILLOW = False


class FieldType(Enum):
    DATETIME = "datetime"
    DATE = "date"
    STRING = "string"
    INTEGER = "integer"
    RATIONAL = "rational"


@dataclass(frozen=True)
class FieldInfo:
    description: str
    type: FieldType


# Normalised (lowercase) name → FieldInfo for all known useful fields.
# Unknown field names are read as STRING with no type-specific formatting.
FIELD_REGISTRY: dict[str, FieldInfo] = {
    # EXIF — timestamps
    "datetimeoriginal": FieldInfo("Date/time the photo was taken", FieldType.DATETIME),
    "datetimedigitized": FieldInfo(
        "Date/time the image was digitised", FieldType.DATETIME
    ),
    "datetime": FieldInfo("File last-modified date/time (EXIF)", FieldType.DATETIME),
    # EXIF — camera
    "make": FieldInfo("Camera manufacturer", FieldType.STRING),
    "model": FieldInfo("Camera model", FieldType.STRING),
    "lensmodel": FieldInfo("Lens model", FieldType.STRING),
    "isospeedratings": FieldInfo("ISO speed rating", FieldType.INTEGER),
    "fnumber": FieldInfo("Aperture (f/number)", FieldType.RATIONAL),
    "exposuretime": FieldInfo("Exposure time (e.g. 1/125)", FieldType.RATIONAL),
    "focallength": FieldInfo("Focal length in mm", FieldType.RATIONAL),
    # IPTC
    "objectname": FieldInfo("IPTC title / object name", FieldType.STRING),
    "caption": FieldInfo("IPTC caption / description", FieldType.STRING),
    "by-line": FieldInfo("IPTC photographer / creator", FieldType.STRING),
    "city": FieldInfo("IPTC city", FieldType.STRING),
    "country": FieldInfo("IPTC country", FieldType.STRING),
    "datecreated": FieldInfo("IPTC creation date", FieldType.DATE),
    "keywords": FieldInfo("IPTC keywords (semicolon-separated)", FieldType.STRING),
    "credit": FieldInfo("IPTC credit line", FieldType.STRING),
    "source": FieldInfo("IPTC source", FieldType.STRING),
}

# IPTC (record, dataset) → normalised field name
_IPTC_DATASETS: dict[tuple[int, int], str] = {
    (2, 5): "objectname",
    (2, 25): "keywords",
    (2, 55): "datecreated",
    (2, 80): "by-line",
    (2, 90): "city",
    (2, 101): "country",
    (2, 110): "credit",
    (2, 115): "source",
    (2, 120): "caption",
}

_IPTC_KEYS: frozenset[str] = frozenset(_IPTC_DATASETS.values())

# Reverse mapping: lowercase EXIF tag name → tag ID (built once at import time)
_EXIF_TAG_IDS: dict[str, int] = (
    {v.lower(): k for k, v in _EXIF_TAGS.items()} if _PILLOW else {}
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_exif_datetime(value: Any) -> datetime.datetime | None:
    try:
        return datetime.datetime.strptime(str(value).strip(), "%Y:%m:%d %H:%M:%S")
    except (ValueError, AttributeError):
        return None


def _rational_to_str(value: Any) -> str:
    try:
        f = float(value)
    except (TypeError, ZeroDivisionError):
        return str(value)
    if f == int(f):
        return str(int(f))
    if 0 < f < 1:
        denom = round(1 / f)
        return f"1/{denom}"
    return f"{f:.2f}".rstrip("0").rstrip(".")


def _decode_bytes(raw: Any) -> str:
    if isinstance(raw, bytes | bytearray):
        return raw.decode("utf-8", errors="replace").rstrip("\x00")
    return str(raw)


def _read_exif(path: str, key: str) -> Any | None:
    tag_id = _EXIF_TAG_IDS.get(key)
    if tag_id is None:
        return None
    try:
        with Image.open(path) as img:
            exif = img.getexif()
        raw = exif.get(tag_id)
    except Exception:  # noqa: BLE001
        return None
    if raw is None:
        return None

    info = FIELD_REGISTRY.get(key)
    field_type = info.type if info else FieldType.STRING

    if field_type == FieldType.DATETIME:
        return _parse_exif_datetime(raw)
    if field_type == FieldType.INTEGER:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return str(raw)
    if field_type == FieldType.RATIONAL:
        return _rational_to_str(raw)
    return str(raw)


def _read_iptc(path: str, key: str) -> Any | None:
    dataset = next((ds for ds, name in _IPTC_DATASETS.items() if name == key), None)
    if dataset is None:
        return None
    try:
        with Image.open(path) as img:
            iptc = IptcImagePlugin.getiptcinfo(img)
    except Exception:  # noqa: BLE001
        return None
    if not iptc:
        return None

    raw = iptc.get(dataset)
    if raw is None:
        return None

    if isinstance(raw, list):
        text = "; ".join(_decode_bytes(v) for v in raw)
    else:
        text = _decode_bytes(raw)

    info = FIELD_REGISTRY.get(key)
    if info and info.type == FieldType.DATE and len(text) >= 8:
        try:
            return datetime.date(int(text[:4]), int(text[4:6]), int(text[6:8]))
        except ValueError:
            pass
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def field_type(field: str) -> FieldType:
    """Return the FieldType for *field* (case-insensitive); STRING if unknown."""
    return FIELD_REGISTRY.get(field.lower(), FieldInfo("", FieldType.STRING)).type


def read_field(path: str, field: str) -> Any | None:
    """Return the value of a metadata field for *path*, or None if unavailable.

    *field* is case-insensitive. The returned type depends on the field:
    - DATETIME fields → datetime.datetime
    - DATE fields → datetime.date
    - INTEGER fields → int
    - RATIONAL fields → str (formatted fraction, e.g. "1/125" or "2.8")
    - STRING / unknown fields → str

    Returns None if Pillow is unavailable, the file is not a supported image,
    or the field is absent.
    """
    if not _PILLOW:
        return None
    key = field.lower()
    if key in _IPTC_KEYS:
        return _read_iptc(path, key)
    return _read_exif(path, key)
