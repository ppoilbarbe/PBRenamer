"""Unified replacement-string parser, validator, and substitutor.

Syntax::

    {field}
    {field:fmt}
    {field:casefmt}
    {field:alignfmt}
    {field:casealignfmt:default}

``field``
    See ``_SIMPLE_FIELDS`` and the ``im:/au:/vi:/re:`` prefixes.

``case``
    Optional first character: ``=`` (unchanged, default if absent), ``-`` (lower),
    ``+`` (upper), ``!`` (capitalise first char, rest lower), ``*`` (Title Case).

``align``
    Optional character after ``case``: ``<`` (left), ``>`` (right),
    ``0`` (zero-pad right), ``^`` (centre; extra space on left when padding is odd).

``fmt``
    Digit string (minimum width) for integers/strings;
    ``strftime`` format for date/datetime fields.

``default``
    Literal fallback when the field is absent; omit to make absence
    an error (file shown in red in the preview).

``{{``
    Literal ``{`` character.
"""

from __future__ import annotations

import datetime
import logging
import os
import re
from dataclasses import dataclass

from pbrenamer.core import audio_meta, image_meta, video_meta

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

SEARCH_PATTERN = "pattern"
SEARCH_REGEX = "regex"
SEARCH_PLAIN = "plain"

_SIMPLE_FIELDS = frozenset(
    {"0", "num", "newnum", "date", "datetime", "mdatetime", "cdatetime", "dir"}
)
_GROUP_RE = re.compile(r"^[1-9][0-9]*$")
_TOKEN_RE = re.compile(r"\{\{|\{([^{}]*)\}")

# All prefixes that introduce a namespaced field (3 characters including the colon).
_META_PREFIXES = frozenset({"im:", "au:", "vi:", "re:"})

# Mapping from field prefix to the corresponding metadata reader function.
_META_READERS = {
    "im:": image_meta.read_field,
    "au:": audio_meta.read_field,
    "vi:": video_meta.read_field,
}

# Mapping from field prefix to the file-type probe for that namespace.
_META_CAN_READ = {
    "im:": image_meta.can_read,
    "au:": audio_meta.can_read,
    "vi:": video_meta.can_read,
}

# File-type namespace prefixes (im:, au:, vi: and any future additions).
# Used to detect "multi-meta mode" in substitute().
_FILE_META_PREFIXES: frozenset[str] = frozenset(_META_READERS)


@dataclass
class LiteralSegment:
    text: str


@dataclass
class FieldSegment:
    name: str  # e.g. "0", "1", "num", "date", "im:Make", "re:year"
    case: str  # "=", "-", "+", "!", "*", or "" (treated as "=")
    align: str  # "<", ">", "0", "^", or ""
    fmt: str  # width digits or strftime string, or ""
    default: str | None  # None = no default → error when field absent
    raw: str  # original "{…}" text for error reporting


Segment = LiteralSegment | FieldSegment


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ReplacementSyntaxError(ValueError):
    """Invalid replacement template syntax."""

    def __init__(self, message: str, raw: str = "") -> None:
        super().__init__(message)
        self.raw = raw


class FieldResolutionError(ValueError):
    """A field has no value for this file and no default was specified."""

    def __init__(self, field: str) -> None:
        super().__init__(f"Field {field!r} not available for this file")
        self.field = field


class NewNumState:
    """Mutable counter shared across one preview/rename batch for {newnum}.

    Tracks which counter values have been used and which target names are
    already reserved, so each file receives a conflict-free number.
    """

    def __init__(self, start: int = 1) -> None:
        self.start = start
        self.current = start
        self.reserved: set[str] = set()


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _is_valid_name(name: str) -> bool:
    if name in _SIMPLE_FIELDS:
        return True
    if _GROUP_RE.match(name):
        return True
    low = name.lower()
    return any(low.startswith(p) for p in _META_PREFIXES) and len(name) > 3


def _split_name_options(content: str) -> tuple[str, str]:
    """Return (field_name, options_string) from the raw content of {…}."""
    low = content.lower()
    if any(low.startswith(p) for p in _META_PREFIXES):
        # Format: "im:FieldName[:options]" — the colon after FieldName is the separator
        rest = content[3:]
        idx = rest.find(":")
        if idx == -1:
            return content, ""
        return content[: 3 + idx], rest[idx + 1 :]
    idx = content.find(":")
    if idx == -1:
        return content, ""
    return content[:idx], content[idx + 1 :]


