"""One-time migrations into profiles, run when ``profiles/`` is created.

- ``migrate_v1`` copies the PBRenamer 1.x settings (pattern presets, sidecar
  configuration, last directory, toolbar state) into the ``default`` profile.
  The original files are left in place.
- ``import_pbpicat`` turns each PBPicat catalogue into a profile.  The
  PBPicat directory is only read, never modified.

Not imported from PBPicat: window geometries (PBPicat's own windows), the
language (global in PBRenamer), ``global_settings.json`` (defaults for new
catalogues) and ``catalog.conf`` (the last profile stays ``default``).
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path

from PySide6.QtCore import QSettings

from pbrenamer import profiles

_log = logging.getLogger(__name__)

_CONF_FILE = "pbrenamer.conf"
_PATTERN_FILES = ("search.json", "replace.json", "saves.json")
_SIDECAR_FILE = "sidecar_config.json"
_OPEN_WITH_FILE = "open_with.json"

# PBPicat settings.json keys copied as is into a profile.json section.
_SECTION_KEYS = {
    "display": ("thumbnail_max_width", "thumbnail_max_height", "history_max"),
    "images": (
        "zoom_step_percent",
        "zoom_max_percent",
        "delete_empty_sidecars",
        "delete_list_max_files",
        "confirm_deletions",
        "use_trash",
        "exif_auto_rotate",
        "metadata_panel_side",
    ),
}
# PBPicat settings.json key → profile.json "schema" key.
_SCHEMA_KEYS = {
    "schema_field_count": "field_count",
    "schema_field_titles": "field_titles",
    "video_marker": "video_marker",
    "last_dest": "dest",
}
# PBPicat app.conf key → pbrenamer.conf key (global viewer options).
_VIEWER_KEYS = {
    "image_viewer/circular_navigation": "viewer/circular_navigation",
    "image_viewer/metadata_panel_visible": "viewer/metadata_panel_visible",
}


def _ini(path: Path) -> QSettings:
    return QSettings(str(path), QSettings.Format.IniFormat)


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _to_bool(value: object) -> bool | None:
    text = str(value).lower()
    if text in ("true", "1", "yes"):
        return True
    if text in ("false", "0", "no"):
        return False
    return None


def _to_int(value: object) -> int | None:
    try:
        return int(str(value))
    except ValueError:
        return None


# ── PBRenamer 1.x ─────────────────────────────────────────────────────────────


def migrate_v1(config_home: Path, profile_dir: Path) -> None:
    """Copy the 1.x settings of *config_home* into the profile *profile_dir*."""
    profile_dir.mkdir(parents=True, exist_ok=True)
    for name in _PATTERN_FILES:
        src = config_home / "patterns" / name
        if src.is_file():
            (profile_dir / "patterns").mkdir(exist_ok=True)
            shutil.copy2(src, profile_dir / "patterns" / name)
    if (config_home / _SIDECAR_FILE).is_file():
        shutil.copy2(config_home / _SIDECAR_FILE, profile_dir / _SIDECAR_FILE)

    data = profiles.merge_defaults({})
    conf = config_home / _CONF_FILE
    if conf.is_file():
        qs = _ini(conf)
        data["last_dir"] = str(qs.value("behaviour/last_dir", ""))
        try:
            toolbar_state = json.loads(str(qs.value("behaviour/toolbar_state", "")))
        except ValueError:
            toolbar_state = None
        if isinstance(toolbar_state, dict):
            data["toolbar_state"] = toolbar_state
    profiles.write_profile(profile_dir, data)


# ── PBPicat ───────────────────────────────────────────────────────────────────


def _profile_name(catalogue: str, profiles_root: Path) -> str:
    """Return a free, valid profile name for the PBPicat *catalogue*."""
    lead = catalogue[0] if catalogue[0] in ".-" else ""
    body = re.sub(r"[^\w-]", "_", catalogue[len(lead) :]) or "_"
    name = lead + body
    if not (profiles_root / name).exists():
        return name
    name = f"{lead}pbpicat-{body}"
    candidate, n = name, 2
    while (profiles_root / candidate).exists():
        candidate, n = f"{name}-{n}", n + 1
    return candidate


def _extensions(values: object) -> list[str] | None:
    """Return PBPicat's dotted extensions without the dot, lower case."""
    if not isinstance(values, list):
        return None
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip("."):
            ext = value.lstrip(".").lower()
            if ext not in result:
                result.append(ext)
    return result


