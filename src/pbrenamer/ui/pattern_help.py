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

<h2 style="color: #1565C0;">Replacement fields</h2>

<p>The replacement string is the same regardless of the search mode.
Fields are written <code>{name}</code> and may include formatting options:</p>

<pre style="background:#f5f5f5; padding:6px; border-radius:4px;">
{name}                 plain value
{name:fmt}             with format
{name:fmt:default}     with format and fallback
{name:&lt;fmt}            left-align  (digit fmt = min width)
{name:&gt;fmt}            right-align
{name:0fmt}            zero-pad right (numbers)
{{                     literal '{' character
</pre>

<p><b>fmt</b> is a minimum width (digit) for text/numbers,
or a <code>strftime</code> format for dates/datetimes.<br>
<b>default</b>: used when the field is absent; omitting it makes absence
an error (file shown in orange in the preview).</p>

<hr/>
<h3>Available fields</h3>

<table border="0" cellspacing="0" cellpadding="4"
       style="border-collapse: collapse; width:100%;">
  <tr style="background:#e8eeff;"><th align="left">Field</th>
      <th align="left">Available in</th><th align="left">Description</th></tr>
  <tr style="background:#f0f4ff;">
    <td><code><b>{0}</b></code></td>
    <td>all modes</td>
    <td>Full matched text (or search literal in plain-text mode)</td>
  </tr>
  <tr>
    <td><code><b>{1}</b>, <b>{2}</b>…</code></td>
    <td>pattern, regex</td>
    <td>Numbered capture groups (1-based)</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code><b>{re:name}</b></code></td>
    <td>regex only</td>
    <td>Named group <code>(?P&lt;name&gt;…)</code> from the search regex</td>
  </tr>
  <tr>
    <td><code><b>{num}</b></code></td>
    <td>all modes</td>
    <td>Auto-incrementing counter — default fmt is a minimum width;
        <em>default</em> sets the start value (e.g. <code>{num:02:10}</code>
        starts at 10, zero-padded to 2 digits)</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code><b>{newnum}</b></code></td>
    <td>all modes</td>
    <td>Like <code>{num}</code> but skips values whose target name already
        exists on disk or has been assigned to another file in the same batch
        — guarantees no conflicts</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code><b>{date}</b></code></td>
    <td>all modes</td>
    <td>Today's date — default fmt <code>%Y-%m-%d</code></td>
  </tr>
  <tr>
    <td><code><b>{datetime}</b></code></td>
    <td>all modes</td>
    <td>Current date and time — default fmt <code>%Y-%m-%d_%H%M%S</code></td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code><b>{mdatetime}</b></code></td>
    <td>all modes</td>
    <td>File modification date/time — default fmt <code>%Y-%m-%d_%H%M%S</code></td>
  </tr>
  <tr>
    <td><code><b>{dir}</b></code></td>
    <td>all modes</td>
    <td>Name of the immediate parent folder</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code><b>{ex:Field}</b></code></td>
    <td>all modes</td>
    <td>EXIF or IPTC metadata field (images only — see list below)</td>
  </tr>
</table>

<hr/>
<h3>Metadata fields for <code>{ex:…}</code></h3>

<p>Field names are case-insensitive.
A <b>default</b> is strongly recommended for metadata fields — they may be
absent from non-image files or images without metadata.</p>

<table border="0" cellspacing="0" cellpadding="4"
       style="border-collapse: collapse; width:100%;">
  <tr style="background:#e8eeff;"><th align="left">Field</th>
      <th align="left">Type</th><th align="left">Description</th></tr>
  <tr style="background:#f0f4ff;">
    <td><code>DateTimeOriginal</code></td><td>datetime</td>
    <td>Date/time the photo was taken</td>
  </tr>
  <tr>
    <td><code>DateTimeDigitized</code></td><td>datetime</td>
    <td>Date/time the image was digitised</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>Make</code></td><td>text</td><td>Camera manufacturer</td>
  </tr>
  <tr>
    <td><code>Model</code></td><td>text</td><td>Camera model</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>LensModel</code></td><td>text</td><td>Lens model</td>
  </tr>
  <tr>
    <td><code>ISOSpeedRatings</code></td><td>integer</td><td>ISO speed</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>FNumber</code></td><td>text</td><td>Aperture (e.g. 2.8)</td>
  </tr>
  <tr>
    <td><code>ExposureTime</code></td><td>text</td><td>Shutter speed (e.g. 1/125)</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>FocalLength</code></td><td>text</td><td>Focal length in mm</td>
  </tr>
  <tr>
    <td><code>ObjectName</code></td><td>text</td><td>IPTC title / object name</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>By-line</code></td><td>text</td><td>IPTC photographer / creator</td>
  </tr>
  <tr>
    <td><code>City</code></td><td>text</td><td>IPTC city</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>Country</code></td><td>text</td><td>IPTC country</td>
  </tr>
  <tr>
    <td><code>DateCreated</code></td><td>date</td><td>IPTC creation date</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>Keywords</code></td><td>text</td>
    <td>IPTC keywords (semicolon-separated)</td>
  </tr>
</table>

<hr/>
<h3>Examples</h3>

<table border="0" cellspacing="0" cellpadding="4"
       style="border-collapse: collapse; width:100%;">
  <tr style="background:#f0f4ff;">
    <td><code>{1}_{num:04}</code></td>
    <td>Capture group 1 followed by a 4-digit zero-padded counter (starts at 1)</td>
  </tr>
  <tr>
    <td><code>{1}_{num:04:10}</code></td>
    <td>Same, but counter starts at 10</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>backup_{newnum:03}</code></td>
    <td>Conflict-free 3-digit counter: skips values where
        <code>backup_NNN</code> already exists</td>
  </tr>
  <tr>
    <td><code>{date}-{0}</code></td>
    <td>Today's date prepended to the matched text</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>{ex:DateTimeOriginal:%Y%m%d_%H%M%S:unknown}</code></td>
    <td>Shooting date/time compact; "unknown" if EXIF absent</td>
  </tr>
  <tr>
    <td><code>{ex:DateTimeDigitized:%H%M:0000}</code></td>
    <td>Hour+minute of digitisation; "0000" if absent</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>{ex:Make::} {ex:Model::}</code></td>
    <td>Camera make and model (empty string if absent)</td>
  </tr>
  <tr>
    <td><code>{re:year}_{re:title}</code></td>
    <td>Named regex groups (regex mode only)</td>
  </tr>
  <tr style="background:#f0f4ff;">
    <td><code>{dir}_{mdatetime:%Y%m%d}_{num:03}</code></td>
    <td>Parent folder, file modification date, 3-digit counter</td>
  </tr>
</table>

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
