"""Tests for pbrenamer.status and the --status option."""

from __future__ import annotations

import sys

import pytest

import pbrenamer.settings as _settings
from pbrenamer import __version__, i18n, profiles, status
from pbrenamer.ui.presets import PatternPresets

yaml = pytest.importorskip("yaml")


def _main(monkeypatch, *args) -> int:
    from pbrenamer.__main__ import main

    monkeypatch.setattr(sys, "argv", ["pbrenamer", *map(str, args)])
    try:
        main()
    except SystemExit as exc:
        return exc.code
    return 0


class TestToYaml:
    @pytest.mark.parametrize(
        "data",
        [
            {"a": 1, "b": 2.5, "c": True, "d": False, "e": None},
            {"s": "plain", "t": "yes", "u": "null", "v": "12", "w": ""},
            {"x": "a: b # c", "y": 'quote " and \\ back', "z": "é 中文\nline"},
            {"empty_list": [], "empty_map": {}},
            {"nested": {"deep": {"k": [1, "two", None]}}},
            {"list_of_maps": [{"a": 1, "b": [1, 2]}, {"c": {"d": "e"}}]},
            {"list_of_lists": [[1, 2], [], ["x"]]},
            {"odd key": 1, "true": 2, "9": 3, "k-v": 4},
        ],
    )
    def test_round_trip(self, data):
        assert yaml.safe_load(status.to_yaml(data)) == data

    def test_strings_are_quoted(self):
        assert status.to_yaml({"v": "1.0"}) == 'v: "1.0"\n'

    def test_block_layout(self):
        text = status.to_yaml({"m": {"l": ["a", {"k": 1, "j": 2}]}})
        assert text == 'm:\n  l:\n    - "a"\n    - k: 1\n      j: 2\n'


class TestCollect:
    def test_defaults(self):
        data = status.collect()
        assert data["version"] == __version__
        assert data["config_dir"] == str(_settings.config_home())
        app = data["application"]
        assert app["language"] is None
        assert app["log_level"] == "INFO"
        assert app["selected_profile"] == "default"
        assert app["default_profile"] is None
        assert app["last_used_profile"] is None
        assert list(data["profiles"]) == ["default"]
        profile = data["profiles"]["default"]
        assert profile["dir"] == str(profiles.profile_dir("default"))
        assert profile["mode"] == "pattern"
        assert "jpg" in profile["sidecars"]["base_extensions"]["image"]
        assert profile["saves"] == []

    def test_values(self):
        i18n.set_language_override("fr")
        profiles.create("p")
        profiles.create(".h")
        profiles.use("p")
        profiles.set_default("p")
        _settings.set_shortcuts([("Home", "/home")])
        _settings.set_extension_normalization([("jpeg", "jpg")])
        _settings.set_sidecar_common_suffixes(["txt"])
        PatternPresets().set_save("s1", {"search": "a"})
        data = profiles.load()
        data["mode"] = "schema"
        profiles.save(data)
        profiles.use("default", remember=False)
        data = status.collect()
        app = data["application"]
        assert app["language"] == "fr"
        assert app["selected_profile"] == "default"
        assert app["default_profile"] == "p"
        assert app["last_used_profile"] == "p"
        assert app["shortcuts"] == [{"name": "Home", "path": "/home"}]
        assert app["extension_normalization"] == [{"from": "jpeg", "to": "jpg"}]
        # Every visible profile, with its own settings; hidden ones left out.
        assert list(data["profiles"]) == ["default", "p"]
        p, default = data["profiles"]["p"], data["profiles"]["default"]
        assert (p["mode"], default["mode"]) == ("schema", "pattern")
        assert p["saves"] == ["s1"] and default["saves"] == []
        assert p["sidecars"]["common_suffixes"] == ["txt"]
        assert default["sidecars"]["common_suffixes"] == []
        # The selected profile is current again.
        assert profiles.current() == "default"


class TestStatusOption:
    def test_prints_yaml(self, monkeypatch, capsys):
        assert _main(monkeypatch, "--status") == 0
        data = yaml.safe_load(capsys.readouterr().out)
        assert data["version"] == __version__
        assert list(data["profiles"]) == ["default"]

    def test_profile_option(self, monkeypatch, capsys):
        profiles.create("p")
        assert _main(monkeypatch, "--status", "--profile", "p") == 0
        data = yaml.safe_load(capsys.readouterr().out)
        assert data["application"]["selected_profile"] == "p"
        assert list(data["profiles"]) == ["default", "p"]
        # --status never changes the profile the GUI opens next.
        assert profiles.last_used() == ""

    def test_default_profile(self, monkeypatch, capsys):
        profiles.create("p")
        profiles.set_default("p")
        _settings.configure(_settings._dirs.config_home)
        assert _main(monkeypatch, "--status") == 0
        data = yaml.safe_load(capsys.readouterr().out)
        assert data["application"]["selected_profile"] == "p"

    def test_missing_default_profile(self, monkeypatch, capsys):
        profiles.set_default("gone")
        _settings.configure(_settings._dirs.config_home)
        assert _main(monkeypatch, "--status") == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "error: default profile 'gone' not found" in captured.err
