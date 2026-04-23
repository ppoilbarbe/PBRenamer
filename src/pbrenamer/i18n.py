"""Internationalisation bootstrap.

Call ``setup(app)`` once, before creating any window. It:
  * reads the language override from QSettings (if set),
  * detects the system language from environment variables as fallback,
  * loads the matching gettext catalogue (falls back to no-op),
  * installs ``_()`` as a builtin for Python-side strings,
  * registers a QTranslator so Qt's retranslateUi() is also translated.
"""

from __future__ import annotations

import gettext
from pathlib import Path

from PySide6.QtCore import QSettings, QTranslator
from PySide6.QtWidgets import QApplication

from pbrenamer.platform import AppDirs, system_language

_DOMAIN = "pbrenamer"
_LOCALE_DIR = Path(__file__).parent / "locale"
_SETTINGS_KEY = "language/override"
_dirs = AppDirs(_DOMAIN)


class _GettextTranslator(QTranslator):
    """Qt translator that delegates every lookup to a gettext catalogue."""

    def __init__(
        self, translation: gettext.NullTranslations, parent: QApplication
    ) -> None:
        super().__init__(parent)
        self._t = translation

    def translate(
        self,
        context: str,
        source_text: str,
        disambiguation: str | None = None,
        n: int = -1,
    ) -> str:
        return self._t.gettext(source_text)


_system_language = system_language


def available_languages() -> list[tuple[str, str]]:
    """Return ``[(lang_code, lang_name_in_that_language), …]`` sorted by code.

    Discovers languages dynamically by scanning ``.mo`` files under the locale
    directory.  Each catalogue must contain a ``language_name`` msgid whose
    msgstr is the language name written in that language (e.g. "Français").
    """
    result: list[tuple[str, str]] = []
    for mo_path in sorted(_LOCALE_DIR.glob("*/LC_MESSAGES/pbrenamer.mo")):
        lang_code = mo_path.parts[-3]
        try:
            t = gettext.translation(
                _DOMAIN, localedir=str(_LOCALE_DIR), languages=[lang_code]
            )
        except FileNotFoundError:
            continue
        lang_name = t.gettext("language_name")
        if lang_name == "language_name":
            lang_name = lang_code
        result.append((lang_code, lang_name))
    return result


def _settings() -> QSettings:
    cfg = _dirs.config_home
    cfg.mkdir(parents=True, exist_ok=True)
    return QSettings(str(cfg / f"{_DOMAIN}.conf"), QSettings.Format.IniFormat)


def get_language_override() -> str:
    """Return the saved language code, or ``""`` for system default."""
    val = _settings().value(_SETTINGS_KEY, "")
    return val if isinstance(val, str) else ""


def set_language_override(code: str) -> None:
    """Persist *code* as the language override (``""`` clears the override)."""
    _settings().setValue(_SETTINGS_KEY, code)


def setup(app: QApplication) -> None:
    """Install translations for *app*.

    Safe to call multiple times (each call replaces the previous translator).
    """
    override = get_language_override()
    lang = override if override else _system_language()

    try:
        t: gettext.NullTranslations = gettext.translation(
            _DOMAIN, localedir=str(_LOCALE_DIR), languages=[lang]
        )
    except FileNotFoundError:
        t = gettext.NullTranslations()

    t.install()

    translator = _GettextTranslator(t, app)
    app.installTranslator(translator)
