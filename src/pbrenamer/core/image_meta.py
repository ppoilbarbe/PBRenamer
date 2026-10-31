"""EXIF and IPTC metadata reading via Pillow."""

from __future__ import annotations

import datetime
import logging
import os
from typing import Any

from pbrenamer.core.meta_common import FieldInfo, FieldType

_log = logging.getLogger(__name__)

try:
    from PIL import Image, IptcImagePlugin
    from PIL.ExifTags import TAGS as _EXIF_TAGS

    _PILLOW = True
except ImportError:  # pragma: no cover — required dep; absent only outside project env
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


def can_read(path: str) -> bool:
    """Return True if PIL can open *path* as a recognised image format."""
    if not _PILLOW:
        return False
    from PIL import Image, UnidentifiedImageError  # noqa: PLC0415

    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except (UnidentifiedImageError, OSError):
        return False
    except Exception:  # noqa: BLE001
        return False


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


# ---------------------------------------------------------------------------
# Raw tag listing (ported from PBPicat's metadata.py)
# ---------------------------------------------------------------------------

# (section title, [(tag, value), ...])
MetadataSection = tuple[str, list[tuple[str, str]]]


def _stringify(value: object) -> str:
    if isinstance(value, dict):
        # XMP lang-alt values, e.g. {'lang="x-default"': 'text'}
        return "; ".join(str(v) for v in value.values())
    if isinstance(value, list | tuple):
        return ", ".join(_stringify(v) for v in value)
    if isinstance(value, bytes):
        return _decode_bytes(value)
    return str(value)


def _strip_family(key: str) -> str:
    """Drop the redundant leading family segment (Exif./Iptc./Xmp.)."""
    _family, _sep, rest = key.partition(".")
    return rest or key


def _to_rows(tags: dict, *, strip: bool = True) -> list[tuple[str, str]]:
    return sorted(
        (_strip_family(k) if strip else str(k), _stringify(v)) for k, v in tags.items()
    )


def _read_tags_pyexiv2(path: str) -> tuple[dict, dict, dict] | None:
    """Embedded EXIF/IPTC/XMP via pyexiv2; None if pyexiv2 is unavailable."""
    try:
        import pyexiv2  # noqa: PLC0415
    except ImportError:
        return None
    try:
        img = pyexiv2.Image(str(path))
    except Exception:  # noqa: BLE001
        return {}, {}, {}
    tags = []
    try:
        for reader in (img.read_exif, img.read_iptc, img.read_xmp):
            try:
                tags.append(reader())
            except Exception:  # noqa: BLE001
                tags.append({})
    finally:
        img.close()
    return tags[0], tags[1], tags[2]


def _read_tags_pillow(path: str) -> tuple[dict, dict, dict]:
    """Fallback without pyexiv2: EXIF (with its sub-IFDs) and IPTC."""
    if not _PILLOW:  # pragma: no cover — required dep
        return {}, {}, {}
    exif: dict = {}
    iptc: dict = {}
    try:
        with Image.open(path) as img:
            raw = img.getexif()
            for tag_id, value in raw.items():
                if tag_id not in _EXIF_IFD_POINTERS:
                    exif[_EXIF_TAGS.get(tag_id, str(tag_id))] = value
            for ptr in _EXIF_IFD_POINTERS:
                for tag_id, value in raw.get_ifd(ptr).items():
                    exif[_EXIF_TAGS.get(tag_id, str(tag_id))] = value
            info = IptcImagePlugin.getiptcinfo(img) or {}
            for dataset, value in info.items():
                iptc[_IPTC_DATASETS.get(dataset, f"{dataset[0]}:{dataset[1]}")] = value
    except Exception:  # noqa: BLE001
        _log.debug("Raw metadata read failed for %s", path, exc_info=True)
    return exif, iptc, {}


def read_raw_sections(
    path: str, sidecars: list[str] | tuple[str, ...] = ()
) -> list[MetadataSection]:
    """Return the non-empty (title, rows) sections of *path*: EXIF, IPTC, XMP,
    then the XMP of the first ``.xmp`` file of *sidecars*, if any."""
    tags = _read_tags_pyexiv2(path)
    strip = tags is not None
    exif, iptc, xmp = tags if tags is not None else _read_tags_pillow(path)
    sections: list[MetadataSection] = []
    for title, data in ((_("EXIF"), exif), (_("IPTC"), iptc), (_("XMP"), xmp)):
        if data:
            sections.append((title, _to_rows(data, strip=strip)))

    sidecar = next((s for s in sidecars if s.lower().endswith(".xmp")), None)
    if sidecar is not None and strip:
        _exif, _iptc, sidecar_xmp = _read_tags_pyexiv2(sidecar)
        if sidecar_xmp:
            rows = [(_("Sidecar file"), os.path.basename(sidecar))]
            sections.append((_("XMP (sidecar)"), rows + _to_rows(sidecar_xmp)))
    return sections
