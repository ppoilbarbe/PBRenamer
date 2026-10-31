"""UI layout for the History dialog (pattern and schema field histories)."""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pbrenamer.ui.widgets import WhitespaceLineEdit


class Ui_HistoryDialog:
    def setupUi(self, dialog):
        dialog.setMinimumSize(620, 360)
        dialog.resize(640, 400)
        dialog.setWindowTitle(_("History"))

        layout = QVBoxLayout(dialog)

        # ── Tabs: patterns (Search | Replace side by side), then one tab per
        # schema field, added by HistoryDialog ─────────────────────────────────
        self.tabs = QTabWidget(dialog)
        patterns = QWidget(self.tabs)
        panels = QHBoxLayout(patterns)
        panels.addWidget(self._make_search_panel(patterns), 1)
        panels.addWidget(self._make_replace_panel(patterns), 1)
        self.tabs.addTab(patterns, _("Patterns"))
        layout.addWidget(self.tabs)

        # ── Close button ───────────────────────────────────────────────────────
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Close, dialog)
        self.buttonBox.rejected.connect(dialog.reject)
        layout.addWidget(self.buttonBox)

    # ── Search panel ──────────────────────────────────────────────────────────

    def _make_search_panel(self, dialog):
        grp = QGroupBox(_("Search"), dialog)
        grp_layout = QVBoxLayout(grp)

        self.lstSearch = QListWidget(grp)
        self.lstSearch.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.lstSearch.setToolTip(_("Search pattern history"))
        self.lstSearch.setStatusTip(_("Select one or more entries to remove them"))
        grp_layout.addWidget(self.lstSearch)

        # Input row: pattern field + mode radio buttons + Add button
        add_row = QHBoxLayout()
        self.edtSearch = WhitespaceLineEdit(grp)
        self.edtSearch.setPlaceholderText(_("Pattern…"))
        self.edtSearch.setToolTip(_("New search pattern to add"))
        add_row.addWidget(self.edtSearch)

        self.cmbSearchMode = QComboBox(grp)
        self.cmbSearchMode.addItem(_("pat"), userData="pattern")
        self.cmbSearchMode.addItem(_("RE"), userData="regex")
        self.cmbSearchMode.addItem(_("txt"), userData="plain")
        self.cmbSearchMode.setToolTip(
            _("Search mode: pattern tokens, regex, or plain text")
        )
        add_row.addWidget(self.cmbSearchMode)

        self.btnAddSearch = QPushButton(_("Add"), grp)
        self.btnAddSearch.setToolTip(_("Add this pattern to the search history"))
        add_row.addWidget(self.btnAddSearch)
        grp_layout.addLayout(add_row)

        # Actions row: Remove + Clear + spacer
        actions_row = QHBoxLayout()
        self.btnRemoveSearch = QPushButton(_("Remove"), grp)
        self.btnRemoveSearch.setToolTip(_("Remove selected entries"))
        self.btnRemoveSearch.setStatusTip(
            _("Delete the selected search history entries")
        )
        actions_row.addWidget(self.btnRemoveSearch)

        self.btnClearSearch = QPushButton(_("Clear all"), grp)
        self.btnClearSearch.setToolTip(_("Remove all search history entries"))
        self.btnClearSearch.setStatusTip(_("Delete the entire search pattern history"))
        actions_row.addWidget(self.btnClearSearch)

        actions_row.addItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )
        grp_layout.addLayout(actions_row)

        return grp

    # ── Replace panel ─────────────────────────────────────────────────────────

    def _make_replace_panel(self, dialog):
        grp = QGroupBox(_("Replace"), dialog)
        grp_layout = QVBoxLayout(grp)

        self.lstReplace = QListWidget(grp)
        self.lstReplace.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.lstReplace.setToolTip(_("Replacement pattern history"))
        self.lstReplace.setStatusTip(_("Select one or more entries to remove them"))
        grp_layout.addWidget(self.lstReplace)

        # Input row: pattern field + Add button
        add_row = QHBoxLayout()
        self.edtReplace = WhitespaceLineEdit(grp)
        self.edtReplace.setPlaceholderText(_("Pattern…"))
        self.edtReplace.setToolTip(_("New replacement pattern to add"))
        add_row.addWidget(self.edtReplace)

        self.btnAddReplace = QPushButton(_("Add"), grp)
        self.btnAddReplace.setToolTip(_("Add this pattern to the replacement history"))
        add_row.addWidget(self.btnAddReplace)
        grp_layout.addLayout(add_row)

        # Actions row: Remove + Clear + spacer
        actions_row = QHBoxLayout()
        self.btnRemoveReplace = QPushButton(_("Remove"), grp)
        self.btnRemoveReplace.setToolTip(_("Remove selected entries"))
        self.btnRemoveReplace.setStatusTip(
            _("Delete the selected replacement history entries")
        )
        actions_row.addWidget(self.btnRemoveReplace)

        self.btnClearReplace = QPushButton(_("Clear all"), grp)
        self.btnClearReplace.setToolTip(_("Remove all replacement history entries"))
        self.btnClearReplace.setStatusTip(
            _("Delete the entire replacement pattern history")
        )
        actions_row.addWidget(self.btnClearReplace)

        actions_row.addItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )
        grp_layout.addLayout(actions_row)

        return grp
