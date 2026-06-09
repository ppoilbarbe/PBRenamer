"""Read system directory bookmarks (GTK on Linux, standard paths elsewhere)."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from PySide6.QtCore import QStandardPaths


def _gtk_bookmarks() -> list[tuple[str, str]]:
    for candidate in (
        Path.home() / ".config" / "gtk-3.0" / "bookmarks",
        Path.home() / ".gtk-bookmarks",
    ):
        if candidate.exists():
            return _parse_gtk(candidate)
    return []


def _parse_gtk(path: Path) -> list[tuple[str, str]]:
    result = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        try:
            parsed = urlparse(parts[0])
        except ValueError:
            continue
        if parsed.scheme != "file":
            continue
        dir_path = unquote(parsed.path)
        if not Path(dir_path).is_dir():
            continue
        name = parts[1] if len(parts) > 1 else Path(dir_path).name
        result.append((name, dir_path))
    return result


def _standard_locations() -> list[tuple[str, str]]:
    locations = [
        (QStandardPaths.StandardLocation.HomeLocation, _("Home")),
        (QStandardPaths.StandardLocation.DesktopLocation, _("Desktop")),
        (QStandardPaths.StandardLocation.DocumentsLocation, _("Documents")),
        (QStandardPaths.StandardLocation.DownloadLocation, _("Downloads")),
        (QStandardPaths.StandardLocation.PicturesLocation, _("Pictures")),
        (QStandardPaths.StandardLocation.MusicLocation, _("Music")),
        (QStandardPaths.StandardLocation.MoviesLocation, _("Videos")),
    ]
    result = []
    for loc, label in locations:
        paths = QStandardPaths.standardLocations(loc)
        if paths and Path(paths[0]).is_dir():
            result.append((label, paths[0]))
    return result


def system_bookmarks() -> list[tuple[str, str]]:
    """Return system directory bookmarks as (display_name, path) pairs."""
    if sys.platform.startswith("linux"):
        gtk = _gtk_bookmarks()
        if gtk:
            return gtk
    return _standard_locations()
