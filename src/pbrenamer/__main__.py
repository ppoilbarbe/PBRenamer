"""Entry point — run as `python -m pbrenamer` or `pbrenamer`."""

import argparse
import logging
import os
import sys

from pbrenamer.argparse_qt import add_qt_arguments

_log = logging.getLogger(__name__)

# Map --case value → replace_capitalization() mode index
_CASE_MAP = {"upper": 0, "lower": 1, "capitalize": 2, "title": 3}

# Map --list value → get_file_listing() mode index
_LIST_MAP = {"files": 0, "dirs": 1, "all": 2}

# Map --sep value → replace_spaces() mode index
_SEP_MAP = {
    "space-underscore": 0,
    "underscore-space": 1,
    "space-dot": 2,
    "dot-space": 3,
    "space-dash": 4,
    "dash-space": 5,
}

# save config integer indices → CLI string values
_SEP_IDX = [
    "none",
    "space-underscore",
    "underscore-space",
    "space-dot",
    "dot-space",
    "space-dash",
    "dash-space",
]
_CASE_IDX = ["none", "upper", "lower", "capitalize", "title"]

_SEP_CHOICES = ["none"] + list(_SEP_MAP)


def _build_parser(*, frozen: bool | None = None) -> argparse.ArgumentParser:
    from pbrenamer import __version__

    # --auto-update is only meaningful for the single-file PyInstaller
    # executable; a source checkout or a pip/PyPI install has no running
    # binary to replace, so the option is not even offered there.
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))

    parser = argparse.ArgumentParser(
        prog="pbrenamer",
        description="PBRenamer — graphical batch file renaming utility.",
        epilog=(
            "Headless mode is activated when --search, --saved or --schema is "
            "provided; the three options are mutually exclusive. "
            "Settings come from the profile chosen with --profile, or from "
            "the last profile used in the GUI. "
            "Qt platform options (--style, --platform, …) are forwarded to Qt "
            "in GUI mode."
        ),
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=None,
        metavar="DIR",
        help="Working directory (default: current working directory)",
    )

    # ── Headless rename options ───────────────────────────────────────────────
    rename_group = parser.add_argument_group(
        "headless rename",
        "These options activate headless (no GUI) mode"
        " when --search, --saved or --schema is given.",
    )
    headless_source = rename_group.add_mutually_exclusive_group()
    headless_source.add_argument(
        "-s",
        "--search",
        metavar="TEXT",
        default=None,
        help="Search pattern/expression — activates headless mode",
    )
    headless_source.add_argument(
        "--saved",
        metavar="NAME",
        default=None,
        help=(
            "Load a named save — activates headless mode; "
            "other options override values from the save"
        ),
    )
    headless_source.add_argument(
        "--schema",
        metavar="LIST",
        default=None,
        help=(
            "Rename schema: comma-separated fields, e.g. 'Trip,,Paris,###' "
            "— activates headless mode. Non-empty fields form both the "
            "directory tree under --dest and the name (joined with '_'); a "
            "field of '#' only is the counter, padded to the number of '#'; "
            "empty fields are skipped. Sidecar mode is always on"
        ),
    )
    rename_group.add_argument(
        "--dest",
        metavar="DIR",
        default=None,
        help=(
            "Destination root: with --schema, defaults to the profile's "
            "destination and is required if it has none (except with "
            "--renumber); value of the {dest} field in --replace"
        ),
    )
    rename_group.add_argument(
        "--fill-gaps",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "{newnum} takes the smallest free number instead of continuing "
            "after the highest one (default: the profile's setting with "
            "--schema, --no-fill-gaps otherwise)"
        ),
    )
    rename_group.add_argument(
        "--renumber",
        action="store_true",
        default=False,
        help=(
            "{newnum} runs from its start value, ignoring the numbers already "
            "used on disk; with --schema, renumber the files in place"
        ),
    )
    rename_group.add_argument(
        "--video-marker",
        metavar="TEXT",
        default=None,
        help=(
            "With --schema: text added to the name of video files "
            "(default: the profile's marker)"
        ),
    )
    rename_group.add_argument(
        "--video-marker-pos",
        metavar="N",
        type=int,
        default=None,
        help=(
            "With --schema: position of the video marker between the fields "
            "(0 = before the first field, default: the profile's position)"
        ),
    )
    rename_group.add_argument(
        "-r",
        "--replace",
        metavar="TEXT",
        default=None,
        help="Replacement string (default: empty string)",
    )
    rename_group.add_argument(
        "--mode",
        choices=["pattern", "regex", "plain"],
        default=None,
        metavar="{pattern,regex,plain}",
        help="Search mode: pattern (default), regex, or plain text",
    )
    rename_group.add_argument(
        "--list",
        choices=["files", "dirs", "all"],
        default="files",
        metavar="{files,dirs,all}",
        help="Entry types to process: files (default), dirs, or all",
    )
    rename_group.add_argument(
        "--recurse",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Recurse into sub-directories (default: --no-recurse)",
    )
    rename_group.add_argument(
        "--ext-mode",
        choices=["keep", "lower", "upper", "normalize", "modify"],
        default=None,
        metavar="{keep,lower,upper,normalize,modify}",
        help="How to handle the extension during rename (default: keep)",
    )
    rename_group.add_argument(
        "--sidecar-mode",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Group sidecar files (e.g. img.xmp) with their base file when"
            " renaming: the sidecar is renamed using the base file's new"
            " stem plus its own original suffix, unchanged. Requires"
            " --ext-mode keep, lower, or upper (default: --no-sidecar-mode)"
        ),
    )
    rename_group.add_argument(
        "--filter",
        metavar="GLOB",
        default=None,
        dest="filter_glob",
        help="Glob pattern to restrict the file listing (e.g. '*.jpg')",
    )
    rename_group.add_argument(
        "--select",
        metavar="GLOB",
        action="append",
        default=None,
        help=(
            "Restrict the rename to entries matching GLOB (basename match), "
            "as if selecting them by clicking in the GUI file list. May be "
            "given multiple times to accumulate (like Ctrl+click). With "
            "--sidecar-mode, selecting a base file also selects its "
            "sidecars, and selecting a sidecar also selects its base file "
            "and siblings. Omit to act on every listed entry (default)"
        ),
    )
    rename_group.add_argument(
        "--accent",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Strip diacritics from result names (default: --no-accent)",
    )
    rename_group.add_argument(
        "--dup",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Collapse consecutive duplicate separators (default: --no-dup)",
    )
    rename_group.add_argument(
        "--sep",
        choices=_SEP_CHOICES,
        default=None,
        metavar="{none,space-underscore,underscore-space,space-dot,dot-space,space-dash,dash-space}",
        help="Separator conversion applied after rename (default: none)",
    )
    rename_group.add_argument(
        "--case",
        choices=["none", "upper", "lower", "capitalize", "title"],
        default=None,
        metavar="{none,upper,lower,capitalize,title}",
        help="Capitalisation applied after rename (default: none)",
    )
    rename_group.add_argument(
        "--confirm",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Preview changes and ask for confirmation (default: --no-confirm)",
    )
    rename_group.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Print the mv commands that would run, without renaming anything "
        "(default: --no-dry-run)",
    )

    # ── Help export ───────────────────────────────────────────────────────────
    help_group = parser.add_argument_group(
        "help export",
        "Print pattern-field help HTML to stdout and exit.",
    )
    help_group.add_argument(
        "--help-search",
        action="store_true",
        default=False,
        help="Print search-field help HTML and exit",
    )
    help_group.add_argument(
        "--help-replace",
        action="store_true",
        default=False,
        help="Print replacement-field help HTML and exit",
    )

    # ── Desktop integration (Linux) ──────────────────────────────────────────
    desktop_group = parser.add_argument_group(
        "desktop integration",
        "Install a .desktop menu entry + icon for the current user and exit "
        "(Linux only — pip installs have no post-install hook to do this "
        "automatically).",
    )
    desktop_target = desktop_group.add_mutually_exclusive_group()
    desktop_target.add_argument(
        "--install-desktop-entry",
        action="store_true",
        default=False,
        help="Install a desktop menu entry + icon for the current user",
    )
    desktop_target.add_argument(
        "--uninstall-desktop-entry",
        action="store_true",
        default=False,
        help="Remove the desktop menu entry + icon installed by "
        "--install-desktop-entry",
    )

    # ── Self-update (PyInstaller executables only) ───────────────────────────
    if frozen:
        update_group = parser.add_argument_group(
            "self-update",
            "Available only in PyInstaller-built executables — a source or "
            "pip/PyPI install has no single running binary to replace.",
        )
        update_group.add_argument(
            "--auto-update",
            action="store_true",
            default=False,
            help=(
                "Download the latest release from GitHub and replace the "
                "running executable, then exit"
            ),
        )

    parser.add_argument(
        "--profile",
        metavar="NAME",
        default=None,
        help=(
            "Use the profile NAME (settings, presets, sidecar configuration, "
            "schema defaults) instead of the last one used in the GUI"
        ),
    )

    # ── Developer / testing ───────────────────────────────────────────────────
    parser.add_argument(
        "--config-dir",
        metavar="DIR",
        default=None,
        help=(
            "Override the configuration directory "
            "(default: ~/.config/pbrenamer on Linux). "
            "Intended for testing."
        ),
    )

    # ── Logging verbosity ─────────────────────────────────────────────────────
    level_group = parser.add_mutually_exclusive_group()
    level_group.add_argument(
        "-d",
        "--debug",
        action="store_const",
        const="DEBUG",
        dest="log_level",
        help="Enable debug output — overrides saved preferences",
    )
    level_group.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        const="INFO",
        dest="log_level",
        help="Enable verbose output (INFO level) — overrides saved preferences",
    )
    level_group.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        const="WARNING",
        dest="log_level",
        help="Suppress informational messages (WARNING level)"
        " — overrides saved preferences",
    )

    add_qt_arguments(parser)

    return parser


