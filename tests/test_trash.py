"""Tests for pbrenamer.core.trash (session trash)."""

from __future__ import annotations

import errno
import os

import pytest
from PySide6.QtCore import QLockFile

from pbrenamer.core import trash as trash_mod
from pbrenamer.core.trash import CrossDeviceError, SessionTrash


@pytest.fixture
def root(tmp_path):
    return tmp_path / "trash"


@pytest.fixture
def victim(tmp_path):
    def make(name, text="x"):
        path = tmp_path / name
        path.write_text(text)
        return str(path)

    return make


class TestPut:
    def test_lazy_creation(self, root):
        trash = SessionTrash(root)
        assert trash.directory is None
        assert not root.exists()

    def test_sequential_names(self, root, victim):
        trash = SessionTrash(root)
        first = trash.put(victim("a.txt", "a"))
        second = trash.put(victim("b.txt", "b"))
        assert os.path.basename(first) == "000001.cache"
        assert os.path.basename(second) == "000002.cache"
        assert open(first).read() == "a"
        assert os.path.exists(str(trash.directory) + ".lock")

    def test_same_path_twice(self, root, victim):
        trash = SessionTrash(root)
        first = trash.put(victim("a.txt", "1"))
        second = trash.put(victim("a.txt", "2"))
        assert first != second
        assert open(first).read() == "1" and open(second).read() == "2"

    def test_cross_device(self, root, victim, monkeypatch):
        def rename(src, dst):
            raise OSError(errno.EXDEV, "Invalid cross-device link")

        path = victim("a.txt")
        trash = SessionTrash(root)
        monkeypatch.setattr(trash_mod.os, "rename", rename)
        with pytest.raises(CrossDeviceError):
            trash.put(path)
        assert os.path.exists(path)

    def test_other_error(self, root, tmp_path):
        trash = SessionTrash(root)
        with pytest.raises(OSError) as info:
            trash.put(str(tmp_path / "missing"))
        assert not isinstance(info.value, CrossDeviceError)


class TestClose:
    def test_removes_directory_and_lock(self, root, victim):
        trash = SessionTrash(root)
        trash.put(victim("a.txt"))
        directory = trash.directory
        trash.close()
        assert not directory.exists()
        assert not os.path.exists(str(directory) + ".lock")
        assert trash.directory is None
        trash.close()  # idempotent

    def test_unused(self, root):
        SessionTrash(root).close()
        assert not root.exists()


class TestCleanupStale:
    def test_keeps_live_sessions(self, root, victim):
        live = SessionTrash(root)
        live.put(victim("a.txt"))
        SessionTrash(root).cleanup_stale()
        assert live.directory.exists()
        live.close()

    def test_removes_dead_sessions(self, root, victim, monkeypatch):
        dead = SessionTrash(root)
        dead.put(victim("a.txt"))
        directory = dead.directory
        # A crash: the lock file stays but its owner is gone.
        lock_path = str(directory) + ".lock"
        dead._lock.unlock()
        with open(lock_path, "w") as f:
            f.write("999999999\npbrenamer\nnohost\n")
        monkeypatch.setattr(QLockFile, "tryLock", lambda self, timeout=0: True)
        SessionTrash(root).cleanup_stale()
        assert not directory.exists()

    def test_removes_unlocked_directory(self, root):
        (root / "orphan").mkdir(parents=True)
        (root / "orphan" / "000001.cache").write_text("x")
        SessionTrash(root).cleanup_stale()
        assert not (root / "orphan").exists()

    def test_missing_root(self, root):
        SessionTrash(root).cleanup_stale()
        assert not root.exists()
