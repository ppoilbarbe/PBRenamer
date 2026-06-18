"""Persistent window geometry and splitter positions."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pbrenamer.platform import AppDirs

_log = logging.getLogger(__name__)

_STATE_FILE = AppDirs("pbrenamer").config_home / "window_state.json"


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
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ── Dialog geometry ───────────────────────────────────────────────────────

    def save_geometry(self, key: str, x: int, y: int, w: int, h: int) -> None:
        raw = self._load_raw()
        raw[key] = {"x": x, "y": y, "w": w, "h": h}
        self._write(raw)
        _log.debug("save_geometry [%s] x=%d y=%d w=%d h=%d", key, x, y, w, h)

    def load_geometry(self, key: str) -> tuple[int, int, int, int] | None:
        raw = self._load_raw()
        d = raw.get(key)
        if not isinstance(d, dict):
            _log.debug("load_geometry [%s] → not found", key)
            return None
        try:
            result = int(d["x"]), int(d["y"]), int(d["w"]), int(d["h"])
            _log.debug("load_geometry [%s] x=%d y=%d w=%d h=%d", key, *result)
            return result
        except (KeyError, TypeError, ValueError):
            _log.debug("load_geometry [%s] → corrupt data: %r", key, d)
            return None

    # ── MainWindow state (geometry + two splitters) ───────────────────────────

    def save(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        splitter_main: list[int],
        splitter_right: list[int],
    ) -> None:
        raw = self._load_raw()
        raw["main"] = {
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "splitter_main": list(splitter_main),
            "splitter_right": list(splitter_right),
        }
        self._write(raw)
        _log.debug(
            "save [main] x=%d y=%d w=%d h=%d splitter_main=%s splitter_right=%s",
            x,
            y,
            w,
            h,
            list(splitter_main),
            list(splitter_right),
        )

    def load(
        self,
    ) -> tuple[tuple[int, int, int, int] | None, list[int] | None, list[int] | None]:
        raw = self._load_raw()
        d = raw.get("main")
        if not isinstance(d, dict):
            _log.debug("load [main] → not found")
            return None, None, None
        try:
            geo = (int(d["x"]), int(d["y"]), int(d["w"]), int(d["h"]))
            sm = [int(v) for v in d["splitter_main"]]
            sr = [int(v) for v in d["splitter_right"]]
            _log.debug(
                "load [main] x=%d y=%d w=%d h=%d splitter_main=%s splitter_right=%s",
                *geo,
                sm,
                sr,
            )
            return geo, sm, sr
        except (KeyError, TypeError, ValueError):
            _log.debug("load [main] → corrupt data: %r", d)
            return None, None, None
