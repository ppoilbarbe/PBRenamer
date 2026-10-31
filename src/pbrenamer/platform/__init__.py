"""Platform-specific abstractions for PBRenamer."""

from pbrenamer.platform.bookmarks import system_bookmarks
from pbrenamer.platform.dirs import AppDirs, XdgDirs, pbpicat_config_dir
from pbrenamer.platform.fs import conflict_key, is_case_sensitive, same_file_path
from pbrenamer.platform.locale import system_language

__all__ = [
    "AppDirs",
    "XdgDirs",
    "conflict_key",
    "is_case_sensitive",
    "pbpicat_config_dir",
    "same_file_path",
    "system_bookmarks",
    "system_language",
]
