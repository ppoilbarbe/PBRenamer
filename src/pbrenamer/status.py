"""Configuration status printed by ``--status``.

The status is a YAML document in English (never translated) so that scripts
can parse it whatever the interface language: the version, the application
settings and those of every visible profile (hidden profiles are left out).
The YAML is written by a small emitter: strings are double-quoted (JSON
escaping, valid YAML), so no value is ever reinterpreted as a number, a
boolean or null.
"""

from __future__ import annotations

import json
import re
import sys

_PLAIN_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def collect() -> dict:
    """Return the configuration status: the application settings and those
    of every visible profile.  ``selected_profile`` is the current profile
    (the one chosen with --profile, else the default profile)."""
    from pbrenamer import __version__, i18n, profiles, settings

    selected = profiles.current()
    try:
        by_name = {}
        for name in profiles.list_profiles():
            # The sidecar settings are read from the current profile.
            profiles.use(name, remember=False)
            by_name[name] = _profile_status(name)
    finally:
        profiles.use(selected, remember=False)
    return {
        "version": __version__,
        "python": sys.version.split()[0],
        "config_dir": str(settings.config_home()),
        "application": {
            "language": i18n.get_language_override() or None,
            "log_level": settings.get_log_level(),
            "selected_profile": selected,
            "default_profile": profiles.get_default() or None,
            "last_used_profile": profiles.last_used() or None,
            "restore_last_dir": settings.get_restore_last_dir(),
            "restore_toolbar_state": settings.get_restore_toolbar_state(),
            "preview_delay_ms": settings.get_preview_delay(),
            "viewer": {
                "circular_navigation": settings.get_viewer_circular(),
                "metadata_panel_visible": settings.get_viewer_metadata_visible(),
            },
            "shortcuts": [
                {"name": label, "path": path}
                for label, path in settings.get_shortcuts()
            ],
            "extension_normalization": [
                {"from": src, "to": dst}
                for src, dst in settings.get_extension_normalization()
            ],
        },
        "profiles": by_name,
    }


def _profile_status(name: str) -> dict:
    """Return the settings of the current profile *name*."""
    from pbrenamer import profiles, settings
    from pbrenamer.ui.presets import PatternPresets

    sidecars = settings.get_sidecar_config()
    return {
        "dir": str(profiles.profile_dir(name)),
        **profiles.load(),
        "sidecars": {
            "base_extensions": {
                category: sorted(exts)
                for category, exts in sidecars.base_extensions.items()
            },
            "own_suffixes": {
                category: sorted(sufs)
                for category, sufs in sidecars.own_suffixes.items()
            },
            "common_suffixes": sorted(sidecars.common_suffixes),
        },
        "saves": list(PatternPresets().get_saves()),
    }


def _scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    return json.dumps(str(value), ensure_ascii=False)


def _key(key: object) -> str:
    text = str(key)
    if _PLAIN_KEY.match(text) and text not in ("true", "false", "null"):
        return text
    return json.dumps(text, ensure_ascii=False)


def _emit(value: object, indent: int, lines: list[str]) -> None:
    """Append the block lines of the non-empty mapping or list *value*."""
    pad = "  " * indent
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, dict | list) and item:
                lines.append(f"{pad}{_key(key)}:")
                _emit(item, indent + 1, lines)
            else:
                lines.append(f"{pad}{_key(key)}: {_inline(item)}")
        return
    for item in value:
        if isinstance(item, dict | list) and item:
            nested: list[str] = []
            _emit(item, indent + 1, nested)
            # The first line goes after the dash, the others keep their indent.
            lines.append(f"{pad}- {nested[0].lstrip()}")
            lines.extend(nested[1:])
        else:
            lines.append(f"{pad}- {_inline(item)}")


def _inline(value: object) -> str:
    if isinstance(value, dict):
        return "{}"
    if isinstance(value, list):
        return "[]"
    return _scalar(value)


def to_yaml(data: dict) -> str:
    """Return *data* (mappings, lists and scalars) as a YAML document."""
    lines: list[str] = []
    _emit(data, 0, lines)
    return "\n".join(lines) + "\n"
