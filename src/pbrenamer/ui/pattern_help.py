"""Non-modal help dialogs for the search and replace pattern fields."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

# ── HTML builders ─────────────────────────────────────────────────────────────
#
# Each function is called at dialog-creation time (after i18n.setup()), so
# _() is guaranteed to be installed and the locale is already active.

_HEAD = '<html><body style="font-family: sans-serif; font-size: 10pt; margin: 8px;">\n'
_FOOT = "</body></html>\n"
_BG1 = "background:#f0f4ff;"
_BG2 = "background:#e8eeff;"
_TABLE = (
    '<table border="0" cellspacing="0" cellpadding="4"'
    ' style="border-collapse: collapse;">\n'
)
_TABLE_W = (
    '<table border="0" cellspacing="0" cellpadding="4"'
    ' style="border-collapse: collapse; width:100%;">\n'
)


def _h2(text: str) -> str:
    return f'<h2 style="color: #1565C0;">{text}</h2>\n'


def _h3(text: str) -> str:
    return f"<h3>{text}</h3>\n"


def _p(text: str) -> str:
    return f"<p>{text}</p>\n"


def _row2(code: str, desc: str, bg: str = "") -> str:
    sty = f' style="{bg}"' if bg else ""
    return (
        f"  <tr{sty}>\n"
        f"    <td><code><b>{code}</b></code></td>\n"
        f"    <td>{desc}</td>\n"
        f"  </tr>\n"
    )


def _row2_plain(col1: str, desc: str, bg: str = "") -> str:
    """Two-column row, first column not in <code><b>."""
    sty = f' style="{bg}"' if bg else ""
    return (
        f"  <tr{sty}>\n"
        f"    <td><code>{col1}</code></td>\n"
        f"    <td>{desc}</td>\n"
        f"  </tr>\n"
    )


def _row3(col1: str, col2: str, desc: str, bg: str = "") -> str:
    sty = f' style="{bg}"' if bg else ""
    return (
        f"  <tr{sty}>\n"
        f"    <td><code>{col1}</code></td>"
        f"<td>{col2}</td>"
        f"<td>{desc}</td>\n"
        f"  </tr>\n"
    )


def search_html() -> str:
    """Build and return the translated search-mode help HTML."""
    # ── Pattern mode ──────────────────────────────────────────────────────────
    pat_intro = _(
        "Tokens act as typed wildcards. Segments enclosed in <b>{1}</b>, <b>{2}</b>… "
        "are <em>captured</em> and available for reuse in the replacement field."
    )
    pat_table = (
        _TABLE
        + _row2("{#}", _("One or more digits (0–9)"), _BG1)
        + _row2("{L}", _("One or more letters (a–z, A–Z and Unicode letters)"))
        + _row2("{C}", _("One or more non-whitespace characters"), _BG1)
        + _row2("{X}", _("Any sequence of characters, including empty"))
        + _row2("{@}", _("Trash — matches and discards a segment (not captured)"), _BG1)
        + _row2(
            "{1}</b>, <b>{2}</b>…",
            _(
                "Capture group — the matched text is bound to"
                " {1}, {2}… in the replacement"
            ),
        )
        + "</table>\n"
    )
    pat_example = _p(
        "<b>"
        + _("Example")
        + "</b><br>\n"
        + _("Search:")
        + " <code>{1}_{@}_{2}</code>&nbsp;&nbsp;\n"
        + _("Replace:")
        + " <code>{2}_{1}</code><br>\n"
        + "<i>photo_trash_holiday</i> → <i>holiday_photo</i>"
    )

    # ── Regex mode ────────────────────────────────────────────────────────────
    re_intro = _(
        "Full Python <code>re</code>-module syntax. The match is applied to the file "
        "stem (or full name if <em>Keep extension</em> is unchecked)."
    )
    re_table = (
        _TABLE
        + _row2_plain(".", _("Any single character"), _BG1)
        + _row2_plain(
            ".*&nbsp;/&nbsp;.+", _("Any sequence (greedy), non-empty variant")
        )
        + _row2_plain("\\d+", _("One or more digits"), _BG1)
        + _row2_plain("\\w+", _("Word characters (letters, digits, _)"))
        + _row2_plain(
            "(…)",
            _(
                "Numbered capture group → <code>\\1</code>, <code>\\2</code>…"
                " in replacement"
            ),
            _BG1,
        )
        + _row2_plain(
            "(?P&lt;name&gt;…)",
            _("Named capture group → <code>\\g&lt;name&gt;</code> in replacement"),
        )
        + _row2_plain("(?i)", _("Case-insensitive flag"), _BG1)
        + _row2_plain("^&nbsp;/&nbsp;$", _("Start / end of the name"))
        + "</table>\n"
    )
    re_example = _p(
        "<b>"
        + _("Example")
        + "</b><br>\n"
        + _("Search:")
        + " <code>(\\d{4})-(\\d{2})-(\\d{2})</code>&nbsp;&nbsp;\n"
        + _("Replace:")
        + " <code>\\3/\\2/\\1</code><br>\n"
        + "<i>2024-06-15</i> → <i>15/06/2024</i>"
    )

    # ── Plain text mode ───────────────────────────────────────────────────────
    plain_intro = _(
        "The search field is matched as a literal string — no wildcards, no special "
        "characters. Every occurrence of the exact text in the file name is replaced."
    )
    plain_example = _p(
        "<b>"
        + _("Example")
        + "</b><br>\n"
        + _("Search:")
        + " <code>IMG_</code>&nbsp;&nbsp;"
        + _("Replace:")
        + " <code>photo_</code><br>\n"
        + "<i>IMG_0042</i> → <i>photo_0042</i>"
    )

    return (
        _HEAD
        + _h2(_("Search patterns"))
        + _h3(_("Pattern mode"))
        + _p(pat_intro)
        + pat_table
        + pat_example
        + "<hr/>\n"
        + _h3(_("Regular expression mode"))
        + _p(re_intro)
        + re_table
        + re_example
        + "<hr/>\n"
        + _h3(_("Plain text mode"))
        + _p(plain_intro)
        + plain_example
        + _FOOT
    )


def replace_html() -> str:
    """Build and return the translated replacement-field help HTML."""
    # ── Intro ─────────────────────────────────────────────────────────────────
    intro = _(
        "The replacement string is the same regardless of the search mode. "
        "Fields are written <code>{name}</code> and may include formatting options:"
    )
    fmt_pre = (
        '<pre style="background:#f5f5f5; padding:6px; border-radius:4px;">\n'
        "{name}                 " + _("plain value") + "\n"
        "{name:fmt}             " + _("with format") + "\n"
        "{name:fmt:default}     " + _("with format and fallback") + "\n"
        "{name:&lt;fmt}            " + _("left-align  (digit fmt = min width)") + "\n"
        "{name:&gt;fmt}            " + _("right-align") + "\n"
        "{name:0fmt}            " + _("zero-pad right (numbers)") + "\n"
        "{{                     " + _("literal '{' character") + "\n"
        "</pre>\n"
    )
    fmt_note = _(
        "<b>fmt</b> is a minimum width (digit) for text/numbers, "
        "or a <code>strftime</code> format for dates/datetimes.<br>"
        "<b>default</b>: used when the field is absent; omitting it makes absence "
        "an error (file shown in red in the preview)."
    )

    # ── Available fields table ────────────────────────────────────────────────
    all_m = _("all modes")
    pat_re = _("pattern, regex")
    re_only = _("regex only")
    th_field = _("Field")
    th_avail = _("Available in")
    th_desc = _("Description")

    fields_hdr = (
        f'  <tr style="{_BG2}"><th align="left">{th_field}</th>'
        f'<th align="left">{th_avail}</th>'
        f'<th align="left">{th_desc}</th></tr>\n'
    )
    fields_rows = (
        _row3(
            "{0}",
            all_m,
            _("Full matched text (or search literal in plain-text mode)"),
            _BG1,
        )
        + _row3(
            "{1}</code>, <code><b>{2}</b>…",
            pat_re,
            _("Numbered capture groups (1-based)"),
        )
        + _row3(
            "{re:name}",
            re_only,
            _("Named group <code>(?P&lt;name&gt;…)</code> from the search regex"),
            _BG1,
        )
        + _row3(
            "{num}",
            all_m,
            _(
                "Auto-incrementing counter — default fmt is a minimum width; "
                "<em>default</em> sets the start value "
                "(e.g. <code>{num:02:10}</code> starts at 10, zero-padded to 2 digits)"
            ),
        )
        + _row3(
            "{newnum}",
            all_m,
            _(
                "Like <code>{num}</code> but skips values whose target name already "
                "exists on disk or has been assigned to another file in the same batch "
                "— guarantees no conflicts"
            ),
            _BG1,
        )
        + _row3(
            "{date}",
            all_m,
            _("Today's date — default fmt <code>%Y-%m-%d</code>"),
            _BG1,
        )
        + _row3(
            "{datetime}",
            all_m,
            _("Current date and time — default fmt <code>%Y-%m-%d_%H%M%S</code>"),
        )
        + _row3(
            "{mdatetime}",
            all_m,
            _("File modification date/time — default fmt <code>%Y-%m-%d_%H%M%S</code>"),
            _BG1,
        )
        + _row3("{dir}", all_m, _("Name of the immediate parent folder"))
        + _row3(
            "{ex:Field}",
            all_m,
            _("EXIF or IPTC metadata field (images only — see list below)"),
            _BG1,
        )
    )

    # ── EXIF/IPTC metadata table ───────────────────────────────────────────────
    meta_intro = _(
        "Field names are case-insensitive. "
        "A <b>default</b> is strongly recommended for metadata fields — they may be "
        "absent from non-image files or images without metadata."
    )
    th_type = _("Type")
    meta_hdr = (
        f'  <tr style="{_BG2}"><th align="left">{th_field}</th>'
        f'<th align="left">{th_type}</th>'
        f'<th align="left">{th_desc}</th></tr>\n'
    )
    meta_rows = (
        _row3("DateTimeOriginal", "datetime", _("Date/time the photo was taken"), _BG1)
        + _row3("DateTimeDigitized", "datetime", _("Date/time the image was digitised"))
        + _row3("Make", "text", _("Camera manufacturer"), _BG1)
        + _row3("Model", "text", _("Camera model"))
        + _row3("LensModel", "text", _("Lens model"), _BG1)
        + _row3("ISOSpeedRatings", "integer", _("ISO speed"))
        + _row3("FNumber", "text", _("Aperture (e.g. 2.8)"), _BG1)
        + _row3("ExposureTime", "text", _("Shutter speed (e.g. 1/125)"))
        + _row3("FocalLength", "text", _("Focal length in mm"), _BG1)
        + _row3("ObjectName", "text", _("IPTC title / object name"))
        + _row3("By-line", "text", _("IPTC photographer / creator"), _BG1)
        + _row3("City", "text", _("IPTC city"))
        + _row3("Country", "text", _("IPTC country"), _BG1)
        + _row3("DateCreated", "date", _("IPTC creation date"))
        + _row3("Keywords", "text", _("IPTC keywords (semicolon-separated)"), _BG1)
    )

    # ── Examples table ────────────────────────────────────────────────────────
    ex_rows = (
        _row2(
            "{1}_{num:04}",
            _(
                "Capture group 1 followed by a 4-digit zero-padded"
                " counter (starts at 1)"
            ),
            _BG1,
        )
        + _row2("{1}_{num:04:10}", _("Same, but counter starts at 10"))
        + _row2(
            "backup_{newnum:03}",
            _(
                "Conflict-free 3-digit counter: skips values where"
                " <code>backup_NNN</code> already exists"
            ),
            _BG1,
        )
        + _row2("{date}-{0}", _("Today's date prepended to the matched text"))
        + _row2(
            "{ex:DateTimeOriginal:%Y%m%d_%H%M%S:unknown}",
            _('Shooting date/time compact; "unknown" if EXIF absent'),
            _BG1,
        )
        + _row2(
            "{ex:DateTimeDigitized:%H%M:0000}",
            _('Hour+minute of digitisation; "0000" if absent'),
        )
        + _row2(
            "{ex:Make::} {ex:Model::}",
            _("Camera make and model (empty string if absent)"),
            _BG1,
        )
        + _row2("{re:year}_{re:title}", _("Named regex groups (regex mode only)"))
        + _row2(
            "{dir}_{mdatetime:%Y%m%d}_{num:03}",
            _("Parent folder, file modification date, 3-digit counter"),
            _BG1,
        )
    )

    return (
        _HEAD
        + _h2(_("Replacement fields"))
        + _p(intro)
        + fmt_pre
        + _p(fmt_note)
        + "<hr/>\n"
        + _h3(_("Available fields"))
        + _TABLE_W
        + fields_hdr
        + fields_rows
        + "</table>\n"
        + "<hr/>\n"
        + _h3(_("Metadata fields for <code>{ex:…}</code>"))
        + _p(meta_intro)
        + _TABLE_W
        + meta_hdr
        + meta_rows
        + "</table>\n"
        + "<hr/>\n"
        + _h3(_("Examples"))
        + _TABLE_W
        + ex_rows
        + "</table>\n"
        + _FOOT
    )


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

    def __init__(
        self,
        html: str,
        title: str,
        state_key: str,
        window_state,
        parent=None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(title)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._state_key = state_key
        self._window_state = window_state

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(html)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addWidget(browser)
        layout.addWidget(buttons)

        geo = window_state.load_geometry(state_key)
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(560, 500)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._window_state.save_geometry(self._state_key, self.saveGeometry())
        super().closeEvent(event)
