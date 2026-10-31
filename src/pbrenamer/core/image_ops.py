"""Lossless image operations (ported from PBPicat): rotation, EXIF orientation,
and the repair of malformed JPEG SOS headers.

JPEG files are rotated by jpegtran (libjpeg-turbo); other formats by Pillow,
saved without loss where the format allows it.  Pillow and pyexiv2 belong to
the optional ``[images]`` extra and are imported lazily.
"""

from __future__ import annotations

import importlib.util
import logging
import shutil
import struct
import subprocess
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

_JPEG_EXTS = frozenset({".jpg", ".jpeg", ".jpe"})
_EXIF_ORIENTATION_TAG = 274

Op = int | str

# EXIF orientation → op descriptor (int = degrees CW, str = flip/transform name)
_ORIENT_TO_OP: dict[int, Op] = {
    2: "hflip",
    3: 180,
    4: "vflip",
    5: "transpose",
    6: 90,
    7: "transverse",
    8: -90,
}

# op descriptor → jpegtran argument(s)
_OP_TO_JPEGTRAN: dict[Op, list[str]] = {
    90: ["-rotate", "90"],
    -90: ["-rotate", "270"],
    180: ["-rotate", "180"],
    "hflip": ["-flip", "horizontal"],
    "vflip": ["-flip", "vertical"],
    "transpose": ["-transpose"],
    "transverse": ["-transverse"],
}

# Inverse op (flip ops are self-inverse)
_OP_INVERSE: dict[Op, Op] = {
    90: -90,
    -90: 90,
    180: 180,
    "hflip": "hflip",
    "vflip": "vflip",
    "transpose": "transpose",
    "transverse": "transverse",
}


def is_jpeg(path: str | Path) -> bool:
    return Path(path).suffix.lower() in _JPEG_EXTS


def pillow_available() -> bool:
    return importlib.util.find_spec("PIL") is not None


def pyexiv2_available() -> bool:
    return importlib.util.find_spec("pyexiv2") is not None


def jpegtran_available() -> bool:
    return _find_jpegtran() is not None


def repair_jpeg_sos(data: bytes) -> bytes:
    """Fix a malformed SOS header found in some camera firmware (e.g. certain
    Samsung front-camera modules): baseline (non-progressive) JPEGs must have
    Se=63 in the SOS segment, but these encoders write Se=0. Strict decoders
    (jpegtran/libjpeg-turbo) reject this with "Invalid SOS parameters for
    sequential JPEG"; lenient decoders (Qt, Pillow) just warn and decode
    anyway. Patching the header byte is lossless: no entropy-coded data is
    touched. Returns the input unchanged if no such defect is found.
    """
    if data[:2] != b"\xff\xd8":
        return data
    baseline = False
    i = 2
    n = len(data)
    while i + 4 <= n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker in (0xC0, 0xC1):
            baseline = True
        elif marker in (0xC2, 0xC3):
            baseline = False
        elif marker == 0xDA:
            if baseline:
                ns = data[i + 4]
                se_offset = i + 6 + 2 * ns
                if se_offset < n and data[se_offset] == 0 and data[se_offset - 1] == 0:
                    patched = bytearray(data)
                    patched[se_offset] = 0x3F
                    return bytes(patched)
            return data
        i += 2 + length
    return data


def get_exif_orientation(path: str | Path) -> int | None:
    """Return the EXIF Orientation value 2–8 if present and non-trivial,
    else None (also without Pillow or on any read error)."""
    try:
        from PIL import Image

        with Image.open(path) as img:
            value = img.getexif().get(_EXIF_ORIENTATION_TAG)
    except Exception:  # noqa: BLE001
        return None
    if value and value != 1:
        return int(value)
    return None


def rotate_lossless(path: str | Path, op: Op) -> Op:
    """Apply a lossless rotation/flip to *path* in place.

    op: 90, -90, 180 (degrees CW), "auto" (apply and clear the EXIF
    orientation), or "hflip" / "vflip" / "transpose" / "transverse" (for the
    undo of flip-type orientations).

    Return the inverse op, for undo.  Raise RuntimeError (user-friendly) if
    jpegtran is unavailable for a JPEG file or fails, ValueError if op is
    "auto" and the file has no usable EXIF orientation.
    """
    path = Path(path)
    if op == "auto":
        orient = get_exif_orientation(path)
        if orient is None:
            raise ValueError(_("No EXIF orientation tag to apply."))
        actual = _ORIENT_TO_OP.get(orient)
        if actual is None:
            raise ValueError(
                _("Unsupported EXIF orientation value: {v}").format(v=orient)
            )
        op = actual
    if is_jpeg(path):
        _jpeg_apply(path, op)
    else:
        _pil_apply(path, op)
    return _OP_INVERSE[op]


