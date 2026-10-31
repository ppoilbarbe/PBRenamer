"""Tests for pbrenamer.platform.open_with and its per-OS modules.

Ports PBPicat's ``test_platform_linux.py``, ``test_platform_macos.py`` and
``test_platform_windows.py``; the MRU list lives in ``settings``.
"""

import pathlib
import subprocess
from unittest.mock import MagicMock, patch

import pytest

import pbrenamer.i18n as i18n
from pbrenamer import settings
from pbrenamer.platform import _open_linux, _open_macos, _open_windows, open_with


@pytest.fixture(autouse=True)
def _stub_current_language(monkeypatch):
    """Keep _desktop_name() locale-independent unless a test overrides it."""
    monkeypatch.setattr(i18n, "current_language", lambda: "en")


# ---------------------------------------------------------------------------
# _parse_gio_output
# ---------------------------------------------------------------------------


def test_parse_gio_output_basic():
    lines = (
        "Default application:\n  gimp.desktop\n"
        "Registered applications:\n  gimp.desktop\n  inkscape.desktop\n"
        "Recommended:\n  foo.desktop\n"
    )
    assert _open_linux._parse_gio_output(lines) == ["gimp.desktop", "inkscape.desktop"]


def test_parse_gio_output_empty():
    assert _open_linux._parse_gio_output("") == []


def test_parse_gio_output_no_registered_section():
    assert _open_linux._parse_gio_output("Default application:\n  gimp.desktop\n") == []


def test_parse_gio_output_non_desktop_line_breaks_section():
    output = (
        "Registered applications:\n  app1.desktop\n  not-a-desktop\n  app2.desktop\n"
    )
    assert _open_linux._parse_gio_output(output) == ["app1.desktop"]


def test_parse_gio_output_empty_line_in_section_is_ignored():
    output = "Registered applications:\n  app1.desktop\n\n  app2.desktop\n"
    assert _open_linux._parse_gio_output(output) == ["app1.desktop", "app2.desktop"]


# ---------------------------------------------------------------------------
# _build_cmd
# ---------------------------------------------------------------------------


def test_build_cmd_with_f(tmp_path):
    f = tmp_path / "img.jpg"
    assert _open_linux._build_cmd("gimp %f", f) == ["gimp", str(f)]


def test_build_cmd_with_percent_f_upper(tmp_path):
    f = tmp_path / "img.jpg"
    assert _open_linux._build_cmd("gimp %F", f) == ["gimp", str(f)]


def test_build_cmd_with_u(tmp_path):
    f = tmp_path / "img.jpg"
    assert _open_linux._build_cmd("eog %u", f) == ["eog", str(f)]


def test_build_cmd_with_percent_u_upper(tmp_path):
    f = tmp_path / "img.jpg"
    assert _open_linux._build_cmd("eog %U", f) == ["eog", str(f)]


def test_build_cmd_path_appended_when_missing(tmp_path):
    f = tmp_path / "img.jpg"
    result = _open_linux._build_cmd("eog", f)
    assert result[-1] == str(f)


def test_build_cmd_unknown_percent_skipped(tmp_path):
    f = tmp_path / "img.jpg"
    result = _open_linux._build_cmd("gimp %k %f", f)
    assert "%k" not in result
    assert str(f) in result


def test_build_cmd_path_not_duplicated(tmp_path):
    f = tmp_path / "img.jpg"
    result = _open_linux._build_cmd("gimp %f --no-splash", f)
    assert result.count(str(f)) == 1


# ---------------------------------------------------------------------------
# _app_dirs
# ---------------------------------------------------------------------------


def test_app_dirs_defaults(monkeypatch):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
    monkeypatch.setattr(
        _open_linux.Path, "home", staticmethod(lambda: pathlib.Path("/home/u"))
    )
    assert _open_linux._app_dirs() == [
        pathlib.Path("/home/u/.local/share/applications"),
        pathlib.Path("/usr/local/share/applications"),
        pathlib.Path("/usr/share/applications"),
    ]


