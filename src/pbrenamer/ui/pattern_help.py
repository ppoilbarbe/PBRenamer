"""Non-modal help dialogs for the search and replace pattern fields."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

# ── HTML content ──────────────────────────────────────────────────────────────

_SEARCH_HTML = """\
<html><body style="font-family: sans-serif; font-size: 10pt; margin: 8px;">

<h2 style="color: #1565C0;">Search patterns</h2>

<h3>Pattern mode</h3>
<p>Tokens act as typed wildcards. Segments enclosed in <b>{1}</b>, <b>{2}</b>…
are <em>captured</em> and available for reuse in the replacement field.</p>

<table border="0" cellspacing="0" cellpadding="4"
       style="border-collapse: collapse;">
  <tr style="background:#f0f4ff;">
    <td><code><b>{#}</b></code></td>
    <td>One or more digits (0–9)</td>
  </tr>
  <tr>
    <td><code><b>{L}</b></code></td>
    <td>One or more letters (a–z, A–Z and Unicode letters)</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code><b>{C}</b></code></td>
    <td>One or more non-whitespace characters</td>
  </tr>
  <tr>
    <td><code><b>{X}</b></code></td>
    <td>Any sequence of characters, including empty</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code><b>{@}</b></code></td>
    <td>Trash — matches and discards a segment (not captured)</td>
  </tr>
  <tr>
    <td><code><b>{1}</b>, <b>{2}</b>…</code></td>
    <td>Capture group — the matched text is bound to {1}, {2}… in the replacement</td>
  </tr>
</table>

<p><b>Example</b><br>
Search: <code>{1}_{@}_{2}</code>&nbsp;&nbsp;
Replace: <code>{2}_{1}</code><br>
<i>photo_trash_holiday</i> → <i>holiday_photo</i></p>

<hr/>
<h3>Regular expression mode</h3>
<p>Full Python <code>re</code>-module syntax. The match is applied to the file
stem (or full name if <em>Keep extension</em> is unchecked).</p>
<table border="0" cellspacing="0" cellpadding="4"
       style="border-collapse: collapse;">
  <tr style="background:#f0f4ff;">
    <td><code>.</code></td><td>Any single character</td>
  </tr>
  <tr>
    <td><code>.*</code>&nbsp;/&nbsp;<code>.+</code></td>
    <td>Any sequence (greedy), non-empty variant</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>\\d+</code></td><td>One or more digits</td>
  </tr>
  <tr>
    <td><code>\\w+</code></td><td>Word characters (letters, digits, _)</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>(…)</code></td>
    <td>Numbered capture group → <code>\\1</code>, <code>\\2</code>… in replacement</td>
  </tr>
  <tr>
    <td><code>(?P&lt;name&gt;…)</code></td>
    <td>Named capture group → <code>\\g&lt;name&gt;</code> in replacement</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>(?i)</code></td><td>Case-insensitive flag</td>
  </tr>
  <tr>
    <td><code>^</code>&nbsp;/&nbsp;<code>$</code></td>
    <td>Start / end of the name</td>
  </tr>
</table>

<p><b>Example</b><br>
Search: <code>(\\d{4})-(\\d{2})-(\\d{2})</code>&nbsp;&nbsp;
Replace: <code>\\3/\\2/\\1</code><br>
<i>2024-06-15</i> → <i>15/06/2024</i></p>

<hr/>
<h3>Plain text mode</h3>
<p>The search field is matched as a literal string — no wildcards, no special
characters. Every occurrence of the exact text in the file name is replaced.</p>

<p><b>Example</b><br>
Search: <code>IMG_</code>&nbsp;&nbsp;Replace: <code>photo_</code><br>
<i>IMG_0042</i> → <i>photo_0042</i></p>

</body></html>
"""

_REPLACE_HTML = """\
<html><body style="font-family: sans-serif; font-size: 10pt; margin: 8px;">

<h2 style="color: #1565C0;">Replacement patterns</h2>

<h3>Pattern mode tokens</h3>
<table border="0" cellspacing="0" cellpadding="4"
       style="border-collapse: collapse;">
  <tr style="background:#f0f4ff;">
    <td><code><b>{1}</b>, <b>{2}</b>…</code></td>
    <td>Content of capture group 1, 2… from the search pattern</td>
  </tr>
  <tr>
    <td><code><b>{num}</b></code></td>
    <td>Auto-incrementing counter starting at 1 (1, 2, 3…)</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code><b>{num2}</b></code></td>
    <td>Counter zero-padded to 2 digits (01, 02…).
        Use any width: <code>{num3}</code>, <code>{num4}</code>…</td>
  </tr>
  <tr>
    <td><code><b>{date}</b></code></td>
    <td>Today's date in <code>YYYY-MM-DD</code> format</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code><b>{dir}</b></code></td>
    <td>Name of the immediate parent folder</td>
  </tr>
</table>

<p><b>Example</b><br>
Search: <code>{1}_{@}_{2}</code>&nbsp;&nbsp;
Replace: <code>{dir}_{2}_{num2}</code><br>
File <i>Photos/shot_raw_beach</i> → <i>Photos_beach_01</i></p>

<hr/>
<h3>Regular expression mode</h3>
<table border="0" cellspacing="0" cellpadding="4"
       style="border-collapse: collapse;">
  <tr style="background:#f0f4ff;">
    <td><code><b>\\1</b>, <b>\\2</b>…</code></td>
    <td>Numbered capture group from the search regex</td>
  </tr>
  <tr>
    <td><code><b>\\g&lt;name&gt;</b></code></td>
    <td>Named capture group <code>(?P&lt;name&gt;…)</code> from the search regex</td>
  </tr>
</table>

<p><b>Example</b><br>
Search: <code>(?P&lt;year&gt;\\d{4})-(?P&lt;rest&gt;.*)</code>&nbsp;&nbsp;
Replace: <code>\\g&lt;rest&gt;_\\g&lt;year&gt;</code><br>
<i>2024-conference_notes</i> → <i>conference_notes_2024</i></p>

<hr/>
<h3>Plain text mode</h3>
<p>The replacement is a literal string with no special tokens. Every occurrence
of the search text is replaced verbatim by the replacement text.</p>

</body></html>
"""

SEARCH_HTML: str = _SEARCH_HTML
REPLACE_HTML: str = _REPLACE_HTML


# ── Icon ──────────────────────────────────────────────────────────────────────


def make_add_icon(size: int = 18) -> QIcon:
    """Orange '+' symbol."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#E65100"))
    pen.setWidthF(2.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    m = size // 4
    cx = size // 2
    p.drawLine(m, cx, size - m, cx)
    p.drawLine(cx, m, cx, size - m)
    p.end()
    return QIcon(px)


def make_help_icon(size: int = 18) -> QIcon:
    """Blue '?' inside a thin black circle."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(Qt.GlobalColor.black)
    pen.setWidthF(1.0)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(1, 1, size - 3, size - 3)
    p.setPen(QColor("#1565C0"))
    font = QFont()
    font.setBold(True)
    font.setPixelSize(size - 6)
    p.setFont(font)
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "?")
    p.end()
    return QIcon(px)


# ── Dialog ────────────────────────────────────────────────────────────────────


class PatternHelpDialog(QDialog):
    """Non-modal help window; use show() not exec()."""

    def __init__(self, html: str, title: str, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(title)
        self.resize(560, 500)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(html)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addWidget(browser)
        layout.addWidget(buttons)
