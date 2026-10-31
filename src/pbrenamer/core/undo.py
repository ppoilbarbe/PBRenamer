"""Undo stack of file operations, one typed entry per batch."""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field

from pbrenamer.core import filetools, image_ops

_log = logging.getLogger(__name__)


class UndoError(OSError):
    """An undo failed; the files are left as they were before the attempt."""


class UndoEntry:
    """One undoable batch.  Subclasses revert it in undo()."""

    def undo(self) -> None:  # pragma: no cover — abstract
        raise NotImplementedError


@dataclass
class RenameEntry(UndoEntry):
    """A batch done by filetools.execute_renames(), reverted atomically.

    Directories it created are removed if left empty; directories it pruned
    are recreated by the reverse rename.
    """

    pairs: list[tuple[str, str]]
    created_dirs: list[str] = field(default_factory=list)
    pruned_dirs: list[str] = field(default_factory=list)

    @classmethod
    def from_result(cls, result: filetools.RenameResult) -> RenameEntry:
        return cls(result.pairs, result.created_dirs, result.pruned_dirs)

    def undo(self) -> None:
        try:
            filetools.execute_renames([(dst, src) for src, dst in self.pairs])
        except filetools.RenameError as exc:
            raise UndoError(str(exc)) from exc
        filetools.remove_empty_dirs(self.created_dirs)


@dataclass
class MoveEntry(UndoEntry):
    """Files or trees moved by drag and drop, moved back one by one."""

    pairs: list[tuple[str, str]]

    def undo(self) -> None:
        errors: list[str] = []
        for src, dst in reversed(self.pairs):
            ok, err = filetools.move_path(dst, src)
            if not ok:
                errors.append(f"{os.path.basename(dst)}: {err}")
        if errors:
            raise UndoError("\n".join(errors))


@dataclass
class CopyEntry(UndoEntry):
    """Files or trees copied: undoing deletes the copies."""

    pairs: list[tuple[str, str]]

    def undo(self) -> None:
        errors: list[str] = []
        for _src, dst in reversed(self.pairs):
            try:
                if os.path.isdir(dst) and not os.path.islink(dst):
                    shutil.rmtree(dst)
                else:
                    os.remove(dst)
            except OSError as exc:
                errors.append(f"{os.path.basename(dst)}: {exc}")
        if errors:
            raise UndoError("\n".join(errors))


@dataclass
class RotationEntry(UndoEntry):
    """Images rotated by image_ops.rotate_lossless(): each item is
    (path, inverse op, EXIF orientation before the rotation or None)."""

    items: list[tuple[str, image_ops.Op, int | None]]

    def undo(self) -> None:
        errors: list[str] = []
        for path, inverse, orientation in reversed(self.items):
            try:
                image_ops.rotate_lossless(path, inverse)
                if orientation is not None:
                    image_ops.set_exif_orientation(path, orientation)
            except (OSError, RuntimeError, ValueError) as exc:
                errors.append(f"{os.path.basename(path)}: {exc}")
        if errors:
            raise UndoError("\n".join(errors))


@dataclass
class ExifResetEntry(UndoEntry):
    """EXIF orientations forced to 1: each item is (path, previous value)."""

    items: list[tuple[str, int]]

    def undo(self) -> None:
        for path, orientation in self.items:
            image_ops.set_exif_orientation(path, orientation)


class UndoManager:
    """Stack-based undo manager; each entry is one batch."""

    def __init__(self) -> None:
        self._history: list[UndoEntry] = []

    def add(self, entry: UndoEntry) -> None:
        self._history.append(entry)

    def add_batch(self, moves: list[tuple[str, str]]) -> None:
        """Record a batch of moves [(original_path, new_path), ...]."""
        self.add(MoveEntry(moves))

    def undo(self) -> None:
        """Revert the most recent batch.

        The entry is dropped even when the undo fails (UndoError), so that a
        broken entry cannot block the older ones.
        """
        if not self._history:
            return
        entry = self._history.pop()
        _log.info("Undoing %s", type(entry).__name__)
        entry.undo()

    def can_undo(self) -> bool:
        return bool(self._history)

    def __len__(self) -> int:
        return len(self._history)

    def clear(self) -> None:
        self._history.clear()
