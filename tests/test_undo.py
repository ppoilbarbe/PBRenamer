"""Tests for pbrenamer.core.undo — UndoManager and typed entries."""

import os

import pytest

from pbrenamer.core import filetools
from pbrenamer.core.undo import (
    CopyEntry,
    MoveEntry,
    RenameEntry,
    UndoError,
    UndoManager,
)


class TestCanUndo:
    def test_empty_stack_returns_false(self):
        assert not UndoManager().can_undo()

    def test_after_add_batch_returns_true(self):
        um = UndoManager()
        um.add_batch([("/a", "/b")])
        assert um.can_undo()

    def test_after_clear_returns_false(self):
        um = UndoManager()
        um.add_batch([("/a", "/b")])
        um.clear()
        assert not um.can_undo()


class TestUndoOnDisk:
    def test_undo_reverts_single_rename(self, tmp_path):
        src = tmp_path / "original.txt"
        dst = tmp_path / "renamed.txt"
        src.touch()
        filetools.rename_file(str(src), str(dst))

        um = UndoManager()
        um.add_batch([(str(src), str(dst))])
        um.undo()

        assert src.exists()
        assert not dst.exists()

    def test_undo_reverts_batch_in_reverse_order(self, tmp_path):
        """A batch of two renames must be reverted newest-first."""
        a, b = tmp_path / "a.txt", tmp_path / "b.txt"
        c, d = tmp_path / "c.txt", tmp_path / "d.txt"
        a.touch()
        b.touch()
        filetools.rename_file(str(a), str(c))
        filetools.rename_file(str(b), str(d))

        um = UndoManager()
        um.add_batch([(str(a), str(c)), (str(b), str(d))])
        um.undo()

        assert a.exists()
        assert b.exists()
        assert not c.exists()
        assert not d.exists()

    def test_undo_empty_stack_is_noop(self):
        um = UndoManager()
        um.undo()  # must not raise

    def test_undo_pops_batch_from_stack(self, tmp_path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.touch()
        filetools.rename_file(str(src), str(dst))

        um = UndoManager()
        um.add_batch([(str(src), str(dst))])
        assert um.can_undo()
        um.undo()
        assert not um.can_undo()

    def test_undo_multiple_batches_lifo(self, tmp_path):
        """Two independent batches are undone in LIFO order."""
        a, b, c = tmp_path / "a.txt", tmp_path / "b.txt", tmp_path / "c.txt"
        a.touch()
        filetools.rename_file(str(a), str(b))

        um = UndoManager()
        um.add_batch([(str(a), str(b))])
        filetools.rename_file(str(b), str(c))
        um.add_batch([(str(b), str(c))])

        um.undo()
        assert b.exists() and not c.exists()

        um.undo()
        assert a.exists() and not b.exists()

    def test_clear_empties_all_batches(self, tmp_path):
        um = UndoManager()
        for i in range(3):
            um.add_batch([(str(tmp_path / f"{i}a"), str(tmp_path / f"{i}b"))])
        um.clear()
        assert not um.can_undo()


class TestLen:
    def test_len_empty(self):
        assert len(UndoManager()) == 0

    def test_len_after_add(self):
        um = UndoManager()
        um.add_batch([("/a", "/b")])
        um.add_batch([("/c", "/d")])
        assert len(um) == 2

    def test_len_after_clear(self):
        um = UndoManager()
        um.add_batch([("/a", "/b")])
        um.clear()
        assert len(um) == 0


class TestRenameEntry:
    def test_undo_restores_names_and_removes_created_dirs(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "sub").mkdir()
        (src / "sub" / "a.jpg").write_text("A")
        dest = tmp_path / "dest"
        result = filetools.execute_renames(
            [(str(src / "sub" / "a.jpg"), str(dest / "x" / "A_1.jpg"))],
            prune_root=str(src),
        )
        assert not (src / "sub").exists()

        um = UndoManager()
        um.add(RenameEntry.from_result(result))
        um.undo()

        assert (src / "sub" / "a.jpg").read_text() == "A"
        assert not dest.exists()

    def test_undo_of_a_swap(self, tmp_path):
        (tmp_path / "a").write_text("A")
        (tmp_path / "b").write_text("B")
        pairs = [(str(tmp_path / "a"), str(tmp_path / "b"))]
        pairs.append((str(tmp_path / "b"), str(tmp_path / "a")))
        entry = RenameEntry.from_result(filetools.execute_renames(pairs))
        entry.undo()
        assert (tmp_path / "a").read_text() == "A"

    def test_undo_refused_when_original_taken(self, tmp_path):
        (tmp_path / "a").touch()
        entry = RenameEntry.from_result(
            filetools.execute_renames([(str(tmp_path / "a"), str(tmp_path / "b"))])
        )
        (tmp_path / "a").touch()
        um = UndoManager()
        um.add(entry)
        with pytest.raises(UndoError):
            um.undo()
        assert (tmp_path / "b").exists()
        assert not um.can_undo()


class TestMoveEntry:
    def test_failure_reported(self, tmp_path):
        entry = MoveEntry([(str(tmp_path / "a"), str(tmp_path / "missing"))])
        with pytest.raises(UndoError, match="missing"):
            entry.undo()


class TestCopyEntry:
    def test_deletes_copies_and_keeps_originals(self, tmp_path):
        (tmp_path / "a").touch()
        (tmp_path / "d").mkdir()
        (tmp_path / "d" / "f").touch()
        filetools.copy_path(str(tmp_path / "a"), str(tmp_path / "a2"))
        filetools.copy_path(str(tmp_path / "d"), str(tmp_path / "d2"))
        CopyEntry(
            [
                (str(tmp_path / "a"), str(tmp_path / "a2")),
                (str(tmp_path / "d"), str(tmp_path / "d2")),
            ]
        ).undo()
        assert sorted(os.listdir(tmp_path)) == ["a", "d"]

    def test_failure_reported(self, tmp_path):
        entry = CopyEntry([(str(tmp_path / "a"), str(tmp_path / "gone"))])
        with pytest.raises(UndoError, match="gone"):
            entry.undo()
