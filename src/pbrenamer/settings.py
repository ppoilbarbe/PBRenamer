"""Application preferences — log level and other non-i18n settings."""

from __future__ import annotations

import json
import logging

from PySide6.QtCore import QSettings

from pbrenamer.platform import AppDirs

_log = logging.getLogger(__name__)

_DOMAIN = "pbrenamer"
_dirs = AppDirs(_DOMAIN)
_LOG_LEVEL_KEY = "log/level"
_DEFAULT_LEVEL = "INFO"
_RESTORE_LAST_DIR_KEY = "behaviour/restore_last_dir"
_LAST_DIR_KEY = "behaviour/last_dir"
_SHORTCUTS_FILE = _dirs.config_home / "shortcuts.json"

LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def _settings() -> QSettings:
    cfg = _dirs.config_home
    cfg.mkdir(parents=True, exist_ok=True)
    return QSettings(str(cfg / f"{_DOMAIN}.conf"), QSettings.Format.IniFormat)


def get_log_level() -> str:
    """Return the saved log level name, defaulting to ``"INFO"``."""
    val = _settings().value(_LOG_LEVEL_KEY, _DEFAULT_LEVEL)
    return val if val in LEVELS else _DEFAULT_LEVEL


def set_log_level(level: str) -> None:
    """Persist *level* to the settings file."""
    if level in LEVELS:
        _settings().setValue(_LOG_LEVEL_KEY, level)


def get_shortcuts() -> list[tuple[str, str]]:
    """Return user-defined directory shortcuts as (display_name, path) pairs."""
    try:
        data = json.loads(_SHORTCUTS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [
        (str(e["name"]), str(e["path"]))
        for e in data
        if isinstance(e, dict)
        and isinstance(e.get("name"), str)
        and isinstance(e.get("path"), str)
        and e["name"]
        and e["path"]
    ]


def set_shortcuts(shortcuts: list[tuple[str, str]]) -> None:
    """Persist user-defined directory shortcuts to shortcuts.json."""
    _SHORTCUTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = [{"name": name, "path": path} for name, path in shortcuts]
    _SHORTCUTS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_restore_last_dir() -> bool:
    """Return True if the app should reopen the last accessed directory."""
    val = _settings().value(_RESTORE_LAST_DIR_KEY, False)
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("true", "1", "yes")


def set_restore_last_dir(enabled: bool) -> None:
    """Persist the restore-last-directory preference."""
    _settings().setValue(_RESTORE_LAST_DIR_KEY, enabled)


def get_last_dir() -> str:
    """Return the last directory accessed, or an empty string if none."""
    return str(_settings().value(_LAST_DIR_KEY, ""))


def set_last_dir(path: str) -> None:
    """Persist the last accessed directory."""
    _settings().setValue(_LAST_DIR_KEY, path)


def apply_log_level(level: str | None = None) -> None:
    """Set the root logger level to *level* (or the saved level if None).

    Passing a level not in LEVELS is silently ignored and the saved preference
    is used instead.
    """
    if level not in LEVELS:
        level = get_log_level()
    numeric = getattr(logging, level, logging.INFO)
    logging.getLogger().setLevel(numeric)
    _log.debug("Log level set to %s", level)
