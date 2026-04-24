"""File renaming and transformation functions."""

import glob as _glob
import logging
import os
import re
import unicodedata
from datetime import datetime

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
    "{L}": "([a-zA-Z]*)",
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
) -> tuple[str | None, str | None]:
    """Apply a search/replacement pattern pair.

    Returns (newname, newpath), or (None, None) on no match or syntax error.
    Raises replacement.FieldResolutionError when a field cannot be resolved.
    """
    regex = _build_regex(pattern_ini)
    try:
        m = re.search(regex, name)
        if m is None:
            return None, None
    except re.error:
        return None, None

    newname = _apply_replacement(
        pattern_end,
        full_match=m.group(0),
        groups=list(m.groups()),
        named_groups={},
        path=path,
        counter=count,
        now=datetime.now(),
        newnum=newnum,
    )
    if newname is None:
        return None, None
    return newname, _new_path(newname, path)


def rename_using_plain_text(
    name: str,
    path: str,
    search: str,
    replacement_template: str,
    *,
    newnum: int | None = None,
) -> tuple[str | None, str | None]:
    """Literal string search; unified replacement syntax.

    Returns (None, None) if *search* does not appear in *name*.
    Raises replacement.FieldResolutionError when a field cannot be resolved.
    """
    if search not in name:
        return None, None

    newname = _apply_replacement(
        replacement_template,
        full_match=search,
        groups=[],
        named_groups={},
        path=path,
        counter=1,
        now=datetime.now(),
        newnum=newnum,
    )
    if newname is None:
        return None, None
    return name.replace(search, newname), _new_path(name.replace(search, newname), path)


def rename_using_regex(
    name: str,
    path: str,
    pattern: str,
    replacement_template: str,
    *,
    newnum: int | None = None,
) -> tuple[str | None, str | None]:
    """Apply a Python regex search with unified replacement syntax.

    Returns (newname, newpath), or (None, None) on no match or invalid pattern.
    Raises replacement.FieldResolutionError when a field cannot be resolved.
    """
    from pbrenamer.core import replacement as _repl

    try:
        if not re.search(pattern, name):
            return None, None
        tokens = _repl.parse(replacement_template)
    except (re.error, _repl.ReplacementSyntaxError):
        return None, None

    now = datetime.now()
    field_error: _repl.FieldResolutionError | None = None

    def _cb(m: re.Match) -> str:
        nonlocal field_error
        if field_error:
            return m.group(0)
        try:
            return _repl.substitute(
                tokens,
                full_match=m.group(0),
                groups=list(m.groups()),
                named_groups=m.groupdict(),
                path=path,
                counter=1,
                now=now,
                newnum=newnum,
            )
        except _repl.FieldResolutionError as exc:
            field_error = exc
            return m.group(0)

    try:
        newname = re.sub(pattern, _cb, name)
    except re.error:
        return None, None

    if field_error:
        raise field_error
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
    """Split *name* into (stem, stem_path, ext). Extension excludes the dot."""
    if "." in name:
        ext = name.split(".")[-1]
        return name[: -len(ext) - 1], path[: -len(ext) - 1], ext
    return name, path, ""


def add_extension(name: str, path: str, ext: str) -> tuple[str, str]:
    if ext and name:
        return f"{name}.{ext}", f"{path}.{ext}"
    return name, path


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