# ---------------------------------------------------------------------------
# Headless mode
# ---------------------------------------------------------------------------


def _resolve_ns(ns: argparse.Namespace) -> None:
    """Fill None fields in *ns*, loading a named save when --saved is given.

    Precedence: explicit CLI flag > saved config > hardcoded default.
    """
    if ns.dest is not None:
        ns.dest = os.path.abspath(ns.dest)
    if ns.schema is not None:
        _resolve_schema_ns(ns)
        return
    for flag, value in (
        ("--video-marker", ns.video_marker),
        ("--video-marker-pos", ns.video_marker_pos),
    ):
        if value is not None:
            print(f"error: {flag} requires --schema", file=sys.stderr)
            sys.exit(1)
    if ns.fill_gaps is None:
        ns.fill_gaps = False

    if ns.saved is not None:
        from pbrenamer.ui.presets import PatternPresets

        saves = PatternPresets().get_saves()
        if ns.saved not in saves:
            print(f"error: save '{ns.saved}' not found", file=sys.stderr)
            sys.exit(1)
        cfg = saves[ns.saved]
        if ns.search is None and "search_pattern" in cfg:
            ns.search = str(cfg["search_pattern"])
        if ns.mode is None and "search_mode" in cfg:
            ns.mode = str(cfg["search_mode"])
        if ns.replace is None and "replace_pattern" in cfg:
            ns.replace = str(cfg["replace_pattern"])
        if ns.sep is None and "separator" in cfg:
            idx = int(cfg["separator"])
            ns.sep = _SEP_IDX[idx] if 0 <= idx < len(_SEP_IDX) else "none"
        if ns.accent is None and "remove_accents" in cfg:
            ns.accent = bool(cfg["remove_accents"])
        if ns.dup is None and "remove_duplicates" in cfg:
            ns.dup = bool(cfg["remove_duplicates"])
        if ns.case is None and "case" in cfg:
            idx = int(cfg["case"])
            ns.case = _CASE_IDX[idx] if 0 <= idx < len(_CASE_IDX) else "none"
        if ns.ext_mode is None:
            if "extension_mode" in cfg:
                ns.ext_mode = str(cfg["extension_mode"])
            elif "keep_extension" in cfg:
                ns.ext_mode = "keep" if cfg["keep_extension"] else "modify"
        if ns.sidecar_mode is None and "sidecar_mode" in cfg:
            ns.sidecar_mode = bool(cfg["sidecar_mode"])

    if ns.search is None:
        print(
            "error: --search or --saved is required for headless mode",
            file=sys.stderr,
        )
        sys.exit(1)

    # Fill remaining None fields with hardcoded defaults
    if ns.mode is None:
        ns.mode = "pattern"
    if ns.replace is None:
        ns.replace = ""
    if ns.sep is None:
        ns.sep = "none"
    if ns.accent is None:
        ns.accent = False
    if ns.dup is None:
        ns.dup = False
    if ns.case is None:
        ns.case = "none"
    if ns.ext_mode is None:
        ns.ext_mode = "keep"
    if ns.sidecar_mode is None:
        ns.sidecar_mode = False
    if ns.sidecar_mode and ns.ext_mode not in ("keep", "lower", "upper"):
        print(
            "error: --sidecar-mode requires --ext-mode keep, lower, or upper",
            file=sys.stderr,
        )
        sys.exit(1)


