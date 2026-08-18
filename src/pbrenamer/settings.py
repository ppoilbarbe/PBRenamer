"""Application preferences — log level and other non-i18n settings."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QSettings

from pbrenamer.core import sidecar
from pbrenamer.platform import AppDirs

_log = logging.getLogger(__name__)

_DOMAIN = "pbrenamer"
_dirs = AppDirs(_DOMAIN)
_LOG_LEVEL_KEY = "log/level"
_DEFAULT_LEVEL = "INFO"
_RESTORE_LAST_DIR_KEY = "behaviour/restore_last_dir"
_LAST_DIR_KEY = "behaviour/last_dir"
_RESTORE_TOOLBAR_KEY = "behaviour/restore_toolbar_state"
_TOOLBAR_STATE_KEY = "behaviour/toolbar_state"
_PREVIEW_DELAY_KEY = "behaviour/preview_delay_ms"
_PREVIEW_DELAY_DEFAULT = 500
_PREVIEW_DELAY_MIN = 100
_PREVIEW_DELAY_MAX = 1000
_SHORTCUTS_FILE = _dirs.config_home / "shortcuts.json"
_EXTENSION_NORMALIZATION_FILE = _dirs.config_home / "extension_normalization.json"
_SIDECAR_CONFIG_FILE = _dirs.config_home / "sidecar_config.json"

LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

_DEFAULT_BASE_EXTENSION_LISTS = {
    "image": sidecar.DEFAULT_IMAGE_EXTENSIONS,
    "video": sidecar.DEFAULT_VIDEO_EXTENSIONS,
    "audio": sidecar.DEFAULT_AUDIO_EXTENSIONS,
}
_DEFAULT_OWN_SUFFIX_LISTS = {
    "image": sidecar.DEFAULT_IMAGE_SIDECAR_SUFFIXES,
    "video": sidecar.DEFAULT_VIDEO_SIDECAR_SUFFIXES,
    "audio": sidecar.DEFAULT_AUDIO_SIDECAR_SUFFIXES,
    "other": sidecar.DEFAULT_OTHER_SIDECAR_SUFFIXES,
}


def configure(config_dir: Path | None = None) -> None:
    """Override the configuration directory used by all settings functions.

    Pass ``None`` to restore the platform default. Intended for testing.
    """
    global _dirs, _SHORTCUTS_FILE, _EXTENSION_NORMALIZATION_FILE, _SIDECAR_CONFIG_FILE
    if config_dir is None:
        _dirs = AppDirs(_DOMAIN)
    else:
        _dirs = SimpleNamespace(
            config_home=config_dir,
            data_home=config_dir,
            cache_home=config_dir,
        )
    _SHORTCUTS_FILE = _dirs.config_home / "shortcuts.json"
    _EXTENSION_NORMALIZATION_FILE = _dirs.config_home / "extension_normalization.json"
    _SIDECAR_CONFIG_FILE = _dirs.config_home / "sidecar_config.json"


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


def get_extension_normalization() -> list[tuple[str, str]]:
    """Return user-defined extension normalization pairs as (from_ext, to_ext).

    Both sides exclude the leading dot, matching ``filetools.cut_extension``.
    """
    try:
        data = json.loads(_EXTENSION_NORMALIZATION_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [
        (str(e["from"]), str(e["to"]))
        for e in data
        if isinstance(e, dict)
        and isinstance(e.get("from"), str)
        and isinstance(e.get("to"), str)
        and e["from"]
        and e["to"]
    ]


def set_extension_normalization(pairs: list[tuple[str, str]]) -> None:
    """Persist user-defined extension normalization pairs."""
    _EXTENSION_NORMALIZATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = [{"from": from_ext, "to": to_ext} for from_ext, to_ext in pairs]
    _EXTENSION_NORMALIZATION_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_extension_normalization_map() -> dict[str, str]:
    """Return the normalization table as {from_ext.lower(): to_ext}.

    Ready to pass to ``filetools.apply_extension_mode``.
    """
    return {
        from_ext.lower(): to_ext for from_ext, to_ext in get_extension_normalization()
    }


def get_sidecar_settings() -> dict:
    """Return the raw persisted sidecar config dict, defensively validated.

    A missing/corrupt file, or a malformed individual key, drops just that
    key rather than rejecting the whole file — callers fall back to
    ``core.sidecar``'s defaults for whatever is missing.
    """
    try:
        data = json.loads(_SIDECAR_CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}

    result: dict = {}
    base_extensions = data.get("base_extensions")
    if isinstance(base_extensions, dict):
        result["base_extensions"] = {
            category: [e for e in exts if isinstance(e, str) and e]
            for category, exts in base_extensions.items()
            if category in sidecar.BASE_CATEGORIES and isinstance(exts, list)
        }
    own_suffixes = data.get("own_suffixes")
    if isinstance(own_suffixes, dict):
        result["own_suffixes"] = {
            category: [s for s in sufs if isinstance(s, str) and s]
            for category, sufs in own_suffixes.items()
            if category in sidecar.CATEGORIES and isinstance(sufs, list)
        }
    common_suffixes = data.get("common_suffixes")
    if isinstance(common_suffixes, list):
        result["common_suffixes"] = [
            s for s in common_suffixes if isinstance(s, str) and s
        ]
    return result


def set_sidecar_settings(data: dict) -> None:
    """Persist the full sidecar config dict as-is."""
    _SIDECAR_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SIDECAR_CONFIG_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_sidecar_base_extensions(category: str) -> list[str]:
    """Return the base extensions for *category* ("image"/"video"/"audio")."""
    saved = get_sidecar_settings().get("base_extensions", {})
    if category in saved:
        return list(saved[category])
    return list(_DEFAULT_BASE_EXTENSION_LISTS.get(category, ()))


def set_sidecar_base_extensions(category: str, extensions: list[str]) -> None:
    """Persist the base extensions for *category*."""
    data = get_sidecar_settings()
    base_extensions = dict(data.get("base_extensions", {}))
    base_extensions[category] = list(extensions)
    data["base_extensions"] = base_extensions
    set_sidecar_settings(data)


def get_sidecar_suffixes(category: str) -> list[str]:
    """Return *category*'s own sidecar suffixes (not including the common list)."""
    saved = get_sidecar_settings().get("own_suffixes", {})
    if category in saved:
        return list(saved[category])
    return list(_DEFAULT_OWN_SUFFIX_LISTS.get(category, ()))


