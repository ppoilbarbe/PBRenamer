"""Session trash: deleted files kept for an undo until the program exits.

Each run owns a unique directory below *root* (``tempfile.mkdtemp``),
guarded by a ``QLockFile`` named after it (``<dir>.lock``).  The lock tells
a live session from the leftovers of a crashed one: when it can be taken,
its owner is dead and the directory is removed (``cleanup_stale``).

Files are moved, never copied: a file on another filesystem than the trash
raises ``CrossDeviceError``.  They are named ``000001.cache``,
``000002.cache``…; the caller keeps their original path.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QLockFile

from pbrenamer.platform.fs import is_cross_device

_log = logging.getLogger(__name__)

_LOCK_SUFFIX = ".lock"
_FILE_SUFFIX = ".cache"


class CrossDeviceError(OSError):
    """The file is not on the filesystem of the session trash."""


def _new_lock(path: str) -> QLockFile:
    lock = QLockFile(path)
    # Only the death of the owner (checked by Qt) makes a lock stale.
    lock.setStaleLockTime(0)
    return lock


class SessionTrash:
    """The session trash of this run, created on first use below *root*."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._dir: Path | None = None
        self._lock: QLockFile | None = None
        self._count = 0

    @property
    def directory(self) -> Path | None:
        """The trash directory of this run, None before the first use."""
        return self._dir

    def cleanup_stale(self) -> None:
        """Remove the trash directories left by sessions no longer running."""
        try:
            entries = list(self._root.iterdir())
        except OSError:
            return
        for entry in entries:
            if not entry.is_dir() or entry == self._dir:
                continue
            lock_path = str(entry) + _LOCK_SUFFIX
            lock = None
            if os.path.exists(lock_path):
                lock = _new_lock(lock_path)
                if not lock.tryLock(0):
                    continue  # a live session
            _log.info("Removing stale session trash %s", entry)
            shutil.rmtree(entry, ignore_errors=True)
            if lock is not None:
                lock.unlock()
        for entry in entries:
            # Lock files whose directory is gone (removed above, or never made).
            name = entry.name
            if (
                name.endswith(_LOCK_SUFFIX)
                and not (self._root / name[: -len(_LOCK_SUFFIX)]).exists()
            ):
                lock = _new_lock(str(entry))
                if lock.tryLock(0):
                    lock.unlock()

    def _ensure(self) -> Path:
        if self._dir is None:
            self._root.mkdir(parents=True, exist_ok=True)
            directory = Path(tempfile.mkdtemp(dir=self._root))
            lock = _new_lock(str(directory) + _LOCK_SUFFIX)
            if not lock.tryLock(0):  # pragma: no cover — fresh unique name
                shutil.rmtree(directory, ignore_errors=True)
                raise OSError(f"cannot lock the session trash {directory}")
            self._dir, self._lock = directory, lock
            _log.info("Session trash: %s", directory)
        return self._dir

    def put(self, path: str) -> str:
        """Move *path* into the trash; return its path there.

        Raises CrossDeviceError when *path* is on another filesystem, and
        OSError for any other failure.
        """
        directory = self._ensure()
        self._count += 1
        target = str(directory / f"{self._count:06d}{_FILE_SUFFIX}")
        try:
            os.rename(path, target)
        except OSError as exc:
            if is_cross_device(exc):
                raise CrossDeviceError(exc.errno, exc.strerror, path) from exc
            raise
        return target

    def close(self) -> None:
        """Remove the trash directory of this run and release its lock."""
        if self._dir is None:
            return
        _log.info("Removing session trash %s", self._dir)
        shutil.rmtree(self._dir, ignore_errors=True)
        if self._lock is not None:
            self._lock.unlock()
        self._dir = self._lock = None
