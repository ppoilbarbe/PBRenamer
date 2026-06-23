"""PyInstaller runtime hook — portable fontconfig on Linux.

On Linux, Qt uses fontconfig to locate fonts. The fonts.conf bundled by
PyInstaller contains absolute paths to the conda environment of the build
machine (e.g. /home/runner/…) that do not exist on the target machine.

This hook runs at frozen-app startup, before Qt initialises. It:
  1. Writes a minimal fonts.conf into sys._MEIPASS pointing to the bundled
     fonts (fonts/) and the system fonts (/usr/share/fonts).
  2. Sets FONTCONFIG_FILE so that fontconfig picks up this file.
"""

import os
import sys

if sys.platform != "linux" or not getattr(sys, "frozen", False):
    pass
else:
    _meipass = sys._MEIPASS
    _fonts_dir = os.path.join(_meipass, "fonts")
    if os.path.isdir(_fonts_dir):
        _conf_path = os.path.join(_meipass, "fonts.conf")
        # Include the system fonts.conf so that all rendering settings
        # (anti-aliasing, hinting, subpixel, …) and system fonts are inherited.
        # Only the bundled fonts directory needs to be added explicitly.
        _conf = f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <dir>{_fonts_dir}</dir>
  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
</fontconfig>
"""
        with open(_conf_path, "w", encoding="utf-8") as _f:
            _f.write(_conf)
        os.environ["FONTCONFIG_FILE"] = _conf_path

        # Force fontconfig to (re-)initialize with the new FONTCONFIG_FILE.
        # libfontconfig may have already been dlopen'd and self-initialized with
        # its compile-time defaults (hardcoded to the build machine's conda path)
        # before this hook ran.  FcFini() + FcInit() resets it so it re-reads
        # FONTCONFIG_FILE before Qt's QFontDatabase is populated.
        try:
            import ctypes

            _fc = ctypes.CDLL("libfontconfig.so.1")
            _fc.FcFini()
            _fc.FcInit()
        except OSError:
            pass
