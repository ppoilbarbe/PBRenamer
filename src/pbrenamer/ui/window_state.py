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

    def save(
        self,
        geometry: QByteArray,
        splitter_main: QByteArray,
        splitter_right: QByteArray,
    ) -> None:
        data = {
            "geometry": _encode(geometry),
            "splitter_main": _encode(splitter_main),
            "splitter_right": _encode(splitter_right),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data), encoding="utf-8")

    def load(
        self,
    ) -> tuple[QByteArray | None, QByteArray | None, QByteArray | None]:
        if not self._path.exists():
            return None, None, None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            geometry = _decode(data["geometry"]) if "geometry" in data else None
            splitter_main = (
                _decode(data["splitter_main"]) if "splitter_main" in data else None
            )
            splitter_right = (
                _decode(data["splitter_right"]) if "splitter_right" in data else None
            )
            return geometry, splitter_main, splitter_right
        except (OSError, json.JSONDecodeError, ValueError, KeyError):
            return None, None, None