# Pattern-mode options that have no meaning with --schema.
_PATTERN_ONLY = {
    "replace": "--replace",
    "mode": "--mode",
    "ext_mode": "--ext-mode",
    "sep": "--sep",
    "case": "--case",
    "accent": "--accent",
    "dup": "--dup",
}


def _resolve_schema_ns(ns: argparse.Namespace) -> None:
    """Check and complete the options of the schema mode (--schema)."""
    for attr, flag in _PATTERN_ONLY.items():
        if getattr(ns, attr) is not None:
            print(f"error: {flag} cannot be used with --schema", file=sys.stderr)
            sys.exit(1)
    if ns.sidecar_mode is False:
        print(
            "error: --no-sidecar-mode cannot be used with --schema",
            file=sys.stderr,
        )
        sys.exit(1)
    from pbrenamer import profiles

    defaults = profiles.get_schema()
    if ns.renumber:
        if ns.dest is not None:
            print(
                "warning: --dest is ignored with --renumber (files are "
                "renumbered in place)",
                file=sys.stderr,
            )
    elif ns.dest is None:
        if not defaults["dest"]:
            print(
                f"error: --schema requires --dest (profile "
                f"'{profiles.current()}' has no destination)",
                file=sys.stderr,
            )
            sys.exit(1)
        ns.dest = os.path.abspath(defaults["dest"])
    ns.sidecar_mode = True
    ns.ext_mode = "lower"
    if ns.video_marker is None:
        ns.video_marker = defaults["video_marker"]
    if ns.video_marker_pos is None:
        ns.video_marker_pos = defaults["video_marker_pos"]
    if ns.fill_gaps is None:
        ns.fill_gaps = defaults["fill_gaps"]
    _rule(ns)  # report an invalid schema before listing the directory


