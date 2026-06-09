"""Tests for pbrenamer.platform.dirs — cross-platform directory resolution."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from pbrenamer.platform.dirs import AppDirs, XdgDirs, _BaseDirs, _MacDirs, _WindowsDirs


class TestBaseDirs:
    def test_config_home_raises(self):
        with pytest.raises(NotImplementedError):
            _ = _BaseDirs("app").config_home

    def test_data_home_raises(self):
        with pytest.raises(NotImplementedError):
            _ = _BaseDirs("app").data_home

    def test_cache_home_raises(self):
        with pytest.raises(NotImplementedError):
            _ = _BaseDirs("app").cache_home


class TestXdgDirs:
    def test_data_home_default(self, monkeypatch):
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        assert XdgDirs("app").data_home == Path.home() / ".local" / "share" / "app"

    def test_data_home_custom(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        assert XdgDirs("app").data_home == tmp_path / "app"

    def test_cache_home_default(self, monkeypatch):
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        assert XdgDirs("app").cache_home == Path.home() / ".cache" / "app"

    def test_cache_home_custom(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        assert XdgDirs("app").cache_home == tmp_path / "app"

    def test_state_home_default(self, monkeypatch):
        monkeypatch.delenv("XDG_STATE_HOME", raising=False)
        assert XdgDirs("app").state_home == Path.home() / ".local" / "state" / "app"

    def test_state_home_custom(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        assert XdgDirs("app").state_home == tmp_path / "app"

    def test_runtime_dir_absent(self, monkeypatch):
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
        assert XdgDirs("app").runtime_dir is None

    def test_runtime_dir_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        assert XdgDirs("app").runtime_dir == tmp_path / "app"

    def test_runtime_dir_relative_ignored(self, monkeypatch):
        monkeypatch.setenv("XDG_RUNTIME_DIR", "relative/path")
        assert XdgDirs("app").runtime_dir is None

    def test_config_dirs_default(self, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_DIRS", raising=False)
        assert XdgDirs("app").config_dirs == [Path("/etc/xdg") / "app"]

    def test_config_dirs_custom(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_DIRS", f"{tmp_path}:/etc/xdg")
        dirs = XdgDirs("app").config_dirs
        assert tmp_path / "app" in dirs
        assert Path("/etc/xdg") / "app" in dirs

    def test_config_dirs_relative_filtered(self, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_DIRS", "relative/path:/etc/xdg")
        dirs = XdgDirs("app").config_dirs
        assert all(d.is_absolute() for d in dirs)

    def test_data_dirs_default(self, monkeypatch):
        monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
        dirs = XdgDirs("app").data_dirs
        assert Path("/usr/local/share") / "app" in dirs
        assert Path("/usr/share") / "app" in dirs

    def test_data_dirs_custom(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_DIRS", f"{tmp_path}:/usr/share")
        dirs = XdgDirs("app").data_dirs
        assert tmp_path / "app" in dirs


class TestWindowsDirs:
    def test_config_home_uses_appdata(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        assert _WindowsDirs("app").config_home == tmp_path / "app"

    def test_config_home_fallback(self, monkeypatch):
        monkeypatch.delenv("APPDATA", raising=False)
        result = _WindowsDirs("app").config_home
        assert result == Path.home() / "AppData" / "Roaming" / "app"

    def test_data_home_same_as_config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        d = _WindowsDirs("app")
        assert d.data_home == d.config_home

    def test_cache_home_uses_localappdata(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        assert _WindowsDirs("app").cache_home == tmp_path / "app"

    def test_cache_home_fallback(self, monkeypatch):
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        result = _WindowsDirs("app").cache_home
        assert result == Path.home() / "AppData" / "Local" / "app"


class TestMacDirs:
    def test_config_home(self):
        assert (
            _MacDirs("app").config_home
            == Path.home() / "Library" / "Preferences" / "app"
        )

    def test_data_home(self):
        assert _MacDirs("app").data_home == (
            Path.home() / "Library" / "Application Support" / "app"
        )

    def test_cache_home(self):
        assert _MacDirs("app").cache_home == Path.home() / "Library" / "Caches" / "app"


class TestAppDirsFactory:
    def test_linux_returns_xdg(self):
        with patch.object(sys, "platform", "linux"):
            assert isinstance(AppDirs("app"), XdgDirs)

    def test_win32_returns_windows(self):
        with patch.object(sys, "platform", "win32"):
            assert isinstance(AppDirs("app"), _WindowsDirs)

    def test_darwin_returns_mac(self):
        with patch.object(sys, "platform", "darwin"):
            assert isinstance(AppDirs("app"), _MacDirs)
