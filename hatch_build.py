"""Hatchling build hook: compile gettext .po catalogues to .mo for the wheel.

The .po sources are committed but the compiled .mo catalogues are gitignored
build artifacts (see `make translate`). Without this hook, a wheel built for
PyPI would ship no .mo files and the app would silently fall back to English
(see i18n.py: available_languages() discovers languages by globbing *.mo).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class TranslationsBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if self.target_name != "wheel":
            return

        from babel.messages.mofile import write_mo
        from babel.messages.pofile import read_po

        locale_dir = Path(self.root) / "src" / "pbrenamer" / "locale"
        for po_path in sorted(locale_dir.glob("*/LC_MESSAGES/pbrenamer.po")):
            lang = po_path.parts[-3]
            mo_path = po_path.with_suffix(".mo")
            with po_path.open("rb") as f:
                catalog = read_po(f, locale=lang, domain="pbrenamer")
            with mo_path.open("wb") as f:
                write_mo(f, catalog)
            build_data["force_include"][str(mo_path)] = (
                f"pbrenamer/locale/{lang}/LC_MESSAGES/pbrenamer.mo"
            )
