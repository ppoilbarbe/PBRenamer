"""Open a file with the default application, or with a chosen one.

The implementation is picked once at import time:

- Linux: XDG (``xdg-open``, ``gio mime``, ``.desktop`` files), with an
  application chooser ordered by the most recently used per MIME type;
- macOS: ``open`` / ``open -a``;
- Windows: ``os.startfile`` with the system "Open with" dialog.
"""

import sys

if sys.platform == "win32":  # pragma: no cover
    from pbrenamer.platform._open_windows import open_default, open_with
elif sys.platform == "darwin":  # pragma: no cover
    from pbrenamer.platform._open_macos import open_default, open_with
else:
    from pbrenamer.platform._open_linux import open_default, open_with

__all__ = ["open_default", "open_with"]
