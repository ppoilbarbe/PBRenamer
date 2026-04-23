"""Filesystem-level utilities."""

from __future__ import annotations

import os
import sys
import tempfile
from functools import lru_cache


@lru_cache(maxsize=32)
def is_case_sensitive(directory: str) -> bool:
    """Return True if the filesystem at *directory* is case-sensitive.

    The result is probed by creating a temporary file with a mixed-case name
    and checking whether the swapped-case counterpart resolves to the same
    inode.  The outcome is cached per directory string.

    Falls back to an OS-level heuristic when probing fails (e.g. read-only
    filesystem, permission error).
    """
    try:
        with tempfile.NamedTemporaryFile(
            prefix="PBrEnAmEr_", dir=directory, delete=False
        ) as f:
            tmp = f.name
        try:
            alt = os.path.join(directory, os.path.basename(tmp).swapcase())
            return not os.path.exists(alt)
        finally:
            os.unlink(tmp)
    except OSError:
        # Cannot probe: Windows and macOS default filesystems are
        # case-insensitive; Linux defaults are case-sensitive.
        return sys.platform not in ("win32", "darwin")


def same_file_path(a: str, b: str, directory: str) -> bool:
    """Return True if *a* and *b* refer to the same filesystem entry.

    Takes case sensitivity of the filesystem at *directory* into account.
    """
    if is_case_sensitive(directory):
        return a == b
    return a.lower() == b.lower()


def conflict_key(path: str, directory: str) -> str:
    """Return a normalised key for *path* suitable for conflict detection.

    On case-insensitive filesystems the key is lowercased so that
    ``File.txt`` and ``file.txt`` collide as expected.
    """
    return path if is_case_sensitive(directory) else path.lower()