def _rule(ns: argparse.Namespace):
    """Return the planner Rule described by the resolved options *ns*.

    Exits with an error message when the schema (--schema) is invalid.
    """
    from pbrenamer import settings as _settings
    from pbrenamer.core import planner

    if ns.schema is not None:
        from pbrenamer.core import schema

        try:
            return schema.compile_rule(
                ns.schema.split(","),
                dest_root=ns.dest,
                video_marker=ns.video_marker,
                video_marker_pos=ns.video_marker_pos,
                fill_gaps=ns.fill_gaps,
                renumber=ns.renumber,
                sidecar_config=_settings.get_sidecar_config(),
            )
        except schema.SchemaError as exc:
            print(f"error: invalid schema: {exc}", file=sys.stderr)
            sys.exit(1)

    return planner.Rule(
        search=ns.search,
        replace=ns.replace,
        mode=ns.mode,
        ext_mode=ns.ext_mode,
        normalization=_settings.get_extension_normalization_map(),
        spaces=_SEP_MAP[ns.sep] if ns.sep != "none" else None,
        remove_accents=ns.accent,
        remove_duplicates=ns.dup,
        capitalization=_CASE_MAP[ns.case] if ns.case != "none" else None,
        dest_root=ns.dest,
        fill_gaps=ns.fill_gaps,
        renumber=ns.renumber,
        sidecar_config=_settings.get_sidecar_config(),
    )


