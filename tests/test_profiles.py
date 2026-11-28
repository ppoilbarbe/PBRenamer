"""Tests for pbrenamer.profiles — profile set, current profile, contents.

Ports the catalogue cases of PBPicat's ``tests/test_config.py``
(listing, hidden catalogues, creation, duplication, deletion, last catalogue,
typed settings, histories).
"""

import json
import shutil

import pytest
from PySide6.QtCore import QSettings

from pbrenamer import profiles, settings


def _last(config_dir):
    return QSettings(str(config_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------


class TestNames:
    @pytest.mark.parametrize(
        "name", ["default", "Été_2026", "a-b", ".IA", "-old", "x1"]
    )
    def test_valid(self, name):
        assert profiles.is_valid_name(name)
        profiles.validate_name(name)

    @pytest.mark.parametrize("name", ["", ".", "a b", "a/b", "a.b", "..x", "é!"])
    def test_invalid(self, name):
        assert not profiles.is_valid_name(name)
        with pytest.raises(profiles.ProfileError, match="Invalid profile name"):
            profiles.validate_name(name)

    @pytest.mark.parametrize("name", ["photos", "Été_2026", "a-b", "-old"])
    def test_valid_new_name(self, name):
        profiles.validate_new_name(name)

    @pytest.mark.parametrize("name", ["", ".IA", "a.b", "a b", "a/b"])
    def test_invalid_new_name(self, name):
        with pytest.raises(profiles.ProfileError, match="Invalid profile name"):
            profiles.validate_new_name(name)

    @pytest.mark.parametrize(
        ("name", "hidden"), [(".IA", True), ("-x", True), ("default", False)]
    )
    def test_hidden(self, name, hidden):
        assert profiles.is_hidden(name) is hidden


# ---------------------------------------------------------------------------
# Profile set
# ---------------------------------------------------------------------------


class TestProfileSet:
    def test_default_created_on_first_access(self, config_dir):
        assert profiles.list_profiles() == ["default"]
        assert (config_dir / "profiles" / "default").is_dir()
        assert profiles.current() == "default"

    def test_list_sorted_and_hidden(self):
        for name in ("b", "a", ".h", "-h"):
            profiles.create(name)
        assert profiles.list_profiles() == ["a", "b", "default"]
        assert profiles.list_profiles(include_hidden=True) == [
            "-h",
            ".h",
            "a",
            "b",
            "default",
        ]

    def test_list_ignores_files_and_invalid_dirs(self, config_dir):
        profiles.current()
        (config_dir / "profiles" / "note.txt").write_text("x")
        (config_dir / "profiles" / "a b").mkdir()
        assert profiles.list_profiles() == ["default"]

    def test_exists(self):
        profiles.create("p")
        assert profiles.exists("p")
        assert not profiles.exists("q")
        assert not profiles.exists("../profiles")

    def test_create_existing_rejected(self):
        with pytest.raises(profiles.ProfileError, match="already exists"):
            profiles.create("default")

    def test_create_invalid_rejected(self):
        with pytest.raises(profiles.ProfileError, match="Invalid"):
            profiles.create("a/b")

    def test_duplicate_copies_everything(self):
        profiles.set_schema(dest="/d")
        profiles.set_history("field_0", ["a"])
        settings.set_sidecar_common_suffixes(["meta"])
        profiles.duplicate("default", "copy")
        profiles.use("copy")
        assert profiles.get_schema()["dest"] == "/d"
        assert profiles.get_history("field_0") == ["a"]
        assert settings.get_sidecar_common_suffixes() == ["meta"]

    def test_duplicate_missing_source(self):
        with pytest.raises(profiles.ProfileError, match="not found"):
            profiles.duplicate("nope", "copy")

    def test_delete(self, config_dir):
        profiles.create("p")
        profiles.delete("p")
        assert not (config_dir / "profiles" / "p").exists()

    def test_delete_default(self):
        profiles.create("p")
        profiles.delete("default")
        assert profiles.list_profiles() == ["p"]
        assert profiles.current() == "p"

    def test_delete_last_visible_rejected(self):
        profiles.create(".h")
        with pytest.raises(profiles.ProfileError, match="last visible profile"):
            profiles.delete("default")
        assert profiles.exists("default")

    def test_delete_hidden_when_one_visible(self):
        profiles.create(".h")
        profiles.delete(".h")
        assert profiles.list_profiles(include_hidden=True) == ["default"]

    def test_delete_missing(self):
        with pytest.raises(profiles.ProfileError, match="not found"):
            profiles.delete("nope")

    def test_delete_current_falls_back_to_default(self, config_dir):
        profiles.create("p")
        profiles.use("p")
        profiles.delete("p")
        assert profiles.current() == "default"
        assert _last(config_dir).value("profiles/last") == "default"

    def test_delete_current_falls_back_to_first_visible(self, config_dir):
        for name in ("b", "a"):
            profiles.create(name)
        profiles.use("b")
        profiles.delete("default")
        profiles.delete("b")
        assert profiles.current() == "a"
        assert _last(config_dir).value("profiles/last") == "a"

    def test_fallback(self):
        assert profiles.fallback(["a", "default"]) == "default"
        assert profiles.fallback(["b", "a"]) == "b"

    def test_delete_other_keeps_current(self):
        profiles.create("p")
        profiles.create("q")
        profiles.use("p")
        profiles.delete("q")
        assert profiles.current() == "p"


class TestRename:
    def test_rename_current(self, config_dir):
        profiles.set_schema(dest="/d")
        profiles.use("default")
        profiles.rename("default", "photos")
        assert profiles.list_profiles() == ["photos"]
        assert profiles.current() == "photos"
        assert profiles.get_schema()["dest"] == "/d"
        assert _last(config_dir).value("profiles/last") == "photos"

    def test_rename_other_keeps_current_and_last(self, config_dir):
        profiles.create("p")
        profiles.use("default")
        profiles.rename("p", "q")
        assert profiles.list_profiles() == ["default", "q"]
        assert profiles.current() == "default"
        assert _last(config_dir).value("profiles/last") == "default"

    @pytest.mark.parametrize("target", ["p", ".p", "-p"])
    def test_rename_onto_existing_rejected(self, target):
        profiles.create("p")
        profiles.create(".p")
        profiles.create("-p")
        with pytest.raises(profiles.ProfileError, match="already exists"):
            profiles.rename("default", target)

    def test_rename_missing(self):
        with pytest.raises(profiles.ProfileError, match="not found"):
            profiles.rename("nope", "x")

    def test_hiding_last_visible_rejected(self):
        with pytest.raises(profiles.ProfileError, match="last visible profile"):
            profiles.rename("default", "-old")
        assert profiles.list_profiles() == ["default"]

    def test_hiding_remembered_profile(self, config_dir):
        profiles.create("p")
        profiles.use("p")
        profiles.rename("p", "-p")
        assert profiles.current() == "-p"
        assert _last(config_dir).value("profiles/last") == "default"

    def test_unhide(self):
        profiles.create(".h")
        profiles.use(".h")
        profiles.rename(".h", "h")
        assert profiles.list_profiles() == ["default", "h"]
        assert profiles.current() == "h"


# ---------------------------------------------------------------------------
# Current profile
# ---------------------------------------------------------------------------


class TestCurrent:
    def test_use_remembers(self, config_dir):
        profiles.create("p")
        profiles.use("p")
        assert profiles.current() == "p"
        assert _last(config_dir).value("profiles/last") == "p"

    def test_use_without_remember(self, config_dir):
        profiles.create("p")
        profiles.use("p", remember=False)
        assert profiles.current() == "p"
        assert _last(config_dir).value("profiles/last") is None

    def test_hidden_not_remembered(self, config_dir):
        profiles.create(".h")
        profiles.use(".h")
        assert profiles.current() == ".h"
        assert _last(config_dir).value("profiles/last") is None

    def test_use_missing(self):
        with pytest.raises(profiles.ProfileError, match="not found"):
            profiles.use("nope")

    def test_last_profile_restored(self, config_dir):
        profiles.create("p")
        profiles.use("p")
        settings.configure(config_dir)
        assert profiles.current() == "p"

    @pytest.mark.parametrize("last", ["gone", ".h", "a b"])
    def test_unusable_last_profile_falls_back(self, config_dir, last):
        profiles.create(".h")
        _last(config_dir).setValue("profiles/last", last)
        settings.configure(config_dir)
        assert profiles.current() == "default"
        assert profiles.missing_startup() == last

    def test_default_not_recreated_when_visible_profile(self, config_dir):
        profiles.create("p")
        profiles.use("p")
        shutil.rmtree(config_dir / "profiles" / "default")
        settings.configure(config_dir)
        assert profiles.list_profiles() == ["p"]
        assert profiles.current() == "p"

    def test_default_recreated_when_only_hidden(self, config_dir):
        profiles.create(".h")
        shutil.rmtree(config_dir / "profiles" / "default")
        settings.configure(config_dir)
        assert profiles.list_profiles(include_hidden=True) == [".h", "default"]
        assert profiles.current() == "default"

    def test_default_recreated_when_empty(self, config_dir):
        profiles.current()
        shutil.rmtree(config_dir / "profiles" / "default")
        settings.configure(config_dir)
        assert profiles.list_profiles() == ["default"]

    def test_start_without_default_selects_first_visible(self, config_dir):
        for name in ("b", "a"):
            profiles.create(name)
        shutil.rmtree(config_dir / "profiles" / "default")
        settings.configure(config_dir)
        assert profiles.current() == "a"

    def test_profile_dir(self, config_dir):
        assert profiles.profile_dir() == config_dir / "profiles" / "default"
        assert profiles.profile_dir("x") == config_dir / "profiles" / "x"


# ---------------------------------------------------------------------------
# profile.json
# ---------------------------------------------------------------------------


class TestProfileData:
    def _write(self, data):
        path = profiles.profile_dir() / profiles.PROFILE_FILE
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_defaults(self):
        assert profiles.load() == profiles.DEFAULTS
        assert profiles.load() is not profiles.DEFAULTS

    def test_round_trip(self):
        data = profiles.load()
        data["mode"] = "schema"
        data["schema"]["field_titles"] = ["A", "B"]
        profiles.save(data)
        assert profiles.load() == data

    def test_type_mismatch_ignored(self):
        self._write(
            {
                "last_dir": 3,
                "schema": {"fill_gaps": 1, "video_marker_pos": True, "dest": "/d"},
            }
        )
        data = profiles.load()
        assert data["last_dir"] == ""
        assert data["schema"]["fill_gaps"] is False
        assert data["schema"]["video_marker_pos"] == 0
        assert data["schema"]["dest"] == "/d"

    def test_non_dict_section_ignored(self):
        self._write({"schema": "oops"})
        assert profiles.load()["schema"] == profiles.DEFAULTS["schema"]

    def test_extra_keys_preserved(self):
        self._write({"future": [1], "files": {"other": True}})
        data = profiles.load()
        assert data["future"] == [1]
        assert data["files"]["other"] is True

    def test_unknown_mode_falls_back(self):
        self._write({"mode": "bogus"})
        assert profiles.load()["mode"] == "pattern"

    def test_deletion_mode_default_is_system_trash(self):
        assert profiles.load()["files"]["deletion_mode"] == "system"

    def test_unknown_deletion_mode_falls_back(self):
        self._write({"files": {"deletion_mode": "bogus"}})
        assert profiles.load()["files"]["deletion_mode"] == "system"

    def test_schema_extension_and_sidecar_defaults(self):
        schema = profiles.load()["schema"]
        assert (schema["extension_mode"], schema["sidecar_mode"]) == ("lower", True)

    @pytest.mark.parametrize(("stored", "loaded"), [("modify", "keep"), ("x", "lower")])
    def test_schema_extension_mode_sanitized(self, stored, loaded):
        self._write({"schema": {"extension_mode": stored}})
        assert profiles.load()["schema"]["extension_mode"] == loaded

    def test_old_trash_setting_ignored_and_dropped(self):
        self._write({"images": {"use_trash": False}})
        data = profiles.load()
        assert data["files"]["deletion_mode"] == "system"
        assert "use_trash" not in data["files"]
        profiles.save(data)
        stored = (profiles.profile_dir() / profiles.PROFILE_FILE).read_text()
        assert "use_trash" not in stored

    def test_old_images_section_split(self):
        self._write(
            {
                "images": {
                    "zoom_step_percent": 10,
                    "metadata_panel_side": "left",
                    "deletion_mode": "session",
                    "sidecar_new_extension": "txt",
                    "unknown": 1,
                },
                "files": {"confirm_deletions": False, "deletion_mode": "delete"},
            }
        )
        data = profiles.load()
        assert "images" not in data
        assert data["viewer"]["zoom_step_percent"] == 10
        assert data["viewer"]["metadata_panel_side"] == "left"
        assert data["files"]["sidecar_new_extension"] == "txt"
        assert data["files"]["confirm_deletions"] is False
        # A value already in the new section wins.
        assert data["files"]["deletion_mode"] == "delete"
        assert "unknown" not in data["files"]

    def test_old_images_section_not_a_dict(self):
        self._write({"images": "oops", "viewer": "oops"})
        data = profiles.load()
        assert "images" not in data
        assert data["viewer"] == profiles.DEFAULTS["viewer"]

    def test_old_images_section_into_bad_new_section(self):
        self._write({"images": {"zoom_step_percent": 10}, "viewer": "oops"})
        assert profiles.load()["viewer"]["zoom_step_percent"] == 10

    @pytest.mark.parametrize("content", ["not json", "[1, 2]"])
    def test_invalid_file(self, content):
        (profiles.profile_dir() / profiles.PROFILE_FILE).write_text(content)
        assert profiles.load() == profiles.DEFAULTS

    def test_set_schema(self):
        profiles.set_schema(dest="/d", fill_gaps=True)
        schema = profiles.get_schema()
        assert (schema["dest"], schema["fill_gaps"], schema["field_count"]) == (
            "/d",
            True,
            6,
        )

    def test_profiles_are_independent(self):
        profiles.set_schema(video_marker="V")
        profiles.create("p")
        profiles.use("p")
        assert profiles.get_schema()["video_marker"] == ""


# ---------------------------------------------------------------------------
# history.json
# ---------------------------------------------------------------------------


class TestHistory:
    def test_missing(self):
        assert profiles.get_all_history() == {}
        assert profiles.get_history("field_0") == []

    def test_round_trip(self):
        profiles.set_history("field_0", ["a", "b"])
        profiles.set_history("sidecar_filter", ["x"])
        assert profiles.get_history("field_0") == ["a", "b"]
        assert profiles.get_all_history() == {
            "field_0": ["a", "b"],
            "sidecar_filter": ["x"],
        }

    def test_invalid_entries_dropped(self):
        path = profiles.profile_dir() / profiles.HISTORY_FILE
        path.write_text(json.dumps({"a": ["x", 1], "b": "y", "c": []}))
        assert profiles.get_all_history() == {"a": ["x"], "c": []}

    @pytest.mark.parametrize("content", ["{oops", "[1]"])
    def test_invalid_file(self, content):
        (profiles.profile_dir() / profiles.HISTORY_FILE).write_text(content)
        assert profiles.get_all_history() == {}


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestInit:
    def test_orphan_tmp_tree_replaced(self, config_dir):
        tmp = config_dir / "profiles.tmp"
        (tmp / "stale").mkdir(parents=True)
        assert profiles.list_profiles() == ["default"]
        assert not tmp.exists()

    def test_existing_tree_not_migrated_again(self, config_dir):
        (config_dir / "profiles" / "default").mkdir(parents=True)
        (config_dir / "patterns").mkdir()
        (config_dir / "patterns" / "replace.json").write_text('["x"]')
        assert profiles.list_profiles() == ["default"]
        assert not (config_dir / "profiles" / "default" / "patterns").exists()

    def test_no_pbpicat_import_with_custom_config_dir(self, config_dir, tmp_path):
        source = tmp_path / "pbpicat"
        (source / "cat").mkdir(parents=True)
        settings.configure(config_dir)
        assert profiles.list_profiles() == ["default"]

    def test_configure_without_dir_uses_platform_pbpicat_dir(self, monkeypatch):
        seen = []
        monkeypatch.setattr(profiles, "reset", seen.append)
        monkeypatch.setattr(settings, "pbpicat_config_dir", lambda: "PBPICAT")
        settings.configure()
        assert seen == ["PBPICAT"]


# ---------------------------------------------------------------------------
# Default profile
# ---------------------------------------------------------------------------


class TestDefaultProfile:
    def test_last_used_by_default(self, config_dir):
        assert profiles.get_default() == ""
        profiles.create("p")
        profiles.use("p")
        settings.configure(config_dir)
        assert profiles.current() == "p"
        assert profiles.missing_startup() is None

    def test_first_start_is_not_missing(self):
        assert profiles.startup_name() == ""
        assert profiles.current() == "default"
        assert profiles.missing_startup() is None

    def test_default_wins_over_last(self, config_dir):
        profiles.create("p")
        profiles.create("q")
        profiles.use("q")
        profiles.set_default("p")
        assert _last(config_dir).value("profiles/default") == "p"
        settings.configure(config_dir)
        assert profiles.startup_name() == "p"
        assert profiles.current() == "p"

    def test_set_default_back_to_last(self, config_dir):
        profiles.create("p")
        profiles.use("p")
        profiles.set_default("default")
        profiles.set_default("")
        settings.configure(config_dir)
        assert profiles.current() == "p"

    def test_set_default_invalid(self):
        with pytest.raises(profiles.ProfileError):
            profiles.set_default("a b")

    @pytest.mark.parametrize("name", ["gone", ".h"])
    def test_missing_default(self, config_dir, name):
        profiles.create(".h")
        profiles.create("p")
        profiles.use("p")
        profiles.set_default(name)
        settings.configure(config_dir)
        assert profiles.missing_startup() == name
        assert profiles.current() == "default"

    def test_use_clears_missing(self, config_dir):
        profiles.set_default("gone")
        settings.configure(config_dir)
        assert profiles.missing_startup() == "gone"
        profiles.use("default")
        assert profiles.missing_startup() is None

    def test_rename_follows(self):
        profiles.create("p")
        profiles.set_default("p")
        profiles.rename("p", "q")
        assert profiles.get_default() == "q"

    def test_rename_hidden_does_not_follow(self):
        profiles.create("p")
        profiles.set_default("p")
        profiles.rename("p", ".p")
        assert profiles.get_default() == "p"

    def test_rename_other_keeps_default(self):
        profiles.create("p")
        profiles.create("q")
        profiles.set_default("p")
        profiles.rename("q", "r")
        assert profiles.get_default() == "p"

    def test_delete_keeps_default(self, config_dir):
        profiles.create("p")
        profiles.set_default("p")
        profiles.delete("p")
        assert profiles.get_default() == "p"
        settings.configure(config_dir)
        assert profiles.missing_startup() == "p"
