"""Main application window."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    """Top-level window for PBRenamer."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PBRenamer")
        self.setMinimumSize(900, 600)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        # Toolbar row
        toolbar = QHBoxLayout()
        self._btn_open = QPushButton("Open folder…")
        self._btn_rename = QPushButton("Rename")
        self._btn_rename.setEnabled(False)
        toolbar.addWidget(self._btn_open)
        toolbar.addStretch()
        toolbar.addWidget(self._btn_rename)
        layout.addLayout(toolbar)

        # Placeholder — replace with QTreeView / QTableView
        placeholder = QLabel("Select a folder to begin.", alignment=Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: gray; font-size: 14px;")
        layout.addWidget(placeholder, stretch=1)

        self.setStatusBar(QStatusBar())

    def _connect_signals(self) -> None:
        self._btn_open.clicked.connect(self._on_open)

    def _on_open(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select folder")
        if folder:
            self.statusBar().showMessage(f"Folder: {folder}")
            self._btn_rename.setEnabled(True)
