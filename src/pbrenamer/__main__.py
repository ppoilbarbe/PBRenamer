"""Entry point — run as `python -m pbrenamer` or `pbrenamer`."""

import argparse
import logging
import os
import sys

_log = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    from pbrenamer import __version__

    parser = argparse.ArgumentParser(
        prog="pbrenamer",
        description="PBRenamer — graphical batch file renaming utility.",
        epilog="Qt platform options (--style, --platform, …) are forwarded to Qt.",
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
        help="Starting directory (default: current working directory)",
    )

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