def _plan(
    entries: list[tuple[str, str]],
    ns: argparse.Namespace,
    followers: dict[str, list[tuple[str, str]]] | None = None,
) -> list[tuple[str, str, str | None]]:
    """Return [(original_path, original_name, new_name_or_None), ...].

    *followers* maps base paths to their sidecars (see
    planner.compute_names); those sidecars get no new name.
    """
    from pbrenamer.core import planner
    from pbrenamer.core import replacement as _repl

    if ns.schema is None:
        try:
            _repl.parse(ns.replace)
        except _repl.ReplacementSyntaxError as exc:
            print(f"error: invalid replacement pattern: {exc}", file=sys.stderr)
            sys.exit(1)

    rule = _rule(ns)
    paths = [path for _name, path in entries]
    results: list[tuple[str, str, str | None]] = []
    for (name, path), entry in zip(
        entries,
        planner.compute_names(rule, paths, followers=followers),
        strict=True,
    ):
        if entry.error is not None:
            _log.debug("%s (file: %r)", entry.error, name)
        results.append((path, name, entry.new_name))
    return results


def _apply_sidecar_grouping(
    plan: list[tuple[str, str, str | None]],
    entries: list[tuple[str, str]],
) -> list[tuple[str, str, str | None]]:
    """Override sidecar rows in *plan* to follow their base file's new stem
    (own suffix unchanged), and drop ambiguous rows (printing a warning).

    Mirrors the GUI's sidecar-mode preview derivation
    (MainWindow._on_preview): each base file's own computed name is left
    untouched; a sidecar's new name is
    ``<base's new stem>.<sidecar's own verbatim suffix>``.
    """
    from pbrenamer import settings as _settings
    from pbrenamer.core import filetools
    from pbrenamer.core import sidecar as _sidecar

    config = _settings.get_sidecar_config()
    result = _sidecar.build_sidecar_groups(entries, config)
    path_to_index = {path: i for i, (path, _name, _new) in enumerate(plan)}

    for sidecar_path, base_path in result.sidecar_of.items():
        s_idx = path_to_index[sidecar_path]
        b_idx = path_to_index[base_path]
        s_path, s_name, _s_new = plan[s_idx]
        _b_path, _b_name, base_new = plan[b_idx]
        if not base_new:
            plan[s_idx] = (s_path, s_name, None)
            continue
        base_stem, _stem_path, _ext = filetools.cut_extension(base_new, base_path)
        suffix = result.sidecar_suffix[sidecar_path]
        plan[s_idx] = (s_path, s_name, f"{base_stem}.{suffix}")

    for path, msg in result.errors.items():
        idx = path_to_index[path]
        p, name, _new = plan[idx]
        plan[idx] = (p, name, None)
        print(f"warning: {name}: {msg}", file=sys.stderr)

    return plan


