"""Unified replacement-string parser, validator, and substitutor.

Syntax: {field}, {field:fmt}, {field:alignfmt:default}

  field   — see _SIMPLE_FIELDS and the ex:/re: prefixes below
  align   — optional first character: < (left), > (right), 0 (zero-pad right)
  fmt     — digit string (minimum width) for integers/strings;
            strftime format for date/datetime fields
  default — literal fallback when the field is absent; omit to make absence
            an error (file shown in red in the preview)
  {{      — literal '{' character
"""

from __future__ import annotations

import datetime
import logging
import os
import re
from dataclasses import dataclass

from pbrenamer.core import meta

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

SEARCH_PATTERN = "pattern"
SEARCH_REGEX = "regex"
SEARCH_PLAIN = "plain"

_SIMPLE_FIELDS = frozenset(
    {"0", "num", "newnum", "date", "datetime", "mdatetime", "dir"}
)
_GROUP_RE = re.compile(r"^[1-9][0-9]*$")
_TOKEN_RE = re.compile(r"\{\{|\{([^{}]*)\}")


@dataclass
class LiteralSegment:
    text: str


@dataclass
class FieldSegment:
    name: str  # e.g. "0", "1", "num", "date", "ex:Make", "re:year"
    align: str  # "<", ">", "0", or ""
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
    if low.startswith("ex:"):
        return len(name) > 3
    if low.startswith("re:"):
        return len(name) > 3
    return False


def _split_name_options(content: str) -> tuple[str, str]:
    """Return (field_name, options_string) from the raw content of {…}."""
    low = content.lower()
    if low.startswith("ex:") or low.startswith("re:"):
        # Format: "ex:FieldName[:options]" — the colon after FieldName is the separator
        rest = content[3:]
        idx = rest.find(":")
        if idx == -1:
            return content, ""
        return content[: 3 + idx], rest[idx + 1 :]
    idx = content.find(":")
    if idx == -1:
        return content, ""
    return content[:idx], content[idx + 1 :]


def _parse_options(options: str) -> tuple[str, str, str | None]:
    """Return (align, fmt, default) from the options part of a field token."""
    if not options:
        return "", "", None
    align = ""
    rest = options
    if rest and rest[0] in "<>0":
        align = rest[0]
        rest = rest[1:]
    idx = rest.find(":")
    if idx == -1:
        return align, rest, None
    return align, rest[:idx], rest[idx + 1 :]


def _parse_field(content: str) -> FieldSegment:
    raw = "{" + content + "}"
    if not content:
        raise ReplacementSyntaxError("Empty field: {}", raw)
    name, options = _split_name_options(content)
    if not _is_valid_name(name):
        raise ReplacementSyntaxError(f"Unknown field name: {name!r}", raw)
    align, fmt, default = _parse_options(options)
    return FieldSegment(name=name, align=align, fmt=fmt, default=default, raw=raw)


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


def _apply_align(s: str, align: str, fmt: str) -> str:
    if not fmt.isdigit():
        return s
    w = int(fmt)
    if align == "0":
        return s.zfill(w)
    if align == "<":
        return s.ljust(w)
    return s.rjust(w)  # ">" or ""


def _format_value(seg: FieldSegment, value: object) -> str:
    if isinstance(value, datetime.datetime):
        fmt = seg.fmt or "%Y-%m-%d_%H%M%S"
        return value.strftime(fmt)
    if isinstance(value, datetime.date):
        fmt = seg.fmt or "%Y-%m-%d"
        return value.strftime(fmt)
    if isinstance(value, int):
        s = str(value)
        return _apply_align(s, seg.align, seg.fmt)
    # str, rational (already str from meta), and default values
    s = str(value)
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
    *path* is the full file path (used for dir, mdatetime, ex: fields).

    Raises FieldResolutionError if a field is absent and has no default.
    """
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
                # Default is a literal string; still apply numeric width.
                parts.append(
                    _apply_align(seg.default, seg.align, seg.fmt)
                    if seg.fmt.isdigit()
                    else seg.default
                )
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

    if name == "dir":
        parent = os.path.dirname(path)
        return os.path.basename(parent) if parent else None

    if low.startswith("ex:"):
        return meta.read_field(path, name[3:])

    return None
