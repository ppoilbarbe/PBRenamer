"""Entry point — run as `python -m pbrenamer` or `pbrenamer`."""

import argparse
import logging
import os
import sys
from collections import defaultdict

_log = logging.getLogger(__name__)

# Map --case value → replace_capitalization() mode index
_CASE_MAP = {"upper": 0, "lower": 1, "capitalize": 2, "title": 3}

# Map --list value → get_file_listing() mode index
_LIST_MAP = {"files": 0, "dirs": 1, "all": 2}


def _build_parser() -> argparse.ArgumentParser:
    from pbrenamer import __version__

    parser = argparse.ArgumentParser(
        prog="pbrenamer",
        description="PBRenamer — graphical batch file renaming utility.",
        epilog=(
            "Headless mode is activated when --search is provided; "
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
        "These options activate headless (no GUI) mode when --search is given.",
    )
    rename_group.add_argument(
        "-s",
        "--search",
        metavar="TEXT",
        default=None,
        help="Search pattern/expression — activates headless mode",
    )
    rename_group.add_argument(
        "-r",
        "--replace",
        metavar="TEXT",
        default="",
        help="Replacement string (default: empty string)",
    )
    rename_group.add_argument(
        "--mode",
        choices=["pattern", "regex", "plain"],
        default="pattern",
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
        "--keep-ext",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Preserve file extension during rename (default: --keep-ext)",
    )
    rename_group.add_argument(
        "--filter",
        metavar="GLOB",
        default=None,
        dest="filter_glob",
        help="Glob pattern to restrict the file listing (e.g. '*.jpg')",
    )
    rename_group.add_argument(
        "--accent",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Strip diacritics from result names (default: --no-accent)",
    )
    rename_group.add_argument(
        "--dup",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Collapse consecutive duplicate separators (default: --no-dup)",
    )
    rename_group.add_argument(
        "--case",
        choices=["none", "upper", "lower", "capitalize", "title"],
        default="none",
        metavar="{none,upper,lower,capitalize,title}",
        help="Capitalisation applied after rename (default: none)",
    )
    rename_group.add_argument(
        "--confirm",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Preview changes and ask for confirmation (default: --no-confirm)",
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

    return parser


# ---------------------------------------------------------------------------
# Headless mode
# ---------------------------------------------------------------------------


def _apply_postproc(
    name: str,
    path: str,
    *,
    accent: bool,
    dup: bool,
    case: str,
) -> str:
    from pbrenamer.core import filetools

    if accent:
        name, _ = filetools.replace_accents(name, path)
    if dup:
        name, _ = filetools.replace_duplicated(name, path)
    if case != "none":
        name, _ = filetools.replace_capitalization(name, path, _CASE_MAP[case])
    return name


def _do_rename(
    use_regex: bool,
    use_plain: bool,
    stem: str,
    orig_path: str,
    search: str,
    replace: str,
    counter: int,
    *,
    newnum: int | None = None,
) -> tuple[str | None, str | None]:
    from pbrenamer.core import filetools

    if use_regex:
        return filetools.rename_using_regex(
            stem, orig_path, search, replace, newnum=newnum
        )
    if use_plain:
        return filetools.rename_using_plain_text(
            stem, orig_path, search, replace, newnum=newnum
        )
    return filetools.rename_using_patterns(
        stem, orig_path, search, replace, counter, newnum=newnum
    )


def _plan(
    entries: list[tuple[str, str]],
    ns: argparse.Namespace,
) -> list[tuple[str, str, str | None]]:
    """Return [(original_path, original_name, new_name_or_None), ...]."""
    from pbrenamer.core import filetools
    from pbrenamer.core import replacement as _repl

    use_regex = ns.mode == "regex"
    use_plain = ns.mode == "plain"

    # Pre-scan for {newnum} in the replacement template
    newnum_state: _repl.NewNumState | None = None
    try:
        segments = _repl.parse(ns.replace)
        for seg in segments:
            if isinstance(seg, _repl.FieldSegment) and seg.name == "newnum":
                start = 1
                if seg.default is not None:
                    try:
                        start = int(seg.default)
                    except ValueError:
                        pass
                newnum_state = _repl.NewNumState(start)
                break
    except _repl.ReplacementSyntaxError as exc:
        print(f"error: invalid replacement pattern: {exc}", file=sys.stderr)
        sys.exit(1)

    results: list[tuple[str, str, str | None]] = []

    for counter, (name, path) in enumerate(entries, start=1):
        if ns.keep_ext:
            stem, stem_path, ext = filetools.cut_extension(name, path)
        else:
            stem, stem_path, ext = name, path, ""

        new_name: str | None = None

        if newnum_state is not None:
            dir_path = os.path.dirname(path)
            k = newnum_state.current
            while True:
                try:
                    raw, _ = _do_rename(
                        use_regex,
                        use_plain,
                        stem,
                        path,
                        ns.search,
                        ns.replace,
                        counter,
                        newnum=k,
                    )
                except _repl.FieldResolutionError as err:
                    _log.debug("Field %r unavailable for %r", err.field, name)
                    break
                if raw is None:
                    break
                processed = _apply_postproc(
                    raw, stem_path, accent=ns.accent, dup=ns.dup, case=ns.case
                )
                candidate = filetools.add_extension(processed, stem_path, ext)[0]
                cand_path = os.path.join(dir_path, candidate)
                from pbrenamer.platform.fs import same_file_path

                if candidate not in newnum_state.reserved and (
                    not os.path.exists(cand_path)
                    or same_file_path(cand_path, path, dir_path)
                ):
                    newnum_state.reserved.add(candidate)
                    newnum_state.current = k + 1
                    new_name = candidate
                    break
                k += 1
        else:
            try:
                raw, _ = _do_rename(
                    use_regex, use_plain, stem, path, ns.search, ns.replace, counter
                )
            except _repl.FieldResolutionError as err:
                _log.debug("Field %r unavailable for %r", err.field, name)
                raw = None
            if raw is not None:
                processed = _apply_postproc(
                    raw, stem_path, accent=ns.accent, dup=ns.dup, case=ns.case
                )
                new_name = filetools.add_extension(processed, stem_path, ext)[0]

        results.append((path, name, new_name))

    return results


def _detect_conflicts(
    plan: list[tuple[str, str, str | None]],
) -> set[int]:
    from pbrenamer.platform.fs import conflict_key, same_file_path

    conflicts: set[int] = set()
    target_map: dict[str, list[int]] = defaultdict(list)

    for idx, (path, _name, new_name) in enumerate(plan):
        if new_name is None or new_name == os.path.basename(path):
            continue
        parent = os.path.dirname(path)
        target = os.path.join(parent, new_name)
        target_map[conflict_key(target, parent)].append(idx)

    for indices in target_map.values():
        if len(indices) > 1:
            conflicts.update(indices)

    for idx, (path, _name, new_name) in enumerate(plan):
        if new_name is None:
            continue
        parent = os.path.dirname(path)
        target = os.path.join(parent, new_name)
        if not same_file_path(target, path, parent) and os.path.exists(target):
            conflicts.add(idx)

    return conflicts


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

    plan = _plan(entries, ns)
    changes = [
        (path, name, new) for path, name, new in plan if new is not None and new != name
    ]

    if not changes:
        print("No files would be renamed.")
        return

    conflicts = _detect_conflicts(plan)

    if ns.confirm:
        # Determine column widths
        col_orig = max(len(name) for _, name, _ in changes)
        col_new = max(len(new) for _, _, new in changes)
        col_orig = max(col_orig, 8)
        col_new = max(col_new, 7)
        sep = f"  {'─' * col_orig}  {'─' * col_new}"
        print(f"  {'Original':<{col_orig}}  {'Renamed':<{col_new}}")
        print(sep)
        for path, name, new in changes:
            idx = next(i for i, (p, _, _) in enumerate(plan) if p == path)
            flag = " [CONFLICT]" if idx in conflicts else ""
            print(f"  {name:<{col_orig}}  {new:<{col_new}}{flag}")
        print(sep)
        print(f"{len(changes)} file(s) would be renamed.", end="")
        if conflicts:
            print(
                f"  {len(conflicts)} conflict(s) detected — those will be skipped.",
                end="",
            )
        print()

        try:
            answer = input("Proceed? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return
        if answer not in ("y", "yes"):
            print("Aborted.")
            return

    conflict_paths = {plan[i][0] for i in conflicts}
    done = 0
    errors: list[str] = []

    for path, name, new in changes:
        if path in conflict_paths:
            _log.warning("Skipping conflict: %s", name)
            continue
        new_path = os.path.join(os.path.dirname(path), new)
        ok, err = filetools.rename_file(path, new_path)
        if ok:
            done += 1
            _log.info("%s → %s", name, new)
            if not ns.confirm:
                print(f"{name} → {new}")
        else:
            errors.append(f"{name}: {err}")

    if done:
        print(f"{done} file(s) renamed.")
    for err in errors:
        print(f"error: {err}", file=sys.stderr)
    if errors:
        sys.exit(1)


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

    # parse_known_args leaves Qt-specific flags (--style, --platform, …)
    # untouched so they can be forwarded to QApplication.
    _ns, qt_argv = _build_parser().parse_known_args()

    if _ns.search is not None:
        # Headless mode — no Qt needed
        if _ns.log_level:
            logging.getLogger().setLevel(_ns.log_level)
        _headless_run(_ns)
        return

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from pbrenamer import __version__
    from pbrenamer.resources import path as _resource

    app = QApplication([sys.argv[0]] + qt_argv)
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

    _log.info("PBRenamer %s starting", __version__)
    _log.debug(
        "Effective log level: %s", logging.getLevelName(logging.getLogger().level)
    )

    from pbrenamer.ui.main_window import MainWindow

    start_dir = os.path.abspath(_ns.directory) if _ns.directory else os.getcwd()
    _log.debug("Start directory: %s", start_dir)
    window = MainWindow(start_dir=start_dir)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