def _parse_options(options: str) -> tuple[str, str, str, str | None]:
    """Return (case, align, fmt, default) from the options part of a field token."""
    if not options:
        return "", "", "", None
    case = ""
    rest = options
    if rest and rest[0] in "=-+!*":
        case = rest[0]
        rest = rest[1:]
    align = ""
    if rest and rest[0] in "<>0^":
        align = rest[0]
        rest = rest[1:]
    idx = rest.find(":")
    if idx == -1:
        return case, align, rest, None
    return case, align, rest[:idx], rest[idx + 1 :]


def _parse_field(content: str) -> FieldSegment:
    raw = "{" + content + "}"
    if not content:
        raise ReplacementSyntaxError("Empty field: {}", raw)
    name, options = _split_name_options(content)
    if not _is_valid_name(name):
        raise ReplacementSyntaxError(f"Unknown field name: {name!r}", raw)
    case, align, fmt, default = _parse_options(options)
    return FieldSegment(
        name=name, case=case, align=align, fmt=fmt, default=default, raw=raw
    )


def parse(template: str) -> list[Segment]:
    """Parse *template* into a list of Segment objects.

    Raises ReplacementSyntaxError if the syntax is invalid.
    """
    _log.debug("Parsing replacement template: %r", template)
    segments: list[Segment] = []
    pos = 0
    for m in _TOKEN_RE.finditer(template):
        if m.start() > pos:
            segments.append(LiteralSegment(template[pos : m.start()]))
        if m.group(0) == "{{":
            segments.append(LiteralSegment("{"))
        else:
            segments.append(_parse_field(m.group(1)))
        pos = m.end()

    tail = template[pos:]
    if "{" in tail:
        raise ReplacementSyntaxError("Unmatched '{' in replacement pattern")
    if tail:
        segments.append(LiteralSegment(tail))
    _log.debug("Parsed %d segment(s) from %r", len(segments), template)
    return segments


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def validate(segments: list[Segment], search_mode: str) -> list[str]:
    """Return a list of mode-compatibility error messages (empty = OK)."""
    errors: list[str] = []
    for seg in segments:
        if not isinstance(seg, FieldSegment):
            continue
        name = seg.name
        if _GROUP_RE.match(name) and search_mode == SEARCH_PLAIN:
            errors.append(
                f"{seg.raw}: capture groups are not available in plain-text mode"
            )
        elif name.lower().startswith("re:") and search_mode != SEARCH_REGEX:
            errors.append(f"{seg.raw}: named groups require regex search mode")
    return errors


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def _apply_case(s: str, case: str) -> str:
    if not case or case == "=":
        return s
    if case == "-":
        return s.lower()
    if case == "+":
        return s.upper()
    if case == "!":
        return s[:1].upper() + s[1:].lower() if s else s
    if case == "*":
        return s.title()
    return s


def _apply_align(s: str, align: str, fmt: str) -> str:
    if not fmt.isdigit():
        return s
    w = int(fmt)
    if align == "0":
        return s.zfill(w)
    if align == "<":
        return s.ljust(w)
    if align == "^":
        total_pad = max(0, w - len(s))
        left_pad = (total_pad + 1) // 2
        return " " * left_pad + s + " " * (total_pad - left_pad)
    return s.rjust(w)  # ">" or ""


def _format_value(seg: FieldSegment, value: object) -> str:
    if isinstance(value, datetime.datetime):
        fmt = seg.fmt or "%Y-%m-%d_%H%M%S"
        return _apply_case(value.strftime(fmt), seg.case)
    if isinstance(value, datetime.date):
        fmt = seg.fmt or "%Y-%m-%d"
        return _apply_case(value.strftime(fmt), seg.case)
    if isinstance(value, int):
        s = str(value)
        return _apply_align(s, seg.align, seg.fmt)
    # str, rational (already str from meta), and default values
    s = str(value)
    s = _apply_case(s, seg.case)
    return _apply_align(s, seg.align, seg.fmt)


# ---------------------------------------------------------------------------
# Substitutor
# ---------------------------------------------------------------------------


