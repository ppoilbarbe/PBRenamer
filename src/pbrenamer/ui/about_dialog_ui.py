"""UI layout for the About dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
)


class Ui_AboutDialog:
    def setupUi(self, dialog):
        dialog.setMinimumWidth(380)
        dialog.resize(420, 320)
        dialog.setWindowTitle(_("About PBRenamer"))

        layout = QVBoxLayout(dialog)

        content = QHBoxLayout()

        # ── Icon column (left) — icon pinned to the top, rest is spacer ────────
        icon_col = QVBoxLayout()
        self.lblIcon = QLabel(dialog)
        self.lblIcon.setFixedSize(64, 64)
        self.lblIcon.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.lblIcon.setScaledContents(True)
        icon_col.addWidget(self.lblIcon)
        icon_col.addItem(
            QSpacerItem(
                20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
        )
        content.addLayout(icon_col)

        # ── Framed info panel (right) ───────────────────────────────────────────
        frame = QFrame(dialog)
        frame.setFrameShape(QFrame.Panel)
        frame.setFrameShadow(QFrame.Raised)
        frame.setLineWidth(3)
        frame_layout = QVBoxLayout(frame)

        frame_layout.addItem(
            QSpacerItem(
                20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
        )

        self.lblAppName = QLabel('<b style="font-size: 14pt;">PBRenamer</b>', frame)
        self.lblAppName.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.lblAppName)

        self.lblVersion = QLabel(frame)
        self.lblVersion.setToolTip(_("Application version"))
        self.lblVersion.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.lblVersion)

        self.lblAuthors = QLabel(frame)
        self.lblAuthors.setTextFormat(Qt.RichText)
        self.lblAuthors.setOpenExternalLinks(True)
        self.lblAuthors.setWordWrap(True)
        self.lblAuthors.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.lblAuthors)

        self.lblDescription = QLabel(
            _("A graphical batch file renaming utility."), frame
        )
        self.lblDescription.setWordWrap(True)
        self.lblDescription.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.lblDescription)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)

        self.lblLicense = QLabel(_("GPLv3"), frame)
        form.addRow(_("License:"), self.lblLicense)

        self.lblPythonVersion = QLabel(frame)
        form.addRow(_("Python version:"), self.lblPythonVersion)

        self.lblPySideVersion = QLabel(frame)
        form.addRow(_("PySide6 version:"), self.lblPySideVersion)

        frame_layout.addLayout(form)

        frame_layout.addItem(
            QSpacerItem(
                20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
        )

        content.addWidget(frame)

        layout.addLayout(content)

        # ── Close button, centered ──────────────────────────────────────────────
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Close, dialog)
        self.buttonBox.setCenterButtons(True)
        self.buttonBox.rejected.connect(dialog.reject)
        layout.addWidget(self.buttonBox)
