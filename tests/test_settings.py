"""Tests for pbrenamer.settings — log level and shortcuts persistence."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock

import pbrenamer.settings as settings
from pbrenamer.settings import (
    LEVELS,
    apply_log_level,
    get_extension_normalization,
    get_extension_normalization_map,
    get_last_dir,
    get_log_level,
    get_preview_delay,
    get_restore_last_dir,
    get_restore_toolbar_state,
    get_shortcuts,
    get_sidecar_base_extensions,
    get_sidecar_common_suffixes,
    get_sidecar_config,
    get_sidecar_settings,
    get_sidecar_suffixes,
    get_toolbar_state,
    restore_sidecar_base_extensions_defaults,
    restore_sidecar_common_suffixes_defaults,
    restore_sidecar_suffixes_defaults,
    set_extension_normalization,
    set_last_dir,
    set_log_level,
    set_preview_delay,
    set_restore_last_dir,
    set_restore_toolbar_state,
    set_shortcuts,
    set_sidecar_base_extensions,
    set_sidecar_common_suffixes,
    set_sidecar_settings,
    set_sidecar_suffixes,
    set_toolbar_state,
)


class TestLevels:
    def test_levels_tuple_contains_expected(self):
        for lvl in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            assert lvl in LEVELS


class TestGetLogLevel:
    def test_default_is_info(self):
        assert get_log_level() == "INFO"

    def test_reads_persisted_level(self):
        set_log_level("DEBUG")
        assert get_log_level() == "DEBUG"

    def test_invalid_stored_value_falls_back_to_info(self, config_dir):
        # Write an invalid value directly via QSettings
        set_log_level("DEBUG")  # put something valid first
        from PySide6.QtCore import QSettings

        qs = QSettings(str(config_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("log/level", "VERBOSE")
        qs.sync()
        assert get_log_level() == "INFO"


class TestSetLogLevel:
    def test_set_and_get_all_levels(self):
        for lvl in LEVELS:
            set_log_level(lvl)
            assert get_log_level() == lvl

    def test_invalid_level_not_persisted(self):
        set_log_level("INFO")
        set_log_level("BOGUS")
        assert get_log_level() == "INFO"


class TestGetShortcuts:
    def test_returns_empty_when_file_absent(self):
        assert get_shortcuts() == []

    def test_returns_empty_on_invalid_json(self, config_dir):
        (config_dir / "shortcuts.json").write_text("not json", encoding="utf-8")
        assert get_shortcuts() == []

    def test_returns_empty_when_not_a_list(self, config_dir):
        (config_dir / "shortcuts.json").write_text('{"key": "val"}', encoding="utf-8")
        assert get_shortcuts() == []

    def test_filters_invalid_entries(self, config_dir):
        data = [
            {"name": "Good", "path": "/valid"},
            {"name": "", "path": "/empty_name"},
            {"name": "No path"},
            "not a dict",
            {"name": "Empty path", "path": ""},
        ]
        (config_dir / "shortcuts.json").write_text(json.dumps(data), encoding="utf-8")
        assert get_shortcuts() == [("Good", "/valid")]


class TestSetShortcuts:
    def test_round_trip(self):
        pairs = [("Home", "/home/user"), ("Projects", "/home/user/projects")]
        set_shortcuts(pairs)
        assert get_shortcuts() == pairs

    def test_empty_list_clears_shortcuts(self):
        set_shortcuts([("X", "/x")])
        set_shortcuts([])
        assert get_shortcuts() == []

    def test_creates_parent_directory(self, tmp_path, monkeypatch):
        nested = tmp_path / "a" / "b" / "c"
        mock_dirs = MagicMock()
        mock_dirs.config_home = nested
        monkeypatch.setattr(settings, "_dirs", mock_dirs)
        sc_file = nested / "shortcuts.json"
        monkeypatch.setattr(settings, "_SHORTCUTS_FILE", sc_file)
        set_shortcuts([("Test", "/test")])
        assert sc_file.exists()


class TestGetExtensionNormalization:
    def test_returns_empty_when_file_absent(self):
        assert get_extension_normalization() == []

    def test_returns_empty_on_invalid_json(self, config_dir):
        (config_dir / "extension_normalization.json").write_text(
            "not json", encoding="utf-8"
        )
        assert get_extension_normalization() == []

    def test_returns_empty_when_not_a_list(self, config_dir):
        (config_dir / "extension_normalization.json").write_text(
            '{"key": "val"}', encoding="utf-8"
        )
        assert get_extension_normalization() == []

    def test_filters_invalid_entries(self, config_dir):
        data = [
            {"from": "jpeg", "to": "jpg"},
            {"from": "", "to": "empty_from"},
            {"from": "no_to"},
            "not a dict",
            {"from": "empty_to", "to": ""},
        ]
        (config_dir / "extension_normalization.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        assert get_extension_normalization() == [("jpeg", "jpg")]


class TestSetExtensionNormalization:
    def test_round_trip(self):
        pairs = [("jpeg", "jpg"), ("yml", "yaml")]
        set_extension_normalization(pairs)
        assert get_extension_normalization() == pairs

    def test_empty_list_clears_table(self):
        set_extension_normalization([("jpeg", "jpg")])
        set_extension_normalization([])
        assert get_extension_normalization() == []

    def test_creates_parent_directory(self, tmp_path, monkeypatch):
        nested = tmp_path / "a" / "b" / "c"
        mock_dirs = MagicMock()
        mock_dirs.config_home = nested
        monkeypatch.setattr(settings, "_dirs", mock_dirs)
        norm_file = nested / "extension_normalization.json"
        monkeypatch.setattr(settings, "_EXTENSION_NORMALIZATION_FILE", norm_file)
        set_extension_normalization([("jpeg", "jpg")])
        assert norm_file.exists()


class TestGetExtensionNormalizationMap:
    def test_returns_empty_dict_when_no_table(self):
        assert get_extension_normalization_map() == {}

    def test_returns_lowercased_keys(self):
        set_extension_normalization([("JPEG", "jpg")])
        assert get_extension_normalization_map() == {"jpeg": "jpg"}

    def test_preserves_to_value_case(self):
        set_extension_normalization([("jpeg", "JPG")])
        assert get_extension_normalization_map() == {"jpeg": "JPG"}


class TestApplyLogLevel:
    def test_direct_level_is_applied(self):
        apply_log_level("WARNING")
        assert logging.getLogger().level == logging.WARNING
        apply_log_level("INFO")  # restore

    def test_none_reads_saved_level(self):
        set_log_level("ERROR")
        apply_log_level(None)
        assert logging.getLogger().level == logging.ERROR
        apply_log_level("INFO")

    def test_invalid_level_falls_back_to_saved(self):
        set_log_level("DEBUG")
        apply_log_level("BOGUS")
        assert logging.getLogger().level == logging.DEBUG
        apply_log_level("INFO")


class TestRestoreLastDir:
    def test_default_is_false(self):
        assert get_restore_last_dir() is False

    def test_set_true_and_get(self):
        set_restore_last_dir(True)
        assert get_restore_last_dir() is True

    def test_set_false_and_get(self):
        set_restore_last_dir(True)
        set_restore_last_dir(False)
        assert get_restore_last_dir() is False

    def test_string_true_values_are_truthy(self, config_dir):
        from PySide6.QtCore import QSettings

        for truthy in ("true", "1", "yes"):
            qs = QSettings(
                str(config_dir / "pbrenamer.conf"), QSettings.Format.IniFormat
            )
            qs.setValue("behaviour/restore_last_dir", truthy)
            qs.sync()
            assert get_restore_last_dir() is True

    def test_string_false_value_is_falsy(self, config_dir):
        from PySide6.QtCore import QSettings

        qs = QSettings(str(config_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/restore_last_dir", "false")
        qs.sync()
        assert get_restore_last_dir() is False


class TestLastDir:
    def test_default_is_empty_string(self):
        assert get_last_dir() == ""

    def test_set_and_get(self):
        set_last_dir("/home/user/documents")
        assert get_last_dir() == "/home/user/documents"

    def test_overwrite(self):
        set_last_dir("/a")
        set_last_dir("/b")
        assert get_last_dir() == "/b"


class TestRestoreToolbarState:
    def test_default_is_false(self):
        assert get_restore_toolbar_state() is False

    def test_set_true_and_get(self):
        set_restore_toolbar_state(True)
        assert get_restore_toolbar_state() is True

    def test_set_false_and_get(self):
        set_restore_toolbar_state(True)
        set_restore_toolbar_state(False)
        assert get_restore_toolbar_state() is False

    def test_string_true_values_are_truthy(self, config_dir):
        from PySide6.QtCore import QSettings

        for truthy in ("true", "1", "yes"):
            qs = QSettings(
                str(config_dir / "pbrenamer.conf"), QSettings.Format.IniFormat
            )
            qs.setValue("behaviour/restore_toolbar_state", truthy)
            qs.sync()
            assert get_restore_toolbar_state() is True

    def test_string_false_value_is_falsy(self, config_dir):
        from PySide6.QtCore import QSettings

        qs = QSettings(str(config_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/restore_toolbar_state", "false")
        qs.sync()
        assert get_restore_toolbar_state() is False


class TestToolbarState:
    def test_default_is_empty_dict(self):
        assert get_toolbar_state() == {}

    def test_set_and_get_round_trip(self):
        state = {"visible": True, "actions": ["a", "b"]}
        set_toolbar_state(state)
        assert get_toolbar_state() == state

    def test_empty_raw_value_returns_empty_dict(self, config_dir):
        from PySide6.QtCore import QSettings

        qs = QSettings(str(config_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/toolbar_state", "")
        qs.sync()
        assert get_toolbar_state() == {}

    def test_invalid_json_returns_empty_dict(self, config_dir):
        from PySide6.QtCore import QSettings

        qs = QSettings(str(config_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/toolbar_state", "not-json")
        qs.sync()
        assert get_toolbar_state() == {}

    def test_non_dict_json_returns_empty_dict(self, config_dir):
        from PySide6.QtCore import QSettings

        qs = QSettings(str(config_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/toolbar_state", '["a","b"]')
        qs.sync()
        assert get_toolbar_state() == {}


class TestPreviewDelay:
    def test_default_is_500(self):
        assert get_preview_delay() == 500

    def test_set_and_get(self):
        set_preview_delay(300)
        assert get_preview_delay() == 300

    def test_clamps_below_minimum(self):
        set_preview_delay(0)
        assert get_preview_delay() == 100

    def test_clamps_above_maximum(self):
        set_preview_delay(9999)
        assert get_preview_delay() == 1000

    def test_boundary_minimum(self):
        set_preview_delay(100)
        assert get_preview_delay() == 100

    def test_boundary_maximum(self):
        set_preview_delay(1000)
        assert get_preview_delay() == 1000

    def test_invalid_stored_value_falls_back_to_default(self, config_dir):
        from PySide6.QtCore import QSettings

        qs = QSettings(str(config_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/preview_delay_ms", "not-a-number")
        qs.sync()
        assert get_preview_delay() == 500


class TestGetSidecarSettings:
    def test_returns_empty_when_file_absent(self):
        assert get_sidecar_settings() == {}

    def test_returns_empty_on_invalid_json(self, config_dir):
        (config_dir / "sidecar_config.json").write_text("not json", encoding="utf-8")
        assert get_sidecar_settings() == {}

    def test_returns_empty_when_not_a_dict(self, config_dir):
        (config_dir / "sidecar_config.json").write_text("[1, 2]", encoding="utf-8")
        assert get_sidecar_settings() == {}

    def test_filters_unknown_category_and_non_string_entries(self, config_dir):
        data = {
            "base_extensions": {
                "image": ["jpg", "", 42, "png"],
                "bogus": ["x"],
                "video": "not a list",
            },
            "own_suffixes": {"image": ["xmp"], "bogus": ["x"]},
            "common_suffixes": ["meta", "", 1],
        }
        (config_dir / "sidecar_config.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        result = get_sidecar_settings()
        assert result["base_extensions"] == {"image": ["jpg", "png"]}
        assert result["own_suffixes"] == {"image": ["xmp"]}
        assert result["common_suffixes"] == ["meta"]

    def test_ignores_non_dict_own_suffixes_and_non_list_common(self, config_dir):
        data = {"own_suffixes": "nope", "common_suffixes": "nope"}
        (config_dir / "sidecar_config.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        assert get_sidecar_settings() == {}


class TestSetSidecarSettings:
    def test_round_trip(self):
        data = {"common_suffixes": ["meta"]}
        set_sidecar_settings(data)
        assert get_sidecar_settings()["common_suffixes"] == ["meta"]

    def test_creates_parent_directory(self, tmp_path, monkeypatch):
        nested = tmp_path / "a" / "b" / "c"
        mock_dirs = MagicMock()
        mock_dirs.config_home = nested
        monkeypatch.setattr(settings, "_dirs", mock_dirs)
        sidecar_file = nested / "sidecar_config.json"
        monkeypatch.setattr(settings, "_SIDECAR_CONFIG_FILE", sidecar_file)
        set_sidecar_settings({"common_suffixes": []})
        assert sidecar_file.exists()


class TestSidecarBaseExtensions:
    def test_default_when_unset(self):
        assert get_sidecar_base_extensions("image") == list(
            settings._DEFAULT_BASE_EXTENSION_LISTS["image"]
        )

    def test_unknown_category_default_is_empty(self):
        assert get_sidecar_base_extensions("bogus") == []

    def test_round_trip(self):
        set_sidecar_base_extensions("image", ["jpg", "png"])
        assert get_sidecar_base_extensions("image") == ["jpg", "png"]

    def test_setting_one_category_does_not_affect_another(self):
        set_sidecar_base_extensions("image", ["jpg"])
        assert get_sidecar_base_extensions("video") == list(
            settings._DEFAULT_BASE_EXTENSION_LISTS["video"]
        )

    def test_restore_defaults_only_affects_that_category(self):
        set_sidecar_base_extensions("image", ["jpg"])
        set_sidecar_base_extensions("video", ["avi"])
        restore_sidecar_base_extensions_defaults("image")
        assert get_sidecar_base_extensions("image") == list(
            settings._DEFAULT_BASE_EXTENSION_LISTS["image"]
        )
        assert get_sidecar_base_extensions("video") == ["avi"]


class TestSidecarSuffixes:
    def test_default_when_unset(self):
        assert get_sidecar_suffixes("image") == list(
            settings._DEFAULT_OWN_SUFFIX_LISTS["image"]
        )

    def test_round_trip(self):
        set_sidecar_suffixes("other", ["nfo"])
        assert get_sidecar_suffixes("other") == ["nfo"]

    def test_restore_defaults_only_affects_that_category(self):
        set_sidecar_suffixes("image", ["custom"])
        set_sidecar_suffixes("video", ["custom2"])
        set_sidecar_common_suffixes(["shared"])
        restore_sidecar_suffixes_defaults("image")
        assert get_sidecar_suffixes("image") == list(
            settings._DEFAULT_OWN_SUFFIX_LISTS["image"]
        )
        assert get_sidecar_suffixes("video") == ["custom2"]
        assert get_sidecar_common_suffixes() == ["shared"]


class TestSidecarCommonSuffixes:
    def test_default_is_empty(self):
        assert get_sidecar_common_suffixes() == []

    def test_round_trip(self):
        set_sidecar_common_suffixes(["meta", "extra"])
        assert get_sidecar_common_suffixes() == ["meta", "extra"]

    def test_restore_defaults(self):
        set_sidecar_common_suffixes(["meta"])
        restore_sidecar_common_suffixes_defaults()
        assert get_sidecar_common_suffixes() == []


class TestGetSidecarConfig:
    def test_defaults_when_unset(self):
        config = get_sidecar_config()
        assert config.category_of_extension("jpg") == "image"
        assert "xmp" in config.effective_suffixes("image")

    def test_reflects_persisted_overrides(self):
        set_sidecar_base_extensions("image", ["foo"])
        set_sidecar_common_suffixes(["meta"])
        config = get_sidecar_config()
        assert config.category_of_extension("foo") == "image"
        assert config.category_of_extension("jpg") == "other"
        assert "meta" in config.effective_suffixes("video")


class TestConfigureSidecarIsolation:
    def test_sidecar_config_file_follows_configure(self, tmp_path):
        settings.configure(tmp_path)
        try:
            set_sidecar_common_suffixes(["meta"])
            assert (tmp_path / "sidecar_config.json").exists()
        finally:
            settings.configure()

    def test_extension_normalization_file_follows_configure(self, tmp_path):
        settings.configure(tmp_path)
        try:
            set_extension_normalization([("jpeg", "jpg")])
            assert (tmp_path / "extension_normalization.json").exists()
        finally:
            settings.configure()
