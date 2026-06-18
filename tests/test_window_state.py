"""Tests for pbrenamer.ui.window_state — WindowState persistence."""

from __future__ import annotations

import json

from pbrenamer.ui.window_state import WindowState


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
        p.write_text(
            json.dumps({"main": {"x": 0, "y": 0, "w": 800, "h": 600}}), encoding="utf-8"
        )
        ws = WindowState(p)
        assert ws._load_raw()["main"]["w"] == 800


class TestSaveAndLoad:
    def test_round_trip(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        ws.save(10, 20, 800, 600, [300, 500], [200, 150])
        geo, sm, sr = ws.load()
        assert geo == (10, 20, 800, 600)
        assert sm == [300, 500]
        assert sr == [200, 150]

    def test_load_returns_none_triple_when_absent(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        assert ws.load() == (None, None, None)

    def test_load_returns_none_for_missing_keys(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("{}", encoding="utf-8")
        ws = WindowState(p)
        assert ws.load() == (None, None, None)

    def test_load_returns_none_on_corrupt_data(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(
            json.dumps(
                {
                    "main": {
                        "x": "bad",
                        "y": 0,
                        "w": 800,
                        "h": 600,
                        "splitter_main": [1],
                        "splitter_right": [1],
                    }
                }
            ),
            encoding="utf-8",
        )
        ws = WindowState(p)
        assert ws.load() == (None, None, None)

    def test_save_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "nested" / "deep" / "state.json"
        ws = WindowState(p)
        ws.save(0, 0, 800, 600, [300, 500], [200, 150])
        assert p.exists()

    def test_save_preserves_existing_keys(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        ws.save_geometry("mywin", 10, 20, 300, 200)
        ws.save(0, 0, 800, 600, [300, 500], [200, 150])
        data = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        assert "mywin" in data


class TestDialogGeometry:
    def test_save_and_load_geometry(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        ws.save_geometry("about", 50, 100, 640, 480)
        loaded = ws.load_geometry("about")
        assert loaded == (50, 100, 640, 480)

    def test_load_geometry_returns_none_when_absent(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        assert ws.load_geometry("missing") is None

    def test_load_geometry_returns_none_when_key_absent(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("{}", encoding="utf-8")
        ws = WindowState(p)
        assert ws.load_geometry("x") is None

    def test_multiple_dialog_keys(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        ws.save_geometry("win1", 10, 20, 300, 200)
        ws.save_geometry("win2", 50, 60, 400, 300)
        assert ws.load_geometry("win1") == (10, 20, 300, 200)
        assert ws.load_geometry("win2") == (50, 60, 400, 300)

    def test_overwrite_geometry(self, tmp_path):
        ws = WindowState(tmp_path / "state.json")
        ws.save_geometry("win", 10, 20, 300, 200)
        ws.save_geometry("win", 99, 88, 640, 480)
        assert ws.load_geometry("win") == (99, 88, 640, 480)

    def test_load_geometry_returns_none_on_corrupt_data(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(
            json.dumps({"win": {"x": "bad", "y": 0, "w": 300, "h": 200}}),
            encoding="utf-8",
        )
        ws = WindowState(p)
        assert ws.load_geometry("win") is None
