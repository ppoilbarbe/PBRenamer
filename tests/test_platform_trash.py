"""Tests for pbrenamer.platform.trash (system trash)."""

from __future__ import annotations

import errno
import os
import sys

import pytest

from pbrenamer.platform import trash
from pbrenamer.platform.fs import is_cross_device


@pytest.fixture
def xdg_trash(tmp_path):
    root = tmp_path / "Trash"
    (root / "files").mkdir(parents=True)
    (root / "info").mkdir()
    return root


@pytest.mark.skipif(sys.platform in ("win32", "darwin"), reason="freedesktop")
class TestRestoreFreedesktop:
    def test_restores_and_removes_trashinfo(self, tmp_path, xdg_trash):
        trashed = xdg_trash / "files" / "a.png-123"
        trashed.write_text("a")
        info = xdg_trash / "info" / "a.png-123.trashinfo"
        info.write_text("[Trash Info]")
        original = tmp_path / "photos" / "a.png"
        trash.restore(str(trashed), str(original))
        assert original.read_text() == "a"
        assert not trashed.exists() and not info.exists()

    def test_missing_trashinfo_is_fine(self, tmp_path, xdg_trash):
        trashed = xdg_trash / "files" / "a.png"
        trashed.write_text("a")
        trash.restore(str(trashed), str(tmp_path / "a.png"))
        assert (tmp_path / "a.png").exists()


class TestRestoreFailures:
    def test_move_fails(self, tmp_path, xdg_trash, monkeypatch):
        trashed = xdg_trash / "files" / "a.png"
        trashed.write_text("a")
        monkeypatch.setattr(
            trash.filetools, "move_path", lambda s, d: (False, "denied")
        )
        with pytest.raises(OSError, match="denied"):
            trash.restore(str(trashed), str(tmp_path / "a.png"))

    def test_metadata_not_removable(self, tmp_path, xdg_trash, monkeypatch):
        trashed = xdg_trash / "files" / "a.png"
        trashed.write_text("a")
        monkeypatch.setattr(trash, "_metadata_path", lambda p: str(tmp_path))
        trash.restore(str(trashed), str(tmp_path / "out" / "a.png"))
        assert (tmp_path / "out" / "a.png").exists()

    def test_no_longer_in_trash(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            trash.restore(str(tmp_path / "gone"), str(tmp_path / "a.png"))

    def test_original_taken(self, tmp_path, xdg_trash):
        trashed = xdg_trash / "files" / "a.png"
        trashed.write_text("a")
        (tmp_path / "a.png").write_text("new")
        with pytest.raises(FileExistsError):
            trash.restore(str(trashed), str(tmp_path / "a.png"))
        assert trashed.exists()


class TestMetadataPath:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr(trash.sys, "platform", "win32")
        path = trash._metadata_path("C:/$Recycle.Bin/S-1/$RAB12CD.png")
        assert path.endswith("$IAB12CD.png")
        assert trash._metadata_path("C:/x/other.png") is None

    def test_macos(self, monkeypatch):
        monkeypatch.setattr(trash.sys, "platform", "darwin")
        assert trash._metadata_path("/Users/u/.Trash/a.png") is None

    def test_linux_outside_files_dir(self, monkeypatch):
        monkeypatch.setattr(trash.sys, "platform", "linux")
        assert trash._metadata_path("/somewhere/a.png") is None


class _FakeQFile:
    result = True

    def __init__(self, path):
        self.path = path

    def moveToTrash(self):  # noqa: N802
        if self.result:
            self.path = "/trash/files/" + self.path.rsplit("/", 1)[-1]
        return self.result

    def fileName(self):  # noqa: N802
        return self.path


class TestMoveToTrash:
    def test_returns_trash_path(self, monkeypatch):
        monkeypatch.setattr(trash, "QFile", _FakeQFile)
        assert trash.move_to_trash("/photos/a.png") == "/trash/files/a.png"

    def test_absolute_path(self, monkeypatch):
        seen = []

        class Fake(_FakeQFile):
            def __init__(self, path):
                seen.append(path)
                super().__init__(path)

        monkeypatch.setattr(trash, "QFile", Fake)
        trash.move_to_trash("a.png")
        assert os.path.isabs(seen[0])

    def test_failure(self, monkeypatch):
        monkeypatch.setattr(_FakeQFile, "result", False)
        monkeypatch.setattr(trash, "QFile", _FakeQFile)
        assert trash.move_to_trash("/photos/a.png") is None


class TestIsCrossDevice:
    def test_exdev(self):
        assert is_cross_device(OSError(errno.EXDEV, "cross"))

    def test_windows_code(self):
        exc = OSError(errno.EINVAL, "x")
        exc.winerror = 17
        assert is_cross_device(exc)

    def test_other(self):
        assert not is_cross_device(OSError(errno.ENOENT, "missing"))
