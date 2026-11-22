"""Open a file with the default application, or with a chosen one.

The implementation is picked once at import time:

- Linux: XDG (``xdg-open``, ``gio mime``, ``.desktop`` files), with an
  application chooser ordered by the most recently used per MIME type;
- macOS: ``open`` / ``open -a``;
- Windows: ``os.startfile`` with the system "Open with" dialog.

``last_app(path)`` names the application last chosen with "Open with" for
the type of *path* (None when there is none, always on Windows, whose
dialog does not tell the choice); ``open_with_last(path)`` opens *path*
with it.
"""

import sys

if sys.platform == "win32":  # pragma: no cover
    from pbrenamer.platform._open_windows import (
        last_app,
        open_default,
        open_with,
        open_with_last,
    )
elif sys.platform == "darwin":  # pragma: no cover
    from pbrenamer.platform._open_macos import (
        last_app,
        open_default,
        open_with,
        open_with_last,
    )
else:
    from pbrenamer.platform._open_linux import (
        last_app,
        open_default,
        open_with,
        open_with_last,
    )

__all__ = ["last_app", "open_default", "open_with", "open_with_last"]
