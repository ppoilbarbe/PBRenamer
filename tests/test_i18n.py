"""Tests for pbrenamer.i18n — translation bootstrap."""

from __future__ import annotations

import gettext
from unittest.mock import patch

import pbrenamer.i18n as i18n
from pbrenamer.i18n import (
    _GettextTranslator,
    available_languages,
    get_language_override,
    set_language_override,
)


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
    def test_default_is_empty_string(self):
        assert get_language_override() == ""

    def test_set_then_get(self):
        set_language_override("fr")
        assert get_language_override() == "fr"

    def test_clear_override(self):
        set_language_override("de")
        set_language_override("")
        assert get_language_override() == ""

    def test_overwrite_changes_value(self):
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
    def test_setup_without_override_uses_system_language(self, qtbot):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        with patch.object(i18n, "_system_language", return_value="en"):
            i18n.setup(app)

    def test_setup_with_override_uses_override(self, qtbot):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        set_language_override("fr")
        i18n.setup(app)

    def test_setup_unknown_language_falls_back_gracefully(self, qtbot):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        with patch.object(i18n, "_system_language", return_value="xx"):
            i18n.setup(app)  # must not raise


class TestAvailableLanguagesEdgeCases:
    def test_skips_mo_files_that_cannot_be_loaded(self, tmp_path, monkeypatch):
        """FileNotFoundError in gettext.translation → entry is skipped."""
        fake_locale = tmp_path / "locale"
        lang_dir = fake_locale / "xx" / "LC_MESSAGES"
        lang_dir.mkdir(parents=True)
        (lang_dir / "pbrenamer.mo").touch()

        monkeypatch.setattr(i18n, "_LOCALE_DIR", fake_locale)
        import gettext as _gt

        def _fake_translation(domain, localedir, languages):
            raise FileNotFoundError("no catalogue")

        monkeypatch.setattr(_gt, "translation", _fake_translation)
        langs = available_languages()
        assert all(c != "xx" for c, _ in langs)

    def test_lang_name_falls_back_to_code_when_msgstr_is_msgid(
        self, tmp_path, monkeypatch
    ):
        """When lang_name == 'language_name' the code is used as the name."""
        fake_locale = tmp_path / "locale"
        lang_dir = fake_locale / "zz" / "LC_MESSAGES"
        lang_dir.mkdir(parents=True)
        (lang_dir / "pbrenamer.mo").touch()

        monkeypatch.setattr(i18n, "_LOCALE_DIR", fake_locale)
        import gettext as _gt

        class _NullWithCode(_gt.NullTranslations):
            def gettext(self, msg):
                return msg  # returns the msgid unchanged

        def _fake_translation(domain, localedir, languages):
            return _NullWithCode()

        monkeypatch.setattr(_gt, "translation", _fake_translation)
        langs = available_languages()
        mapping = dict(langs)
        assert mapping.get("zz") == "zz"
