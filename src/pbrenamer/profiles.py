"""Profiles: named sets of per-workflow settings (PBPicat catalogues + presets).

Each profile is a directory ``<config>/profiles/<name>/`` holding::

    profile.json        mode, schema settings, display and image options,
                        last directory, toolbar state
    history.json        input histories ({key: [str, ...]}, PBPicat format)
    sidecar_config.json sidecar categories and suffixes (see ``settings``)
    patterns/           search/replace histories and named saves (``PatternPresets``)

Names starting with ``.`` or ``-`` are hidden: they are not listed by
default and never remembered as the last profile.  At least one visible
profile always exists: ``default`` is (re)created when there is none, and the
last visible profile can be neither deleted nor hidden by a rename.  Apart
from that, ``default`` is a profile like any other.  The ``profiles/`` tree
is created on first access, after migrating the 1.x configuration into
``default`` and importing PBPicat's catalogues (``migration``).
"""

from __future__ import annotations

import copy
import json
import logging
import re
import shutil
from pathlib import Path

from pbrenamer.platform.dirs import pbpicat_config_dir

_log = logging.getLogger(__name__)

DEFAULT = "default"
MODES = ("pattern", "schema")
PROFILE_FILE = "profile.json"
HISTORY_FILE = "history.json"

_NAME_RE = re.compile(r"^\.?[\w-]+$")
# Names typed in the interface: no ".", hidden profiles are not created there.
_NEW_NAME_RE = re.compile(r"^[\w-]+$")
_LAST_KEY = "profiles/last"

DEFAULTS: dict = {
    "mode": "pattern",
    "schema": {
        "field_count": 6,
        "field_titles": [],
        "dest": "",
        "video_marker": "",
        "video_marker_pos": 0,
        "fill_gaps": False,
    },
    "display": {
        "thumbnail_max_width": 128,
        "thumbnail_max_height": 128,
        "history_max": 20,
        "thumbnails": False,
        "sidecar_column": False,
        "sidecar_filter": False,
        "sort_by_date": False,
        "sort_reverse": False,
    },
    "images": {
        "zoom_step_percent": 25,
        "zoom_max_percent": 400,
        "sidecar_new_extension": "xmp",
        "delete_empty_sidecars": False,
        "delete_list_max_files": 12,
        "confirm_deletions": True,
        "use_trash": True,
        "exif_auto_rotate": True,
        "metadata_panel_side": "right",
    },
    "last_dir": "",
    "toolbar_state": {},
}

_current: str | None = None
_pbpicat_source: Path | None = pbpicat_config_dir()


class ProfileError(ValueError):
    """Invalid, missing or protected profile."""


def reset(pbpicat_source: Path | None) -> None:
    """Forget the current profile; the next access re-reads the configuration.

    *pbpicat_source* is the PBPicat directory imported when the profiles are
    created (None: no import).  Called by ``settings.configure``.
    """
    global _current, _pbpicat_source
    _current = None
    _pbpicat_source = pbpicat_source


# ── Names ─────────────────────────────────────────────────────────────────────


def is_valid_name(name: str) -> bool:
    """True if *name* is a valid profile name."""
    return bool(_NAME_RE.match(name))


def validate_name(name: str) -> None:
    """Raise ProfileError if *name* is not a valid profile name."""
    if not is_valid_name(name):
        raise ProfileError(
            _(
                "Invalid profile name “{name}”: use letters, digits, “-” and “_”"
                " (a leading “.” hides the profile)."
            ).format(name=name)
        )


def validate_new_name(name: str) -> None:
    """Raise ProfileError if *name* is not valid for a profile created from
    the interface (letters, digits, "-" and "_" only, no ".")."""
    if not _NEW_NAME_RE.match(name):
        raise ProfileError(
            _(
                "Invalid profile name “{name}”: use letters, digits, “-” and “_”."
            ).format(name=name)
        )


def is_hidden(name: str) -> bool:
    """True if the profile *name* is hidden."""
    return name.startswith((".", "-"))


# ── Profile set ───────────────────────────────────────────────────────────────


def _root() -> Path:
    from pbrenamer import settings

    return settings._dirs.config_home / "profiles"


def _names(root: Path, *, include_hidden: bool = False) -> list[str]:
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir()
        and is_valid_name(p.name)
        and (include_hidden or not is_hidden(p.name))
    )


def fallback(names: list[str]) -> str:
    """Return the profile to select among the visible *names* (not empty):
    ``default`` if present, else the first one."""
    return DEFAULT if DEFAULT in names else names[0]


def _ensure_init() -> None:
    """Create the profile tree on first use, make sure a visible profile
    exists and select the last profile."""
    global _current
    if _current is not None:
        return
    root = _root()
    if not root.is_dir():
        _create_tree(root)
    visible = _names(root)
    if not visible:
        (root / DEFAULT).mkdir(parents=True, exist_ok=True)
        visible = [DEFAULT]
    from pbrenamer import settings

    last = str(settings._settings().value(_LAST_KEY, ""))
    _current = last if last in visible else fallback(visible)


