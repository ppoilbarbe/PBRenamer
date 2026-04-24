"""Tests for pbrenamer.core.undo — UndoManager."""

from pbrenamer.core import filetools
from pbrenamer.core.undo import UndoManager


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
