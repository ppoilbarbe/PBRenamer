"""File renaming and transformation functions."""

import glob as _glob
import logging
import os
import re
import shutil
import unicodedata
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from pbrenamer.platform.fs import conflict_key

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Directory / file listing
# ---------------------------------------------------------------------------


def _escape_glob(pattern: str) -> str:
    return pattern.replace("[", "[[]")


def get_file_listing(
    directory: str, mode: int, pattern: str | None = None
) -> list[tuple[str, str]]:
    """Return [(name, full_path), ...] for *directory*.

    mode: 0 = files only, 1 = dirs only, 2 = both
    """
    _log.debug("Listing %s (mode=%d, pattern=%r)", directory, mode, pattern)
    if pattern:
        glob_pat = _escape_glob(directory.rstrip("/") + "/" + pattern)
        paths = sorted(_glob.glob(glob_pat), key=lambda p: os.path.basename(p).lower())
    else:
        names = sorted(os.listdir(directory), key=str.lower)
        paths = [os.path.join(directory, n) for n in names]

    result: list[tuple[str, str]] = []
    for full in paths:
        is_dir = os.path.isdir(full)
        if mode == 1 and not is_dir:
            continue
        if mode == 0 and is_dir:
            continue
        result.append((os.path.basename(full), full))
    _log.debug("Listed %d entries in %s", len(result), directory)
    return result


def get_file_listing_recursive(
    directory: str, mode: int, pattern: str | None = None
) -> list[tuple[str, str]]:
    """Recursively return file entries from *directory* (subdirs first, then root)."""
    result: list[tuple[str, str]] = []
    for root, dirs, _files in os.walk(directory, topdown=False):
        for d in dirs:
            result.extend(get_file_listing(os.path.join(root, d), mode, pattern))
    result.extend(get_file_listing(directory, mode, pattern))
    return result


# ---------------------------------------------------------------------------
# Internal path helper
# ---------------------------------------------------------------------------


def _new_path(name: str, path: str) -> str:
    return os.path.join(os.path.dirname(path), name)


# ---------------------------------------------------------------------------
# Text transformations
# ---------------------------------------------------------------------------

_SPACE_MAPS: dict[int, tuple[str, str]] = {
    0: (" ", "_"),
    1: ("_", " "),
    2: (" ", "."),
    3: (".", " "),
    4: (" ", "-"),
    5: ("-", " "),
}


def replace_spaces(name: str, path: str, mode: int) -> tuple[str, str]:
    """Replace space-like delimiters.

    0: ' '→'_'  1: '_'→' '  2: ' '→'.'  3: '.'→' '  4: ' '→'-'  5: '-'→' '
    """
    src, dst = _SPACE_MAPS[mode]
    newname = name.replace(src, dst)
    return newname, _new_path(newname, path)


def replace_capitalization(name: str, path: str, mode: int) -> tuple[str, str]:
    """0: UPPERCASE  1: lowercase  2: Capitalize  3: Title Case"""
    if mode == 0:
        newname = name.upper()
    elif mode == 1:
        newname = name.lower()
    elif mode == 2:
        newname = name.capitalize()
    else:
        newname = " ".join(x.capitalize() for x in name.split())
    return newname, _new_path(newname, path)


def replace_accents(name: str, path: str) -> tuple[str, str]:
    """Strip diacritics via NFD normalisation (á→a, ü→u, etc.)."""
    newname = "".join(
        c for c in unicodedata.normalize("NFD", name) if unicodedata.category(c) != "Mn"
    )
    return newname, _new_path(newname, path)


def replace_duplicated(name: str, path: str) -> tuple[str, str]:
    """Collapse consecutive identical separator characters (. - _ space)."""
    separators = frozenset(". -_")
    result = name[:1]
    for c in name[1:]:
        if c in separators and result[-1] == c:
            continue
        result += c
    return result, _new_path(result, path)


# ---------------------------------------------------------------------------
# Pattern-based renaming engine
# ---------------------------------------------------------------------------

_PATTERN_TOKENS: dict[str, str] = {
    "{#}": "([0-9]*)",
    "{L}": "([^\\W\\d_]*)",
    "{C}": r"([\S]*)",
    "{X}": r"([\S\s]*)",
    "{@}": "(?:.*)",  # non-capturing: does not consume a group number
}