def test_app_dirs_respects_xdg_data_dirs(monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", "/home/u/.data")
    monkeypatch.setenv("XDG_DATA_DIRS", "/opt/apps/share:/usr/share")
    assert _open_linux._app_dirs() == [
        pathlib.Path("/home/u/.data/applications"),
        pathlib.Path("/opt/apps/share/applications"),
        pathlib.Path("/usr/share/applications"),
    ]


def test_app_dirs_deduplicates_and_skips_empty(monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", "/usr/share")
    monkeypatch.setenv("XDG_DATA_DIRS", "/usr/share::/usr/share")
    assert _open_linux._app_dirs() == [pathlib.Path("/usr/share/applications")]


# ---------------------------------------------------------------------------
# _scan_desktop_dirs
# ---------------------------------------------------------------------------


def test_scan_desktop_dirs_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    assert _open_linux._scan_desktop_dirs("image/png") == []


def test_scan_desktop_dirs_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path / "nonexistent"])
    assert _open_linux._scan_desktop_dirs("image/png") == []


def test_scan_desktop_dirs_finds_app(tmp_path, monkeypatch):
    (tmp_path / "gimp.desktop").write_text(
        "[Desktop Entry]\nName=GIMP\nMimeType=image/png;image/jpeg;\n"
    )
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    result = _open_linux._scan_desktop_dirs("image/png")
    assert "gimp.desktop" in result


def test_scan_desktop_dirs_no_match(tmp_path, monkeypatch):
    (tmp_path / "vlc.desktop").write_text("[Desktop Entry]\nMimeType=video/mp4;\n")
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    assert _open_linux._scan_desktop_dirs("image/png") == []


def test_scan_desktop_dirs_deduplicates_across_dirs(tmp_path, monkeypatch):
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    d1.joinpath("gimp.desktop").write_text("MimeType=image/png;\n")
    d2.joinpath("gimp.desktop").write_text("MimeType=image/png;\n")
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [d1, d2])
    assert _open_linux._scan_desktop_dirs("image/png").count("gimp.desktop") == 1


def test_scan_desktop_dirs_oserror(tmp_path, monkeypatch):
    (tmp_path / "bad.desktop").write_text("...")
    orig = pathlib.Path.read_text

    def mock_read(self, *a, **kw):
        if self.name == "bad.desktop":
            raise OSError("denied")
        return orig(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "read_text", mock_read)
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    assert _open_linux._scan_desktop_dirs("image/png") == []


# ---------------------------------------------------------------------------
# _desktop_name
# ---------------------------------------------------------------------------


def test_desktop_name_found(tmp_path, monkeypatch):
    (tmp_path / "gimp.desktop").write_text("[Desktop Entry]\nName=GIMP\nExec=gimp %f\n")
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    assert _open_linux._desktop_name("gimp.desktop") == "GIMP"


def test_desktop_name_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    assert _open_linux._desktop_name("nonexistent.desktop") == ""


def test_desktop_name_oserror(tmp_path, monkeypatch):
    (tmp_path / "bad.desktop").write_text("...")
    orig = pathlib.Path.read_text

    def mock_read(self, *a, **kw):
        if self.name == "bad.desktop":
            raise OSError
        return orig(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "read_text", mock_read)
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    assert _open_linux._desktop_name("bad.desktop") == ""


_LOCALIZED_DESKTOP = (
    "[Desktop Entry]\n"
    "Name=GNU Image Manipulation Program\n"
    "Name[fr]=Programme de manipulation d'images GNU\n"
    "Name[zh_CN]=GNU图像处理程序\n"
    "[Desktop Action NewWindow]\n"
    "Name=New Window\n"
    "Name[fr]=Nouvelle fenêtre\n"
)


def test_desktop_name_uses_ui_language(tmp_path, monkeypatch):
    (tmp_path / "gimp.desktop").write_text(_LOCALIZED_DESKTOP)
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    monkeypatch.setattr(i18n, "current_language", lambda: "fr")
    assert (
        _open_linux._desktop_name("gimp.desktop")
        == "Programme de manipulation d'images GNU"
    )


def test_desktop_name_falls_back_to_bare_language(tmp_path, monkeypatch):
    (tmp_path / "gimp.desktop").write_text(
        "[Desktop Entry]\nName=GIMP\nName[fr]=GIMP (fr)\n"
    )
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    monkeypatch.setattr(i18n, "current_language", lambda: "fr_CA")
    assert _open_linux._desktop_name("gimp.desktop") == "GIMP (fr)"


def test_desktop_name_exact_locale_wins(tmp_path, monkeypatch):
    (tmp_path / "gimp.desktop").write_text(_LOCALIZED_DESKTOP)
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    monkeypatch.setattr(i18n, "current_language", lambda: "zh_CN")
    assert _open_linux._desktop_name("gimp.desktop") == "GNU图像处理程序"


