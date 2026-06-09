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
    get_log_level,
    get_shortcuts,
    set_log_level,
    set_shortcuts,
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