def _build_regex(pattern: str) -> str:
    """Convert a user-facing search pattern into a compiled regex string."""
    for ch in ".[]()?":
        pattern = pattern.replace(ch, "\\" + ch)
    for token, regex in _PATTERN_TOKENS.items():
        pattern = pattern.replace(token, regex)
    return pattern


def _apply_replacement(
    replacement_template: str,
    *,
    full_match: str,
    groups: list[str],
    named_groups: dict[str, str],
    path: str,
    counter: int,
    now: datetime,
    newnum: int | None = None,
    category: str | None = None,
    newnum_probe: bool = False,
) -> str | None:
    """Parse and apply *replacement_template*. Returns None on syntax error."""
    from pbrenamer.core import replacement  # local import to avoid circular deps

    try:
        tokens = replacement.parse(replacement_template)
        return replacement.substitute(
            tokens,
            full_match=full_match,
            groups=groups,
            named_groups=named_groups,
            path=path,
            counter=counter,
            now=now,
            newnum=newnum,
            category=category,
            newnum_probe=newnum_probe,
        )
    except replacement.ReplacementSyntaxError:
        return None
    # FieldResolutionError propagates intentionally to the caller


def rename_using_patterns(
    name: str,
    path: str,
    pattern_ini: str,
    pattern_end: str,
    count: int,
    ext: str = "",
    *,
    newnum: int | None = None,
    case_insensitive: bool = False,
    category: str | None = None,
    newnum_probe: bool = False,
) -> tuple[str | None, str | None]:
    """Apply a search/replacement pattern pair to all matches within *name*.

    Returns (newname, newpath), or (None, None) on no match or syntax error.
    Raises replacement.FieldResolutionError when a field cannot be resolved.
    """
    regex = _build_regex(pattern_ini)
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        if re.search(regex, name, flags) is None:
            return None, None
    except re.error:  # pragma: no cover — pre-validated; guard for API misuse
        return None, None

    now = datetime.now()
    _syntax_error = False

    def _repl(m: re.Match) -> str:
        nonlocal _syntax_error
        if not m.group(0):
            return ""
        result = _apply_replacement(
            pattern_end,
            full_match=m.group(0),
            groups=list(m.groups()),
            named_groups={},
            path=path,
            counter=count,
            now=now,
            newnum=newnum,
            category=category,
            newnum_probe=newnum_probe,
        )
        if result is None:
            _syntax_error = True
            return m.group(0)
        return result

    newname = re.sub(regex, _repl, name, flags=flags)
    if _syntax_error:
        return None, None
    return newname, _new_path(newname, path)


def rename_using_plain_text(
    name: str,
    path: str,
    search: str,
    replacement_template: str,
    *,
    newnum: int | None = None,
    case_insensitive: bool = False,
    category: str | None = None,
    newnum_probe: bool = False,
) -> tuple[str | None, str | None]:
    """Literal string search; unified replacement syntax.

    Returns (None, None) if *search* does not appear in *name*.
    Raises replacement.FieldResolutionError when a field cannot be resolved.
    """
    if case_insensitive:
        m = re.search(re.escape(search), name, re.IGNORECASE)
        if m is None:
            return (
                None,
                None,
            )
        actual_match = m.group(0)
    else:
        if search not in name:
            return None, None
        actual_match = search

    newname = _apply_replacement(
        replacement_template,
        full_match=actual_match,
        groups=[],
        named_groups={},
        path=path,
        counter=1,
        now=datetime.now(),
        newnum=newnum,
        category=category,
        newnum_probe=newnum_probe,
    )
    if newname is None:
        return None, None
    if case_insensitive:
        result = re.sub(re.escape(search), lambda _: newname, name, flags=re.IGNORECASE)
    else:
        result = name.replace(search, newname)
    return result, _new_path(result, path)


def rename_using_regex(
    name: str,
    path: str,
    pattern: str,
    replacement_template: str,
    *,
    newnum: int | None = None,
    case_insensitive: bool = False,
    category: str | None = None,
    newnum_probe: bool = False,
) -> tuple[str | None, str | None]:
    """Apply a Python regex substitution to all matches within *name*.

    Use {0} for the full match, {1}/{2}/… for numbered groups,
    {re:name} for named groups.

    Returns (newname, newpath), or (None, None) on no match or invalid pattern.
    Raises replacement.FieldResolutionError when a field cannot be resolved.
    """
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        if re.search(pattern, name, flags) is None:
            return None, None
    except re.error:
        return None, None

    now = datetime.now()
    _syntax_error = False

    def _repl(m: re.Match) -> str:
        nonlocal _syntax_error
        if not m.group(0):
            return ""
        result = _apply_replacement(
            replacement_template,
            full_match=m.group(0),
            groups=list(m.groups()),
            named_groups=m.groupdict(),
            path=path,
            counter=1,
            now=now,
            newnum=newnum,
            category=category,
            newnum_probe=newnum_probe,
        )
        if result is None:
            _syntax_error = True
            return m.group(0)
        return result

    newname = re.sub(pattern, _repl, name, flags=flags)
    if _syntax_error:
        return None, None
    return newname, _new_path(newname, path)