def substitute(
    segments: list[Segment],
    *,
    full_match: str | None,
    groups: list[str],
    named_groups: dict[str, str],
    path: str,
    counter: int,
    now: datetime.datetime,
    newnum: int | None = None,
) -> str:
    """Resolve all field segments and return the assembled replacement string.

    *full_match* is {0}: the entire matched substring (or the search literal
    in plain-text mode).
    *groups* are {1}, {2}…: numbered capture groups (1-based indexing).
    *named_groups* are {re:name}: named regex groups.
    *path* is the full file path (used for dir, mdatetime, im: and au: fields).

    Raises FieldResolutionError if a field is absent and has no default.
    """
    # Multi-meta mode: when fields from more than one file-type namespace
    # (im:, vi:, au:…) appear in the same template, each namespace is probed
    # with can_read() to determine whether it applies to this file.
    # - Applicable namespace: strict behaviour — absent field + no default → error.
    # - Non-applicable namespace: silently contributes "".
    # - No namespace applicable at all → FieldResolutionError on the first meta field.
    # With a single namespace the strict behaviour is always preserved.
    _active_ns = {
        seg.name[:3].lower()
        for seg in segments
        if isinstance(seg, FieldSegment) and seg.name[:3].lower() in _FILE_META_PREFIXES
    }
    multi_meta = len(_active_ns) > 1

    _applicable_ns: frozenset[str] = frozenset()
    if multi_meta:
        _applicable_ns = frozenset(ns for ns in _active_ns if _META_CAN_READ[ns](path))
        if not _applicable_ns:
            for seg in segments:
                if (
                    isinstance(seg, FieldSegment)
                    and seg.name[:3].lower() in _FILE_META_PREFIXES
                ):
                    raise FieldResolutionError(seg.name)

    parts: list[str] = []
    for seg in segments:
        if isinstance(seg, LiteralSegment):
            parts.append(seg.text)
            continue

        value = _resolve(
            seg,
            full_match=full_match,
            groups=groups,
            named_groups=named_groups,
            path=path,
            counter=counter,
            now=now,
            newnum=newnum,
        )

        if value is None:
            if seg.default is not None:
                default_str = _apply_case(seg.default, seg.case)
                parts.append(
                    _apply_align(default_str, seg.align, seg.fmt)
                    if seg.fmt.isdigit()
                    else default_str
                )
            elif multi_meta and seg.name[:3].lower() in _FILE_META_PREFIXES:
                if seg.name[:3].lower() in _applicable_ns:
                    raise FieldResolutionError(seg.name)
                # non-applicable namespace in mixed template → silently ""
            else:
                raise FieldResolutionError(seg.name)
        else:
            # For {num}, default encodes the starting value instead of a fallback.
            # {newnum} receives its value pre-resolved by NewNumState; no offset.
            if seg.name == "num" and seg.default is not None:
                try:
                    value = int(value) + int(seg.default) - 1
                except (ValueError, TypeError):
                    pass
            parts.append(_format_value(seg, value))

    return "".join(parts)


def _resolve(
    seg: FieldSegment,
    *,
    full_match: str | None,
    groups: list[str],
    named_groups: dict[str, str],
    path: str,
    counter: int,
    now: datetime.datetime,
    newnum: int | None = None,
) -> object | None:
    name = seg.name
    low = name.lower()

    if name == "0":
        return full_match

    if _GROUP_RE.match(name):
        idx = int(name) - 1
        return groups[idx] if idx < len(groups) else None

    if low.startswith("re:"):
        return named_groups.get(name[3:])

    if name == "num":
        return counter

    if name == "newnum":
        return newnum  # pre-resolved by NewNumState; None if not provided

    if name == "date":
        return now.date()

    if name == "datetime":
        return now

    if name == "mdatetime":
        try:
            return datetime.datetime.fromtimestamp(os.stat(path).st_mtime)
        except OSError:
            return None

    if name == "cdatetime":
        try:
            st = os.stat(path)
            # st_birthtime on macOS; st_ctime on Windows (creation) and Linux (fallback)
            return datetime.datetime.fromtimestamp(
                getattr(st, "st_birthtime", st.st_ctime)
            )
        except OSError:
            return None

    if name == "dir":
        parent = os.path.dirname(path)
        return os.path.basename(parent) if parent else None

    reader = _META_READERS.get(low[:3])
    if reader is not None:
        return reader(path, name[3:])

    return None
