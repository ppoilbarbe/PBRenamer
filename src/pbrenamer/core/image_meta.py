"""EXIF and IPTC metadata reading via Pillow."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from pbrenamer.core.meta_common import FieldInfo, FieldType

_log = logging.getLogger(__name__)

try:
    from PIL import Image, IptcImagePlugin
    from PIL.ExifTags import TAGS as _EXIF_TAGS

    _PILLOW = True
except ImportError:
    _PILLOW = False
    _log.debug("Pillow not available — {im:…} metadata fields will always be empty")


# Normalised (lowercase) name → FieldInfo for all known useful fields.
# Unknown field names are read as STRING with no type-specific formatting.
FIELD_REGISTRY: dict[str, FieldInfo] = {
    # EXIF — timestamps
    "datetimeoriginal": FieldInfo("Date/time the photo was taken", FieldType.DATETIME),
    "datetimedigitized": FieldInfo(
        "Date/time the image was digitised", FieldType.DATETIME
    ),
    "datetime": FieldInfo("File last-modified date/time (EXIF)", FieldType.DATETIME),
    # EXIF — image-level text
    "imagedescription": FieldInfo("Image description / title", FieldType.STRING),
    "artist": FieldInfo("Photographer / creator (EXIF)", FieldType.STRING),
    "copyright": FieldInfo("Copyright notice", FieldType.STRING),
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


def _fix_str_encoding(s: str) -> str:
    """Recover UTF-8 strings mis-decoded as latin-1 by Pillow.

    EXIF tags are declared ASCII but many tools write UTF-8 bytes.
    Pillow decodes them as latin-1, producing mojibake for non-ASCII
    characters.  Re-encoding as latin-1 and decoding as UTF-8 restores
    the original text; if the bytes are not valid UTF-8 we keep the
    latin-1 string as-is.
    """
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


_EXIF_IFD_POINTERS = (0x8769, 0x8825)  # ExifIFD, GPS IFD


def _read_exif(path: str, key: str) -> Any | None:
    tag_id = _EXIF_TAG_IDS.get(key)
    if tag_id is None:
        _log.debug("Unknown EXIF key %r — skipping %s", key, path)
        return None
    _log.debug("Reading EXIF %r (tag %d) from %s", key, tag_id, path)
    try:
        with Image.open(path) as img:
            exif = img.getexif()
        raw = exif.get(tag_id)
        if raw is None:
            for ptr in _EXIF_IFD_POINTERS:
                raw = exif.get_ifd(ptr).get(tag_id)
                if raw is not None:
                    break
    except Exception as exc:  # noqa: BLE001
        _log.debug("EXIF open failed for %s: %s", path, exc)
        return None
    if raw is None:
        _log.debug("EXIF tag %r absent in %s", key, path)
        return None

    info = FIELD_REGISTRY.get(key)
    field_type = info.type if info else FieldType.STRING

    if field_type == FieldType.DATETIME:
        result = _parse_exif_datetime(raw)
        _log.debug("EXIF %r → %r (datetime)", key, result)
        return result
    if field_type == FieldType.INTEGER:
        try:
            result = int(raw)
        except (TypeError, ValueError):
            result = str(raw)
        _log.debug("EXIF %r → %r (int)", key, result)
        return result
    if field_type == FieldType.RATIONAL:
        result = _rational_to_str(raw)
        _log.debug("EXIF %r → %r (rational)", key, result)
        return result
    result = _fix_str_encoding(str(raw))
    _log.debug("EXIF %r → %r (str)", key, result)
    return result


def _read_iptc(path: str, key: str) -> Any | None:
    dataset = next((ds for ds, name in _IPTC_DATASETS.items() if name == key), None)
    if dataset is None:
        return None
    _log.debug("Reading IPTC %r (dataset %s) from %s", key, dataset, path)
    try:
        with Image.open(path) as img:
            iptc = IptcImagePlugin.getiptcinfo(img)
    except Exception as exc:  # noqa: BLE001
        _log.debug("IPTC open failed for %s: %s", path, exc)
        return None
    if not iptc:
        _log.debug("No IPTC data in %s", path)
        return None

    raw = iptc.get(dataset)
    if raw is None:
        _log.debug("IPTC dataset %s absent in %s", dataset, path)
        return None

    if isinstance(raw, list):
        text = "; ".join(_decode_bytes(v) for v in raw)
    else:
        text = _decode_bytes(raw)

    info = FIELD_REGISTRY.get(key)
    if info and info.type == FieldType.DATE and len(text) >= 8:
        try:
            result: Any = datetime.date(int(text[:4]), int(text[4:6]), int(text[6:8]))
            _log.debug("IPTC %r → %r (date)", key, result)
            return result
        except ValueError:
            pass
    _log.debug("IPTC %r → %r", key, text)
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
