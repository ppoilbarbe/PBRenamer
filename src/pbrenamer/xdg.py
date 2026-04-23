"""Backwards-compatible re-export — prefer ``pbrenamer.platform`` for new code."""

from pbrenamer.platform.dirs import XdgDirs as AppDirs  # noqa: F401

__all__ = ["AppDirs"]
