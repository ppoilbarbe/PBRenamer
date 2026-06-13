"""Tests for pbrenamer.ui.window_state — WindowState persistence."""

from __future__ import annotations

import json

from PySide6.QtCore import QByteArray

from pbrenamer.ui.window_state import WindowState


def _dummy_ba(content: str = "cafebabe") -> QByteArray:
    return QByteArray(bytes.fromhex(content))


class TestLoadRaw:
    def test_returns_empty_when_file_absent(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        assert ws._load_raw() == {}

    def test_returns_empty_on_invalid_json(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("not json", encoding="utf-8")
        ws = WindowState(p)
        assert ws._load_raw() == {}

    def test_returns_empty_on_oserror(self, tmp_path):
        p = tmp_path / "state.json"
        p.mkdir()  # directory instead of file → OSError on read_text
        ws = WindowState(p)
        assert ws._load_raw() == {}

    def test_returns_parsed_dict(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(json.dumps({"geometry": "deadbeef"}), encoding="utf-8")
        ws = WindowState(p)
        assert ws._load_raw() == {"geometry": "deadbeef"}


class TestSaveAndLoad:
    def test_round_trip(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        geo = _dummy_ba("aabbcc")
        sm = _dummy_ba("112233")
        sr = _dummy_ba("445566")
        ws.save(geo, sm, sr)
        g2, m2, r2 = ws.load()
        assert bytes(g2) == bytes(geo)
        assert bytes(m2) == bytes(sm)
        assert bytes(r2) == bytes(sr)

    def test_load_returns_none_triple_when_absent(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        assert ws.load() == (None, None, None)

    def test_load_returns_none_for_missing_keys(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("{}", encoding="utf-8")
        ws = WindowState(p)
        assert ws.load() == (None, None, None)

    def test_load_returns_none_on_corrupt_hex(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(
            json.dumps(
                {"geometry": "ZZ", "splitter_main": "00", "splitter_right": "00"}
            ),
            encoding="utf-8",
        )
        ws = WindowState(p)
        assert ws.load() == (None, None, None)

    def test_save_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "nested" / "deep" / "state.json"
        ws = WindowState(p)
        ws.save(_dummy_ba(), _dummy_ba(), _dummy_ba())
        assert p.exists()

    def test_save_preserves_existing_keys(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        ws.save_geometry("mywin", _dummy_ba("aabb"))
        ws.save(_dummy_ba(), _dummy_ba(), _dummy_ba())
        data = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        assert "dialogs" in data


class TestDialogGeometry:
    def test_save_and_load_geometry(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        geo = _dummy_ba("deadbeef")
        ws.save_geometry("about", geo)
        loaded = ws.load_geometry("about")
        assert bytes(loaded) == bytes(geo)

    def test_load_geometry_returns_none_when_absent(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        assert ws.load_geometry("missing") is None

    def test_load_geometry_returns_none_when_no_dialogs_key(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("{}", encoding="utf-8")
        ws = WindowState(p)
        assert ws.load_geometry("x") is None

    def test_multiple_dialog_keys(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        ws.save_geometry("win1", _dummy_ba("aabb"))
        ws.save_geometry("win2", _dummy_ba("ccdd"))
        assert bytes(ws.load_geometry("win1")) == bytes.fromhex("aabb")
        assert bytes(ws.load_geometry("win2")) == bytes.fromhex("ccdd")

    def test_overwrite_geometry(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        ws.save_geometry("win", _dummy_ba("aabb"))
        ws.save_geometry("win", _dummy_ba("eeff"))
        assert bytes(ws.load_geometry("win")) == bytes.fromhex("eeff")