# ---------------------------------------------------------------------------
# Insert / Delete
# ---------------------------------------------------------------------------


def insert_at(name: str, path: str, text: str, pos: int) -> tuple[str, str]:
    """Insert *text* at character position *pos* (negative = append)."""
    if pos >= 0:
        newname = name[:pos] + text + name[pos:]
    else:
        newname = name + text
    return newname, _new_path(newname, path)


def delete_from(name: str, path: str, start: int, end: int) -> tuple[str, str]:
    """Delete characters from index *start* to *end* inclusive."""
    newname = name[:start] + name[end + 1 :]
    return newname, _new_path(newname, path)


# ---------------------------------------------------------------------------
# Extension handling
# ---------------------------------------------------------------------------


def cut_extension(name: str, path: str) -> tuple[str, str, str]:
    """Split *name* into (stem, stem_path, ext). Extension excludes the dot.

    Only the last path component of *name* is searched for an extension.
    """
    if "." in os.path.basename(name):
        ext = name.split(".")[-1]
        return name[: -len(ext) - 1], path[: -len(ext) - 1], ext
    return name, path, ""


def add_extension(name: str, path: str, ext: str) -> tuple[str, str]:
    if ext and name:
        return f"{name}.{ext}", f"{path}.{ext}"
    return name, path


def apply_extension_mode(
    ext: str, mode: str, normalization: dict[str, str] | None = None
) -> str:
    """Transform *ext* (no leading dot) according to *mode*.

    "keep": unchanged. "lower"/"upper": case-folded. "normalize": looked up
    case-insensitively in *normalization*, unchanged if absent from the
    table or if no table is given. Any other mode (e.g. "modify", which
    callers handle upstream by not cutting the extension at all) leaves
    *ext* unchanged.
    """
    if mode == "lower":
        return ext.lower()
    if mode == "upper":
        return ext.upper()
    if mode == "normalize" and normalization:
        return normalization.get(ext.lower(), ext)
    return ext


# ---------------------------------------------------------------------------
# File rename
# ---------------------------------------------------------------------------


def rename_file(original: str, new: str) -> tuple[bool, str | None]:
    """Rename a file on disk. Returns (success, error_message)."""
    if original == new:
        return True, None
    if os.path.exists(new):
        err = f"[Errno 17] {os.strerror(17)}: {new!r} already exists"
        _log.warning("Rename skipped (target exists): %s → %s", original, new)
        return False, err
    _log.debug("Renaming: %r → %r", original, new)
    try:
        os.renames(original, new)
        return True, None
    except OSError as exc:
        _log.warning("Rename failed: %s → %s: %s", original, new, exc)
        return False, str(exc)


def _clear_existing_target(dst: str) -> tuple[bool, str | None]:
    try:
        if os.path.isdir(dst) and not os.path.islink(dst):
            shutil.rmtree(dst)
        else:
            os.remove(dst)
        return True, None
    except OSError as exc:
        return False, str(exc)