def _create_tree(root: Path) -> None:
    """Build profiles/ from the 1.x configuration and PBPicat's catalogues.

    The tree is assembled next to its final place and renamed at the end,
    so an interrupted migration is simply replayed at the next start.
    """
    from pbrenamer import migration

    tmp = root.with_name(root.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    config_home = root.parent
    migration.migrate_v1(config_home, tmp / DEFAULT)
    if _pbpicat_source is not None and _pbpicat_source.is_dir():
        migration.import_pbpicat(_pbpicat_source, tmp, config_home)
    tmp.rename(root)


def list_profiles(*, include_hidden: bool = False) -> list[str]:
    """Return the sorted profile names (hidden ones only if *include_hidden*)."""
    _ensure_init()
    return _names(_root(), include_hidden=include_hidden)


def exists(name: str) -> bool:
    """True if the profile *name* exists (False for an invalid name)."""
    _ensure_init()
    return is_valid_name(name) and (_root() / name).is_dir()


def _require(name: str) -> None:
    validate_name(name)
    if not exists(name):
        raise ProfileError(_("Profile “{name}” not found.").format(name=name))


def _require_new(name: str) -> None:
    validate_name(name)
    if exists(name):
        raise ProfileError(_("Profile “{name}” already exists.").format(name=name))


def create(name: str) -> None:
    """Create the empty profile *name* (all settings at their defaults)."""
    _require_new(name)
    (_root() / name).mkdir(parents=True)


def duplicate(source: str, name: str) -> None:
    """Create the profile *name* as a copy of *source*."""
    _require(source)
    _require_new(name)
    shutil.copytree(_root() / source, _root() / name)


def _require_other_visible(name: str) -> None:
    """Raise ProfileError if *name* is the only visible profile."""
    if list_profiles() == [name]:
        raise ProfileError(
            _(
                "The profile “{name}” is the last visible profile:"
                " it cannot be deleted or hidden."
            ).format(name=name)
        )


def _forget_last(name: str) -> None:
    """Replace *name*, if remembered as the last profile, by the fallback."""
    from pbrenamer import settings

    if settings._settings().value(_LAST_KEY) == name:
        settings._settings().setValue(_LAST_KEY, fallback(list_profiles()))


def delete(name: str) -> None:
    """Delete the profile *name*, unless it is the last visible one; the
    current profile falls back to ``default`` or the first visible one."""
    global _current
    _require(name)
    _require_other_visible(name)
    shutil.rmtree(_root() / name)
    if _current == name:
        _current = fallback(list_profiles())
    _forget_last(name)


def rename(name: str, new_name: str) -> None:
    """Rename the profile *name* to *new_name* (which must not exist); the
    last visible profile cannot be hidden this way."""
    global _current
    _require(name)
    _require_new(new_name)
    if is_hidden(new_name):
        _require_other_visible(name)
    (_root() / name).rename(_root() / new_name)
    if _current == name:
        _current = new_name
    from pbrenamer import settings

    if settings._settings().value(_LAST_KEY) == name:
        if is_hidden(new_name):
            _forget_last(name)
        else:
            settings._settings().setValue(_LAST_KEY, new_name)


def current() -> str:
    """Return the current profile name."""
    _ensure_init()
    assert _current is not None
    return _current


def use(name: str, *, remember: bool = True) -> None:
    """Make *name* the current profile.

    With *remember* a non-hidden profile becomes the one selected at the
    next start.
    """
    global _current
    _require(name)
    _current = name
    if remember and not is_hidden(name):
        from pbrenamer import settings

        settings._settings().setValue(_LAST_KEY, name)


def profile_dir(name: str | None = None) -> Path:
    """Return the directory of the profile *name* (default: the current one)."""
    return _root() / (name or current())


# ── profile.json ──────────────────────────────────────────────────────────────


def merge_defaults(data: object, defaults: dict = DEFAULTS) -> dict:
    """Return *defaults* overridden by the values of *data* of the same type.

    Nested dicts are merged recursively; keys unknown to *defaults* are kept.
    """
    result = copy.deepcopy(defaults)
    if not isinstance(data, dict):
        return result
    for key, value in data.items():
        if key not in defaults:
            result[key] = value
        elif isinstance(defaults[key], dict):
            result[key] = merge_defaults(value, defaults[key])
        elif type(value) is type(defaults[key]):
            result[key] = value
    return result


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_profile(directory: Path) -> dict:
    """Return the settings stored in the profile *directory*, with defaults."""
    data = merge_defaults(_read_json(directory / PROFILE_FILE))
    if data["mode"] not in MODES:
        data["mode"] = DEFAULTS["mode"]
    return data


def write_profile(directory: Path, data: dict) -> None:
    """Store *data* as the settings of the profile *directory*."""
    _write_json(directory / PROFILE_FILE, data)


def load() -> dict:
    """Return the settings of the current profile."""
    return read_profile(profile_dir())


def save(data: dict) -> None:
    """Store *data* as the settings of the current profile."""
    write_profile(profile_dir(), data)


def get_schema() -> dict:
    """Return the schema settings of the current profile."""
    return load()["schema"]


def set_schema(**values: object) -> None:
    """Update the schema settings of the current profile."""
    data = load()
    data["schema"].update(values)
    save(data)


# ── history.json ──────────────────────────────────────────────────────────────


def clean_history(data: object) -> dict[str, list[str]]:
    """Return the valid entries of a history mapping ({str: [str, ...]})."""
    if not isinstance(data, dict):
        return {}
    return {
        key: [v for v in values if isinstance(v, str)]
        for key, values in data.items()
        if isinstance(key, str) and isinstance(values, list)
    }


def get_all_history() -> dict[str, list[str]]:
    """Return every history of the current profile."""
    return clean_history(_read_json(profile_dir() / HISTORY_FILE))


def get_history(key: str) -> list[str]:
    """Return the history *key* of the current profile, most recent first."""
    return get_all_history().get(key, [])


def set_history(key: str, values: list[str]) -> None:
    """Replace the history *key* of the current profile."""
    data = get_all_history()
    data[key] = list(values)
    _write_json(profile_dir() / HISTORY_FILE, data)
