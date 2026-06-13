"""Tests for pbrenamer.settings — log level and shortcuts persistence."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock

import pytest

import pbrenamer.settings as settings
from pbrenamer.settings import (
    LEVELS,
    apply_log_level,
    get_last_dir,
    get_log_level,
    get_preview_delay,
    get_restore_last_dir,
    get_restore_toolbar_state,
    get_shortcuts,
    get_toolbar_state,
    set_last_dir,
    set_log_level,
    set_preview_delay,
    set_restore_last_dir,
    set_restore_toolbar_state,
    set_shortcuts,
    set_toolbar_state,
)


@pytest.fixture
def cfg_dir(tmp_path, monkeypatch):
    """Redirect all settings I/O to a temporary directory."""
    mock_dirs = MagicMock()
    mock_dirs.config_home = tmp_path
    monkeypatch.setattr(settings, "_dirs", mock_dirs)
    monkeypatch.setattr(settings, "_SHORTCUTS_FILE", tmp_path / "shortcuts.json")
    return tmp_path


class TestLevels:
    def test_levels_tuple_contains_expected(self):
        for lvl in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            assert lvl in LEVELS


class TestGetLogLevel:
    def test_default_is_info(self, cfg_dir):
        assert get_log_level() == "INFO"

    def test_reads_persisted_level(self, cfg_dir):
        set_log_level("DEBUG")
        assert get_log_level() == "DEBUG"

    def test_invalid_stored_value_falls_back_to_info(self, cfg_dir):
        # Write an invalid value directly via QSettings
        set_log_level("DEBUG")  # put something valid first
        # Manually corrupt by writing an invalid key via set_log_level bypass
        from PySide6.QtCore import QSettings

        qs = QSettings(str(cfg_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("log/level", "VERBOSE")
        qs.sync()
        assert get_log_level() == "INFO"


class TestSetLogLevel:
    def test_set_and_get_all_levels(self, cfg_dir):
        for lvl in LEVELS:
            set_log_level(lvl)
            assert get_log_level() == lvl

    def test_invalid_level_not_persisted(self, cfg_dir):
        set_log_level("INFO")
        set_log_level("BOGUS")
        assert get_log_level() == "INFO"


class TestGetShortcuts:
    def test_returns_empty_when_file_absent(self, cfg_dir):
        assert get_shortcuts() == []

    def test_returns_empty_on_invalid_json(self, cfg_dir):
        (cfg_dir / "shortcuts.json").write_text("not json", encoding="utf-8")
        assert get_shortcuts() == []

    def test_returns_empty_when_not_a_list(self, cfg_dir):
        (cfg_dir / "shortcuts.json").write_text('{"key": "val"}', encoding="utf-8")
        assert get_shortcuts() == []

    def test_filters_invalid_entries(self, cfg_dir):
        data = [
            {"name": "Good", "path": "/valid"},
            {"name": "", "path": "/empty_name"},
            {"name": "No path"},
            "not a dict",
            {"name": "Empty path", "path": ""},
        ]
        (cfg_dir / "shortcuts.json").write_text(json.dumps(data), encoding="utf-8")
        assert get_shortcuts() == [("Good", "/valid")]


class TestSetShortcuts:
    def test_round_trip(self, cfg_dir):
        pairs = [("Home", "/home/user"), ("Projects", "/home/user/projects")]
        set_shortcuts(pairs)
        assert get_shortcuts() == pairs

    def test_empty_list_clears_shortcuts(self, cfg_dir):
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


class TestApplyLogLevel:
    def test_direct_level_is_applied(self, cfg_dir):
        apply_log_level("WARNING")
        assert logging.getLogger().level == logging.WARNING
        apply_log_level("INFO")  # restore

    def test_none_reads_saved_level(self, cfg_dir):
        set_log_level("ERROR")
        apply_log_level(None)
        assert logging.getLogger().level == logging.ERROR
        apply_log_level("INFO")

    def test_invalid_level_falls_back_to_saved(self, cfg_dir):
        set_log_level("DEBUG")
        apply_log_level("BOGUS")
        assert logging.getLogger().level == logging.DEBUG
        apply_log_level("INFO")


class TestRestoreLastDir:
    def test_default_is_false(self, cfg_dir):
        assert get_restore_last_dir() is False

    def test_set_true_and_get(self, cfg_dir):
        set_restore_last_dir(True)
        assert get_restore_last_dir() is True

    def test_set_false_and_get(self, cfg_dir):
        set_restore_last_dir(True)
        set_restore_last_dir(False)
        assert get_restore_last_dir() is False

    def test_string_true_values_are_truthy(self, cfg_dir):
        from PySide6.QtCore import QSettings

        for truthy in ("true", "1", "yes"):
            qs = QSettings(str(cfg_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
            qs.setValue("behaviour/restore_last_dir", truthy)
            qs.sync()
            assert get_restore_last_dir() is True

    def test_string_false_value_is_falsy(self, cfg_dir):
        from PySide6.QtCore import QSettings

        qs = QSettings(str(cfg_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/restore_last_dir", "false")
        qs.sync()
        assert get_restore_last_dir() is False


class TestLastDir:
    def test_default_is_empty_string(self, cfg_dir):
        assert get_last_dir() == ""

    def test_set_and_get(self, cfg_dir):
        set_last_dir("/home/user/documents")
        assert get_last_dir() == "/home/user/documents"

    def test_overwrite(self, cfg_dir):
        set_last_dir("/a")
        set_last_dir("/b")
        assert get_last_dir() == "/b"


class TestRestoreToolbarState:
    def test_default_is_false(self, cfg_dir):
        assert get_restore_toolbar_state() is False

    def test_set_true_and_get(self, cfg_dir):
        set_restore_toolbar_state(True)
        assert get_restore_toolbar_state() is True

    def test_set_false_and_get(self, cfg_dir):
        set_restore_toolbar_state(True)
        set_restore_toolbar_state(False)
        assert get_restore_toolbar_state() is False

    def test_string_true_values_are_truthy(self, cfg_dir):
        from PySide6.QtCore import QSettings

        for truthy in ("true", "1", "yes"):
            qs = QSettings(str(cfg_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
            qs.setValue("behaviour/restore_toolbar_state", truthy)
            qs.sync()
            assert get_restore_toolbar_state() is True

    def test_string_false_value_is_falsy(self, cfg_dir):
        from PySide6.QtCore import QSettings

        qs = QSettings(str(cfg_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/restore_toolbar_state", "false")
        qs.sync()
        assert get_restore_toolbar_state() is False


class TestToolbarState:
    def test_default_is_empty_dict(self, cfg_dir):
        assert get_toolbar_state() == {}

    def test_set_and_get_round_trip(self, cfg_dir):
        state = {"visible": True, "actions": ["a", "b"]}
        set_toolbar_state(state)
        assert get_toolbar_state() == state

    def test_empty_raw_value_returns_empty_dict(self, cfg_dir):
        from PySide6.QtCore import QSettings

        qs = QSettings(str(cfg_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/toolbar_state", "")
        qs.sync()
        assert get_toolbar_state() == {}

    def test_invalid_json_returns_empty_dict(self, cfg_dir):
        from PySide6.QtCore import QSettings

        qs = QSettings(str(cfg_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/toolbar_state", "not-json")
        qs.sync()
        assert get_toolbar_state() == {}

    def test_non_dict_json_returns_empty_dict(self, cfg_dir):
        from PySide6.QtCore import QSettings

        qs = QSettings(str(cfg_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/toolbar_state", '["a","b"]')
        qs.sync()
        assert get_toolbar_state() == {}


class TestPreviewDelay:
    def test_default_is_500(self, cfg_dir):
        assert get_preview_delay() == 500

    def test_set_and_get(self, cfg_dir):
        set_preview_delay(300)
        assert get_preview_delay() == 300

    def test_clamps_below_minimum(self, cfg_dir):
        set_preview_delay(0)
        assert get_preview_delay() == 100

    def test_clamps_above_maximum(self, cfg_dir):
        set_preview_delay(9999)
        assert get_preview_delay() == 1000

    def test_boundary_minimum(self, cfg_dir):
        set_preview_delay(100)
        assert get_preview_delay() == 100

    def test_boundary_maximum(self, cfg_dir):
        set_preview_delay(1000)
        assert get_preview_delay() == 1000

    def test_invalid_stored_value_falls_back_to_default(self, cfg_dir):
        from PySide6.QtCore import QSettings

        qs = QSettings(str(cfg_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/preview_delay_ms", "not-a-number")
        qs.sync()
        assert get_preview_delay() == 500
