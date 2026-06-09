"""Tests for pbrenamer.i18n — translation bootstrap."""

from __future__ import annotations

import gettext
from unittest.mock import MagicMock, patch

import pytest

import pbrenamer.i18n as i18n
from pbrenamer.i18n import (
    _GettextTranslator,
    available_languages,
    get_language_override,
    set_language_override,
)


@pytest.fixture
def cfg_dir(tmp_path, monkeypatch):
    """Redirect i18n settings I/O to a temporary directory."""
    mock_dirs = MagicMock()
    mock_dirs.config_home = tmp_path
    monkeypatch.setattr(i18n, "_dirs", mock_dirs)
    return tmp_path


class TestAvailableLanguages:
    def test_returns_list_of_pairs(self):
        langs = available_languages()
        assert isinstance(langs, list)
        assert all(isinstance(c, str) and isinstance(n, str) for c, n in langs)

    def test_includes_fr(self):
        assert "fr" in [c for c, _ in available_languages()]

    def test_includes_en(self):
        assert "en" in [c for c, _ in available_languages()]

    def test_sorted_by_code(self):
        codes = [c for c, _ in available_languages()]
        assert codes == sorted(codes)

    def test_fr_name_is_francais(self):
        assert dict(available_languages()).get("fr") == "Français"

    def test_en_name_is_english(self):
        assert dict(available_languages()).get("en") == "English"


class TestLanguageOverride:
    def test_default_is_empty_string(self, cfg_dir):
        assert get_language_override() == ""

    def test_set_then_get(self, cfg_dir):
        set_language_override("fr")
        assert get_language_override() == "fr"

    def test_clear_override(self, cfg_dir):
        set_language_override("de")
        set_language_override("")
        assert get_language_override() == ""

    def test_overwrite_changes_value(self, cfg_dir):
        set_language_override("fr")
        set_language_override("en")
        assert get_language_override() == "en"


class TestGettextTranslator:
    def test_translate_delegates_to_gettext(self, qtbot):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        translator = _GettextTranslator(gettext.NullTranslations(), app)
        assert translator.translate("ctx", "hello") == "hello"

    def test_translate_with_disambiguation_and_n(self, qtbot):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        translator = _GettextTranslator(gettext.NullTranslations(), app)
        assert translator.translate("ctx", "world", "disambig", 2) == "world"


class TestSetup:
    def test_setup_without_override_uses_system_language(self, cfg_dir, qtbot):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        with patch.object(i18n, "_system_language", return_value="en"):
            i18n.setup(app)

    def test_setup_with_override_uses_override(self, cfg_dir, qtbot):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        set_language_override("fr")
        i18n.setup(app)

    def test_setup_unknown_language_falls_back_gracefully(self, cfg_dir, qtbot):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        with patch.object(i18n, "_system_language", return_value="xx"):
            i18n.setup(app)  # must not raise
