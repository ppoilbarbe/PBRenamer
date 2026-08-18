"""Sidecar file detection and grouping.

A sidecar file is associated with a base file by a filename suffix: given a
base file ``img.jpg``, a sidecar file has a name of the form ``img`` + ``.``
+ one or more dot-segments, e.g. ``img.info.json`` (sidecar suffix
``info.json``). Grouping is done per base-file category (image/video/audio/
other), each with its own configurable set of base extensions and sidecar
suffixes, plus a common sidecar-suffix set applying to every category.
"""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from pbrenamer.platform.fs import is_case_sensitive as _default_is_case_sensitive

CATEGORIES = ("image", "video", "audio", "other")
BASE_CATEGORIES = ("image", "video", "audio")

DEFAULT_IMAGE_EXTENSIONS = (
    "bmp",
    "gif",
    "heic",
    "heif",
    "j2k",
    "jp2",
    "jpeg",
    "jpg",
    "png",
    "tif",
    "tiff",
    "webp",
)
DEFAULT_VIDEO_EXTENSIONS = (
    "avi",
    "dv",
    "flv",
    "m4v",
    "mkv",
    "mov",
    "mp4",
    "mpeg",
    "mpg",
    "ogv",
    "ts",
    "vob",
    "webm",
    "wmv",
)
DEFAULT_AUDIO_EXTENSIONS = (
    "aac",
    "au",
    "flac",
    "m4a",
    "mka",
    "mp3",
    "ogg",
    "wav",
    "wma",
)

DEFAULT_IMAGE_SIDECAR_SUFFIXES = ("info", "xmp")
DEFAULT_VIDEO_SIDECAR_SUFFIXES = (
    "ass",
    "cue",
    "dctl",
    "fcpxml",
    "idx",
    "lrc",
    "nfo",
    "srt",
    "ssa",
    "sub",
    "vtt",
    "xmp",
)
DEFAULT_AUDIO_SIDECAR_SUFFIXES = (
    "caf",
    "cue",
    "lrc",
    "nfo",
    "srt",
    "vtt",
    "xmp",
)
# Empty by default: "other" is the unbounded catch-all category (every file
# whose extension isn't a recognized image/video/audio base extension —
# including single-segment sidecar files themselves, e.g. "img.xmp" — is
# "other"). A non-empty default here would make an ordinary file with an
# extension like "img.xmp" register as an "other"-category base with stem
# "img", spuriously colliding with any other sidecar sharing that stem
# (e.g. "img.info.json") and forcing an ambiguity error on a perfectly
# normal multi-sidecar group. Left for the user to opt into deliberately.
DEFAULT_OTHER_SIDECAR_SUFFIXES: tuple[str, ...] = ()
DEFAULT_COMMON_SIDECAR_SUFFIXES: tuple[str, ...] = ()

_DEFAULT_BASE_EXTENSIONS = {
    "image": DEFAULT_IMAGE_EXTENSIONS,
    "video": DEFAULT_VIDEO_EXTENSIONS,
    "audio": DEFAULT_AUDIO_EXTENSIONS,
}
_DEFAULT_OWN_SUFFIXES = {
    "image": DEFAULT_IMAGE_SIDECAR_SUFFIXES,
    "video": DEFAULT_VIDEO_SIDECAR_SUFFIXES,
    "audio": DEFAULT_AUDIO_SIDECAR_SUFFIXES,
    "other": DEFAULT_OTHER_SIDECAR_SUFFIXES,
}


@dataclass(frozen=True)
class SidecarConfig:
    """Per-category base extensions and sidecar suffixes."""

    base_extensions: dict[str, frozenset[str]]
    own_suffixes: dict[str, frozenset[str]]
    common_suffixes: frozenset[str]

    def effective_suffixes(self, category: str) -> frozenset[str]:
        """Return *category*'s own sidecar suffixes union the common ones."""
        return self.own_suffixes.get(category, frozenset()) | self.common_suffixes

    def category_of_extension(self, ext: str) -> str:
        """Return the base category owning *ext* (no dot), or "other"."""
        ext = ext.lower()
        for category in BASE_CATEGORIES:
            if ext in self.base_extensions.get(category, frozenset()):
                return category
        return "other"

    @classmethod
    def defaults(cls) -> SidecarConfig:
        return cls(
            base_extensions={
                c: frozenset(v) for c, v in _DEFAULT_BASE_EXTENSIONS.items()
            },
            own_suffixes={c: frozenset(v) for c, v in _DEFAULT_OWN_SUFFIXES.items()},
            common_suffixes=frozenset(DEFAULT_COMMON_SIDECAR_SUFFIXES),
        )


