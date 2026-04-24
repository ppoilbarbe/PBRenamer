"""Custom reusable widgets."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QTextLayout
from PySide6.QtWidgets import QLineEdit, QStyle, QStyleOptionFrame


class WhitespaceLineEdit(QLineEdit):
    """Fixed-pitch QLineEdit that renders spaces as a grey dot and tabs as → (blue)."""

    _TAB_MARKER = "→"  # RIGHTWARDS ARROW
    _SPACE_COLOR = QColor(160, 160, 160)
    _TAB_COLOR = QColor(80, 140, 200)
    _DOT_RADIUS = 1.5  # px

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        text = self.text()
        if not text:
            return
        ws = [(i, ch) for i, ch in enumerate(text) if ch in (" ", "\t")]
        if not ws:
            return

        # QTextLayout uses the same shaping engine as QLineEdit internally.
        # cursorToX(i) is computed in floating-point, avoiding the accumulated
        # rounding errors of summing horizontalAdvance() char-by-char.
        layout = QTextLayout(text, self.font())
        layout.beginLayout()
        tline = layout.createLine()
        tline.setLineWidth(1_000_000)
        layout.endLayout()

        # Anchor: widget-coordinate origin of the text rendering area.
        # cursorRect().x() = base + int(cursorToX(p)) where int() truncates.
        # Subtracting the float cursorToX(p) gives base - frac, shifting left.
        # Subtracting its floor instead recovers base exactly.
        cursor_to_x = tline.cursorToX(self.cursorPosition())
        text_origin_x = self.cursorRect().x() - math.floor(cursor_to_x)
        fm = self.fontMetrics()

        opt = QStyleOptionFrame()
        self.initStyleOption(opt)
        contents = self.style().subElementRect(
            QStyle.SubElement.SE_LineEditContents, opt, self
        )
        cy = self.height() / 2.0

        painter = QPainter(self)
        painter.setClipRect(contents)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for i, ch in ws:
            x0 = text_origin_x + tline.cursorToX(i)
            x1 = text_origin_x + tline.cursorToX(i + 1)
            if x1 < contents.left() or x0 > contents.right():
                continue
            center_x = (x0 + x1) / 2.0
            if ch == " ":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self._SPACE_COLOR)
                r = self._DOT_RADIUS
                painter.drawEllipse(QPointF(center_x, cy), r, r)
            else:
                painter.setPen(self._TAB_COLOR)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                mw = fm.horizontalAdvance(self._TAB_MARKER)
                draw_x = int(x0 + (x1 - x0 - mw) / 2)
                painter.drawText(
                    QRect(draw_x, 0, mw, self.height()),
                    Qt.AlignmentFlag.AlignVCenter,
                    self._TAB_MARKER,
                )

        painter.end()
