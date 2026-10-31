"""Image loading helpers with Pillow fallback for formats Qt cannot handle."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QBuffer, QSize, Qt
from PySide6.QtGui import QImage, QImageReader, QPixmap

from pbrenamer.core.image_ops import is_jpeg, repair_jpeg_sos

try:  # HEIC/HEIF through Pillow (extra [images])
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover
    pass

# Qt's image format plugins (qjpeg, etc.) are not safe to invoke concurrently
# from multiple threads: the thumbnail worker threads (load_qimage) and the
# GUI thread (load_pixmap) can deadlock inside QImageReader.read() if they
# decode at the same time. Serialize all Qt decodes behind one lock; Pillow's
# fallback path is unaffected since it never runs concurrently with a Qt
# decode of the same call.
_qimage_reader_lock = threading.Lock()

# Qt's default (256 MiB) is sized against the *undecoded* image dimensions,
# before any setScaledSize() downscaling is applied. Large but legitimate
# photos (high-MP phone cameras, panoramas) can exceed it, causing
# QImageReader to reject the image and forcing a much slower, full-resolution
# Pillow fallback just to produce a small thumbnail. Raise it generously while
# still guarding against corrupt files advertising absurd dimensions.
_ALLOCATION_LIMIT_MIB = 1024


def _pillow_to_qimage(pil_img) -> QImage:
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    w, h = pil_img.size
    data = pil_img.tobytes("raw", "RGBA")
    img = QImage(data, w, h, QImage.Format.Format_RGBA8888)
    return img.copy()


def _make_reader(path: Path) -> tuple[QImageReader, QBuffer | None]:
    """Build a QImageReader for *path*, repairing malformed JPEG headers first.

    Some camera firmware writes an invalid SOS marker that Qt merely warns
    about; repairing it up front avoids the warning and the decode issues it
    can cause.  The buffer is returned so that it outlives the reader.
    """
    if is_jpeg(path):
        try:
            data = repair_jpeg_sos(path.read_bytes())
        except OSError:
            reader = QImageReader(str(path))
            reader.setAllocationLimit(_ALLOCATION_LIMIT_MIB)
            return reader, None
        buf = QBuffer()
        buf.setData(data)
        buf.open(QBuffer.OpenModeFlag.ReadOnly)
        reader = QImageReader(buf, b"jpg")
        reader.setAllocationLimit(_ALLOCATION_LIMIT_MIB)
        return reader, buf
    reader = QImageReader(str(path))
    reader.setAllocationLimit(_ALLOCATION_LIMIT_MIB)
    return reader, None


def _pillow_image(path: Path, auto_rotate: bool):
    from PIL import Image, ImageOps

    pil_img = Image.open(str(path))
    pil_img.load()
    if auto_rotate:
        pil_img = ImageOps.exif_transpose(pil_img)
    return pil_img


def load_qimage(
    path: str | Path, max_w: int = 0, max_h: int = 0, auto_rotate: bool = True
) -> QImage:
    """Load an image as QImage, scaled to fit *max_w* × *max_h* when both
    are positive.  Thread-safe; returns a null QImage on failure."""
    path = Path(path)
    with _qimage_reader_lock:
        reader, _buf = _make_reader(path)
        reader.setAutoTransform(auto_rotate)
        if max_w > 0 and max_h > 0:
            orig = reader.size()
            if orig.isValid():
                reader.setScaledSize(
                    orig.scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio)
                )
        image = reader.read()
    if not image.isNull():
        return image

    try:
        from PIL import Image

        pil_img = _pillow_image(path, auto_rotate)
        if max_w > 0 and max_h > 0:
            pil_img.thumbnail((max_w, max_h), Image.LANCZOS)
        return _pillow_to_qimage(pil_img)
    except Exception:  # noqa: BLE001
        return QImage()


def image_size(path: str | Path, auto_rotate: bool = True) -> QSize | None:
    """Return the image's pixel dimensions, read from the header only.

    Reflects the EXIF-rotated dimensions when *auto_rotate* is set, matching
    what load_qimage()/load_pixmap() display.
    """
    with _qimage_reader_lock:
        reader, _buf = _make_reader(Path(path))
        reader.setAutoTransform(auto_rotate)
        size = reader.size()
    return size if size.isValid() else None


def load_pixmap(path: str | Path, auto_rotate: bool = True) -> QPixmap:
    """Load an image as QPixmap. Must be called from the main thread."""
    path = Path(path)
    with _qimage_reader_lock:
        reader, _buf = _make_reader(path)
        reader.setAutoTransform(auto_rotate)
        image = reader.read()
    if not image.isNull():
        return QPixmap.fromImage(image)

    try:
        img = _pillow_to_qimage(_pillow_image(path, auto_rotate))
        if not img.isNull():
            return QPixmap.fromImage(img)
    except Exception:  # noqa: BLE001
        pass
    return QPixmap()
