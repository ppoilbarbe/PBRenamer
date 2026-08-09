"""Tests for pbrenamer.platform.desktop — user-level .desktop entry install."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from pbrenamer.platform import desktop
from pbrenamer.platform.desktop import (
    _resolve_executable,
    _xdg_data_home,
    install_desktop_entry,
    uninstall_desktop_entry,
)


class TestResolveExecutable:
    def test_returns_resolved_script_path(self, tmp_path, monkeypatch):
        script = tmp_path / "pbrenamer"
        script.touch()
        monkeypatch.setattr(sys, "argv", [str(script)])
        assert _resolve_executable() == str(script.resolve())

    def test_falls_back_to_path_lookup_for_module_invocation(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["/some/path/__main__.py"])
        with patch("shutil.which", return_value="/usr/bin/pbrenamer"):
            assert _resolve_executable() == "/usr/bin/pbrenamer"

    def test_returns_none_when_unresolvable(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["/some/path/__main__.py"])
        with patch("shutil.which", return_value=None):
            assert _resolve_executable() is None

    def test_missing_argv0_file_falls_back_to_path_lookup(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["/nonexistent/pbrenamer"])
        with patch("shutil.which", return_value="/usr/bin/pbrenamer"):
            assert _resolve_executable() == "/usr/bin/pbrenamer"


class TestXdgDataHome:
    def test_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        with patch.object(Path, "home", return_value=tmp_path):
            assert _xdg_data_home() == tmp_path / ".local" / "share"

    def test_custom(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        assert _xdg_data_home() == tmp_path

    def test_relative_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", "relative/path")
        with patch.object(Path, "home", return_value=tmp_path):
            assert _xdg_data_home() == tmp_path / ".local" / "share"


class TestLocalizedComments:
    def test_no_catalogues_returns_default_only(self, tmp_path, monkeypatch):
        monkeypatch.setattr(desktop, "_LOCALE_DIR", tmp_path)
        assert desktop._localized_comments() == [f"Comment={desktop._DESCRIPTION}"]

    def test_translated_language_gets_localized_line(self, tmp_path, monkeypatch):
        mo_dir = tmp_path / "fr" / "LC_MESSAGES"
        mo_dir.mkdir(parents=True)
        (mo_dir / "pbrenamer.mo").touch()
        monkeypatch.setattr(desktop, "_LOCALE_DIR", tmp_path)

        fake_translation = MagicMock()
        fake_translation.gettext.return_value = "Un utilitaire de renommage."
        with patch("gettext.translation", return_value=fake_translation):
            lines = desktop._localized_comments()

        assert lines == [
            f"Comment={desktop._DESCRIPTION}",
            "Comment[fr]=Un utilitaire de renommage.",
        ]

    def test_untranslated_language_is_skipped(self, tmp_path, monkeypatch):
        mo_dir = tmp_path / "en" / "LC_MESSAGES"
        mo_dir.mkdir(parents=True)
        (mo_dir / "pbrenamer.mo").touch()
        monkeypatch.setattr(desktop, "_LOCALE_DIR", tmp_path)

        fake_translation = MagicMock()
        fake_translation.gettext.return_value = desktop._DESCRIPTION
        with patch("gettext.translation", return_value=fake_translation):
            lines = desktop._localized_comments()

        assert lines == [f"Comment={desktop._DESCRIPTION}"]

    def test_missing_catalogue_is_skipped(self, tmp_path, monkeypatch):
        mo_dir = tmp_path / "de" / "LC_MESSAGES"
        mo_dir.mkdir(parents=True)
        (mo_dir / "pbrenamer.mo").touch()
        monkeypatch.setattr(desktop, "_LOCALE_DIR", tmp_path)

        with patch("gettext.translation", side_effect=FileNotFoundError):
            lines = desktop._localized_comments()

        assert lines == [f"Comment={desktop._DESCRIPTION}"]


class TestDesktopEntryContent:
    def test_name_is_never_localized(self, tmp_path, monkeypatch):
        mo_dir = tmp_path / "fr" / "LC_MESSAGES"
        mo_dir.mkdir(parents=True)
        (mo_dir / "pbrenamer.mo").touch()
        monkeypatch.setattr(desktop, "_LOCALE_DIR", tmp_path)

        fake_translation = MagicMock()
        fake_translation.gettext.return_value = "Traduit"
        with patch("gettext.translation", return_value=fake_translation):
            content = desktop._desktop_entry_content("/usr/bin/pbrenamer")

        assert "Name=PBRenamer" in content
        assert "Name[fr]" not in content
        assert "Comment[fr]=Traduit" in content

    def test_includes_exec_and_default_comment(self, tmp_path, monkeypatch):
        monkeypatch.setattr(desktop, "_LOCALE_DIR", tmp_path)
        content = desktop._desktop_entry_content("/usr/bin/pbrenamer")
        assert "Exec=/usr/bin/pbrenamer %f" in content
        assert f"Comment={desktop._DESCRIPTION}" in content


class TestInstallDesktopEntry:
    def test_non_linux_rejected(self):
        with patch.object(sys, "platform", "win32"):
            ok, message = install_desktop_entry()
        assert ok is False
        assert "only supported on Linux" in message

    def test_no_executable_found(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["/some/path/__main__.py"])
        with patch.object(sys, "platform", "linux"):
            with patch("shutil.which", return_value=None):
                ok, message = install_desktop_entry()
        assert ok is False
        assert "could not locate" in message

    def test_success_writes_desktop_file_and_icon(self, tmp_path, monkeypatch):
        script = tmp_path / "bin" / "pbrenamer"
        script.parent.mkdir()
        script.touch()
        monkeypatch.setattr(sys, "argv", [str(script)])
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))

        with patch.object(sys, "platform", "linux"):
            with patch("shutil.which", return_value=None):  # no update-* tools
                ok, message = install_desktop_entry()

        assert ok is True
        desktop_path = tmp_path / "share" / "applications" / "pbrenamer.desktop"
        icon_path = (
            tmp_path
            / "share"
            / "icons"
            / "hicolor"
            / "scalable"
            / "apps"
            / "pbrenamer.svg"
        )
        assert str(desktop_path) in message
        assert desktop_path.is_file()
        assert icon_path.is_file()

        content = desktop_path.read_text(encoding="utf-8")
        assert "[Desktop Entry]" in content
        assert "Name=PBRenamer" in content
        assert f"Exec={script.resolve()} %f" in content
        assert "Icon=pbrenamer" in content

    def test_success_invokes_available_update_tools(self, tmp_path, monkeypatch):
        script = tmp_path / "bin" / "pbrenamer"
        script.parent.mkdir()
        script.touch()
        monkeypatch.setattr(sys, "argv", [str(script)])
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))

        calls = []
        with patch.object(sys, "platform", "linux"):
            with patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}"):
                with patch(
                    "subprocess.run",
                    side_effect=lambda args, **kw: calls.append(args),
                ):
                    ok, _message = install_desktop_entry()

        assert ok is True
        invoked = [c[0] for c in calls]
        assert "/usr/bin/update-desktop-database" in invoked
        assert "/usr/bin/gtk-update-icon-cache" in invoked


class TestUninstallDesktopEntry:
    def test_non_linux_rejected(self):
        with patch.object(sys, "platform", "win32"):
            ok, message = uninstall_desktop_entry()
        assert ok is False
        assert "only supported on Linux" in message

    def test_nothing_to_remove_is_not_an_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
        with patch.object(sys, "platform", "linux"):
            with patch("shutil.which", return_value=None):
                ok, message = uninstall_desktop_entry()
        assert ok is True
        assert "nothing to remove" in message

    def test_removes_existing_entry_and_icon(self, tmp_path, monkeypatch):
        script = tmp_path / "bin" / "pbrenamer"
        script.parent.mkdir()
        script.touch()
        monkeypatch.setattr(sys, "argv", [str(script)])
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))

        with patch.object(sys, "platform", "linux"):
            with patch("shutil.which", return_value=None):
                install_ok, _msg = install_desktop_entry()
                assert install_ok is True

                desktop_path = tmp_path / "share" / "applications" / "pbrenamer.desktop"
                icon_path = (
                    tmp_path
                    / "share"
                    / "icons"
                    / "hicolor"
                    / "scalable"
                    / "apps"
                    / "pbrenamer.svg"
                )
                assert desktop_path.is_file()
                assert icon_path.is_file()

                ok, message = uninstall_desktop_entry()

        assert ok is True
        assert str(desktop_path) in message
        assert not desktop_path.exists()
        assert not icon_path.exists()

    def test_invokes_available_update_tools(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))

        calls = []
        with patch.object(sys, "platform", "linux"):
            with patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}"):
                with patch(
                    "subprocess.run",
                    side_effect=lambda args, **kw: calls.append(args),
                ):
                    ok, _message = uninstall_desktop_entry()

        assert ok is True
        invoked = [c[0] for c in calls]
        assert "/usr/bin/update-desktop-database" in invoked
        assert "/usr/bin/gtk-update-icon-cache" in invoked
