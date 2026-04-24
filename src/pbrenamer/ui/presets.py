"""Pattern presets — JSON persistence in the platform config directory.

search.json  : list of {"mode": str, "pattern": str} objects, most recent first.
replace.json : list of strings, most recent first.
History is LRU: the most recently used entry is at the top.
"""

from __future__ import annotations

import json
from pathlib import Path

from pbrenamer.platform import AppDirs

_CONFIG_DIR = AppDirs("pbrenamer").config_home / "patterns"

_SEARCH_MODES = {"pattern", "regex", "plain"}

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
        self._write_search(entries)

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
        self._write_replace(entries)

    def set_replace(self, entries: list[str]) -> None:
        """Overwrite the entire replace history with *entries*."""
        self._write_replace([e for e in entries if e])
