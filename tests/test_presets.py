"""Tests for pbrenamer.ui.presets — PatternPresets persistence."""

from __future__ import annotations

import json

import pytest

from pbrenamer.ui.presets import _REPLACE_DEFAULTS, _SEARCH_DEFAULTS, PatternPresets


@pytest.fixture
def presets(tmp_path):
    return PatternPresets(tmp_path / "patterns")


class TestReadJsonEdgeCases:
    def test_missing_file_returns_none(self, presets):
        from pbrenamer.ui.presets import _read_json

        result = _read_json(presets._dir / "nonexistent.json")
        assert result is None

    def test_invalid_json_returns_none(self, tmp_path):
        from pbrenamer.ui.presets import _read_json

        p = tmp_path / "bad.json"
        p.write_text("not json", encoding="utf-8")
        assert _read_json(p) is None

    def test_valid_json_returns_parsed(self, tmp_path):
        from pbrenamer.ui.presets import _read_json

        p = tmp_path / "good.json"
        p.write_text("[1, 2, 3]", encoding="utf-8")
        assert _read_json(p) == [1, 2, 3]


class TestGetSearch:
    def test_returns_defaults_when_file_absent(self, presets):
        assert presets.get_search() == list(_SEARCH_DEFAULTS)

    def test_returns_defaults_when_file_not_a_list(self, presets):
        (presets._dir / "search.json").write_text('{"key": "val"}', encoding="utf-8")
        assert presets.get_search() == list(_SEARCH_DEFAULTS)

    def test_returns_saved_entries(self, presets):
        presets.add_search("pattern", "{X}")
        result = presets.get_search()
        assert ("pattern", "{X}") in result

    def test_filters_invalid_mode(self, presets):
        data = [{"mode": "badmode", "pattern": "foo"}]
        (presets._dir / "search.json").write_text(json.dumps(data), encoding="utf-8")
        assert presets.get_search() == list(_SEARCH_DEFAULTS)

    def test_filters_empty_pattern(self, presets):
        data = [{"mode": "pattern", "pattern": ""}]
        (presets._dir / "search.json").write_text(json.dumps(data), encoding="utf-8")
        assert presets.get_search() == list(_SEARCH_DEFAULTS)

    def test_filters_non_dict_entries(self, presets):
        data = ["not-a-dict", 42, None]
        (presets._dir / "search.json").write_text(json.dumps(data), encoding="utf-8")
        assert presets.get_search() == list(_SEARCH_DEFAULTS)


class TestAddSearch:
    def test_prepend_new_entry(self, presets):
        presets.add_search("regex", r"\d+")
        assert presets.get_search()[0] == ("regex", r"\d+")

    def test_promotes_existing_entry(self, presets):
        presets.add_search("pattern", "{X}")
        presets.add_search("regex", r"\d+")
        presets.add_search("pattern", "{X}")
        entries = presets.get_search()
        assert entries[0] == ("pattern", "{X}")
        assert entries.count(("pattern", "{X}")) == 1

    def test_invalid_mode_is_ignored(self, presets):
        presets.add_search("badmode", "test")
        assert presets.get_search() == list(_SEARCH_DEFAULTS)

    def test_empty_pattern_is_ignored(self, presets):
        presets.add_search("pattern", "")
        assert presets.get_search() == list(_SEARCH_DEFAULTS)

    def test_all_valid_modes(self, presets):
        for mode in ("pattern", "regex", "plain"):
            presets.add_search(mode, f"test_{mode}")
        entries = presets.get_search()
        assert any(m == "plain" and p == "test_plain" for m, p in entries)


class TestSetSearch:
    def test_overwrites_all_entries(self, presets):
        presets.add_search("pattern", "{X}")
        presets.set_search([("regex", r"\d+")])
        assert presets.get_search() == [("regex", r"\d+")]

    def test_filters_invalid_mode(self, presets):
        presets.set_search([("badmode", "x"), ("plain", "good")])
        assert presets.get_search() == [("plain", "good")]

    def test_filters_empty_pattern(self, presets):
        presets.set_search([("pattern", ""), ("pattern", "ok")])
        assert presets.get_search() == [("pattern", "ok")]

    def test_empty_list_resets_to_defaults(self, presets):
        presets.add_search("plain", "hello")
        presets.set_search([])
        assert presets.get_search() == list(_SEARCH_DEFAULTS)


