"""Show which of the directory tree and the file list has the keyboard focus.

The focused view gets a frame in the highlight color and keeps the normal
selection color; the other one gets a transparent frame of the same width
(nothing moves) and a grey selection.  Colors come from the application
palette, so light and dark themes both work.

Opening a context menu or another window does not count as leaving the
view: the marker stays until the focus goes to another widget of the
window.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QAbstractItemView, QApplication

BORDER_WIDTH = 2
# Share of the text color in the grey selection of the unfocused view.
_INACTIVE_MIX = 0.25
_GROUPS = (
    QPalette.ColorGroup.Active,
    QPalette.ColorGroup.Inactive,
    QPalette.ColorGroup.Disabled,
)
# Focus losses that do not move the focus elsewhere in the window.
_KEEP_REASONS = (
    Qt.FocusReason.PopupFocusReason,
    Qt.FocusReason.ActiveWindowFocusReason,
)


def _mix(base: QColor, other: QColor, ratio: float) -> QColor:
    """*base* moved by *ratio* (0 to 1) towards *other*."""
    return QColor.fromRgbF(
        base.redF() + (other.redF() - base.redF()) * ratio,
        base.greenF() + (other.greenF() - base.greenF()) * ratio,
        base.blueF() + (other.blueF() - base.blueF()) * ratio,
    )


class FocusMarker(QObject):
    """Event filter that marks *view* as focused or not (see module doc)."""

    def __init__(self, view: QAbstractItemView) -> None:
        super().__init__(view)
        self._view = view
        if not view.objectName():
            view.setObjectName(type(view).__name__)
        self.active = view.hasFocus()
        self._update()
        view.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        kind = event.type()
        if kind == QEvent.Type.FocusIn:
            self._set_active(True)
        elif kind == QEvent.Type.FocusOut:
            if event.reason() not in _KEEP_REASONS:
                self._set_active(False)
        elif kind == QEvent.Type.ApplicationPaletteChange:
            self._update()
        return False

    def _set_active(self, active: bool) -> None:
        if active != self.active:
            self.active = active
            self._update()

    def _update(self) -> None:
        base = QApplication.palette(self._view)
        if self.active:
            border = base.color(QPalette.ColorRole.Highlight).name()
        else:
            border = "transparent"
        # Selected by object name: the header and the scroll bars, also
        # scroll areas, keep their own look.  The style sheet goes first:
        # changing it restores the palette the widget had before.
        self._view.setStyleSheet(
            f"#{self._view.objectName()} {{ border: {BORDER_WIDTH}px solid {border}; }}"
        )
        palette = QPalette(self._view.palette())
        for group in _GROUPS:
            if self.active:
                highlight = base.color(group, QPalette.ColorRole.Highlight)
                text = base.color(group, QPalette.ColorRole.HighlightedText)
            else:
                text = base.color(group, QPalette.ColorRole.Text)
                highlight = _mix(
                    base.color(group, QPalette.ColorRole.Base), text, _INACTIVE_MIX
                )
            palette.setColor(group, QPalette.ColorRole.Highlight, highlight)
            palette.setColor(group, QPalette.ColorRole.HighlightedText, text)
        self._view.setPalette(palette)


def mark_focus(view: QAbstractItemView) -> FocusMarker:
    """Install a :class:`FocusMarker` on *view* and return it."""
    return FocusMarker(view)
