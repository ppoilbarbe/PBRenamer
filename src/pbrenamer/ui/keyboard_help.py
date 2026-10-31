"""HTML content of the keyboard and mouse shortcuts help window (F1)."""

from __future__ import annotations

import sys

from PySide6.QtGui import QKeySequence

_STYLE = (
    "<style>"
    "body{font-family:sans-serif;font-size:10pt;margin:8px;}"
    "h2{color:#1565C0;font-size:12pt;margin:14px 0 4px 0;}"
    "h3{font-size:10pt;margin:10px 0 2px 0;}"
    "table{border-collapse:collapse;margin-bottom:6px;}"
    "td{padding:4px 10px;vertical-align:top;}"
    "td.key{font-family:monospace;font-weight:bold;}"
    "td.mouse{font-weight:bold;}"
    "</style>"
)
_BG = ("background:#f0f4ff;", "background:#e8eeff;")


def _key(portable: str) -> str:
    """*portable* ("Ctrl+O") in the platform's notation (⌘O on macOS)."""
    return QKeySequence(portable).toString(QKeySequence.SequenceFormat.NativeText)


def _mod(name: str) -> str:
    """Modifier *name* ("Ctrl") as a prefix in the platform's notation
    ("Ctrl+" or "⌘")."""
    return _key(f"{name}+A")[:-1]


def _keys(*portables: str) -> str:
    return " / ".join(_key(p) for p in portables)


def _table(rows: list[tuple[str, str]], css: str) -> str:
    """Two columns, the first one 40 % wide so all tables line up."""
    body = "".join(
        f'<tr style="{_BG[i % 2]}"><td class="{css}" width="40%">{key}</td>'
        f"<td>{desc}</td></tr>"
        for i, (key, desc) in enumerate(rows)
    )
    return f'<table width="100%">{body}</table>'


def _section(title: str, keyboard: list, mouse: list) -> str:
    return (
        f"<h2>{title}</h2>"
        f"<h3>{_('Keyboard')}</h3>{_table(keyboard, 'key')}"
        f"<h3>{_('Mouse')}</h3>{_table(mouse, 'mouse')}"
    )


def keyboard_html() -> str:
    """Build the help page; called after i18n setup so _() is translated."""
    rotations = [
        (_key("F6"), _("Rotate 90° left, without loss")),
        (_key("F7"), _("Rotate 180°, without loss")),
        (_key("F8"), _("Rotate 90° right, without loss")),
        (_key("F9"), _("Apply EXIF orientation")),
        (_key("F10"), _("Force EXIF orientation to 0°")),
    ]
    tree = _("directory tree")
    files = _("file list")
    # Qt's copy modifier when dragging: Option on macOS, Ctrl elsewhere.
    copy_mod = _mod("Alt" if sys.platform == "darwin" else "Ctrl")
    ctrl, shift = _mod("Ctrl"), _mod("Shift")

    main_keys = [
        (_key("Ctrl+O"), _("Open a folder")),
        (_key("Ctrl+I"), _("File information")),
        (_key("Ctrl+Q"), _("Quit")),
        (_key("Ctrl+N"), _("New profile")),
        (_key("Ctrl+Shift+D"), _("Duplicate profile")),
        (_key("Ctrl+,"), _("Profile configuration")),
        (_key("F1"), _("Keyboard and mouse shortcuts (this window)")),
        (_key("F2"), _("Rename as shown in the Preview column")),
        (_key("F5"), _("Reload the file list")),
        (
            _keys("Tab", "Shift+Tab"),
            _("Switch focus between directory tree and file list"),
        ),
        (f"← ↑ → ↓ ({tree})", _("Navigate directories")),
        (f"↑ / ↓ ({files})", _("Select previous / next file")),
        (_keys("Home", "End"), _("Jump to first / last entry")),
        (f"{_key('Return')} ({files})", _("Show the selected images in the viewer")),
        (
            _key("Ctrl+Return"),
            _("Open the selected files with their default application"),
        ),
        (_key("Ctrl+Shift+O"), _("Open with…")),
        (f"{_key('Del')} ({files})", _("Delete selected file(s) and their sidecars")),
        *rotations,
    ]
    main_mouse = [
        (
            f"{ctrl}{_('click')}, {shift}{_('click')}",
            _("Add to the selection / select a range"),
        ),
        (_("No selection"), _("Rename, renumber and preview act on all listed files")),
        (_("Double-click on a thumbnail"), _("Show the image in the viewer")),
        (_("Double-click on a name"), _("Open the file with its default application")),
        (_("Double-click on a sidecar"), _("Open the sidecar file")),
        (_("Right-click on the file list"), _("Images menu")),
        (_("Right-click on the directory tree"), _("Add the folder as a shortcut")),
        (_("Drag onto a folder"), _("Move the files and their sidecars")),
        (
            copy_mod + _("drag onto a folder"),
            _("Copy the files and their sidecars"),
        ),
    ]
    viewer_keys = [
        (_keys("0", "X"), _("Fit window")),
        (_keys("1", "Z"), _("Actual size (1:1)")),
        (_key("W"), _("Fit width")),
        (_key("H"), _("Fit height")),
        ("+ / −", _("Zoom in / Zoom out")),
        ("← ↑ / → ↓", _("Previous / next image of the selection, or of the list")),
        (_key("I"), _("Show / hide the metadata")),
        (_key("Ctrl+Return"), _("Open with the default application")),
        (_key("Ctrl+Shift+O"), _("Open with…")),
        (_key("Del"), _("Delete current image and its sidecars")),
        *rotations,
        (_key("Esc"), _("Close image viewer")),
    ]
    viewer_mouse = [
        (_("Left-click + drag"), _("Pan image")),
        (_("Double left-click"), _("Center on clicked point")),
        (ctrl + _("left-click"), _("Zoom in centered on point")),
        (ctrl + _("right-click"), _("Zoom out centered on point")),
        (_("Click on a thumbnail of the strip"), _("Show this image")),
    ]
    return (
        f"<html><head>{_STYLE}</head><body>"
        + _section(_("Main window"), main_keys, main_mouse)
        + _section(_("Image viewer"), viewer_keys, viewer_mouse)
        + "</body></html>"
    )
