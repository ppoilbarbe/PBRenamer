"""UI layout for the About dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
)


class Ui_AboutDialog:
    def setupUi(self, dialog):
        dialog.setMinimumWidth(360)
        dialog.resize(400, 290)

        layout = QVBoxLayout(dialog)

        # ── Header: 64×64 icon on the left, app name + version on the right ──
        header = QHBoxLayout()

        self.lblIcon = QLabel(dialog)
        self.lblIcon.setFixedSize(64, 64)
        self.lblIcon.setAlignment(Qt.AlignCenter)
        header.addWidget(self.lblIcon)

        name_col = QVBoxLayout()
        self.lblAppName = QLabel('<b style="font-size: 16pt;">PBRenamer</b>', dialog)
        name_col.addWidget(self.lblAppName)
        self.lblVersion = QLabel(dialog)
        self.lblVersion.setToolTip(_("Application version"))
        name_col.addWidget(self.lblVersion)
        name_col.addItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )
        header.addLayout(name_col)

        layout.addLayout(header)

        # ── Visual separator ───────────────────────────────────────────────────
        separator = QFrame(dialog)
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # ── Informational labels ───────────────────────────────────────────────
        self.lblDescription = QLabel(
            _("A graphical batch file renaming utility."), dialog
        )
        self.lblDescription.setWordWrap(True)
        layout.addWidget(self.lblDescription)

        self.lblAuthors = QLabel(dialog)
        self.lblAuthors.setTextFormat(Qt.RichText)
        self.lblAuthors.setOpenExternalLinks(True)
        self.lblAuthors.setWordWrap(True)
        layout.addWidget(self.lblAuthors)

        self.lblLicense = QLabel(_("License: GPLv3"), dialog)
        layout.addWidget(self.lblLicense)

        self.lblPythonVersion = QLabel(dialog)
        layout.addWidget(self.lblPythonVersion)

        self.lblPySideVersion = QLabel(dialog)
        layout.addWidget(self.lblPySideVersion)

        # ── Close button ───────────────────────────────────────────────────────
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Close, dialog)
        self.buttonBox.rejected.connect(dialog.reject)
        layout.addWidget(self.buttonBox)

        dialog.setWindowTitle(_("About PBRenamer"))