class TestGetReplace:
    def test_returns_defaults_when_file_absent(self, presets):
        assert presets.get_replace() == list(_REPLACE_DEFAULTS)

    def test_returns_defaults_when_file_not_a_list(self, presets):
        (presets._dir / "replace.json").write_text("{}", encoding="utf-8")
        assert presets.get_replace() == list(_REPLACE_DEFAULTS)

    def test_filters_empty_strings(self, presets):
        data = ["", "good", ""]
        (presets._dir / "replace.json").write_text(json.dumps(data), encoding="utf-8")
        assert presets.get_replace() == ["good"]

    def test_filters_non_string_entries(self, presets):
        data = [42, None, "valid"]
        (presets._dir / "replace.json").write_text(json.dumps(data), encoding="utf-8")
        assert presets.get_replace() == ["valid"]


class TestAddReplace:
    def test_prepend_new_entry(self, presets):
        presets.add_replace("{1}_{2}")
        assert presets.get_replace()[0] == "{1}_{2}"

    def test_promotes_existing_entry(self, presets):
        presets.add_replace("{1}")
        presets.add_replace("{2}")
        presets.add_replace("{1}")
        entries = presets.get_replace()
        assert entries[0] == "{1}"
        assert entries.count("{1}") == 1

    def test_empty_pattern_is_ignored(self, presets):
        presets.add_replace("")
        assert presets.get_replace() == list(_REPLACE_DEFAULTS)


class TestSetReplace:
    def test_overwrites_all_entries(self, presets):
        presets.add_replace("{1}")
        presets.set_replace(["{A}", "{B}"])
        assert presets.get_replace() == ["{A}", "{B}"]

    def test_filters_empty_strings(self, presets):
        presets.set_replace(["", "ok", ""])
        assert presets.get_replace() == ["ok"]

    def test_empty_list_resets_to_defaults(self, presets):
        presets.add_replace("x")
        presets.set_replace([])
        assert presets.get_replace() == list(_REPLACE_DEFAULTS)


class TestNamedSaves:
    def test_get_saves_returns_empty_when_absent(self, presets):
        assert presets.get_saves() == {}

    def test_set_and_get_save(self, presets):
        config = {"search": "{X}", "replace": "{1}"}
        presets.set_save("mysave", config)
        assert presets.get_saves()["mysave"] == config

    def test_invalid_name_is_rejected(self, presets):
        presets.set_save("bad name!", {"x": 1})
        assert "bad name!" not in presets.get_saves()

    def test_delete_existing_save(self, presets):
        presets.set_save("tosave", {"x": 1})
        presets.delete_save("tosave")
        assert "tosave" not in presets.get_saves()

    def test_delete_nonexistent_save_is_noop(self, presets):
        presets.delete_save("does_not_exist")
        assert presets.get_saves() == {}

    def test_multiple_saves(self, presets):
        presets.set_save("save1", {"a": 1})
        presets.set_save("save2", {"b": 2})
        saves = presets.get_saves()
        assert saves["save1"] == {"a": 1}
        assert saves["save2"] == {"b": 2}

    def test_overwrite_save(self, presets):
        presets.set_save("s", {"v": 1})
        presets.set_save("s", {"v": 2})
        assert presets.get_saves()["s"] == {"v": 2}

    def test_get_saves_filters_invalid_names(self, presets):
        data = {
            "valid-name": {"x": 1},
            "bad name": {"y": 2},
            "also_valid": {"z": 3},
        }
        (presets._dir / "saves.json").write_text(json.dumps(data), encoding="utf-8")
        saves = presets.get_saves()
        assert "valid-name" in saves
        assert "also_valid" in saves
        assert "bad name" not in saves

    def test_get_saves_returns_empty_when_not_a_dict(self, presets):
        (presets._dir / "saves.json").write_text(
            '["not", "a", "dict"]', encoding="utf-8"
        )
        assert presets.get_saves() == {}

    def test_hyphen_and_underscore_allowed_in_name(self, presets):
        presets.set_save("my-save_1", {"ok": True})
        assert "my-save_1" in presets.get_saves()
