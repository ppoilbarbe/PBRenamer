"""Application preferences — log level and other non-i18n settings."""

from __future__ import annotations

import logging

from PySide6.QtCore import QSettings

from pbrenamer.platform import AppDirs

_DOMAIN = "pbrenamer"
_dirs = AppDirs(_DOMAIN)
_LOG_LEVEL_KEY = "log/level"
_DEFAULT_LEVEL = "INFO"

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


def apply_log_level(level: str | None = None) -> None:
    """Set the root logger level to *level* (or the saved level if None)."""
    if level is None:
        level = get_log_level()
    logging.getLogger().setLevel(getattr(logging, level, logging.INFO))
