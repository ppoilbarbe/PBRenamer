"""Pattern presets — JSON persistence in the platform config directory.

search.json  : list of {"mode": str, "pattern": str} objects, most recent first.
replace.json : list of strings, most recent first.
saves.json   : list of {"name": str, ...config} objects, most recent first.
All three lists are LRU-managed: the most recently used entry is at the top.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pbrenamer.platform import AppDirs

_CONFIG_DIR = AppDirs("pbrenamer").config_home / "patterns"

_SEARCH_MODES = {"pattern", "regex", "plain"}
_SAVE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

_MAX_HISTORY = 20

_SEARCH_DEFAULTS: list[tuple[str, str]] = [("pattern", "{X}")]
_REPLACE_DEFAULTS: list[str] = ["{1}"]


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


class PatternPresets:
    def __init__(self, config_dir: Path = _CONFIG_DIR) -> None:
        self._dir = config_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _read_search_raw(self) -> list[tuple[str, str]]:
        data = _read_json(self._dir / "search.json")
        if not isinstance(data, list):
            return []
        result = []
        for item in data:
            if (
                isinstance(item, dict)
                and isinstance(item.get("mode"), str)
                and item["mode"] in _SEARCH_MODES
                and isinstance(item.get("pattern"), str)
                and item["pattern"]
            ):
                result.append((item["mode"], item["pattern"]))
        return result

    def _write_search(self, entries: list[tuple[str, str]]) -> None:
        data = [{"mode": m, "pattern": p} for m, p in entries]
        (self._dir / "search.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _read_replace_raw(self) -> list[str]:
        data = _read_json(self._dir / "replace.json")
        if not isinstance(data, list):
            return []
        return [e for e in data if isinstance(e, str) and e]

    def _write_replace(self, entries: list[str]) -> None:
        (self._dir / "replace.json").write_text(
            json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── Search ────────────────────────────────────────────────────────────────

    def get_search(self) -> list[tuple[str, str]]:
        """Return saved search entries as (mode, pattern) pairs, most recent first."""
        result = self._read_search_raw()
        return result if result else list(_SEARCH_DEFAULTS)

    def add_search(self, mode: str, pattern: str) -> None:
        """Promote an existing entry or prepend a new one (LRU), then save."""
        if mode not in _SEARCH_MODES or not pattern:
            return
        entries = self._read_search_raw()
        entries = [(m, p) for m, p in entries if not (m == mode and p == pattern)]
        entries.insert(0, (mode, pattern))
        self._write_search(entries[:_MAX_HISTORY])

    def set_search(self, entries: list[tuple[str, str]]) -> None:
        """Overwrite the entire search history with *entries*."""
        self._write_search([(m, p) for m, p in entries if m in _SEARCH_MODES and p])

    # ── Replace ───────────────────────────────────────────────────────────────

    def get_replace(self) -> list[str]:
        """Return saved replacement patterns, most recent first."""
        result = self._read_replace_raw()
        return result if result else list(_REPLACE_DEFAULTS)

    def add_replace(self, pattern: str) -> None:
        """Promote an existing entry or prepend a new one (LRU), then save."""
        if not pattern:
            return
        entries = self._read_replace_raw()
        entries = [e for e in entries if e != pattern]
        entries.insert(0, pattern)
        self._write_replace(entries[:_MAX_HISTORY])

    def set_replace(self, entries: list[str]) -> None:
        """Overwrite the entire replace history with *entries*."""
        self._write_replace([e for e in entries if e])

    # ── Named saves ───────────────────────────────────────────────────────────

    def _read_saves_raw(self) -> list[tuple[str, dict]]:
        """Return [(name, config)] in LRU order (most recent first).

        Supports both the new list format and the legacy dict format.
        """
        data = _read_json(self._dir / "saves.json")
        if isinstance(data, list):
            result = []
            seen: set[str] = set()
            for item in data:
                if not isinstance(item, dict):
                    continue
                name = item.get("name", "")
                if not isinstance(name, str) or not _SAVE_NAME_RE.match(name):
                    continue
                if name in seen:
                    continue
                seen.add(name)
                result.append((name, {k: v for k, v in item.items() if k != "name"}))
            return result
        # Legacy dict format — migrate transparently
        if isinstance(data, dict):
            return [
                (name, cfg)
                for name, cfg in data.items()
                if isinstance(name, str)
                and _SAVE_NAME_RE.match(name)
                and isinstance(cfg, dict)
            ]
        return []

    def _write_saves(self, entries: list[tuple[str, dict]]) -> None:
        data = [{"name": name, **config} for name, config in entries]
        (self._dir / "saves.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get_saves(self) -> dict[str, dict]:
        """Return all named saves as {name: config_dict} in LRU order."""
        return dict(self._read_saves_raw())

    def set_save(self, name: str, config: dict) -> None:
        """Create or overwrite *name* with *config* (LRU: moves to front)."""
        if not _SAVE_NAME_RE.match(name):
            return
        entries = [(n, c) for n, c in self._read_saves_raw() if n != name]
        entries.insert(0, (name, config))
        self._write_saves(entries)

    def use_save(self, name: str) -> None:
        """Promote *name* to the front of the LRU list without changing its config."""
        entries = self._read_saves_raw()
        for i, (n, c) in enumerate(entries):
            if n == name:
                entries.pop(i)
                entries.insert(0, (n, c))
                self._write_saves(entries)
                return

    def delete_save(self, name: str) -> None:
        """Delete the named save *name* (no-op if not found)."""
        entries = self._read_saves_raw()
        new_entries = [(n, c) for n, c in entries if n != name]
        if len(new_entries) < len(entries):
            self._write_saves(new_entries)
