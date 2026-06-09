"""Tests for pbrenamer.platform.locale — system language detection."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pbrenamer.platform.locale import system_language


@pytest.fixture(autouse=True)
def _clear_locale_env(monkeypatch):
    """Remove all locale-related env vars before each test."""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)


class TestSystemLanguage:
    def test_language_env_takes_priority(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "fr_FR.UTF-8")
        monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
        assert system_language() == "fr"

    def test_colon_separated_language_uses_first(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "fr:en:de")
        assert system_language() == "fr"

    def test_underscore_stripped(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "de_DE.UTF-8")
        assert system_language() == "de"

    def test_dot_encoding_stripped(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "fr.UTF-8")
        assert system_language() == "fr"

    def test_lc_all_fallback(self, monkeypatch):
        monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
        assert system_language() == "de"

    def test_lc_messages_fallback(self, monkeypatch):
        monkeypatch.setenv("LC_MESSAGES", "es_ES.UTF-8")
        assert system_language() == "es"

    def test_lang_fallback(self, monkeypatch):
        monkeypatch.setenv("LANG", "it_IT.UTF-8")
        assert system_language() == "it"

    def test_c_locale_is_skipped(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "C")
        monkeypatch.setenv("LANG", "fr_FR.UTF-8")
        assert system_language() == "fr"

    def test_posix_locale_is_skipped(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "POSIX")
        monkeypatch.setenv("LANG", "de_DE.UTF-8")
        assert system_language() == "de"

    def test_locale_module_fallback(self):
        with patch("locale.getlocale", return_value=("fr_FR", "UTF-8")):
            assert system_language() == "fr"

    def test_locale_module_returns_lang_only(self):
        with patch("locale.getlocale", return_value=("fr_FR", None)):
            assert system_language() == "fr"

    def test_ultimate_en_fallback(self):
        with patch("locale.getlocale", return_value=(None, None)):
            assert system_language() == "en"