@dataclass
class SidecarGroupResult:
    """Result of grouping a file listing into base/sidecar relationships."""

    sidecar_of: dict[str, str] = field(default_factory=dict)
    groups: dict[str, list[str]] = field(default_factory=dict)
    sidecar_suffix: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


def _fold(s: str, case_sensitive: bool) -> str:
    return s if case_sensitive else s.lower()


def _own_category_and_stem(name: str, config: SidecarConfig) -> tuple[str, str]:
    """Split *name* on its last dot into (category, stem)."""
    if "." not in name:
        return "other", name
    ext = name.rsplit(".", 1)[1]
    stem = name[: -len(ext) - 1]
    return config.category_of_extension(ext), stem


def _sidecar_candidates(
    name: str, config: SidecarConfig, *, case_sensitive: bool
) -> dict[str, tuple[str, str]]:
    """Return {category: (stem, matched_suffix)} for every category whose
    longest matching effective suffix matches the end of *name*."""
    folded_name = _fold(name, case_sensitive)
    candidates: dict[str, tuple[str, str]] = {}
    for category in CATEGORIES:
        best_suffix = ""
        for suffix in config.effective_suffixes(category):
            marker = "." + _fold(suffix, case_sensitive)
            if folded_name.endswith(marker) and len(suffix) > len(best_suffix):
                best_suffix = suffix
        if best_suffix:
            stem = name[: -(len(best_suffix) + 1)]
            # Keep the suffix exactly as it appears on disk (case preserved)
            # rather than the configured spelling, so a case-insensitive
            # match never silently changes the sidecar's suffix casing.
            verbatim_suffix = name[-len(best_suffix) :]
            candidates[category] = (stem, verbatim_suffix)
    return candidates


def _ambiguous_message(name: str, owners: list[str]) -> str:
    owner_names = ", ".join(sorted(os.path.basename(o) for o in owners))
    return _("{name!r} could be a sidecar of multiple base files: {owners}").format(
        name=name, owners=owner_names
    )


def build_sidecar_groups(
    files: list[tuple[str, str]],
    config: SidecarConfig,
    *,
    is_case_sensitive: Callable[[str], bool] = _default_is_case_sensitive,
) -> SidecarGroupResult:
    """Group sidecar files with their base file.

    *files* is a list of ``(name, full_path)`` as returned by
    ``filetools.get_file_listing``/``get_file_listing_recursive``. Grouping
    is done per directory (``os.path.dirname(path)``) — a base file and its
    sidecars are always in the same directory.

    A sidecar candidate is only searched among the sidecar suffixes of the
    category of its potential base file(s) (plus the common suffix list). If
    a candidate's suffix could belong to more than one base file present in
    the same directory — whether in the same category or different
    categories — this is an ambiguity error, reported on the sidecar and on
    every candidate base file involved (no silent resolution).
    """
    by_dir: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for name, path in files:
        by_dir[os.path.dirname(path)].append((name, path))

    result = SidecarGroupResult()
    conflicts: dict[str, list[str]] = defaultdict(list)

    for directory, entries in by_dir.items():
        case_sensitive = is_case_sensitive(directory)

        bases: dict[tuple[str, str], list[str]] = defaultdict(list)
        for name, path in entries:
            category, stem = _own_category_and_stem(name, config)
            bases[(_fold(stem, case_sensitive), category)].append(path)

        for name, path in entries:
            candidates = _sidecar_candidates(
                name, config, case_sensitive=case_sensitive
            )
            if not candidates:
                continue

            owners: list[str] = []
            owner_suffix: dict[str, str] = {}
            for category, (stem, suffix) in candidates.items():
                key = (_fold(stem, case_sensitive), category)
                for owner in bases.get(key, []):
                    if owner == path:
                        continue  # a file is never its own sidecar/base
                    if owner not in owner_suffix:
                        owner_suffix[owner] = suffix
                    owners.append(owner)
            owners = list(dict.fromkeys(owners))

            if not owners:
                continue
            if len(owners) == 1:
                base = owners[0]
                result.sidecar_of[path] = base
                result.groups.setdefault(base, []).append(path)
                result.sidecar_suffix[path] = owner_suffix[base]
            else:
                msg = _ambiguous_message(name, owners)
                conflicts[path].append(msg)
                for owner in owners:
                    conflicts[owner].append(msg)

    result.errors = {
        path: " / ".join(dict.fromkeys(msgs)) for path, msgs in conflicts.items()
    }
    return result