# ---------------------------------------------------------------------------
# JPEG path (requires jpegtran from libjpeg-turbo)
# ---------------------------------------------------------------------------


def _jpegtran_error_hints() -> dict[str, str]:
    """Substrings of jpegtran's stderr mapped to a user-friendly explanation,
    shown above the raw technical message.  Files hitting these are genuinely
    defective (missing or malformed data) rather than affected by a fixable
    quirk."""
    return {
        "Premature end of JPEG file": _(
            "This file appears to be truncated (data is missing at the end), "
            "likely from an incomplete write by the camera. Lossless rotation "
            "is not possible without discarding the affected rows."
        ),
    }


def _find_jpegtran() -> str | None:
    """Locate jpegtran, checking the PyInstaller bundle directory first."""
    if hasattr(sys, "_MEIPASS"):
        for name in ("jpegtran", "jpegtran.exe"):
            candidate = Path(sys._MEIPASS) / name  # noqa: SLF001
            if candidate.exists():
                return str(candidate)
    return shutil.which("jpegtran")


def _jpeg_apply(path: Path, op: Op) -> None:
    exe = _find_jpegtran()
    if not exe:
        raise RuntimeError(
            _(
                "jpegtran is not available.\n"
                "JPEG lossless rotation requires jpegtran.\n"
                "Install libjpeg-turbo to enable this feature."
            )
        )
    data = repair_jpeg_sos(path.read_bytes())
    proc = subprocess.run(
        [exe, "-copy", "all", "-trim", *_OP_TO_JPEGTRAN[op]],
        input=data,
        capture_output=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="replace").strip()
        hint = next(
            (msg for key, msg in _jpegtran_error_hints().items() if key in detail),
            None,
        )
        raise RuntimeError(f"{hint}\n\n({detail})" if hint else detail)
    path.write_bytes(proc.stdout)
    # jpegtran rotates the pixels but copies the EXIF block as is.
    set_exif_orientation(path, 1)


def set_exif_orientation(path: str | Path, value: int) -> None:
    """Set the EXIF Orientation tag of *path* in place (requires pyexiv2).

    No-op if the file has no EXIF block at all, matching the pre-rotation
    state (a rotated file that never had EXIF should not gain one just to
    hold Orientation=1), and without pyexiv2.
    """
    try:
        import pyexiv2
    except ImportError:
        _log.warning("pyexiv2 unavailable: EXIF orientation of %s left as is", path)
        return
    try:
        img = pyexiv2.Image(str(path))
        try:
            if img.read_exif():
                img.modify_exif({"Exif.Image.Orientation": str(value)})
        finally:
            img.close()
    except Exception:  # noqa: BLE001
        _log.warning("Could not set the EXIF orientation of %s", path, exc_info=True)


# ---------------------------------------------------------------------------
# Non-JPEG path (Pillow)
# ---------------------------------------------------------------------------


def _pil_apply(path: Path, op: Op) -> None:
    from PIL import Image

    transpose = {
        "hflip": Image.Transpose.FLIP_LEFT_RIGHT,
        "vflip": Image.Transpose.FLIP_TOP_BOTTOM,
        "transpose": Image.Transpose.TRANSPOSE,
        "transverse": Image.Transpose.TRANSVERSE,
    }
    with Image.open(path) as img:
        if isinstance(op, int):
            # Pillow rotates counter-clockwise; our convention is clockwise.
            result = img.rotate(-op, expand=True)
        elif op in transpose:
            result = img.transpose(transpose[op])
        else:
            raise ValueError(f"Unknown op: {op}")
        _pil_save_lossless(result, path)


def _pil_save_lossless(img, path: Path) -> None:
    ext = path.suffix.lower()
    if ext == ".png":
        img.save(path, format="PNG")
    elif ext in (".tiff", ".tif"):
        img.save(path, format="TIFF", compression="none")
    elif ext == ".bmp":
        img.save(path, format="BMP")
    elif ext == ".webp":
        img.save(path, format="WEBP", lossless=True)
    else:
        img.save(path)
