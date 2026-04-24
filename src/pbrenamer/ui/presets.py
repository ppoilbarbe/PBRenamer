"""Pattern presets — file-based persistence in the platform config directory.

Search entries are stored as ``mode<TAB>pattern`` (one per line).
Replace entries are stored as plain text (one per line).
History is LRU: the most recently used entry is at the top.
When writing, only valid entries are kept; unreadable lines are dropped.
"""

from __future__ import annotations

from pathlib import Path

from pbrenamer.platform import AppDirs

_CONFIG_DIR = AppDirs("pbrenamer").config_home / "patterns"

_SEARCH_MODES = {"pattern", "regex", "plain"}

_SEARCH_DEFAULTS: list[tuple[str, str]] = [("pattern", "{X}")]
_REPLACE_DEFAULTS: list[str] = ["{1}"]


class PatternPresets:
    def __init__(self, config_dir: Path = _CONFIG_DIR) -> None:
        self._dir = config_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _read_search_raw(self) -> list[tuple[str, str]]:
        p = self._dir / "search"
        if not p.exists():
            return []
        result: list[tuple[str, str]] = []
        for raw in p.read_text(encoding="utf-8").splitlines():
            parts = raw.split("\t", 1)
            if len(parts) == 2 and parts[0] in _SEARCH_MODES and parts[1]:
                result.append((parts[0], parts[1]))
        return result

    def _write_search(self, entries: list[tuple[str, str]]) -> None:
        with (self._dir / "search").open("w", encoding="utf-8") as fh:
            for mode, pattern in entries:
                fh.write(f"{mode}\t{pattern}\n")

    def _read_replace_raw(self) -> list[str]:
        p = self._dir / "replace"
        if not p.exists():
            return []
        lines = p.read_text(encoding="utf-8").splitlines()
        return [ln for ln in (ln.strip() for ln in lines) if ln]

    def _write_replace(self, entries: list[str]) -> None:
        with (self._dir / "replace").open("w", encoding="utf-8") as fh:
            for pattern in entries:
                fh.write(pattern + "\n")

    # ── Search ────────────────────────────────────────────────────────────────

    def get_search(self) -> list[tuple[str, str]]:
        """Return saved search entries as (mode, pattern) pairs, most recent first.

        Falls back to defaults when the file is absent or yields no valid entry.
        """
        result = self._read_search_raw()
        return result if result else list(_SEARCH_DEFAULTS)

    def add_search(self, mode: str, pattern: str) -> None:
        """Promote an existing entry or prepend a new one (LRU), then rewrite the file.

        Unreadable lines in the previous file are silently dropped on rewrite.
        """
        if mode not in _SEARCH_MODES or not pattern:
            return
        entries = self._read_search_raw()
        entries = [(m, p) for m, p in entries if not (m == mode and p == pattern)]
        entries.insert(0, (mode, pattern))
        self._write_search(entries)

    # ── Replace ───────────────────────────────────────────────────────────────

    def get_replace(self) -> list[str]:
        """Return saved replacement patterns, most recent first.

        Falls back to defaults when the file is absent or yields no valid entry.
        """
        result = self._read_replace_raw()
        return result if result else list(_REPLACE_DEFAULTS)

    def add_replace(self, pattern: str) -> None:
        """Promote an existing entry or prepend a new one (LRU), then rewrite the file.

        Unreadable lines in the previous file are silently dropped on rewrite.
        """
        if not pattern:
            return
        entries = self._read_replace_raw()
        entries = [e for e in entries if e != pattern]
        entries.insert(0, pattern)
        self._write_replace(entries)
