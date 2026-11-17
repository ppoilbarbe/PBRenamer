"""PyInstaller runtime hook — clean library path for child processes on Linux.

The onefile bootloader points LD_LIBRARY_PATH at the extraction directory
(sys._MEIPASS) and keeps the user's value in LD_LIBRARY_PATH_ORIG.  Every
child process inherits it, so system tools launched by PBRenamer (xdg-open →
gio, gtk-launch, file managers, viewers…) load the bundled conda libraries
instead of the system ones.  The bundled libgio then looks for its helper
``gio-launch-desktop`` under the build machine's prefix, which does not exist
on the target machine: opening a folder, a file or the user guide silently
does nothing.

glibc reads LD_LIBRARY_PATH only once, at process start, so restoring it here
does not affect PBRenamer itself; it only fixes the environment handed to the
programs it starts (via subprocess or Qt's QDesktopServices).
"""

import os
import sys

if sys.platform == "linux" and getattr(sys, "frozen", False):
    _orig = os.environ.pop("LD_LIBRARY_PATH_ORIG", None)
    if _orig:
        os.environ["LD_LIBRARY_PATH"] = _orig
    else:
        os.environ.pop("LD_LIBRARY_PATH", None)
