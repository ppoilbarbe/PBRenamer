"""Undo manager for batch file renames."""

from pbrenamer.core import filetools


class UndoManager:
    """Stack-based undo manager; each entry is one rename batch."""

    def __init__(self) -> None:
        self._history: list[list[tuple[str, str]]] = []

    def add_batch(self, renames: list[tuple[str, str]]) -> None:
        """Record a completed rename batch [(original_path, new_path), ...]."""
        self._history.append(renames)

    def undo(self) -> None:
        """Revert the most recent rename batch."""
        if not self._history:
            return
        for original, renamed in reversed(self._history.pop()):
            filetools.rename_file(renamed, original)

    def can_undo(self) -> bool:
        return bool(self._history)

    def clear(self) -> None:
        self._history.clear()