def test_desktop_name_unknown_language_falls_back_to_unlocalized(tmp_path, monkeypatch):
    (tmp_path / "gimp.desktop").write_text(_LOCALIZED_DESKTOP)
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    monkeypatch.setattr(i18n, "current_language", lambda: "de")
    assert _open_linux._desktop_name("gimp.desktop") == "GNU Image Manipulation Program"


def test_desktop_name_ignores_desktop_action_group(tmp_path, monkeypatch):
    (tmp_path / "gimp.desktop").write_text(_LOCALIZED_DESKTOP)
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    monkeypatch.setattr(i18n, "current_language", lambda: "en")
    assert _open_linux._desktop_name("gimp.desktop") == "GNU Image Manipulation Program"


# ---------------------------------------------------------------------------
# _desktop_names / _pick_localized
# ---------------------------------------------------------------------------


def test_desktop_names_parses_entry_group_only():
    text = (
        "[Desktop Entry]\n"
        "# a comment line\n"
        "\n"
        "Name=Main\n"
        "Name[fr]=Principal\n"
        "Comment=x\n"
        "[Desktop Action Foo]\n"
        "Name=Action\n"
    )
    assert _open_linux._desktop_names(text) == {"": "Main", "fr": "Principal"}


def test_desktop_names_value_with_equals_sign():
    assert _open_linux._desktop_names("[Desktop Entry]\nName=a=b=c\n") == {"": "a=b=c"}


def test_desktop_names_no_entry_group():
    assert _open_linux._desktop_names("[Desktop Action Foo]\nName=Action\n") == {}


def test_pick_localized_prefers_exact_then_bare_then_default():
    names = {"": "d", "pt": "p", "pt_BR": "pb"}
    assert _open_linux._pick_localized(names, "pt_BR") == "pb"
    assert _open_linux._pick_localized(names, "pt_PT") == "p"
    assert _open_linux._pick_localized(names, "ru") == "d"
    assert _open_linux._pick_localized({"fr": "f"}, "de") == ""


# ---------------------------------------------------------------------------
# _mime_type
# ---------------------------------------------------------------------------


def _mock_run_result(returncode: int, stdout: str):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    return r


def test_mime_type_from_xdg(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: _mock_run_result(0, "image/jpeg\n")
    )
    assert _open_linux._mime_type(tmp_path / "test.jpg") == "image/jpeg"


def test_mime_type_xdg_not_found_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError())
    )
    assert _open_linux._mime_type(tmp_path / "test.jpg") == "image/jpeg"


def test_mime_type_xdg_empty_stdout_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _mock_run_result(0, ""))
    mime = _open_linux._mime_type(tmp_path / "test.jpg")
    assert "jpeg" in mime or mime == ""


def test_mime_type_xdg_nonzero_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: _mock_run_result(1, "error")
    )
    _open_linux._mime_type(tmp_path / "test.txt")  # should not raise


def test_mime_type_timeout_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: (_ for _ in ()).throw(
            subprocess.TimeoutExpired("xdg-mime", 3)
        ),
    )
    mime = _open_linux._mime_type(tmp_path / "test.png")
    assert "png" in mime


def test_mime_type_oserror_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(OSError())
    )
    _open_linux._mime_type(tmp_path / "test.jpg")  # should not raise


def test_mime_type_unknown_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError())
    )
    assert _open_linux._mime_type(tmp_path / "test.unknownxyz") == ""


# ---------------------------------------------------------------------------
# _registered_apps
# ---------------------------------------------------------------------------


def test_registered_apps_via_gio(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: _mock_run_result(
            0, "Registered applications:\n  gimp.desktop\n"
        ),
    )
    apps = _open_linux._registered_apps("image/png")
    assert "gimp.desktop" in apps


def test_registered_apps_gio_fails_fallback_scan(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError())
    )
    (tmp_path / "gimp.desktop").write_text("MimeType=image/png;\n")
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    apps = _open_linux._registered_apps("image/png")
    assert "gimp.desktop" in apps


def test_registered_apps_gio_empty_fallback_scan(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _mock_run_result(0, ""))
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    assert _open_linux._registered_apps("image/png") == []


def test_registered_apps_gio_timeout_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired("gio", 3)),
    )
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    assert _open_linux._registered_apps("image/png") == []


