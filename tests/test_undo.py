"""Tests for pbrenamer.core.undo — UndoManager and typed entries."""

import os

import pytest

from pbrenamer.core import filetools, image_ops
from pbrenamer.core.undo import (
    CopyEntry,
    DeleteEntry,
    ExifResetEntry,
    MoveEntry,
    RenameEntry,
    RotationEntry,
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
            prune=True,
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
    def test_recreates_removed_source_folder(self, tmp_path):
        (tmp_path / "a").write_text("A")
        MoveEntry([(str(tmp_path / "gone" / "a"), str(tmp_path / "a"))]).undo()
        assert (tmp_path / "gone" / "a").read_text() == "A"

    def test_folder_creation_failure_reported(self, tmp_path):
        (tmp_path / "file").touch()
        (tmp_path / "a").touch()
        entry = MoveEntry([(str(tmp_path / "file" / "a"), str(tmp_path / "a"))])
        with pytest.raises(UndoError, match="a"):
            entry.undo()

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


class TestDeleteEntry:
    def test_session_restores_in_place(self, tmp_path):
        trash = tmp_path / "trash"
        (tmp_path / "sub").mkdir()
        trash.mkdir()
        (trash / "000001.cache").write_text("a")
        original = str(tmp_path / "sub" / "gone" / "a.txt")
        DeleteEntry([(original, str(trash / "000001.cache"))], system=False).undo()
        assert open(original).read() == "a"

    def test_session_missing_or_taken(self, tmp_path):
        trash = tmp_path / "trash"
        trash.mkdir()
        (trash / "000002.cache").write_text("b")
        (tmp_path / "b.txt").write_text("other")
        entry = DeleteEntry(
            [
                (str(tmp_path / "a.txt"), str(trash / "000001.cache")),
                (str(tmp_path / "b.txt"), str(trash / "000002.cache")),
            ],
            system=False,
        )
        with pytest.raises(UndoError) as info:
            entry.undo()
        assert "a.txt" in str(info.value) and "b.txt" in str(info.value)
        assert (tmp_path / "b.txt").read_text() == "other"
        assert (trash / "000002.cache").exists()

    def test_system_uses_platform_restore(self, tmp_path, monkeypatch):
        from pbrenamer.platform import trash as system_trash

        done = []
        monkeypatch.setattr(system_trash, "restore", lambda t, o: done.append((t, o)))
        DeleteEntry([("/o/a", "/t/1"), ("/o/b", "/t/2")], system=True).undo()
        assert done == [("/t/2", "/o/b"), ("/t/1", "/o/a")]


# ── Entries that rewrite file contents: progress and stop ────────────────────


class TestContentEntries:
    def test_move_entries_have_no_content_files(self):
        assert MoveEntry([("a", "b")]).content_files() == 0

    def test_rotation_undo_steps_and_stops(self, monkeypatch):
        done = []
        monkeypatch.setattr(
            image_ops, "rotate_lossless", lambda p, op: done.append((p, op))
        )
        monkeypatch.setattr(image_ops, "set_exif_orientation", lambda p, o: None)
        manager = UndoManager()
        manager.add(RotationEntry([("a", 90, None), ("b", 90, None), ("c", 90, 6)]))
        assert manager.next_content_files() == 3
        budget = iter([True, False])
        manager.undo(lambda: next(budget))
        # Reverted in reverse order; the stop keeps the rest on the stack.
        assert done == [("c", 90)]
        assert manager.next_content_files() == 2
        manager.undo(lambda: True)
        assert [p for p, _ in done] == ["c", "b", "a"]
        assert len(manager) == 0

    def test_rotation_undo_without_step(self, monkeypatch):
        done = []
        monkeypatch.setattr(image_ops, "rotate_lossless", lambda p, op: done.append(p))
        manager = UndoManager()
        manager.add(RotationEntry([("a", 90, None), ("b", 90, None)]))
        manager.undo()
        assert done == ["b", "a"]
        assert len(manager) == 0

    def test_exif_reset_undo_stops(self, monkeypatch):
        done = []
        monkeypatch.setattr(
            image_ops, "set_exif_orientation", lambda p, o: done.append((p, o))
        )
        manager = UndoManager()
        manager.add(ExifResetEntry([("a", 6), ("b", 8)]))
        manager.undo(lambda: False)
        assert done == []
        assert manager.next_content_files() == 2
        manager.undo(lambda: True)
        assert sorted(done) == [("a", 6), ("b", 8)]
        assert manager.next_content_files() == 0

    def test_errors_still_keep_remaining_files(self, monkeypatch):
        def fail(p, _op):
            raise OSError("broken")

        monkeypatch.setattr(image_ops, "rotate_lossless", fail)
        manager = UndoManager()
        manager.add(RotationEntry([("a", 90, None), ("b", 90, None)]))
        budget = iter([True, False])
        with pytest.raises(UndoError):
            manager.undo(lambda: next(budget))
        assert manager.next_content_files() == 1


class TestListeners:
    def test_notified_on_add_undo_clear(self, tmp_path):
        um = UndoManager()
        calls = []
        um.add_listener(lambda: calls.append(len(um)))
        um.add(CopyEntry([]))
        um.add(CopyEntry([]))
        um.undo()
        um.clear()
        assert calls == [1, 2, 1, 0]

    def test_notified_when_undo_fails(self):
        um = UndoManager()
        um.add(MoveEntry([("/nonexistent/a", "/nonexistent/b")]))
        calls = []
        um.add_listener(lambda: calls.append(len(um)))
        with pytest.raises(UndoError):
            um.undo()
        assert calls == [0]

    def test_remove_listener(self):
        um = UndoManager()
        calls = []
        um.add_listener(calls.append)
        um.remove_listener(calls.append)
        um.remove_listener(calls.append)  # unknown: ignored
        um.add(CopyEntry([]))
        assert calls == []


class TestEntries:
    def test_most_recent_first(self, monkeypatch):
        um = UndoManager()
        first, second = CopyEntry([]), MoveEntry([])
        monkeypatch.setattr("pbrenamer.core.undo.time.time", lambda: 100.0)
        um.add(first)
        monkeypatch.setattr("pbrenamer.core.undo.time.time", lambda: 200.0)
        um.add(second)
        assert um.entries() == [(second, 200.0), (first, 100.0)]
        um.undo()
        assert um.entries() == [(first, 100.0)]

    def test_stopped_undo_keeps_time(self, monkeypatch):
        um = UndoManager()
        monkeypatch.setattr("pbrenamer.core.undo.time.time", lambda: 50.0)
        entry = ExifResetEntry([("/x", 6)])
        um.add(entry)
        um.undo(lambda: False)
        assert um.entries() == [(entry, 50.0)]