def _detect_conflicts(
    plan: list[tuple[str, str, str | None]],
) -> set[int]:
    """Return the indices of *plan* whose target is shared or already taken."""
    from pbrenamer.core import filetools

    pairs = {
        idx: (path, os.path.join(os.path.dirname(path), new_name))
        for idx, (path, _name, new_name) in enumerate(plan)
        if new_name is not None and new_name != os.path.basename(path)
    }
    conflicting = set(filetools.find_rename_conflicts(list(pairs.values())))
    return {idx for idx, pair in pairs.items() if pair in conflicting}


def _print_dry_run(
    changes: list[tuple[str, str, str | None]],
    conflict_paths: set[str],
) -> None:
    """Print the shell-equivalent `mv` commands, without touching disk."""
    import shlex

    for path, name, new in changes:
        if path in conflict_paths:
            print(f"# CONFLICT: {name}")
            continue
        new_path = os.path.join(os.path.dirname(path), new)
        print(f"mv -- {shlex.quote(path)} {shlex.quote(new_path)}")

    if conflict_paths:
        print(f"# {len(conflict_paths)} conflict(s): nothing would be renamed.")
    else:
        print(f"# {len(changes)} file(s) would be renamed.")


def _report_conflicts(changes, conflict_paths: set[str]) -> None:
    for _path, name, new in changes:
        if _path in conflict_paths:
            print(f"error: conflict: {name} → {new}", file=sys.stderr)
    print(
        f"error: {len(conflict_paths)} conflict(s): nothing renamed.",
        file=sys.stderr,
    )


def _resolve_selection(
    entries: list[tuple[str, str]],
    ns: argparse.Namespace,
) -> set[str] | None:
    """Return the set of selected paths, or None if --select was not given
    (meaning: no restriction, act on every entry).

    Mirrors the GUI's selection: a glob may match several entries at once,
    and --select may be repeated (equivalent of Ctrl+click, additive). With
    --sidecar-mode active, matching a base file also selects its sidecars,
    and matching a sidecar also selects its base file and every sibling
    sidecar (MainWindow._group_of), using the full directory listing so
    ambiguity detection is unaffected by the selection itself.
    """
    import fnmatch

    if not ns.select:
        return None

    selected: set[str] = set()
    for pattern in ns.select:
        matched = [path for name, path in entries if fnmatch.fnmatch(name, pattern)]
        if not matched:
            print(f"warning: --select {pattern!r} matched no entry", file=sys.stderr)
        selected.update(matched)

    if ns.sidecar_mode and selected:
        from pbrenamer import settings as _settings
        from pbrenamer.core import sidecar as _sidecar

        config = _settings.get_sidecar_config()
        result = _sidecar.build_sidecar_groups(entries, config)
        expanded = set(selected)
        for path in selected:
            base = result.sidecar_of.get(path, path)
            expanded.add(base)
            expanded.update(result.groups.get(base, []))
        selected = expanded

    return selected