# ---------------------------------------------------------------------------
# _apps_for_path
# ---------------------------------------------------------------------------


def test_apps_for_path_no_mime(tmp_path, monkeypatch):
    monkeypatch.setattr(_open_linux, "_mime_type", lambda p: "")
    assert _open_linux._apps_for_path(tmp_path / "test.xyz") == ("", [])


def test_apps_for_path_with_name(tmp_path, monkeypatch):
    monkeypatch.setattr(_open_linux, "_mime_type", lambda p: "image/png")
    monkeypatch.setattr(_open_linux, "_registered_apps", lambda mime: ["gimp.desktop"])
    (tmp_path / "gimp.desktop").write_text("[Desktop Entry]\nName=GIMP\n")
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    mime, apps = _open_linux._apps_for_path(tmp_path / "test.png")
    assert mime == "image/png"
    assert apps == [("GIMP", "gimp.desktop")]


def test_apps_for_path_no_name_uses_stem(tmp_path, monkeypatch):
    monkeypatch.setattr(_open_linux, "_mime_type", lambda p: "image/png")
    monkeypatch.setattr(_open_linux, "_registered_apps", lambda mime: ["eog.desktop"])
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [])
    _, apps = _open_linux._apps_for_path(tmp_path / "test.png")
    assert apps == [("eog", "eog.desktop")]


def test_apps_for_path_deduplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(_open_linux, "_mime_type", lambda p: "image/png")
    monkeypatch.setattr(
        _open_linux, "_registered_apps", lambda mime: ["gimp.desktop", "gimp.desktop"]
    )
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [])
    _, apps = _open_linux._apps_for_path(tmp_path / "test.png")
    assert len(apps) == 1


def test_apps_for_path_orders_by_saved_lru(tmp_path, monkeypatch):
    settings.set_open_with_lru({"image/png": ["eog.desktop", "gone.desktop"]})
    monkeypatch.setattr(_open_linux, "_mime_type", lambda p: "image/png")
    monkeypatch.setattr(
        _open_linux, "_registered_apps", lambda mime: ["gimp.desktop", "eog.desktop"]
    )
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [])
    _, apps = _open_linux._apps_for_path(tmp_path / "test.png")
    # eog (remembered) first, gimp (newly appeared) at the end, gone.desktop dropped.
    assert [df for _, df in apps] == ["eog.desktop", "gimp.desktop"]


# ---------------------------------------------------------------------------
# _order_by_lru / _remember_choice
# ---------------------------------------------------------------------------


def test_order_by_lru_no_mime_is_identity():
    apps = [("GIMP", "gimp.desktop"), ("EOG", "eog.desktop")]
    assert _open_linux._order_by_lru("", apps) == apps


def test_order_by_lru_empty_saved_list_keeps_system_order(monkeypatch):
    monkeypatch.setattr(settings, "get_open_with_lru", lambda: {})
    apps = [("GIMP", "gimp.desktop"), ("EOG", "eog.desktop")]
    assert _open_linux._order_by_lru("image/png", apps) == apps


def test_order_by_lru_remembered_first_new_last(monkeypatch):
    monkeypatch.setattr(
        settings,
        "get_open_with_lru",
        lambda: {"image/png": ["eog.desktop", "krita.desktop"]},
    )
    apps = [
        ("GIMP", "gimp.desktop"),
        ("EOG", "eog.desktop"),
        ("Krita", "krita.desktop"),
    ]
    assert [df for _, df in _open_linux._order_by_lru("image/png", apps)] == [
        "eog.desktop",
        "krita.desktop",
        "gimp.desktop",
    ]


def test_remember_choice_moves_selection_to_front_and_prunes(tmp_path, monkeypatch):
    settings.set_open_with_lru({"image/png": ["old.desktop"]})
    _open_linux._remember_choice(
        "image/png", "gimp.desktop", ["gimp.desktop", "eog.desktop"]
    )
    assert settings.get_open_with_lru() == {
        "image/png": ["gimp.desktop", "eog.desktop"]
    }


def test_remember_choice_no_mime_is_noop(tmp_path):
    _open_linux._remember_choice("", "gimp.desktop", ["gimp.desktop"])
    assert settings.get_open_with_lru() == {}


# ---------------------------------------------------------------------------
# open_default
# ---------------------------------------------------------------------------


