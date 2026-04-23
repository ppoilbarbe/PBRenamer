"""File renaming and transformation functions."""

import glob as _glob
import os
import random
import re
import time
import unicodedata
from datetime import datetime  # noqa: I001

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


def replace_with(name: str, path: str, orig: str, new: str) -> tuple[str, str]:
    newname = name.replace(orig, new)
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
    "{@}": "(.*)",
}

_NUM_RE = re.compile(r"\{(num)([0-9]*)\}|\{(num)([0-9]*)(\+)([0-9]*)\}")

_RAND_RE = re.compile(
    r"\{(rand)([0-9]*)\}"
    r"|\{(rand)([0-9]*)(\-)([0-9]*)\}"
    r"|\{(rand)([0-9]*)(\,)([0-9]*)\}"
    r"|\{(rand)([0-9]*)(\-)([0-9]*)(\,)([0-9]*)\}"
)


def _build_regex(pattern: str) -> str:
    """Convert a user-facing search pattern into a compiled regex string."""
    for ch in ".[]()?":
        pattern = pattern.replace(ch, "\\" + ch)
    for token, regex in _PATTERN_TOKENS.items():
        pattern = pattern.replace(token, regex)
    return pattern


def rename_using_patterns(
    name: str,
    path: str,
    pattern_ini: str,
    pattern_end: str,
    count: int,
    ext: str = "",
) -> tuple[str | None, str | None]:
    """Apply a search/replacement pattern pair.

    Returns (newname, newpath), or (None, None) on failure.
    """
    regex = _build_regex(pattern_ini)
    newname = pattern_end

    try:
        m = re.search(regex, name)
        if m is None:
            return None, None
        for i, group in enumerate(m.groups()):
            newname = newname.replace("{" + str(i + 1) + "}", group)
    except re.error:
        return None, None

    # {num} / {num2} / {num2+5} counter substitution
    count_str = str(count)
    m_num = _NUM_RE.search(newname)
    if m_num:
        g = m_num.groups()
        if g[0] == "num":
            if g[1]:
                count_str = count_str.zfill(int(g[1]))
        elif g[2] == "num" and g[4] == "+":
            if g[5]:
                count_str = str(int(count_str) + int(g[5]))
            if g[3]:
                count_str = count_str.zfill(int(g[3]))
        newname = _NUM_RE.sub(count_str, newname)

    # {dir} — parent folder name
    newname = newname.replace("{dir}", os.path.basename(os.path.dirname(path)))

    # Current-date tokens
    now = time.localtime()
    for token, fmt in {
        "{date}": "%Y%m%d",
        "{datedelim}": "%Y-%m-%d",
        "{year}": "%Y",
        "{month}": "%m",
        "{monthname}": "%B",
        "{monthsimp}": "%b",
        "{day}": "%d",
        "{dayname}": "%A",
        "{daysimp}": "%a",
    }.items():
        newname = newname.replace(token, time.strftime(fmt, now))

    # File-stat date tokens
    full_path = _new_path(f"{name}.{ext}" if ext else name, path)
    createdate, modifydate = _get_filestat(full_path)
    for prefix, stat in (("create", createdate), ("modify", modifydate)):
        for suffix, fmt in {
            "date": "%Y%m%d",
            "datedelim": "%Y-%m-%d",
            "year": "%Y",
            "month": "%m",
            "monthname": "%B",
            "monthsimp": "%b",
            "day": "%d",
            "dayname": "%A",
            "daysimp": "%a",
        }.items():
            token = "{" + prefix + suffix + "}"
            newname = newname.replace(token, time.strftime(fmt, stat) if stat else "")

    # {rand} / {rand500} / {rand10-20} / {rand20,5} random number substitution
    m_rand = _RAND_RE.search(newname)
    if m_rand:
        g = m_rand.groups()  # 16 groups across 4 alternatives
        rnd: str
        if g[0] == "rand":
            rnd = str(random.randint(0, int(g[1]) if g[1] else 100))
        elif g[2] == "rand" and g[4] == "-":
            rnd = str(random.randint(int(g[3]), int(g[5])))
        elif g[6] == "rand" and g[8] == ",":
            rnd = str(random.randint(0, int(g[7]) if g[7] else 100)).zfill(int(g[9]))
        elif g[10] == "rand" and g[12] == "-" and g[14] == ",":
            rnd = str(random.randint(int(g[11]), int(g[13]))).zfill(int(g[15]))
        else:
            rnd = str(random.randint(0, 100))
        newname = _RAND_RE.sub(rnd, newname)

    return newname, _new_path(newname, path)


def _get_filestat(path: str) -> tuple[time.struct_time | None, time.struct_time | None]:
    try:
        st = os.stat(path)
        return (
            datetime.fromtimestamp(st.st_ctime).timetuple(),
            datetime.fromtimestamp(st.st_mtime).timetuple(),
        )
    except OSError:
        return None, None


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
        return False, f"[Errno 17] {os.strerror(17)}: {new!r} already exists"
    try:
        os.renames(original, new)
        return True, None
    except OSError as exc:
        return False, str(exc)
