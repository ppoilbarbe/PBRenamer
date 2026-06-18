"""UI layout for the Settings dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QVBoxLayout,
)


class Ui_SettingsDialog:
    def setupUi(self, dialog):
        dialog.setMinimumWidth(340)
        dialog.resize(380, 290)
        dialog.setWindowTitle(_("Settings"))

        layout = QVBoxLayout(dialog)

        # ── Top-level options (language, log level) ────────────────────────────
        form = QFormLayout()

        self.cmbLanguage = QComboBox(dialog)
        self.cmbLanguage.setToolTip(_("Select the interface language"))
        form.addRow(_("Language:"), self.cmbLanguage)

        self.cmbLogLevel = QComboBox(dialog)
        self.cmbLogLevel.setToolTip(_("Set the application logging verbosity"))
        form.addRow(_("Log level:"), self.cmbLogLevel)

        layout.addLayout(form)

        # ── Behaviour group ────────────────────────────────────────────────────
        grp = QGroupBox(_("Behaviour"), dialog)
        grp_layout = QVBoxLayout(grp)

        self.chkRestoreLastDir = QCheckBox(_("Restore last opened directory"), grp)
        self.chkRestoreLastDir.setToolTip(
            _(
                "On startup, reopen the directory that was active in the previous session"
            )
        )
        grp_layout.addWidget(self.chkRestoreLastDir)

        self.chkRestoreToolbarState = QCheckBox(_("Restore toolbar state"), grp)
        self.chkRestoreToolbarState.setToolTip(
            _(
                "On startup, restore the toolbar settings from the previous session"
                " (display mode, recursive, keep extension, auto-preview, filter)"
            )
        )
        grp_layout.addWidget(self.chkRestoreToolbarState)

        # Auto-preview delay (label + spinbox + horizontal spacer)
        delay_row = QHBoxLayout()
        delay_tip = _(
            "Debounce delay before the preview refreshes"
            " after a search or replacement pattern change (ms)"
        )
        lbl_delay = QLabel(_("Auto-preview delay:"), grp)
        lbl_delay.setToolTip(delay_tip)
        delay_row.addWidget(lbl_delay)
        self.spnPreviewDelay = QSpinBox(grp)
        self.spnPreviewDelay.setRange(100, 1000)
        self.spnPreviewDelay.setSingleStep(100)
        self.spnPreviewDelay.setValue(500)
        self.spnPreviewDelay.setSuffix(_(" ms"))
        self.spnPreviewDelay.setToolTip(delay_tip)
        delay_row.addWidget(self.spnPreviewDelay)
        delay_row.addItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )
        grp_layout.addLayout(delay_row)

        layout.addWidget(grp)

        # ── Restart notice + buttons ───────────────────────────────────────────
        lbl_notice = QLabel(
            _("A restart is required for the language change to take effect."), dialog
        )
        lbl_notice.setWordWrap(True)
        layout.addWidget(lbl_notice)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            dialog,
        )
        self.buttonBox.rejected.connect(dialog.reject)
        layout.addWidget(self.buttonBox)
