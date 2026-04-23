"""Entry point — run as `python -m pbrenamer` or `pbrenamer`."""

import argparse
import sys


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
    return parser


def main() -> None:
    # parse_known_args leaves Qt-specific flags (--style, --platform, …)
    # untouched so they can be forwarded to QApplication.
    _ns, qt_argv = _build_parser().parse_known_args()

    from PySide6.QtWidgets import QApplication

    from pbrenamer import __version__

    app = QApplication([sys.argv[0]] + qt_argv)
    app.setApplicationName("PBRenamer")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("ppoilbarbe")

    # i18n must be set up before any window is created so that
    # retranslateUi() picks up the correct translator.
    from pbrenamer import i18n

    i18n.setup(app)

    from pbrenamer.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
