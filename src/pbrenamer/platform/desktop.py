"""Install a desktop menu entry for the current user (Linux/XDG only).

pip installs cannot register themselves in the system application menu —
there is no post-install hook in the wheel/pip install flow. This module
implements the opt-in fallback: a CLI flag the user runs once after
installing from PyPI.
"""

from __future__ import annotations

import gettext
import os
import shutil
import subprocess
import sys
from pathlib import Path

from pbrenamer import resources

_DOMAIN = "pbrenamer"
# platform/desktop.py -> platform/ -> pbrenamer/ -> locale/  (mirrors i18n.py,
# duplicated rather than imported so this module stays Qt-free — it must run
# before i18n.setup()/QApplication exist, same constraint as --help-search).
_LOCALE_DIR = Path(__file__).resolve().parent.parent / "locale"

# Kept as plain text (not wrapped in `_()`) and matched verbatim against the
# existing msgid from about_dialog_ui.py, so every language already has a
# translated msgstr — no new translation work needed.
_DESCRIPTION = "A graphical batch file renaming utility."


def _localized_comments() -> list[str]:
    """Return ["Comment=...", "Comment[fr]=...", ...] for every catalogue that
    actually translates `_DESCRIPTION` (skips languages with no .mo, and any
    whose translation is identical to the default, e.g. English)."""
    lines = [f"Comment={_DESCRIPTION}"]
    for mo_path in sorted(_LOCALE_DIR.glob("*/LC_MESSAGES/pbrenamer.mo")):
        lang = mo_path.parts[-3]
        try:
            t = gettext.translation(
                _DOMAIN, localedir=str(_LOCALE_DIR), languages=[lang]
            )
        except FileNotFoundError:
            continue
        translated = t.gettext(_DESCRIPTION)
        if translated != _DESCRIPTION:
            lines.append(f"Comment[{lang}]={translated}")
    return lines


def _desktop_entry_content(exec_path: str) -> str:
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        "Name=PBRenamer",
        *_localized_comments(),
        f"Exec={exec_path} %f",
        "Icon=pbrenamer",
        "Categories=Utility;FileTools;",
        "Terminal=false",
        "",
    ]
    return "\n".join(lines)


def _resolve_executable() -> str | None:
    """Return the absolute path to the running `pbrenamer` script, if any.

    `sys.argv[0]` is the script that was actually resolved on PATH to launch
    this process. It is unusable when running via `python -m pbrenamer`
    (points at `__main__.py`), in which case fall back to a PATH lookup.
    """
    script = Path(sys.argv[0])
    if script.suffix != ".py" and script.is_file():
        return str(script.resolve())
    return shutil.which("pbrenamer")


def _xdg_data_home() -> Path:
    val = os.environ.get("XDG_DATA_HOME", "")
    p = Path(val) if val else None
    return p if (p and p.is_absolute()) else Path.home() / ".local" / "share"


def _paths(data_home: Path) -> tuple[Path, Path]:
    """Return (desktop_file_path, icon_path) for *data_home*."""
    return (
        data_home / "applications" / "pbrenamer.desktop",
        data_home / "icons" / "hicolor" / "scalable" / "apps" / "pbrenamer.svg",
    )


def _refresh_caches(data_home: Path) -> None:
    """Best-effort refresh of the desktop/icon caches; missing tools are fine."""
    for cmd, arg in (
        ("update-desktop-database", str(data_home / "applications")),
        ("gtk-update-icon-cache", str(data_home / "icons" / "hicolor")),
    ):
        resolved = shutil.which(cmd)
        if resolved:
            subprocess.run([resolved, arg], check=False, capture_output=True)


def install_desktop_entry() -> tuple[bool, str]:
    """Install a .desktop entry + icon for the current user.

    Returns (success, message) — the message is meant to be printed as-is.
    """
    if not sys.platform.startswith("linux"):
        return False, (
            "error: desktop entry installation is only supported on Linux; "
            "macOS and Windows builds already integrate via the native "
            "app bundle / installer"
        )

    exec_path = _resolve_executable()
    if exec_path is None:
        return False, (
            "error: could not locate the 'pbrenamer' executable on PATH "
            "— desktop entry installation aborted"
        )

    data_home = _xdg_data_home()
    desktop_path, icon_path = _paths(data_home)
    desktop_path.parent.mkdir(parents=True, exist_ok=True)
    icon_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(resources.path("pbrenamer.svg"), icon_path)

    desktop_path.write_text(_desktop_entry_content(exec_path), encoding="utf-8")
    desktop_path.chmod(0o755)

    _refresh_caches(data_home)

    return True, f"Desktop entry installed: {desktop_path}"


def uninstall_desktop_entry() -> tuple[bool, str]:
    """Remove the .desktop entry + icon installed by `install_desktop_entry`.

    Returns (success, message) — the message is meant to be printed as-is.
    Removing an entry that was never installed is not an error.
    """
    if not sys.platform.startswith("linux"):
        return False, (
            "error: desktop entry removal is only supported on Linux; "
            "macOS and Windows builds already integrate via the native "
            "app bundle / installer"
        )

    data_home = _xdg_data_home()
    desktop_path, icon_path = _paths(data_home)

    removed = False
    for target in (desktop_path, icon_path):
        if target.is_file():
            target.unlink()
            removed = True

    _refresh_caches(data_home)

    if removed:
        return True, f"Desktop entry removed: {desktop_path}"
    return True, "No desktop entry found (nothing to remove)."
