"""HiDPI-aware cursor pixmaps for drag'n'drop feedback.

Cursor images come from PBIcons' ``cursors/`` set (synced into
``resources/`` by ``tools/update_icons.py``): one PNG per DnD state — copy,
move, alias (link), not-allowed — each with ``@2x``/``@3x`` variants. Each
image's arrow tip is centered on its canvas, matching ``QDrag.setDragCursor``'s
default (centered) hotspot.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QDrag, QPixmap
from PySide6.QtWidgets import QApplication

from pbrenamer.resources import path as _resource

_SUFFIX_BY_SCALE = {1: "", 2: "@2x", 3: "@3x"}

_cache: dict[str, QPixmap] = {}


def _screen_scale() -> int:
    """Return the nearest supported cursor scale (1, 2, or 3) for the
    primary screen's device pixel ratio."""
    screen = QApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    if dpr > 2:
        return 3
    if dpr > 1:
        return 2
    return 1


def drag_cursor(name: str) -> QPixmap:
    """Return a cached, HiDPI-correct pixmap for cursor *name*."""
    scale = _screen_scale()
    key = f"{name}:{scale}"
    if key not in _cache:
        pixmap = QPixmap(_resource(f"{name}{_SUFFIX_BY_SCALE[scale]}.png"))
        pixmap.setDevicePixelRatio(float(scale))
        _cache[key] = pixmap
    return _cache[key]


def set_drag_cursors(drag: QDrag) -> None:
    """Assign the copy/move/alias/not-allowed cursors to *drag*."""
    drag.setDragCursor(drag_cursor("copy"), Qt.DropAction.CopyAction)
    drag.setDragCursor(drag_cursor("move"), Qt.DropAction.MoveAction)
    drag.setDragCursor(drag_cursor("alias"), Qt.DropAction.LinkAction)
    drag.setDragCursor(drag_cursor("not-allowed"), Qt.DropAction.IgnoreAction)
