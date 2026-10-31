"""Linux (XDG) file-open helpers (ported from PBPicat)."""

from __future__ import annotations

import mimetypes
import os
import shlex
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

# Run subprocesses with English output to avoid locale-dependent parsing.
_C_ENV = {**os.environ, "LANG": "C", "LC_ALL": "C"}


def _app_dirs() -> list[Path]:
    """Application directories per the XDG Base Directory spec, highest
    priority first."""
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local/share")
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    dirs: list[Path] = []
    seen: set[Path] = set()
    for base in [data_home, *data_dirs.split(":")]:
        if not base:
            continue
        d = Path(base) / "applications"
        if d not in seen:
            seen.add(d)
            dirs.append(d)
    return dirs


def open_default(path: str | Path) -> None:
    subprocess.Popen(["xdg-open", str(path)])


def open_with(path: str | Path, parent=None) -> None:
    path = Path(path)
    mime, apps = _apps_for_path(path)
    dialog = _AppChooserDialog(apps, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    desktop_file = dialog.selected_desktop_file()
    if desktop_file:
        _remember_choice(mime, desktop_file, [df for _, df in apps])
        _launch(desktop_file, path)


# ---------------------------------------------------------------------------
# MIME type
# ---------------------------------------------------------------------------


def _mime_type(path: Path) -> str:
    try:
        result = subprocess.run(
            ["xdg-mime", "query", "filetype", str(path)],
            capture_output=True,
            text=True,
            timeout=3,
            env=_C_ENV,
        )
        if result.returncode == 0:
            mime = result.stdout.strip()
            if mime:
                return mime
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    mime, _ = mimetypes.guess_type(str(path))
    return mime or ""


# ---------------------------------------------------------------------------
# App list
# ---------------------------------------------------------------------------


def _apps_for_path(path: Path) -> tuple[str, list[tuple[str, str]]]:
    """Return ``(mime, apps)`` where *apps* is the ``(name, desktop_file)`` list
    for the file's MIME type, ordered most-recently-used first (see
    ``_order_by_lru``)."""
    mime = _mime_type(path)
    desktop_files = _registered_apps(mime) if mime else []

    seen: set[str] = set()
    apps: list[tuple[str, str]] = []
    for df in desktop_files:
        if df in seen:
            continue
        seen.add(df)
        name = _desktop_name(df) or df.removesuffix(".desktop")
        apps.append((name, df))
    return mime, _order_by_lru(mime, apps)


def _order_by_lru(mime: str, apps: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Reorder *apps* by the saved MRU list for *mime*: remembered apps that are
    still available come first (in saved order), newly-appeared apps keep their
    system order at the end. Apps that vanished since last run are simply absent."""
    if not mime:
        return apps
    from pbrenamer import settings

    remembered = settings.get_open_with_lru().get(mime, [])
    by_df: dict[str, tuple[str, str]] = {df: (name, df) for name, df in apps}
    ordered = [by_df.pop(df) for df in remembered if df in by_df]
    ordered.extend((name, df) for name, df in apps if df in by_df)
    return ordered


def _remember_choice(mime: str, desktop_file: str, available: list[str]) -> None:
    """Persist *desktop_file* at the front of the MRU list for *mime*, keeping the
    other currently-available apps (dropped: those that disappeared)."""
    if not mime:
        return
    from pbrenamer import settings

    data = settings.get_open_with_lru()
    data[mime] = [desktop_file] + [df for df in available if df != desktop_file]
    try:
        settings.set_open_with_lru(data)
    except OSError:
        pass


def _registered_apps(mime: str) -> list[str]:
    # Try gio first (LANG=C avoids locale-dependent section headers).
    try:
        result = subprocess.run(
            ["gio", "mime", mime],
            capture_output=True,
            text=True,
            timeout=3,
            env=_C_ENV,
        )
        if result.returncode == 0:
            apps = _parse_gio_output(result.stdout)
            if apps:
                return apps
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return _scan_desktop_dirs(mime)


def _parse_gio_output(output: str) -> list[str]:
    """Extract .desktop file names from 'gio mime' output."""
    apps: list[str] = []
    in_registered = False
    for line in output.splitlines():
        s = line.strip()
        if s == "Registered applications:":
            in_registered = True
        elif in_registered:
            if s.endswith(".desktop"):
                apps.append(s)
            elif s:
                break  # reached "Default application:" or next section
    return apps


def _scan_desktop_dirs(mime: str) -> list[str]:
    """Fallback: scan .desktop files for matching MimeType entry."""
    apps: list[str] = []
    seen: set[str] = set()
    for d in _app_dirs():
        if not d.is_dir():
            continue
        for fp in d.glob("*.desktop"):
            if fp.name in seen:
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
                for line in text.splitlines():
                    if line.startswith("MimeType="):
                        if mime in line[9:].split(";"):
                            apps.append(fp.name)
                            seen.add(fp.name)
                        break
            except OSError:
                pass
    return apps


def _desktop_name(desktop_file: str) -> str:
    from pbrenamer.i18n import current_language

    lang = current_language()
    for d in _app_dirs():
        fp = d / desktop_file
        if not fp.is_file():
            continue
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        names = _desktop_names(text)
        if names:
            return _pick_localized(names, lang)
    return ""


def _desktop_names(text: str) -> dict[str, str]:
    """Map locale suffix -> Name value from the [Desktop Entry] group
    ('' = unlocalized)."""
    names: dict[str, str] = {}
    in_entry = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            if in_entry:
                break  # left [Desktop Entry] for the next group
            in_entry = s == "[Desktop Entry]"
            continue
        if not in_entry:
            continue
        key, sep, value = s.partition("=")
        if not sep:
            continue
        key = key.strip()
        if key == "Name":
            names[""] = value.strip()
        elif key.startswith("Name[") and key.endswith("]"):
            names[key[5:-1]] = value.strip()
    return names


def _pick_localized(names: dict[str, str], lang: str) -> str:
    """Best Name for lang: exact locale, then bare language, then unlocalized."""
    for key in (lang, lang.split("_")[0]):
        if names.get(key):
            return names[key]
    return names.get("", "")


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------


def _launch(desktop_file: str, path: Path) -> None:
    try:
        subprocess.Popen(["gtk-launch", desktop_file, str(path)])
        return
    except FileNotFoundError:
        pass
    _exec_via_desktop(desktop_file, path)


def _exec_via_desktop(desktop_file: str, path: Path) -> None:
    for d in _app_dirs():
        fp = d / desktop_file
        if not fp.is_file():
            continue
        try:
            for line in fp.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("Exec="):
                    cmd = _build_cmd(line[5:].strip(), path)
                    subprocess.Popen(cmd)
                    return
        except OSError:
            pass


def _build_cmd(exec_val: str, path: Path) -> list[str]:
    parts = shlex.split(exec_val)
    result: list[str] = []
    for part in parts:
        if part in ("%f", "%F", "%u", "%U"):
            result.append(str(path))
        elif part.startswith("%"):
            pass
        else:
            result.append(part)
    if str(path) not in result:
        result.append(str(path))
    return result


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


class _AppChooserDialog(QDialog):
    def __init__(self, apps: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Open with"))
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_("Choose an application:")))

        self._list = QListWidget()
        for name, desktop_file in apps:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, desktop_file)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)
        self._list.itemActivated.connect(self._on_activate)
        layout.addWidget(self._list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_activate(self, _item) -> None:
        self.accept()

    def selected_desktop_file(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None
