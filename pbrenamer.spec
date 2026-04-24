# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PBRenamer.

The output name embeds the version and the target platform so that builds
for different systems can coexist in the same directory:

  Linux   → dist/PBRenamer-<version>-linux-x86_64
  Windows → dist/PBRenamer-<version>-windows-x86_64.exe
  macOS   → dist/PBRenamer-<version>-macos-arm64.app

Build with:  make dist
"""

import platform
import sys
import tomllib
from pathlib import Path

# ---------------------------------------------------------------------------
# Version (read from pyproject.toml — single source of truth)
# ---------------------------------------------------------------------------

with open("pyproject.toml", "rb") as _f:
    _version = tomllib.load(_f)["project"]["version"]

# ---------------------------------------------------------------------------
# Platform tag  (OS-arch, e.g. linux-x86_64, windows-x86_64, macos-arm64)
# ---------------------------------------------------------------------------

_machine = platform.machine().lower()
_arch = {
    "x86_64": "x86_64",
    "amd64":  "x86_64",   # Windows reports AMD64
    "arm64":  "arm64",    # macOS Apple Silicon
    "aarch64":"arm64",    # Linux ARM 64-bit
}.get(_machine, _machine)

if sys.platform == "linux":
    _os = "linux"
elif sys.platform == "win32":
    _os = "windows"
elif sys.platform == "darwin":
    _os = "macos"
else:
    _os = sys.platform

_artifact_name = f"PBRenamer-{_version}-{_os}-{_arch}"

# ---------------------------------------------------------------------------
# Data files to bundle
# ---------------------------------------------------------------------------

# Compiled gettext catalogues (.mo).  Source layout:
#   src/pbrenamer/locale/<lang>/LC_MESSAGES/pbrenamer.mo
# Destination inside the frozen app (mirrors the installed package layout):
#   pbrenamer/locale/<lang>/LC_MESSAGES/pbrenamer.mo
_locale_root = Path("src/pbrenamer/locale")
_datas = [
    (str(mo), f"pbrenamer/locale/{mo.parts[-3]}/LC_MESSAGES")
    for mo in sorted(_locale_root.glob("*/LC_MESSAGES/pbrenamer.mo"))
]

# Bundled resources (icons, …).
_datas += [("src/pbrenamer/resources", "pbrenamer/resources")]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

a = Analysis(
    ["src/pbrenamer/__main__.py"],
    # Needed so that `import pbrenamer` resolves against the src tree even
    # without an editable install in the build environment.
    pathex=["src"],
    datas=_datas,
    # The platform sub-package is discovered dynamically; list it explicitly
    # so PyInstaller does not miss any module.
    hiddenimports=[
        "pbrenamer.platform",
        "pbrenamer.platform.dirs",
        "pbrenamer.platform.fs",
        "pbrenamer.platform.locale",
    ],
    hookspath=[],
    runtime_hooks=[],
    # Exclude heavy stdlib modules that PBRenamer never uses.
    excludes=["tkinter", "unittest", "email", "http", "xml", "numpy", "matplotlib"],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# Platform-specific packaging
# ---------------------------------------------------------------------------

if sys.platform == "darwin":
    # macOS: directory-based .app bundle (Apple convention).
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=_artifact_name,
        console=False,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        name=_artifact_name,
    )
    BUNDLE(
        coll,
        name=f"{_artifact_name}.app",
        bundle_identifier="net.cardolan.pbrenamer",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": _version,
            "CFBundleName": "PBRenamer",
        },
    )

else:
    # Linux / Windows: single self-contained file.
    EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        name=_artifact_name,
        # No console window on Windows; harmless on Linux.
        console=False,
    )
