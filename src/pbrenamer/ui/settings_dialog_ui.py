"""UI layout for the Settings dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class Ui_SettingsDialog:
    def setupUi(self, dialog):
        dialog.setMinimumSize(420, 440)
        dialog.resize(460, 480)
        dialog.setWindowTitle(_("Settings"))

        layout = QVBoxLayout(dialog)

        self.tabs = QTabWidget(dialog)
        self.tabs.addTab(self._make_general_tab(dialog), _("General"))
        self.tabs.addTab(self._make_extension_tab(dialog), _("Extension Normalization"))
        layout.addWidget(self.tabs)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            dialog,
        )
        self.buttonBox.rejected.connect(dialog.reject)
        layout.addWidget(self.buttonBox)

    # ── General tab ───────────────────────────────────────────────────────────

    def _make_general_tab(self, dialog):
        tab = QWidget(dialog)
        layout = QVBoxLayout(tab)

        # Top-level options (language, log level)
        form = QFormLayout()

        self.cmbLanguage = QComboBox(tab)
        self.cmbLanguage.setToolTip(_("Select the interface language"))
        form.addRow(_("Language:"), self.cmbLanguage)

        self.cmbLogLevel = QComboBox(tab)
        self.cmbLogLevel.setToolTip(_("Set the application logging verbosity"))
        form.addRow(_("Log level:"), self.cmbLogLevel)

        layout.addLayout(form)

        # Behaviour group
        grp = QGroupBox(_("Behaviour"), tab)
        grp_layout = QVBoxLayout(grp)

        self.chkRestoreLastDir = QCheckBox(_("Restore last opened directory"), grp)
        self.chkRestoreLastDir.setToolTip(
            _(
                "On startup, reopen the directory that was active"
                " in the previous session"
            )
        )
        grp_layout.addWidget(self.chkRestoreLastDir)

        self.chkRestoreToolbarState = QCheckBox(_("Restore toolbar state"), grp)
        self.chkRestoreToolbarState.setToolTip(
            _(
                "On startup, restore the toolbar settings from the previous session"
                " (display mode, recursive, extension mode, auto-preview, filter)"
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

        # Restart notice
        lbl_notice = QLabel(
            _("A restart is required for the language change to take effect."), tab
        )
        lbl_notice.setWordWrap(True)
        layout.addWidget(lbl_notice)

        layout.addStretch()
        return tab

    # ── Extension normalization tab ──────────────────────────────────────────

    def _make_extension_tab(self, dialog):
        tab = QWidget(dialog)
        layout = QVBoxLayout(tab)

        lbl_intro = QLabel(
            _(
                "Extensions mapped here are applied by the"
                ' "Normalize extension" mode. Matching is'
                " case-insensitive; extensions not listed are left unchanged."
            ),
            tab,
        )
        lbl_intro.setWordWrap(True)
        layout.addWidget(lbl_intro)

        self.lstExtensionPairs = QListWidget(tab)
        self.lstExtensionPairs.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.lstExtensionPairs.setToolTip(_("Extension normalization table"))
        self.lstExtensionPairs.setStatusTip(
            _("Select one or more entries to remove them")
        )
        layout.addWidget(self.lstExtensionPairs)

        # Input row: from-extension + arrow + to-extension + Add button
        add_row = QHBoxLayout()
        self.edtExtensionFrom = QLineEdit(tab)
        self.edtExtensionFrom.setPlaceholderText("jpeg")
        self.edtExtensionFrom.setToolTip(_("Extension to match (without the dot)"))
        add_row.addWidget(self.edtExtensionFrom)

        add_row.addWidget(QLabel("→", tab))

        self.edtExtensionTo = QLineEdit(tab)
        self.edtExtensionTo.setPlaceholderText("jpg")
        self.edtExtensionTo.setToolTip(_("Replacement extension (without the dot)"))
        add_row.addWidget(self.edtExtensionTo)

        self.btnExtensionAdd = QPushButton(_("Add"), tab)
        self.btnExtensionAdd.setToolTip(
            _("Add this mapping to the normalization table")
        )
        add_row.addWidget(self.btnExtensionAdd)
        layout.addLayout(add_row)

        # Actions row: Remove + Clear + spacer
        actions_row = QHBoxLayout()
        self.btnExtensionRemove = QPushButton(_("Remove"), tab)
        self.btnExtensionRemove.setToolTip(_("Remove selected entries"))
        self.btnExtensionRemove.setStatusTip(
            _("Delete the selected normalization entries")
        )
        actions_row.addWidget(self.btnExtensionRemove)

        self.btnExtensionClear = QPushButton(_("Clear all"), tab)
        self.btnExtensionClear.setToolTip(_("Remove all normalization entries"))
        self.btnExtensionClear.setStatusTip(_("Delete the entire normalization table"))
        actions_row.addWidget(self.btnExtensionClear)

        actions_row.addItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )
        layout.addLayout(actions_row)

        return tab