def _catalogue_profile(settings: dict, ui: QSettings | None) -> dict:
    """Return the profile.json data of a PBPicat catalogue."""
    raw: dict = {"mode": "schema", "schema": {}}
    for key, target in _SCHEMA_KEYS.items():
        if key in settings:
            raw["schema"][target] = settings[key]
    titles = raw["schema"].get("field_titles")
    if isinstance(titles, list) and not all(isinstance(t, str) for t in titles):
        del raw["schema"]["field_titles"]
    for section, keys in _SECTION_KEYS.items():
        raw[section] = {k: settings[k] for k in keys if k in settings}
    # PBPicat always shows thumbnails, the sidecar column and the sidecar
    # filter, and deletes empty sidecars unless told otherwise.
    raw["display"].update(thumbnails=True, sidecar_column=True, sidecar_filter=True)
    raw["images"].setdefault("delete_empty_sidecars", True)
    new_ext = settings.get("sidecar_new_extension")
    if isinstance(new_ext, str) and new_ext.strip("."):
        raw["images"]["sidecar_new_extension"] = new_ext.lstrip(".")
    if ui is not None:
        pos = _to_int(ui.value("schema/video_marker_pos", ""))
        if pos is not None:
            raw["schema"]["video_marker_pos"] = pos
        fill_gaps = _to_bool(ui.value("schema/fill_number_gaps", ""))
        if fill_gaps is not None:
            raw["schema"]["fill_gaps"] = fill_gaps
        last_dir = ui.value("source/last_dir", "")
        if last_dir:
            raw["last_dir"] = str(last_dir)
    return profiles.merge_defaults(raw)


def _catalogue_sidecars(settings: dict) -> dict:
    """Return the sidecar_config.json data of a PBPicat catalogue.

    PBPicat lists images and videos only, with one sidecar list for both.
    """
    data: dict = {}
    base = {
        category: exts
        for category, key in (
            ("image", "image_extensions"),
            ("video", "video_extensions"),
        )
        if (exts := _extensions(settings.get(key))) is not None
    }
    if base:
        data["base_extensions"] = base
    suffixes = _extensions(settings.get("sidecar_extensions"))
    if suffixes is not None:
        data["own_suffixes"] = {"image": suffixes, "video": list(suffixes)}
    return data


def _import_catalogue(catalogue: Path, profile_dir: Path) -> None:
    settings = _read_json(catalogue / "settings.json")
    if not isinstance(settings, dict):
        settings = {}
    ui_conf = catalogue / "ui.conf"
    ui = _ini(ui_conf) if ui_conf.is_file() else None
    profiles.write_profile(profile_dir, _catalogue_profile(settings, ui))
    sidecars = _catalogue_sidecars(settings)
    if sidecars:
        _write_json(profile_dir / _SIDECAR_FILE, sidecars)
    history = profiles.clean_history(_read_json(catalogue / "history.json"))
    if history:
        _write_json(profile_dir / profiles.HISTORY_FILE, history)


def _import_globals(src: Path, config_home: Path) -> None:
    open_with = _read_json(src / _OPEN_WITH_FILE)
    dest = config_home / _OPEN_WITH_FILE
    if (
        isinstance(open_with, dict)
        and all(
            isinstance(v, list) and all(isinstance(x, str) for x in v)
            for v in open_with.values()
        )
        and not dest.exists()
    ):
        _write_json(dest, open_with)
    if (src / "app.conf").is_file():
        app = _ini(src / "app.conf")
        conf = _ini(config_home / _CONF_FILE)
        for key, target in _VIEWER_KEYS.items():
            value = _to_bool(app.value(key, ""))
            if value is not None:
                conf.setValue(target, value)
        conf.sync()


def import_pbpicat(src: Path, profiles_root: Path, config_home: Path) -> list[str]:
    """Import every PBPicat catalogue of *src* as a profile under
    *profiles_root*, and PBPicat's global options into *config_home*.

    Return the names of the profiles created.
    """
    created = []
    for catalogue in sorted(p for p in src.iterdir() if p.is_dir()):
        name = _profile_name(catalogue.name, profiles_root)
        _import_catalogue(catalogue, profiles_root / name)
        _log.info("Imported PBPicat catalogue %r as profile %r", catalogue.name, name)
        created.append(name)
    _import_globals(src, config_home)
    return created
