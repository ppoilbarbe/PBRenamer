"""Entry point — run as `python -m pbrenamer` or `pbrenamer`."""

import sys


def main() -> None:
    from PySide6.QtWidgets import QApplication

    from pbrenamer.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("PBRenamer")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("ppoilbarbe")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