def test_open_default_calls_xdg_open(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        _open_linux.subprocess, "Popen", lambda args: calls.append(args)
    )
    path = tmp_path / "test.png"
    _open_linux.open_default(path)
    assert calls == [["xdg-open", str(path)]]


# ---------------------------------------------------------------------------
# open_with
# ---------------------------------------------------------------------------


def test_open_with_dialog_cancelled(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QDialog

    monkeypatch.setattr(_open_linux, "_apps_for_path", lambda p: ("", []))

    class _CancelDialog:
        def exec(self):
            return QDialog.Rejected

        def selected_desktop_file(self):
            return None

    monkeypatch.setattr(
        _open_linux, "_AppChooserDialog", lambda apps, parent: _CancelDialog()
    )
    _open_linux.open_with(tmp_path / "test.png")


def test_open_with_app_selected(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QDialog

    monkeypatch.setattr(
        _open_linux,
        "_apps_for_path",
        lambda p: ("image/png", [("GIMP", "gimp.desktop")]),
    )
    launched = []

    class _AcceptDialog:
        def exec(self):
            return QDialog.Accepted

        def selected_desktop_file(self):
            return "gimp.desktop"

    monkeypatch.setattr(
        _open_linux, "_AppChooserDialog", lambda apps, parent: _AcceptDialog()
    )
    monkeypatch.setattr(_open_linux, "_launch", lambda df, p: launched.append(df))
    _open_linux.open_with(tmp_path / "test.png")
    assert launched == ["gimp.desktop"]
    # The selection is recorded in the MRU list for that MIME type.
    assert settings.get_open_with_lru() == {"image/png": ["gimp.desktop"]}


def test_open_with_no_file_selected(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QDialog

    monkeypatch.setattr(
        _open_linux,
        "_apps_for_path",
        lambda p: ("image/png", [("GIMP", "gimp.desktop")]),
    )

    class _AcceptNoFile:
        def exec(self):
            return QDialog.Accepted

        def selected_desktop_file(self):
            return None

    monkeypatch.setattr(
        _open_linux, "_AppChooserDialog", lambda apps, parent: _AcceptNoFile()
    )
    _open_linux.open_with(tmp_path / "test.png")  # no crash


# ---------------------------------------------------------------------------
# _launch
# ---------------------------------------------------------------------------


def test_launch_via_gtk_launch(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: calls.append(cmd))
    _open_linux._launch("gimp.desktop", tmp_path / "test.png")
    assert calls[0][0] == "gtk-launch"


def test_launch_fallback_to_exec_via_desktop(tmp_path, monkeypatch):
    def mock_popen(cmd):
        if cmd[0] == "gtk-launch":
            raise FileNotFoundError
        return None

    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    exec_calls = []
    monkeypatch.setattr(
        _open_linux, "_exec_via_desktop", lambda df, p: exec_calls.append(df)
    )
    _open_linux._launch("gimp.desktop", tmp_path / "test.png")
    assert exec_calls == ["gimp.desktop"]


# ---------------------------------------------------------------------------
# _exec_via_desktop
# ---------------------------------------------------------------------------


def test_exec_via_desktop_with_exec(tmp_path, monkeypatch):
    (tmp_path / "gimp.desktop").write_text("[Desktop Entry]\nExec=gimp %f\n")
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    popen_calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: popen_calls.append(cmd))
    _open_linux._exec_via_desktop("gimp.desktop", tmp_path / "test.png")
    assert popen_calls[0][0] == "gimp"


def test_exec_via_desktop_file_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    _open_linux._exec_via_desktop("nonexistent.desktop", tmp_path / "test.png")


def test_exec_via_desktop_oserror(tmp_path, monkeypatch):
    (tmp_path / "bad.desktop").write_text("...")
    orig = pathlib.Path.read_text

    def mock_read(self, *a, **kw):
        if self.name == "bad.desktop":
            raise OSError
        return orig(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "read_text", mock_read)
    monkeypatch.setattr(_open_linux, "_app_dirs", lambda: [tmp_path])
    _open_linux._exec_via_desktop("bad.desktop", tmp_path / "test.png")


# ---------------------------------------------------------------------------
# _AppChooserDialog
# ---------------------------------------------------------------------------


def test_app_chooser_dialog_empty_list(qapp):
    dlg = _open_linux._AppChooserDialog([], None)
    assert dlg._list.count() == 0
    assert dlg.selected_desktop_file() is None


def test_app_chooser_dialog_with_apps(qtbot):
    apps = [("GIMP", "gimp.desktop"), ("Inkscape", "inkscape.desktop")]
    dlg = _open_linux._AppChooserDialog(apps, None)
    qtbot.addWidget(dlg)
    assert dlg._list.count() == 2
    assert dlg._list.currentRow() == 0
    assert dlg.selected_desktop_file() == "gimp.desktop"


def test_app_chooser_dialog_activate_accepts(qtbot):
    apps = [("GIMP", "gimp.desktop")]
    dlg = _open_linux._AppChooserDialog(apps, None)
    qtbot.addWidget(dlg)
    dlg._on_activate(dlg._list.item(0))
    # accepted state set (we can't call exec() but _on_activate calls accept())


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------


def test_macos_open_default(tmp_path, monkeypatch):
    f = tmp_path / "test.png"
    f.touch()
    calls = []
    monkeypatch.setattr(
        _open_macos.QDesktopServices,
        "openUrl",
        staticmethod(lambda url: calls.append(url)),
    )
    _open_macos.open_default(f)
    assert len(calls) == 1


def test_macos_open_with_cancel(tmp_path, monkeypatch):
    from unittest.mock import patch

    f = tmp_path / "test.png"
    f.touch()
    open_calls = []
    monkeypatch.setattr(
        _open_macos.QDesktopServices,
        "openUrl",
        staticmethod(lambda url: open_calls.append(url)),
    )
    with patch("PySide6.QtWidgets.QInputDialog.getText", return_value=("", False)):
        _open_macos.open_with(f)
    # Cancel (ok=False) → falls back to open_default → openUrl is called
    assert len(open_calls) == 1


def test_macos_open_with_app(tmp_path, monkeypatch):
    from unittest.mock import patch

    f = tmp_path / "test.png"
    f.touch()
    popen_calls = []
    monkeypatch.setattr(
        _open_macos.subprocess, "Popen", lambda cmd: popen_calls.append(cmd)
    )
    with patch(
        "PySide6.QtWidgets.QInputDialog.getText", return_value=("Preview", True)
    ):
        _open_macos.open_with(f)
    assert popen_calls == [["open", "-a", "Preview", str(f)]]


def test_macos_open_with_empty_app_falls_back(tmp_path, monkeypatch):
    from unittest.mock import patch

    f = tmp_path / "test.png"
    f.touch()
    open_calls = []
    monkeypatch.setattr(
        _open_macos.QDesktopServices,
        "openUrl",
        staticmethod(lambda url: open_calls.append(url)),
    )
    with patch("PySide6.QtWidgets.QInputDialog.getText", return_value=("   ", True)):
        _open_macos.open_with(f)
    assert len(open_calls) == 1


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


def test_windows_open_default(tmp_path):
    f = tmp_path / "test.jpg"
    f.touch()
    calls = []
    with patch(
        "pbrenamer.platform._open_windows.os.startfile",
        create=True,
        side_effect=lambda p: calls.append(p),
    ):
        _open_windows.open_default(f)
    assert calls == [str(f)]


def test_windows_open_with_success(tmp_path):
    f = tmp_path / "test.jpg"
    f.touch()
    calls = []
    with patch(
        "pbrenamer.platform._open_windows.os.startfile",
        create=True,
        side_effect=lambda p, verb=None: calls.append((p, verb)),
    ):
        _open_windows.open_with(f)
    assert calls[0] == (str(f), "openas")


def test_windows_open_with_oserror_falls_back_to_default(tmp_path):
    f = tmp_path / "test.jpg"
    f.touch()
    calls = []

    def mock_startfile(p, verb=None):
        if verb == "openas":
            raise OSError("not supported")
        calls.append(p)

    with patch(
        "pbrenamer.platform._open_windows.os.startfile",
        create=True,
        side_effect=mock_startfile,
    ):
        _open_windows.open_with(f)
    assert calls == [str(f)]


def test_dispatch_on_linux():
    assert open_with.open_default is _open_linux.open_default
    assert open_with.open_with is _open_linux.open_with


def test_remember_choice_write_error_ignored(monkeypatch):
    def boom(_data):
        raise OSError("read-only")

    monkeypatch.setattr(settings, "set_open_with_lru", boom)
    _open_linux._remember_choice("image/png", "gimp.desktop", ["gimp.desktop"])
