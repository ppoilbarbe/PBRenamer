"""Rename schema: PBPicat-style fields compiled into a pattern-mode rule.

A schema is a list of fields.  Non-empty, non-numeric fields (the *parts*)
form both the directory tree under the destination root and the file name,
joined with ``_``; a field made only of ``#`` is the counter, padded to the
number of ``#``; empty fields are skipped.  For instance ``A, , B, ###``
with destination ROOT gives ``ROOT/A/B/A_B_001.ext``.

The schema compiles to a planner.Rule that searches the whole stem and
replaces it with ``{dest}/A/B/A_B_{newnum:03}``, so that preview, conflicts,
execution and undo are those of the pattern mode.
"""

from __future__ import annotations

import os

from pbrenamer.core import planner
from pbrenamer.core import replacement as _repl
from pbrenamer.core.sidecar import SidecarConfig

# Characters a field may not contain: "_" separates the parts in the name,
# "." would be mistaken for an extension, "/" and "\" separate directories.
FORBIDDEN_FIELD_CHARS = "_./\\"
# The video marker sits in an {if:video:…} field, literal up to "}".
FORBIDDEN_MARKER_CHARS = FORBIDDEN_FIELD_CHARS + "{}"


class SchemaError(ValueError):
    """Invalid schema or video marker."""


def is_numeric(field: str) -> bool:
    """True if *field* is a counter (only ``#``)."""
    return bool(field) and set(field) == {"#"}


def validate(fields: list[str]) -> tuple[list[str], str | None]:
    """Return (parts, numeric_spec) of *fields*, or raise SchemaError.

    *parts* are the non-empty non-numeric fields, *numeric_spec* the counter
    field (None if absent).
    """
    numeric = [f for f in fields if is_numeric(f)]
    if len(numeric) > 1:
        raise SchemaError(
            _("The schema contains several numeric fields (only one allowed).")
        )
    for f in fields:
        for ch in FORBIDDEN_FIELD_CHARS:
            if ch in f:
                raise SchemaError(
                    _(
                        "Field “{field}” contains the forbidden character “{char}”."
                    ).format(field=f, char=ch)
                )
    parts = [f for f in fields if f and not is_numeric(f)]
    if not parts and not numeric:
        raise SchemaError(_("The schema is empty: fill in at least one field."))
    return parts, numeric[0] if numeric else None


def _marker_index(fields: list[str], position: int) -> int:
    """Index among the parts of the displayed marker *position* (0 = before
    the first field, len(fields) = after the last one)."""
    return sum(1 for f in fields[: max(position, 0)] if f and not is_numeric(f))


def _escape(text: str) -> str:
    return text.replace("{", "{{")


def compile_template(
    fields: list[str],
    *,
    video_marker: str = "",
    video_marker_pos: int = 0,
    in_place: bool = False,
) -> str:
    """Return the replacement template of the schema *fields*.

    With *in_place* the template is the file name only (renumbering);
    otherwise it starts with ``{dest}/`` followed by the directory tree.
    """
    parts, numeric = validate(fields)
    for ch in FORBIDDEN_MARKER_CHARS:
        if ch in video_marker:
            raise SchemaError(
                _("The video marker contains the forbidden character “{char}”.").format(
                    char=ch
                )
            )
    items = [_escape(p) for p in parts]
    if numeric:
        items.append(f"{{newnum:0{len(numeric)}}}")
    name = "_".join(items)
    if video_marker:
        index = _marker_index(fields, video_marker_pos)
        if index == 0:
            sep = "_" if items else ""
            name = f"{{if:video:{video_marker}{sep}}}" + name
        else:
            head = "_".join(items[:index])
            tail = "_".join(items[index:])
            name = f"{head}{{if:video:_{video_marker}}}" + (f"_{tail}" if tail else "")
    if in_place:
        return name
    return "/".join(["{dest}", *(_escape(p) for p in parts), name])


def compile_rule(
    fields: list[str],
    *,
    dest_root: str | None,
    video_marker: str = "",
    video_marker_pos: int = 0,
    fill_gaps: bool = False,
    renumber: bool = False,
    sidecar_config: SidecarConfig | None = None,
) -> planner.Rule:
    """Return the planner Rule of the schema *fields*.

    Renaming moves the files under *dest_root*; with *renumber* they are
    renumbered from the counter start in place, and *dest_root* is unused.
    Images and videos (and other categories) have separate counters.
    """
    if renumber and not any(is_numeric(f) for f in fields):
        validate(fields)
        raise SchemaError(
            _("The schema has no numeric field (use “#” to define a counter).")
        )
    template = compile_template(
        fields,
        video_marker=video_marker,
        video_marker_pos=video_marker_pos,
        in_place=renumber,
    )
    return planner.Rule(
        search="{X}",
        replace=template,
        mode=_repl.SEARCH_PATTERN,
        ext_mode="lower",
        dest_root=None if renumber else dest_root,
        fill_gaps=fill_gaps,
        per_category=True,
        renumber=renumber,
        sidecar_config=sidecar_config or SidecarConfig.defaults(),
    )


def infer_fields(
    path: str, field_count: int, history: dict[str, list[str]]
) -> list[str] | None:
    """Guess the schema fields of *path* from the field histories
    (``history["field_<i>"]``), as PBPicat's "Template" does.

    The stem is split on ``_``; a trailing number marks the counter.  The
    stem parts, then up to three parent directory names, are assigned in
    order, each to the first following field whose history holds it.  The
    counter goes to the first field whose history holds a ``#`` entry, with
    the longest such width.  Return None if nothing matched.
    """
    field_sets = [
        {v for v in history.get(f"field_{i}", []) if v} for i in range(field_count)
    ]
    stem = os.path.splitext(os.path.basename(path))[0]
    parts = stem.split("_")
    number = parts.pop() if parts and parts[-1].isdigit() else None
    parent = os.path.dirname(os.path.abspath(path))
    dirs = []
    for _level in range(3):
        parent, name = os.path.split(parent)
        if not name:
            break
        dirs.insert(0, name)
    candidates = parts + [d for d in dirs if d not in parts]

    result = [""] * field_count
    last = -1
    matched = False
    for part in candidates:
        for index in range(last + 1, field_count):
            if part in field_sets[index]:
                result[index] = part
                last = index
                matched = True
                break

    if number is not None:
        for index in range(field_count):
            counters = [v for v in history.get(f"field_{index}", []) if is_numeric(v)]
            if counters:
                result[index] = "#" * max(len(v) for v in counters)
                matched = True
                break
    return result if matched else None