def _headless_run(ns: argparse.Namespace) -> None:
    directory = os.path.abspath(ns.directory) if ns.directory else os.getcwd()
    list_mode = _LIST_MAP[ns.list]

    from pbrenamer.core import filetools

    if ns.recurse:
        entries = filetools.get_file_listing_recursive(
            directory, list_mode, ns.filter_glob
        )
    else:
        entries = filetools.get_file_listing(directory, list_mode, ns.filter_glob)

    if not entries:
        print("No entries found.")
        return

    followers: dict[str, list[tuple[str, str]]] = {}
    if ns.sidecar_mode:
        from pbrenamer import settings as _settings
        from pbrenamer.core import sidecar as _sidecar

        groups = _sidecar.build_sidecar_groups(entries, _settings.get_sidecar_config())
        followers = _sidecar.followers(groups)
    plan = _plan(entries, ns, followers)
    if ns.sidecar_mode:
        plan = _apply_sidecar_grouping(plan, entries)

    selection = _resolve_selection(entries, ns)
    if selection is not None:
        plan = [
            (path, name, new if path in selection else None) for path, name, new in plan
        ]

    changes = [
        (path, name, new) for path, name, new in plan if new is not None and new != name
    ]

    if not changes:
        print("No files would be renamed.")
        return

    conflicts = _detect_conflicts(plan)
    conflict_paths = {plan[i][0] for i in conflicts}

    if ns.dry_run:
        _print_dry_run(changes, conflict_paths)
        if conflict_paths:
            sys.exit(1)
        return

    if conflict_paths:
        _report_conflicts(changes, conflict_paths)
        sys.exit(1)

    if ns.confirm:
        # Determine column widths
        col_orig = max(len(name) for _, name, _ in changes)
        col_new = max(len(new) for _, _, new in changes)
        col_orig = max(col_orig, 8)
        col_new = max(col_new, 7)
        sep = f"  {'─' * col_orig}  {'─' * col_new}"
        print(f"  {'Original':<{col_orig}}  {'Renamed':<{col_new}}")
        print(sep)
        for _path, name, new in changes:
            print(f"  {name:<{col_orig}}  {new:<{col_new}}")
        print(sep)
        print(f"{len(changes)} file(s) would be renamed.")

        try:
            answer = input("Proceed? [y/N] ").strip().lower()
        except (
            EOFError,
            KeyboardInterrupt,
        ):  # pragma: no cover — TTY abort; not testable without interactive input
            print("\nAborted.")
            return
        if answer not in ("y", "yes"):
            print("Aborted.")
            return

    pairs = [
        (path, os.path.join(os.path.dirname(path), new)) for path, _name, new in changes
    ]
    try:
        filetools.execute_renames(pairs, prune_root=directory)
    except filetools.RenameError as exc:
        if exc.conflicts:  # pragma: no cover — disk changed since the check
            _report_conflicts(changes, {src for src, _dst in exc.conflicts})
        else:
            print(f"error: {exc}", file=sys.stderr)
            print("error: nothing renamed.", file=sys.stderr)
        sys.exit(1)

    for _path, name, new in changes:
        _log.info("%s → %s", name, new)
        if not ns.confirm:
            print(f"{name} → {new}")
    print(f"{len(changes)} file(s) renamed.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    # Configure logging early so that module-level loggers are usable
    # from the first import. The level is a temporary floor until
    # settings (or a CLI flag) raises/lowers it below.
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=logging.WARNING,
    )

    parser = _build_parser()
    _ns = parser.parse_args()

    if _ns.config_dir is not None:
        from pathlib import Path

        from pbrenamer import settings as _settings

        _settings.configure(Path(_ns.config_dir))

    headless = _ns.search is not None or _ns.saved is not None or _ns.schema is not None
    if _ns.profile is not None:
        from pbrenamer import profiles

        if not profiles.exists(_ns.profile):
            print(f"error: profile '{_ns.profile}' not found", file=sys.stderr)
            sys.exit(2)
        # A headless run never changes the profile the GUI opens next.
        profiles.use(_ns.profile, remember=not headless)

    if getattr(_ns, "auto_update", False):
        from pbrenamer.platform.auto_update import perform_auto_update

        ok, message = perform_auto_update()
        if ok:
            print(message)
        else:
            print(message, file=sys.stderr)
        sys.exit(0 if ok else 1)

    if _ns.install_desktop_entry or _ns.uninstall_desktop_entry:
        if _ns.install_desktop_entry:
            from pbrenamer.platform.desktop import install_desktop_entry as _action
        else:
            from pbrenamer.platform.desktop import uninstall_desktop_entry as _action

        ok, message = _action()
        if ok:
            print(message)
        else:
            print(message, file=sys.stderr)
        sys.exit(0 if ok else 1)

    if _ns.help_search or _ns.help_replace:
        # Help export — no Qt needed; NullTranslations returns msgids as-is
        import gettext

        gettext.NullTranslations().install()
        from pbrenamer.ui.pattern_help import replace_html, search_html

        if _ns.help_search:
            sys.stdout.write(search_html())
        if _ns.help_replace:
            sys.stdout.write(replace_html())
        return

    if headless:
        if _ns.log_level:
            logging.getLogger().setLevel(_ns.log_level)
        # Core messages (schema errors, sidecar ambiguities) use _(); the
        # headless output is in English.
        import gettext

        gettext.NullTranslations().install()
        _resolve_ns(_ns)
        _headless_run(_ns)
        return

    _gui_main(_ns)  # pragma: no cover — GUI mode; not invoked by tests


