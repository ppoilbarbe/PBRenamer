"""Platform-specific abstractions for PBRenamer."""

from pbrenamer.platform.dirs import AppDirs, XdgDirs
from pbrenamer.platform.fs import conflict_key, is_case_sensitive, same_file_path
from pbrenamer.platform.locale import system_language

__all__ = [
    "AppDirs",
    "XdgDirs",
    "conflict_key",
    "is_case_sensitive",
    "same_file_path",
    "system_language",
]
