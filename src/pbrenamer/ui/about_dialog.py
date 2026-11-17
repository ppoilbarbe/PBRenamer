"""About dialog."""

from __future__ import annotations

import importlib
import sys
from email.utils import getaddresses
from importlib.metadata import PackageNotFoundError, metadata, version

from PySide6 import __version__ as _pyside_version
from PySide6.QtWidgets import QApplication, QDialog, QLabel

from pbrenamer import __version__
from pbrenamer.ui.about_dialog_ui import Ui_AboutDialog


class AboutDialog(QDialog):
    """Application About dialog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ui = Ui_AboutDialog()
        self._ui.setupUi(self)

        self._ui.lblVersion.setText(__version__)
        self._ui.lblAuthors.setText(_authors_html())
        py = sys.version_info
        self._ui.lblPythonVersion.setText(f"{py.major}.{py.minor}.{py.micro}")
        self._ui.lblPySideVersion.setText(_pyside_version)

        for name, ver in optional_dependencies():
            value = QLabel(ver if ver is not None else _("Not installed"), self)
            if ver is None:
                value.setEnabled(False)
            self._ui.formOptional.addRow(name + ":", value)

        icon = QApplication.windowIcon()
        if not icon.isNull():
            self._ui.lblIcon.setPixmap(icon.pixmap(64, 64))


# (display name, module to import, distribution name for importlib.metadata)
_OPTIONAL_DEPENDENCIES = (
    ("Pillow", "PIL", "pillow"),
    ("pillow-heif", "pillow_heif", "pillow-heif"),
    ("pyexiv2", "pyexiv2", "pyexiv2"),
    ("mutagen", "mutagen", "mutagen"),
    ("pymediainfo", "pymediainfo", "pymediainfo"),
)


def optional_dependencies() -> list[tuple[str, str | None]]:
    """Return ``(name, version)`` for each optional dependency.

    *version* is ``None`` when the package cannot be imported, and ``"?"``
    when it is present but its version is unknown.  For wrappers around a
    native library, the library version (or its absence) is appended in
    parentheses.
    """
    result: list[tuple[str, str | None]] = []
    for name, module_name, dist in _OPTIONAL_DEPENDENCIES:
        try:
            module = importlib.import_module(module_name)
        except Exception:  # noqa: BLE001 — missing package or native library
            result.append((name, None))
            continue
        ver = _module_version(module, dist)
        extra = _native_library_info(module_name, module)
        result.append((name, f"{ver} ({extra})" if extra else ver))
    return result


def _module_version(module, dist: str) -> str:
    # Module attributes first: the frozen executable may lack dist-info.
    for attr in ("__version__", "version_string"):
        ver = getattr(module, attr, None)
        if isinstance(ver, str) and ver:
            return ver
    try:
        return version(dist)
    except PackageNotFoundError:
        return "?"


def _native_library_info(module_name: str, module) -> str:
    """Describe the native library a wrapper module depends on, if any."""
    try:
        if module_name == "pillow_heif":
            return f"libheif {module.libheif_version()}"
        if module_name == "pyexiv2":
            return f"Exiv2 {module.__exiv2_version__}"
        if module_name == "pymediainfo":
            if module.MediaInfo.can_parse():
                return ""
            return _("MediaInfo library not found")
    except Exception:  # noqa: BLE001
        return ""
    return ""


def _authors_html() -> str:
    try:
        meta = metadata("pbrenamer")
        raw = meta.get_all("Author-email") or []
        pairs = getaddresses(raw)
    except Exception:  # noqa: BLE001
        pairs = []

    parts = []
    for name, addr in pairs:
        label = name or addr
        if addr:
            parts.append(f'<a href="mailto:{addr}">{label}</a>')
        else:
            parts.append(label)
    return ", ".join(parts)