def copy_path(
    src: str, dst: str, *, overwrite: bool = False
) -> tuple[bool, str | None]:
    """Copy a file or directory tree. Returns (success, error_message)."""
    if src == dst:
        return True, None
    if os.path.exists(dst):
        if not overwrite:
            err = f"[Errno 17] {os.strerror(17)}: {dst!r} already exists"
            _log.warning("Copy skipped (target exists): %s → %s", src, dst)
            return False, err
        ok, err = _clear_existing_target(dst)
        if not ok:
            return False, err
    _log.debug("Copying: %r → %r", src, dst)
    try:
        if os.path.isdir(src) and not os.path.islink(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return True, None
    except OSError as exc:
        _log.warning("Copy failed: %s → %s: %s", src, dst, exc)
        return False, str(exc)


def move_path(
    src: str, dst: str, *, overwrite: bool = False
) -> tuple[bool, str | None]:
    """Move a file or directory tree, across filesystems if needed.

    Returns (success, error_message).
    """
    if src == dst:
        return True, None
    if os.path.exists(dst):
        if not overwrite:
            err = f"[Errno 17] {os.strerror(17)}: {dst!r} already exists"
            _log.warning("Move skipped (target exists): %s → %s", src, dst)
            return False, err
        ok, err = _clear_existing_target(dst)
        if not ok:
            return False, err
    _log.debug("Moving: %r → %r", src, dst)
    try:
        shutil.move(src, dst)
        return True, None
    except OSError as exc:
        _log.warning("Move failed: %s → %s: %s", src, dst, exc)
        return False, str(exc)


# ---------------------------------------------------------------------------
# Target paths
# ---------------------------------------------------------------------------

_SEPARATORS_RE = re.compile(
    "[" + re.escape("".join(sorted({"/", os.sep, os.altsep or "/"}))) + "]"
)


class TargetPathError(ValueError):
    """A computed name cannot be turned into a valid target path.

    *reason* is one of the class constants, so that callers can display a
    translated message.
    """

    NO_DEST = "no_dest"
    DEST_POSITION = "dest_position"
    ABSOLUTE = "absolute"
    INVALID_COMPONENT = "invalid_component"
    # The search consumed the dot that separates the kept extension.
    EXT_SEPARATOR = "ext_separator"

    def __init__(self, reason: str, name: str) -> None:
        super().__init__(f"{reason}: {name!r}")
        self.reason = reason
        self.name = name


def resolve_target(src_path: str, new_name: str, dest_root: str | None = None) -> str:
    """Return the absolute target path of *src_path* renamed to *new_name*.

    *new_name* is relative to the directory of *src_path* and may contain
    ``/`` to reach sub-directories.  When it starts with the {dest} marker it
    is relative to *dest_root* instead.  ``..``, ``.``, empty components and
    absolute paths are rejected with TargetPathError.
    """
    from pbrenamer.core.replacement import DEST_MARKER

    if DEST_MARKER in new_name:
        rest = new_name[len(DEST_MARKER) :]
        if not new_name.startswith(DEST_MARKER) or DEST_MARKER in rest:
            raise TargetPathError(TargetPathError.DEST_POSITION, new_name)
        if rest and not _SEPARATORS_RE.match(rest):
            raise TargetPathError(TargetPathError.DEST_POSITION, new_name)
        if not dest_root:
            raise TargetPathError(TargetPathError.NO_DEST, new_name)
        base, relative = dest_root, rest[1:]
    else:
        if os.path.isabs(new_name) or os.path.splitdrive(new_name)[0]:
            raise TargetPathError(TargetPathError.ABSOLUTE, new_name)
        base, relative = os.path.dirname(src_path), new_name

    components = _SEPARATORS_RE.split(relative)
    if any(c in ("", ".", "..") for c in components):
        raise TargetPathError(TargetPathError.INVALID_COMPONENT, new_name)
    return os.path.join(base, *components)


def display_target(new_name: str, dest_root: str | None) -> str:
    """Return *new_name* with the {dest} marker replaced by *dest_root*."""
    from pbrenamer.core.replacement import DEST_MARKER

    if dest_root and new_name.startswith(DEST_MARKER):
        return dest_root.rstrip("/" + os.sep) + new_name[len(DEST_MARKER) :]
    return new_name


# ---------------------------------------------------------------------------
# Atomic batch rename
# ---------------------------------------------------------------------------


class RenameError(OSError):
    """A batch rename was refused or rolled back; nothing was renamed.

    *conflicts* lists the (src, dst) pairs whose target is taken when the
    batch was refused by the pre-check; it is empty for a rolled-back error.
    """

    def __init__(
        self, message: str, conflicts: list[tuple[str, str]] | None = None
    ) -> None:
        super().__init__(message)
        self.conflicts = conflicts or []


@dataclass
class RenameResult:
    """Outcome of execute_renames(), enough to undo it."""

    pairs: list[tuple[str, str]]
    created_dirs: list[str] = field(default_factory=list)
    pruned_dirs: list[str] = field(default_factory=list)


def _existing_ancestor(path: str) -> str:
    while not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return path


def path_key(path: str) -> str:
    """Conflict key of *path*, probing case sensitivity on its nearest
    existing ancestor directory (the target directory may not exist yet)."""
    return conflict_key(path, _existing_ancestor(os.path.dirname(path)))


def find_rename_conflicts(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Return the pairs whose target is shared with another pair, or exists
    on disk without being freed by the batch itself."""
    sources = {path_key(src) for src, _dst in pairs}
    by_target: dict[str, int] = defaultdict(int)
    for _src, dst in pairs:
        by_target[path_key(dst)] += 1
    conflicts: list[tuple[str, str]] = []
    for src, dst in pairs:
        key = path_key(dst)
        if by_target[key] > 1 or (os.path.lexists(dst) and key not in sources):
            conflicts.append((src, dst))
    return conflicts


def _make_parents(path: str, created: list[str]) -> None:
    missing: list[str] = []
    directory = os.path.dirname(path)
    while not os.path.isdir(directory):
        missing.append(directory)
        directory = os.path.dirname(directory)
    for directory in reversed(missing):
        os.mkdir(directory)
        created.append(directory)


def _rollback(moved: list[tuple[str, str]], created: list[str]) -> None:
    for src, dst in reversed(moved):
        try:
            shutil.move(dst, src)
        except OSError as exc:
            _log.error("Rollback failed: %s → %s: %s", dst, src, exc)
    remove_empty_dirs(created)


def remove_empty_dirs(directories: list[str]) -> list[str]:
    """Remove each of *directories* that is empty, deepest first.

    Returns the removed directories.
    """
    removed: list[str] = []
    for directory in sorted(set(directories), key=len, reverse=True):
        try:
            os.rmdir(directory)
            removed.append(directory)
        except OSError:
            pass
    return removed


def _prune_source_dirs(sources: list[str], root: str) -> list[str]:
    """Remove the source directories left empty, strictly below *root*."""
    root = os.path.abspath(root)
    candidates: set[str] = set()
    for src in sources:
        directory = os.path.dirname(os.path.abspath(src))
        while directory != root and os.path.commonpath([root, directory]) == root:
            candidates.add(directory)
            directory = os.path.dirname(directory)
    pruned: list[str] = []
    for directory in sorted(candidates, key=len, reverse=True):
        if os.path.isdir(directory) and not os.listdir(directory):
            os.rmdir(directory)
            pruned.append(directory)
    return pruned


def execute_renames(
    pairs: list[tuple[str, str]], *, prune_root: str | None = None
) -> RenameResult:
    """Rename every (src, dst) pair, all or nothing.

    All targets are checked first (RenameError with the conflicting pairs).
    Missing target directories are created.  When a target is the source of
    another pair (chain or cycle, e.g. a renumbering), sources are first moved
    to temporary names.  Any error rolls back the moves already done and the
    directories created, then raises RenameError.  Finally, source
    directories left empty are removed, strictly below *prune_root* (no
    pruning when it is None).
    """
    pairs = [(src, dst) for src, dst in pairs if src != dst]
    if not pairs:
        return RenameResult([])
    conflicts = find_rename_conflicts(pairs)
    if conflicts:
        _log.warning("Rename refused: %d conflict(s)", len(conflicts))
        raise RenameError(
            "Target(s) already taken: "
            + ", ".join(os.path.basename(dst) for _src, dst in conflicts),
            conflicts,
        )

    sources = {path_key(src): src for src, _dst in pairs}
    chained = any(
        path_key(dst) in sources and path_key(dst) != path_key(src)
        for src, dst in pairs
    )
    work = pairs
    moved: list[tuple[str, str]] = []
    created: list[str] = []
    try:
        if chained:
            tag = f".__pbrenamer_{uuid.uuid4().hex[:8]}_"
            work = []
            for i, (src, dst) in enumerate(pairs):
                tmp = os.path.join(os.path.dirname(src), f"{tag}{i:04d}")
                shutil.move(src, tmp)
                moved.append((src, tmp))
                work.append((tmp, dst))
        for src, dst in work:
            _make_parents(dst, created)
            _log.debug("Renaming: %r → %r", src, dst)
            shutil.move(src, dst)
            moved.append((src, dst))
    except OSError as exc:
        _log.warning("Rename failed, rolling back: %s", exc)
        _rollback(moved, created)
        raise RenameError(str(exc)) from exc

    pruned = (
        _prune_source_dirs([src for src, _dst in pairs], prune_root)
        if prune_root is not None
        else []
    )
    return RenameResult(pairs, created, pruned)
