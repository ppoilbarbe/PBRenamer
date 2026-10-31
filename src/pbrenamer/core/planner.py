"""Compute the new names of a batch of files from a search/replace rule.

This is the single name-computation loop shared by the GUI preview and the
headless CLI: search/replace, extension mode, post-processing, target path
resolution ({dest}, sub-directories) and the contextual {newnum} counter.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field

from pbrenamer.core import filetools
from pbrenamer.core import replacement as _repl
from pbrenamer.core.sidecar import SidecarConfig

_log = logging.getLogger(__name__)


@dataclass
class Rule:
    """Everything needed to compute new names, independent of the UI."""

    search: str
    replace: str
    mode: str = _repl.SEARCH_PATTERN
    case_insensitive: bool = False
    ext_mode: str = "keep"
    normalization: dict[str, str] | None = None
    # Post-processing: filetools.replace_spaces / replace_capitalization
    # modes, or None when disabled.
    spaces: int | None = None
    remove_accents: bool = False
    remove_duplicates: bool = False
    capitalization: int | None = None
    # Root substituted for {dest}; None makes {dest} an error.
    dest_root: str | None = None
    # {newnum}: smallest free number instead of max + 1; one counter per file
    # category; or plain 1..N sequence ignoring the files on disk.
    fill_gaps: bool = False
    per_category: bool = False
    renumber: bool = False
    sidecar_config: SidecarConfig = field(default_factory=SidecarConfig.defaults)


@dataclass
class PlanEntry:
    """New name of one file.

    *new_name* is the text to display (relative to the source directory, or
    absolute under the destination root); None when the rule does not apply
    (no match, empty result) or on *error*.  *target* is the absolute path.
    """

    new_name: str | None = None
    target: str | None = None
    error: _repl.FieldResolutionError | filetools.TargetPathError | None = None


def apply_postproc(name: str, path: str, rule: Rule) -> str:
    """Apply the post-processing options of *rule* to *name*."""
    if rule.spaces is not None:
        name, _op = filetools.replace_spaces(name, path, rule.spaces)
    if rule.remove_accents:
        name, _op = filetools.replace_accents(name, path)
    if rule.remove_duplicates:
        name, _op = filetools.replace_duplicated(name, path)
    if rule.capitalization is not None:
        name, _op = filetools.replace_capitalization(name, path, rule.capitalization)
    return name


def _apply_rule(rule: Rule, stem: str, path: str, counter: int, **fields) -> str | None:
    """Dispatch to the filetools function of the rule's search mode.

    *path* must be the actual file path (with extension) so that metadata
    fields such as {mdatetime} and {im:…}/{au:…} can stat the file.
    """
    if rule.mode == _repl.SEARCH_REGEX:
        raw, _op = filetools.rename_using_regex(
            stem,
            path,
            rule.search,
            rule.replace,
            case_insensitive=rule.case_insensitive,
            **fields,
        )
    elif rule.mode == _repl.SEARCH_PLAIN:
        raw, _op = filetools.rename_using_plain_text(
            stem,
            path,
            rule.search,
            rule.replace,
            case_insensitive=rule.case_insensitive,
            **fields,
        )
    else:
        raw, _op = filetools.rename_using_patterns(
            stem,
            path,
            rule.search,
            rule.replace,
            counter,
            case_insensitive=rule.case_insensitive,
            **fields,
        )
    return raw


def newnum_start(template: str) -> int | None:
    """Return the start value of {newnum} in *template* (its default part,
    1 when absent or not an integer), or None if it has no {newnum}."""
    try:
        segments = _repl.parse(template)
    except _repl.ReplacementSyntaxError:
        return None
    for seg in segments:
        if isinstance(seg, _repl.FieldSegment) and seg.name == "newnum":
            try:
                return int(seg.default) if seg.default is not None else 1
            except ValueError:
                return 1
    return None


class NewNumState:
    """{newnum} counters of one batch, one per series.

    A series is identified by the target directory and the name around the
    number (plus the file category with *per_category*).  Its first number is
    max + 1 of the numbers already used on disk by that series, or the
    smallest free one with *fill_gaps*; files of the batch itself are not
    counted, so that they can keep their own number.  With *renumber* the
    disk is ignored and every series runs from *start*.
    """

    def __init__(
        self,
        start: int = 1,
        *,
        fill_gaps: bool = False,
        per_category: bool = False,
        renumber: bool = False,
        sources: Collection[str] = (),
        config: SidecarConfig | None = None,
    ) -> None:
        self.start = start
        self.fill_gaps = fill_gaps
        self.per_category = per_category
        self.renumber = renumber
        self.reserved: set[str] = set()
        self._sources = {filetools.path_key(s) for s in sources}
        self._config = config or SidecarConfig.defaults()
        self._next: dict[tuple, int] = {}
        self._used: dict[tuple, set[int]] = {}

    def used_numbers(
        self, directory: str, pattern: re.Pattern[str], category: str | None
    ) -> set[int]:
        """Numbers used in *directory* by entries matching *pattern*, of
        *category* when given, batch sources excluded."""
        try:
            names = os.listdir(directory)
        except OSError:
            return set()
        used: set[int] = set()
        for name in names:
            m = pattern.match(name)
            if m is None:
                continue
            if filetools.path_key(os.path.join(directory, name)) in self._sources:
                continue
            if category is not None:
                ext = filetools.cut_extension(name, name)[2]
                if self._config.category_of_extension(ext) != category:
                    continue
            used.add(int(m.group(1)))
        return used

    def first(
        self,
        key: tuple,
        directory: str | None,
        pattern: re.Pattern[str] | None,
        category: str | None,
    ) -> int:
        """Return the first number to try for series *key*."""
        if key not in self._next:
            used: set[int] = set()
            if not self.renumber and directory is not None and pattern is not None:
                used = self.used_numbers(
                    directory, pattern, category if self.per_category else None
                )
            self._used[key] = used
            if self.fill_gaps or self.renumber or not used:
                self._next[key] = self.start
            else:
                self._next[key] = max(self.start, max(used) + 1)
        return self.following(key, self._next[key] - 1)

    def following(self, key: tuple, number: int) -> int:
        """Return the number to try after *number* in series *key*."""
        number += 1
        while number in self._used[key]:
            number += 1
        return number

    def accept(self, key: tuple, number: int, target: str) -> None:
        self._used[key].add(number)
        self._next[key] = number + 1
        self.reserved.add(filetools.path_key(target))

    def is_free(self, target: str, src: str) -> bool:
        """True if *target* is neither reserved nor taken on disk by a file
        other than *src* (with *renumber*, other batch files are moved away
        and do not count)."""
        key = filetools.path_key(target)
        if key in self.reserved:
            return False
        if not os.path.lexists(target) or key == filetools.path_key(src):
            return True
        return self.renumber and key in self._sources


def _series(
    probe_target: str, ext: str, category: str, per_category: bool
) -> tuple[tuple, str | None, re.Pattern[str] | None]:
    """Return (key, directory, pattern) of the series of *probe_target*.

    *probe_target* is the target path computed with NEWNUM_MARKER in place
    of the number.  The pattern matches the names of the series whatever
    their extension.  When the number lies in a directory component, there
    is no pattern: the counter is not contextual.
    """
    directory, name = os.path.split(probe_target)
    cat_key = category if per_category else None
    if _repl.NEWNUM_MARKER in directory:
        return (probe_target, cat_key), None, None
    if ext and name.endswith("." + ext):
        name = name[: -len(ext) - 1]
    pieces = [re.escape(p) for p in name.split(_repl.NEWNUM_MARKER)]
    regex = "^" + pieces[0] + r"(\d+)" + r"\d+".join(pieces[1:]) + r"(?:\..*)?$"
    key = (filetools.path_key(os.path.join(directory, "")), regex.lower(), cat_key)
    return key, directory, re.compile(regex, re.IGNORECASE)


def compute_names(
    rule: Rule,
    paths: list[str],
    followers: Mapping[str, list[tuple[str, str]]] | None = None,
) -> list[PlanEntry]:
    """Return the PlanEntry of each path in *paths* under *rule*.

    *followers* maps a base path to its sidecars as (sidecar path, sidecar
    suffix).  Sidecars get an empty entry (their name follows the base) and
    take no {newnum} value; the value of their base is chosen so that the
    names they will take are free too.
    """
    followers = followers or {}
    skip = {sc for scs in followers.values() for sc, _suffix in scs}
    start = newnum_start(rule.replace)
    state = (
        NewNumState(
            start,
            fill_gaps=rule.fill_gaps,
            per_category=rule.per_category,
            renumber=rule.renumber,
            sources=paths,
            config=rule.sidecar_config,
        )
        if start is not None
        else None
    )
    entries: list[PlanEntry] = []
    for counter, path in enumerate(paths, start=1):
        if path in skip:
            entries.append(PlanEntry())
            continue
        try:
            entries.append(
                _compute_one(rule, path, counter, state, followers.get(path, []))
            )
        except (_repl.FieldResolutionError, filetools.TargetPathError) as err:
            _log.debug("Plan: %r — %s", os.path.basename(path), err)
            entries.append(PlanEntry(error=err))
    return entries


def sidecar_target(base_target: str, suffix: str) -> str:
    """Target of a sidecar with *suffix* following a base renamed to
    *base_target*."""
    return f"{filetools.cut_extension(base_target, base_target)[0]}.{suffix}"


def _apply_rule_with_separator(
    rule: Rule, stem: str, path: str, counter: int, category: str, fields: dict
) -> str | None:
    """Apply *rule* to the stem followed by the extension separator, for a
    search that spans it (``..`` in ``name..xmp``).  The result must still
    end with that dot, which is removed; otherwise TargetPathError."""
    raw = _apply_rule(rule, stem + ".", path, counter, category=category, **fields)
    if raw is None:
        return None
    if not raw.endswith("."):
        raise filetools.TargetPathError(filetools.TargetPathError.EXT_SEPARATOR, raw)
    return raw[:-1]


def _compute_one(
    rule: Rule,
    path: str,
    counter: int,
    state: NewNumState | None,
    followers: list[tuple[str, str]],
) -> PlanEntry:
    name = os.path.basename(path)
    _stem, _stem_path, orig_ext = filetools.cut_extension(name, path)
    category = rule.sidecar_config.category_of_extension(orig_ext)
    if rule.ext_mode == "modify":
        stem, stem_path, ext = name, path, ""
    else:
        stem, stem_path, ext = _stem, _stem_path, orig_ext
        ext = filetools.apply_extension_mode(ext, rule.ext_mode, rule.normalization)

    def render(**fields) -> str | None:
        raw = _apply_rule(rule, stem, path, counter, category=category, **fields)
        if raw is None and ext:
            raw = _apply_rule_with_separator(
                rule, stem, path, counter, category, fields
            )
        if raw is None:
            return None
        processed = apply_postproc(raw, stem_path, rule)
        return filetools.add_extension(processed, stem_path, ext)[0]

    def entry(candidate: str) -> PlanEntry:
        return PlanEntry(
            filetools.display_target(candidate, rule.dest_root),
            filetools.resolve_target(path, candidate, rule.dest_root),
        )

    if state is None:
        candidate = render()
        if not candidate:
            return PlanEntry()
        return entry(candidate)

    probe = render(newnum_probe=True)
    if not probe:
        return PlanEntry()
    if _repl.NEWNUM_MARKER not in probe:
        # {newnum} lies outside every match: the name does not depend on it.
        candidate = render(newnum=state.start)
        return entry(candidate)
    probe_target = filetools.resolve_target(path, probe, rule.dest_root)
    key, directory, pattern = _series(probe_target, ext, category, rule.per_category)
    number = state.first(key, directory, pattern, category)
    while True:
        candidate = render(newnum=number)
        target = filetools.resolve_target(path, candidate, rule.dest_root)
        moves = [(target, path)] + [
            (sidecar_target(target, suffix), sc) for sc, suffix in followers
        ]
        if all(state.is_free(t, src) for t, src in moves):
            for t, _src in moves:
                state.accept(key, number, t)
            return entry(candidate)
        number = state.following(key, number)
