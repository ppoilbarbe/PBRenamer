"""Main application window."""

from PySide6.QtWidgets import QFileDialog, QMainWindow

from pbrenamer.ui.main_window_ui import Ui_MainWindow


class MainWindow(QMainWindow):
    """Top-level window for PBRenamer."""

    def __init__(self) -> None:
        super().__init__()
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)
        self._connect_signals()

    def _connect_signals(self) -> None:
        self._ui.btnOpen.clicked.connect(self._on_open)

    def _on_open(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select folder")
        if folder:
            self.statusBar().showMessage(f"Folder: {folder}")
            self._ui.btnRename.setEnabled(True)
