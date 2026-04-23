"""Cross-platform application directory resolver.

Dispatches to the right implementation based on ``sys.platform``:
- Windows  : %APPDATA% / %LOCALAPPDATA%
- macOS    : ~/Library/…
- Linux    : Freedesktop XDG Base Directory Specification (v0.8)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------


class _BaseDirs:
    def __init__(self, app_name: str) -> None:
        self._app = app_name

    @property
    def config_home(self) -> Path:
        raise NotImplementedError

    @property
    def data_home(self) -> Path:
        raise NotImplementedError

    @property
    def cache_home(self) -> Path:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


class _WindowsDirs(_BaseDirs):
    @property
    def config_home(self) -> Path:
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / self._app

    @property
    def data_home(self) -> Path:
        return self.config_home

    @property
    def cache_home(self) -> Path:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / self._app


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------


class _MacDirs(_BaseDirs):
    @property
    def config_home(self) -> Path:
        return Path.home() / "Library" / "Preferences" / self._app

    @property
    def data_home(self) -> Path:
        return Path.home() / "Library" / "Application Support" / self._app

    @property
    def cache_home(self) -> Path:
        return Path.home() / "Library" / "Caches" / self._app


# ---------------------------------------------------------------------------
# Linux / XDG
# ---------------------------------------------------------------------------


def _xdg_dir(var: str, default: Path) -> Path:
    """Return the XDG directory for *var*, falling back to *default*.

    Per spec the value is ignored if it is not set, empty, or not absolute.
    """
    val = os.environ.get(var, "")
    p = Path(val) if val else None
    return p if (p and p.is_absolute()) else default


class XdgDirs(_BaseDirs):
    """Freedesktop XDG Base Directory Specification (version 0.8).

    Reference: https://specifications.freedesktop.org/basedir-spec/latest/
    """

    @property
    def config_home(self) -> Path:
        return _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config") / self._app

    @property
    def data_home(self) -> Path:
        return _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share") / self._app

    @property
    def cache_home(self) -> Path:
        return _xdg_dir("XDG_CACHE_HOME", Path.home() / ".cache") / self._app

    @property
    def state_home(self) -> Path:
        return _xdg_dir("XDG_STATE_HOME", Path.home() / ".local" / "state") / self._app

    @property
    def runtime_dir(self) -> Path | None:
        val = os.environ.get("XDG_RUNTIME_DIR", "")
        p = Path(val) if val else None
        return (p / self._app) if (p and p.is_absolute()) else None

    @property
    def config_dirs(self) -> list[Path]:
        val = os.environ.get("XDG_CONFIG_DIRS", "")
        dirs = [Path(p) for p in val.split(":") if p] if val else [Path("/etc/xdg")]
        return [d / self._app for d in dirs if d.is_absolute()]

    @property
    def data_dirs(self) -> list[Path]:
        val = os.environ.get("XDG_DATA_DIRS", "")
        defaults = [Path("/usr/local/share"), Path("/usr/share")]
        dirs = [Path(p) for p in val.split(":") if p] if val else defaults
        return [d / self._app for d in dirs if d.is_absolute()]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def AppDirs(app_name: str) -> _BaseDirs:
    """Return the platform-appropriate application directory object."""
    if sys.platform == "win32":
        return _WindowsDirs(app_name)
    if sys.platform == "darwin":
        return _MacDirs(app_name)
    return XdgDirs(app_name)
