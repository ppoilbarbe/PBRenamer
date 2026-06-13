"""Tests for pbrenamer.resources and pbrenamer.xdg."""

from __future__ import annotations

import os
from pathlib import Path


class TestResourcesPath:
    def test_returns_string(self):
        from pbrenamer.resources import path

        result = path("icons/app.png")
        assert isinstance(result, str)

    def test_path_ends_with_name(self):
        from pbrenamer.resources import path

        result = path("icons/app.png")
        assert result.endswith("icons/app.png")

    def test_path_is_absolute(self):
        from pbrenamer.resources import path

        result = path("something.txt")
        assert os.path.isabs(result)

    def test_path_parent_exists(self):
        from pbrenamer.resources import path

        result = path("icons/app.png")
        # The resources directory itself must exist
        assert Path(result).parent.parent.exists()


class TestXdg:
    def test_import_appdirs_from_xdg(self):
        from pbrenamer.xdg import AppDirs

        assert AppDirs is not None

    def test_appdirs_is_xdgdirs(self):
        from pbrenamer.platform.dirs import XdgDirs
        from pbrenamer.xdg import AppDirs

        assert AppDirs is XdgDirs

    def test_xdg_in_all(self):
        import pbrenamer.xdg as xdg

        assert "AppDirs" in xdg.__all__