def set_sidecar_suffixes(category: str, suffixes: list[str]) -> None:
    """Persist *category*'s own sidecar suffixes."""
    data = get_sidecar_settings()
    own_suffixes = dict(data.get("own_suffixes", {}))
    own_suffixes[category] = list(suffixes)
    data["own_suffixes"] = own_suffixes
    set_sidecar_settings(data)


def get_sidecar_common_suffixes() -> list[str]:
    """Return the sidecar suffixes common to every category."""
    saved = get_sidecar_settings()
    if "common_suffixes" in saved:
        return list(saved["common_suffixes"])
    return list(sidecar.DEFAULT_COMMON_SIDECAR_SUFFIXES)


def set_sidecar_common_suffixes(suffixes: list[str]) -> None:
    """Persist the sidecar suffixes common to every category."""
    data = get_sidecar_settings()
    data["common_suffixes"] = list(suffixes)
    set_sidecar_settings(data)


def restore_sidecar_base_extensions_defaults(category: str) -> None:
    """Reset *category*'s base-extension list to its default."""
    data = get_sidecar_settings()
    base_extensions = dict(data.get("base_extensions", {}))
    base_extensions.pop(category, None)
    data["base_extensions"] = base_extensions
    set_sidecar_settings(data)


def restore_sidecar_suffixes_defaults(category: str) -> None:
    """Reset *category*'s own sidecar-suffix list to its default."""
    data = get_sidecar_settings()
    own_suffixes = dict(data.get("own_suffixes", {}))
    own_suffixes.pop(category, None)
    data["own_suffixes"] = own_suffixes
    set_sidecar_settings(data)


def restore_sidecar_common_suffixes_defaults() -> None:
    """Reset the common sidecar-suffix list to its default (empty)."""
    data = get_sidecar_settings()
    data.pop("common_suffixes", None)
    set_sidecar_settings(data)


def get_sidecar_config() -> sidecar.SidecarConfig:
    """Return the effective sidecar configuration (persisted, falling back
    to ``core.sidecar``'s defaults for anything not customized)."""
    return sidecar.SidecarConfig(
        base_extensions={
            category: frozenset(get_sidecar_base_extensions(category))
            for category in sidecar.BASE_CATEGORIES
        },
        own_suffixes={
            category: frozenset(get_sidecar_suffixes(category))
            for category in sidecar.CATEGORIES
        },
        common_suffixes=frozenset(get_sidecar_common_suffixes()),
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


def get_restore_toolbar_state() -> bool:
    """Return True if the toolbar state should be restored on startup."""
    val = _settings().value(_RESTORE_TOOLBAR_KEY, False)
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("true", "1", "yes")


def set_restore_toolbar_state(enabled: bool) -> None:
    """Persist the restore-toolbar-state preference."""
    _settings().setValue(_RESTORE_TOOLBAR_KEY, enabled)


def get_toolbar_state() -> dict:
    """Return the saved toolbar state dict, or an empty dict."""
    import json as _json

    raw = _settings().value(_TOOLBAR_STATE_KEY, "")
    if not raw:
        return {}
    try:
        data = _json.loads(str(raw))
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def set_toolbar_state(state: dict) -> None:
    """Persist the toolbar state dict."""
    import json as _json

    _settings().setValue(_TOOLBAR_STATE_KEY, _json.dumps(state))


def get_preview_delay() -> int:
    """Return the auto-preview debounce delay in milliseconds (100–1000)."""
    try:
        val = int(_settings().value(_PREVIEW_DELAY_KEY, _PREVIEW_DELAY_DEFAULT))
    except (TypeError, ValueError):
        val = _PREVIEW_DELAY_DEFAULT
    return max(_PREVIEW_DELAY_MIN, min(_PREVIEW_DELAY_MAX, val))


def set_preview_delay(ms: int) -> None:
    """Persist the auto-preview debounce delay."""
    _settings().setValue(
        _PREVIEW_DELAY_KEY,
        max(_PREVIEW_DELAY_MIN, min(_PREVIEW_DELAY_MAX, int(ms))),
    )


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
