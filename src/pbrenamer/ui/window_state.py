"""Persistent window geometry and splitter positions."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QByteArray

from pbrenamer.platform import AppDirs

_STATE_FILE = AppDirs("pbrenamer").config_home / "window_state.json"


def _encode(ba: QByteArray) -> str:
    return bytes(ba).hex()


def _decode(s: str) -> QByteArray:
    return QByteArray(bytes.fromhex(s))


class WindowState:
    def __init__(self, path: Path = _STATE_FILE) -> None:
        self._path = path

    def _load_raw(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return {}

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data), encoding="utf-8")

    def save(
        self,
        geometry: QByteArray,
        splitter_main: QByteArray,
        splitter_right: QByteArray,
    ) -> None:
        data = self._load_raw()
        data["geometry"] = _encode(geometry)
        data["splitter_main"] = _encode(splitter_main)
        data["splitter_right"] = _encode(splitter_right)
        self._write(data)

    def load(
        self,
    ) -> tuple[QByteArray | None, QByteArray | None, QByteArray | None]:
        data = self._load_raw()
        try:
            geometry = _decode(data["geometry"]) if "geometry" in data else None
            splitter_main = (
                _decode(data["splitter_main"]) if "splitter_main" in data else None
            )
            splitter_right = (
                _decode(data["splitter_right"]) if "splitter_right" in data else None
            )
            return geometry, splitter_main, splitter_right
        except (ValueError, KeyError):
            return None, None, None

    def save_geometry(self, key: str, geometry: QByteArray) -> None:
        """Persist the geometry of a secondary window identified by *key*."""
        data = self._load_raw()
        data.setdefault("dialogs", {})[key] = _encode(geometry)
        self._write(data)

    def load_geometry(self, key: str) -> QByteArray | None:
        """Return the saved geometry for *key*, or None if absent."""
        data = self._load_raw()
        encoded = data.get("dialogs", {}).get(key)
        return _decode(encoded) if encoded else None
