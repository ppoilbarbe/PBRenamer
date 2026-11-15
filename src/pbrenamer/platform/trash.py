"""System trash: move a file to it, and move it back for an undo.

Qt moves files to the trash (``QFile.moveToTrash``) but cannot restore
them.  The path Qt gives the file in the trash is enough to move it back;
the metadata the platform keeps beside it is then removed:

- Linux (freedesktop): ``Trash/files/<name>`` + ``Trash/info/<name>.trashinfo``;
- Windows: ``$Recycle.Bin/<SID>/$R…`` + ``$I…`` (same suffix);
- macOS: nothing to remove (the Finder "Put Back" data is merely lost).
"""

from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import QFile

from pbrenamer.core import filetools

_log = logging.getLogger(__name__)


def move_to_trash(path: str) -> str | None:
    """Move *path* to the system trash; return its path there, or None.

    The instance form of ``moveToTrash`` is used: it updates ``fileName()``
    with the path in the trash, which the static form does not return in
    PySide6.  *path* is made absolute: a relative one would be written as
    is in the freedesktop ``.trashinfo``.
    """
    file = QFile(os.path.abspath(path))
    if not file.moveToTrash():
        return None
    return file.fileName()


def _metadata_path(trash_path: str) -> str | None:
    """Return the metadata file the platform keeps for *trash_path*."""
    directory, name = os.path.split(trash_path)
    if sys.platform == "win32":
        if name.startswith("$R"):
            return os.path.join(directory, "$I" + name[2:])
        return None
    if sys.platform == "darwin":
        return None
    trash_dir, files = os.path.split(directory)
    if files != "files":
        return None
    return os.path.join(trash_dir, "info", name + ".trashinfo")


def restore(trash_path: str, original: str) -> None:
    """Move *trash_path* back to *original*; raise OSError on failure.

    Fails when the file has left the trash (emptied, restored by hand) or
    when *original* exists again.
    """
    if not os.path.lexists(trash_path):
        raise FileNotFoundError(f"no longer in the trash: {trash_path}")
    if os.path.lexists(original):
        raise FileExistsError(f"already exists: {original}")
    os.makedirs(os.path.dirname(original) or ".", exist_ok=True)
    ok, err = filetools.move_path(trash_path, original)
    if not ok:
        raise OSError(err)
    metadata = _metadata_path(trash_path)
    if metadata is not None:
        try:
            os.remove(metadata)
        except FileNotFoundError:
            pass
        except OSError as exc:
            _log.warning("Could not remove trash metadata %s: %s", metadata, exc)