def _load_bundled_fonts(app: object) -> None:  # pragma: no cover
    """Register bundled fonts into Qt's font database (frozen builds only).

    In a PyInstaller onefile build, fontconfig uses paths hardcoded at build
    time that don't exist on the target machine.  QFontDatabase.addApplicationFont
    bypasses fontconfig entirely and guarantees that the bundled fonts (Ubuntu,
    DejaVu, …) are available regardless of the host fontconfig configuration.
    """
    if not getattr(sys, "frozen", False):
        return
    from pathlib import Path

    from PySide6.QtGui import QFont, QFontDatabase

    fonts_dir = Path(sys._MEIPASS) / "fonts"  # type: ignore[attr-defined]
    if not fonts_dir.is_dir():
        return

    loaded: set[str] = set()
    for ttf in sorted(fonts_dir.glob("*.ttf")):
        fid = QFontDatabase.addApplicationFont(str(ttf))
        if fid >= 0:
            loaded.update(QFontDatabase.applicationFontFamilies(fid))

    # Set Ubuntu as the default application font so the bundle renders
    # consistently on any machine, regardless of whether fontconfig finds
    # the system config.  The bundled libfontconfig.so has its default config
    # path hardcoded to the build machine's conda prefix, which does not exist
    # on target machines, so font selection cannot rely on fontconfig.
    if "Ubuntu" in loaded:
        current = app.font()  # type: ignore[union-attr]
        app.setFont(  # type: ignore[union-attr]
            QFont("Ubuntu", current.pointSize() if current.pointSize() > 0 else 10)
        )


def _gui_main(_ns):  # pragma: no cover
    # GUI mode — only reached when none of --search, --saved and --schema
    # is given.
    # Tests never enter this path: they invoke _headless_run() directly
    # and rely on pytest-qt for the QApplication instance.
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from pbrenamer import __version__
    from pbrenamer.resources import path as _resource

    app = QApplication([sys.argv[0]] + _ns.qt_args)
    _load_bundled_fonts(app)
    app.setApplicationName("PBRenamer")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("ppoilbarbe")
    app.setWindowIcon(QIcon(_resource("pbrenamer.svg")))

    # i18n must be set up before any window is created so that
    # retranslateUi() picks up the correct translator.
    from pbrenamer import i18n, settings

    i18n.setup(app)

    # CLI flag overrides the saved preference; None falls back to the preference.
    settings.apply_log_level(_ns.log_level)

    f = app.font()
    from PySide6.QtGui import QFontMetrics

    fm = QFontMetrics(f)
    _log.debug(
        "Application font: %s %dpt — ascent %dpx height %dpx",
        f.family(),
        f.pointSize(),
        fm.ascent(),
        fm.height(),
    )
    _log.info("PBRenamer %s starting", __version__)
    _log.debug(
        "Effective log level: %s", logging.getLevelName(logging.getLogger().level)
    )

    from pbrenamer.ui.main_window import MainWindow

    start_dir = os.path.abspath(_ns.directory) if _ns.directory else None
    _log.debug("Start directory: %s", start_dir or os.getcwd())
    window = MainWindow(start_dir=start_dir)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover — standard script guard
    main()
