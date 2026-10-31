"""UI layout for the main application window."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pbrenamer.resources import path as _resource
from pbrenamer.ui.dnd_widgets import DirectoryTreeView, FileListWidget


class Ui_MainWindow:
    def setupUi(self, window):
        window.setMinimumSize(900, 600)
        window.resize(1100, 720)
        window.setWindowTitle("PBRenamer")

        self._setup_actions(window)
        self._setup_image_actions(window)
        self._setup_central_widget(window)
        self._setup_statusbar(window)
        self._setup_menubar(window)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _setup_actions(self, window):
        self.actionOpenFolder = QAction(
            QIcon(_resource("open.svg")), _("Open folder…"), window
        )
        self.actionOpenFolder.setShortcut(QKeySequence("Ctrl+O"))
        self.actionOpenFolder.setToolTip(_("Open a folder"))
        self.actionOpenFolder.setStatusTip(
            _("Open a directory chooser and navigate the tree to the selected folder")
        )

        self.actionQuit = QAction(QIcon(_resource("quit.svg")), _("Quit"), window)
        self.actionQuit.setShortcut(QKeySequence("Ctrl+Q"))
        self.actionQuit.setToolTip(_("Quit PBRenamer"))
        self.actionQuit.setStatusTip(_("Exit the application"))

        self.actionHistory = QAction(
            QIcon(_resource("history.svg")), _("History…"), window
        )
        self.actionHistory.setToolTip(_("Manage pattern history"))
        self.actionHistory.setStatusTip(
            _("Add or remove entries from the search and replacement pattern history")
        )

        self.actionSettings = QAction(
            QIcon(_resource("configure.svg")), _("Settings…"), window
        )
        self.actionSettings.setToolTip(_("Open settings"))
        self.actionSettings.setStatusTip(_("Configure language and other preferences"))

        self.actionSidecarFiles = QAction(
            QIcon(_resource("sidecars.svg")), _("Sidecar Files…"), window
        )
        self.actionSidecarFiles.setToolTip(_("Configure sidecar file categories"))
        self.actionSidecarFiles.setStatusTip(
            _("Configure base-file extensions and sidecar suffixes for each category")
        )

        self.actionAbout = QAction(
            QIcon(_resource("help-about.svg")), _("About PBRenamer"), window
        )
        self.actionAbout.setToolTip(_("About this application"))
        self.actionAbout.setStatusTip(_("Show version and license information"))

        self.actionKeyboardHelp = QAction(
            QIcon(_resource("help-keyboard-shortcuts.svg")),
            _("Keyboard and mouse shortcuts…"),
            window,
        )
        self.actionKeyboardHelp.setShortcut(QKeySequence("F1"))
        self.actionKeyboardHelp.setToolTip(_("Show the keyboard and mouse shortcuts"))
        self.actionKeyboardHelp.setStatusTip(
            _("List the keyboard and mouse shortcuts of the main window and viewer")
        )

        self.actionUserGuide = QAction(
            QIcon(_resource("help-user-manual.svg")), _("User guide"), window
        )
        self.actionUserGuide.setToolTip(_("Open the online user guide"))
        self.actionUserGuide.setStatusTip(
            _("Open the user guide, in the interface language, in the web browser")
        )

        self.actionEditShortcuts = QAction(
            QIcon(_resource("edit.svg")), _("Edit shortcuts…"), window
        )
        self.actionEditShortcuts.setToolTip(_("Manage directory shortcuts"))
        self.actionEditShortcuts.setStatusTip(
            _("Add or remove entries from the shortcuts list")
        )

        self.actionFileInfo = QAction(
            QIcon(_resource("question.svg")), _("Information"), window
        )
        self.actionFileInfo.setShortcut(QKeySequence("Ctrl+I"))
        self.actionFileInfo.setToolTip(_("Show file field values"))
        self.actionFileInfo.setStatusTip(
            _("Open the file information window for the selected file")
        )

        self.actionProfileNew = QAction(
            QIcon(_resource("add.svg")), _("New profile…"), window
        )
        self.actionProfileNew.setShortcut(QKeySequence("Ctrl+N"))
        self.actionProfileNew.setToolTip(_("Create a new profile"))
        self.actionProfileNew.setStatusTip(
            _("Create a profile with default settings and switch to it")
        )

        self.actionProfileDuplicate = QAction(_("Duplicate profile…"), window)
        self.actionProfileDuplicate.setShortcut(QKeySequence("Ctrl+Shift+D"))
        self.actionProfileDuplicate.setToolTip(_("Duplicate the current profile"))
        self.actionProfileDuplicate.setStatusTip(
            _("Copy the current profile under a new name and switch to the copy")
        )

        self.actionProfileRename = QAction(_("Rename profile…"), window)
        self.actionProfileRename.setToolTip(_("Rename the current profile"))
        self.actionProfileRename.setStatusTip(
            _("Give the current profile a new name (letters, digits, “-” and “_”)")
        )

        self.actionProfileDelete = QAction(_("Delete profile…"), window)
        self.actionProfileDelete.setToolTip(_("Delete a profile"))
        self.actionProfileDelete.setStatusTip(
            _("Permanently delete a profile and all its settings")
        )

        self.actionProfileConfig = QAction(
            QIcon(_resource("configure.svg")), _("Profile configuration…"), window
        )
        self.actionProfileConfig.setShortcut(QKeySequence("Ctrl+,"))
        self.actionProfileConfig.setToolTip(_("Configure the current profile"))
        self.actionProfileConfig.setStatusTip(
            _("Configure the schema fields and options of the current profile")
        )

    def _setup_image_actions(self, window):
        """Actions of the Images menu, also in the file list context menu
        and (rotations, open, delete…) in the image viewer."""

        def action(icon, text, shortcut, tip, status):
            act = QAction(QIcon(_resource(icon)) if icon else QIcon(), text, window)
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
            act.setToolTip(tip)
            act.setStatusTip(status)
            act.setEnabled(False)
            return act

        self.actionImgOpen = action(
            "open.svg",
            _("Open"),
            "Ctrl+Return",
            _("Open with the default application"),
            _("Open the selected files with their default application"),
        )
        self.actionImgOpenWith = action(
            "open-with.svg",
            _("Open with…"),
            "Ctrl+Shift+O",
            _("Open with a chosen application"),
            _("Choose the application that opens the selected file"),
        )
        self.actionImgView = action(
            "zoom-fit.svg",
            _("View"),
            "Return",
            _("Show in the image viewer"),
            _("Show the selected images and videos in the image viewer"),
        )
        self.actionImgTemplate = action(
            "rename-template.svg",
            _("Template"),
            "",
            _("Fill the schema from the file name"),
            _("Infer the schema fields from the selected file name and its folders"),
        )
        self.actionImgDelete = action(
            "delete.svg",
            _("Delete"),
            "Delete",
            _("Delete the selected files"),
            _("Delete the selected files and their sidecars (to the trash if enabled)"),
        )
        self.actionImgOrphans = action(
            "sidecars.svg",
            _("Orphan sidecars…"),
            "",
            _("List the sidecars without a base file"),
            _("List, then delete, the sidecar files of the folder without a base file"),
        )
        self.actionRotateLeft = action(
            "object-rotate-left.svg",
            _("Rotate 90° left"),
            "F6",
            _("Rotate counter-clockwise, without loss"),
            _("Rotate the selected images 90° counter-clockwise, without loss"),
        )
        self.actionRotate180 = action(
            "object-flip-vertical.svg",
            _("Rotate 180°"),
            "F7",
            _("Rotate 180°, without loss"),
            _("Rotate the selected images 180°, without loss"),
        )
        self.actionRotateRight = action(
            "object-rotate-right.svg",
            _("Rotate 90° right"),
            "F8",
            _("Rotate clockwise, without loss"),
            _("Rotate the selected images 90° clockwise, without loss"),
        )
        self.actionRotateExif = action(
            "auto-rotate.svg",
            _("Apply EXIF orientation"),
            "F9",
            _("Rotate the pixels as the EXIF orientation says"),
            _("Rotate the pixels as the EXIF orientation says, then reset it"),
        )
        self.actionResetExif = action(
            "reset-exif.svg",
            _("Force EXIF orientation to 0°"),
            "F10",
            _("Set the EXIF orientation to normal"),
            _("Set the EXIF orientation tag to 1 (0°) without rotating the pixels"),
        )
        self.actionRefresh = action(
            "view-refresh.svg",
            _("Refresh"),
            "F5",
            _("Reload the file list"),
            _("Read the folder again and refresh the thumbnails"),
        )
        self.actionRefresh.setEnabled(True)
        # Return and Delete also edit text fields: only on the file list.
        for act in (self.actionImgView, self.actionImgDelete, self.actionImgOpen):
            act.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)

    # ── Central widget ────────────────────────────────────────────────────────

    def _setup_central_widget(self, window):
        central = QWidget(window)
        root = QVBoxLayout(central)

        root.addLayout(self._make_options_bar(central))

        # Main horizontal splitter: directory tree | right pane
        self.splitterMain = QSplitter(Qt.Horizontal, central)

        self.treeDirectory = DirectoryTreeView(self.splitterMain)
        self.treeDirectory.setMinimumWidth(180)
        self.treeDirectory.setHeaderHidden(True)
        self.treeDirectory.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeDirectory.setToolTip(_("Browse the filesystem"))
        self.treeDirectory.setStatusTip(
            _("Select a directory to list its contents in the panel on the right")
        )
        self.splitterMain.addWidget(self.treeDirectory)

        self.splitterRight = QSplitter(Qt.Vertical, self.splitterMain)
        self.splitterRight.addWidget(self._make_file_list(self.splitterRight))
        self.splitterRight.addWidget(self._make_bottom_panel(self.splitterRight))
        self.splitterMain.addWidget(self.splitterRight)
        self.treeDirectory.tab_partner = self.tblFiles
        self.tblFiles.tab_partner = self.treeDirectory

        root.addWidget(self.splitterMain)
        root.setStretch(1, 1)  # splitter takes all vertical space
        window.setCentralWidget(central)

    def _make_options_bar(self, parent):
        """Top toolbar: display mode, flags, and glob filter."""
        bar = QHBoxLayout()

        bar.addWidget(QLabel(_("Show:"), parent))

        self.cmbMode = QComboBox(parent)
        self.cmbMode.addItems(
            [
                _("Files only"),
                _("Directories only"),
                _("Files and directories"),
            ]
        )
        self.cmbMode.setToolTip(_("Choose which entries to list"))
        self.cmbMode.setStatusTip(_("List files only, directories only, or both"))
        bar.addWidget(self.cmbMode)

        self.chkRecursive = QCheckBox(_("Recursive"), parent)
        self.chkRecursive.setToolTip(_("Include all subdirectories"))
        self.chkRecursive.setStatusTip(
            _("When checked, files from all subdirectories are listed")
        )
        bar.addWidget(self.chkRecursive)

        self.chkThumbnails = QCheckBox(_("Thumbnails"), parent)
        self.chkThumbnails.setToolTip(_("Show image thumbnails in the file list"))
        self.chkThumbnails.setStatusTip(
            _("Show a thumbnail column; this setting belongs to the current profile")
        )
        bar.addWidget(self.chkThumbnails)

        self.chkSortByDate = QCheckBox(_("By date"), parent)
        self.chkSortByDate.setToolTip(_("Sort the files by modification date"))
        self.chkSortByDate.setStatusTip(
            _("Sort by modification date instead of by name; folders stay first")
        )
        bar.addWidget(self.chkSortByDate)

        self.chkSortReverse = QCheckBox(_("Reversed"), parent)
        self.chkSortReverse.setToolTip(_("Reverse the sort order"))
        self.chkSortReverse.setStatusTip(
            _("List the files in reverse order; folders stay first")
        )
        bar.addWidget(self.chkSortReverse)

        self.cmbExtensionMode = QComboBox(parent)
        self.cmbExtensionMode.addItem(_("Keep extension"), userData="keep")
        self.cmbExtensionMode.addItem(_("Extension in lowercase"), userData="lower")
        self.cmbExtensionMode.addItem(_("Extension in uppercase"), userData="upper")
        self.cmbExtensionMode.addItem(_("Normalize extension"), userData="normalize")
        self.cmbExtensionMode.addItem(_("Modify extension"), userData="modify")
        self.cmbExtensionMode.setToolTip(_("How to handle the file extension"))
        self.cmbExtensionMode.setStatusTip(
            _(
                "Keep: extension untouched. Lowercase/Uppercase: extension"
                " case-folded. Normalize: extension mapped via the"
                " normalization table (Edit menu). Modify: the extension is"
                " included in the search/replace pattern like the rest of"
                " the name"
            )
        )
        bar.addWidget(self.cmbExtensionMode)

        self.chkSidecarMode = QCheckBox(_("Sidecar mode"), parent)
        self.chkSidecarMode.setToolTip(
            _("Group sidecar files (e.g. img.xmp) with their base file when renaming")
        )
        self.chkSidecarMode.setStatusTip(
            _(
                "When enabled, sidecar files are colored, selected together"
                " with their base file, and renamed using the base file's"
                " new name plus their own original suffix, unchanged."
                " Only available with the Keep/Lowercase/Uppercase"
                " extension modes"
            )
        )
        bar.addWidget(self.chkSidecarMode)

        self.chkAutoPreview = QCheckBox(_("Auto-preview"), parent)
        self.chkAutoPreview.setToolTip(_("Refresh the preview automatically"))
        self.chkAutoPreview.setStatusTip(
            _("Recompute the preview each time the pattern or options change")
        )
        bar.addWidget(self.chkAutoPreview)

        bar.addWidget(QLabel(_("Filter:"), parent))

        self.edtFilter = QLineEdit(parent)
        self.edtFilter.setMaximumWidth(160)
        self.edtFilter.setPlaceholderText("*.txt")
        self.edtFilter.setToolTip(_("Glob pattern to filter the file list"))
        self.edtFilter.setStatusTip(
            _("Only files matching this glob pattern are listed (e.g. *.txt, image_*)")
        )
        bar.addWidget(self.edtFilter)

        self.cmbSidecarFilter = QComboBox(parent)
        self.cmbSidecarFilter.setEditable(True)
        self.cmbSidecarFilter.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.cmbSidecarFilter.setMinimumWidth(200)
        self.cmbSidecarFilter.lineEdit().setPlaceholderText(_("Sidecar filter…"))
        self.cmbSidecarFilter.setToolTip(
            _(
                "<b>Sidecar content filter</b><br>"
                "Python regular expression applied to the <i>content</i>"
                " of sidecar files.<br>"
                "Only files with at least one sidecar whose content matches"
                " are shown, with their sidecars.<br>"
                "Files with no sidecar are always hidden when a filter is"
                " active.<br>"
                "<tt>.*</tt> matches across line breaks (re.DOTALL).<br>"
                "Case-insensitive (re.IGNORECASE), including accented"
                " characters.<br>"
                "Press Enter to keep the filter in the history; leave empty"
                " to show all files."
            )
        )
        self.cmbSidecarFilter.setVisible(False)
        bar.addWidget(self.cmbSidecarFilter)

        bar.addItem(
            QSpacerItem(
                20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )
        return bar

    def _make_file_list(self, parent):
        """File tree: Original | Preview, plus Thumbnail and Sidecar columns."""
        self.tblFiles = FileListWidget(parent)
        self.tblFiles.setHeaderLabels(
            [_("Original"), _("Preview"), _("Thumbnail"), _("Sidecar")]
        )
        # Logical columns 0 and 1 keep their meaning; shown order is
        # Thumbnail | Original | Sidecar | Preview.  Columns 2 and 3 are
        # shown according to the profile.
        header = self.tblFiles.header()
        header.moveSection(2, 0)
        header.moveSection(3, 2)
        self.tblFiles.setColumnHidden(2, True)
        self.tblFiles.setColumnHidden(3, True)
        self.tblFiles.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tblFiles.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tblFiles.setAlternatingRowColors(True)
        self.tblFiles.setRootIsDecorated(False)
        self.tblFiles.setSortingEnabled(False)
        self.tblFiles.setToolTip(_("Files to be renamed"))
        self.tblFiles.setStatusTip(
            _(
                "Select rows to restrict operations to those files;"
                " leave unselected to apply to all"
            )
        )
        return self.tblFiles

    def _make_bottom_panel(self, parent):
        """Bottom pane: rule tabs (left) + action buttons (right)."""
        panel = QWidget(parent)
        row = QHBoxLayout(panel)
        row.setContentsMargins(0, 0, 0, 0)

        self.tabRules = QTabWidget(panel)
        self.tabRules.addTab(self._make_rename_frame(self.tabRules), _("Pattern"))
        self.tabRules.setTabToolTip(
            0, _("Rename in place with search/replace patterns")
        )
        # Filled by MainWindow with the schema rule panel (dynamic fields).
        self.tabSchema = QWidget(self.tabRules)
        QVBoxLayout(self.tabSchema).setContentsMargins(0, 0, 0, 0)
        self.tabRules.addTab(self.tabSchema, _("Schema"))
        self.tabRules.setTabToolTip(
            1, _("Sort files into a destination tree built from schema fields")
        )
        row.addWidget(self.tabRules)

        row.addLayout(self._make_action_buttons(panel))
        return panel

    def _make_rename_frame(self, parent):
        """Framed panel with search/replace patterns, modes, post-processing, saves."""
        frame = QFrame(parent)
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setFrameShadow(QFrame.Raised)
        col = QVBoxLayout(frame)

        # Search row
        col.addLayout(self._make_search_row(frame))

        # Mode row: Pattern / Regex / Plain text + case-insensitive checkbox
        col.addLayout(self._make_mode_row(frame))

        # Replace row
        col.addLayout(self._make_replace_row(frame))

        col.addItem(
            QSpacerItem(20, 5, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        # Post-processing group
        col.addWidget(self._make_postprocess_group(frame))

        # Named save row
        col.addLayout(self._make_save_row(frame))

        return frame

    def _make_search_row(self, parent):
        row = QHBoxLayout()

        lbl = QLabel(_("Search:"), parent)
        lbl.setMinimumWidth(60)
        row.addWidget(lbl)

        # Expanding editable combo inheriting horizontal stretch
        sp = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sp.setHorizontalStretch(1)

        self.cmbPatternSearch = QComboBox(parent)
        self.cmbPatternSearch.setEditable(True)
        self.cmbPatternSearch.setSizePolicy(sp)
        self.cmbPatternSearch.setToolTip(_("Search pattern"))
        self.cmbPatternSearch.setStatusTip(
            _(
                "Pattern to match against file names."
                " Use tokens: {#} numbers, {L} letters, {C} non-space, {X} anything"
            )
        )
        row.addWidget(self.cmbPatternSearch)

        self.btnSearchAdd = QToolButton(parent)
        self.btnSearchAdd.setAutoRaise(True)
        self.btnSearchAdd.setToolTip(_("Save to history"))
        self.btnSearchAdd.setStatusTip(
            _("Add the current search pattern and mode to the drop-down history")
        )
        row.addWidget(self.btnSearchAdd)

        self.btnSearchHelp = QToolButton(parent)
        self.btnSearchHelp.setAutoRaise(True)
        self.btnSearchHelp.setToolTip(_("Search pattern help"))
        self.btnSearchHelp.setStatusTip(
            _(
                "Show help about search patterns"
                " (Pattern tokens, Regular expressions, Plain text)"
            )
        )
        row.addWidget(self.btnSearchHelp)

        return row

    def _make_mode_row(self, parent):
        row = QHBoxLayout()

        self.radPattern = QRadioButton(_("Pattern"), parent)
        self.radPattern.setChecked(True)
        self.radPattern.setToolTip(_("Search using pattern tokens"))
        self.radPattern.setStatusTip(
            _("Match file names using pattern tokens ({#}, {L}, {X}…)")
        )
        row.addWidget(self.radPattern)

        self.radRegex = QRadioButton(_("Regular expression"), parent)
        self.radRegex.setToolTip(_("Search using a Python regular expression"))
        self.radRegex.setStatusTip(
            _(
                "Match file names using a Python regular expression;"
                " use \\1 \\2… for backreferences in the replacement"
            )
        )
        row.addWidget(self.radRegex)

        self.radPlainText = QRadioButton(_("Plain text"), parent)
        self.radPlainText.setToolTip(_("Search for a literal string"))
        self.radPlainText.setStatusTip(
            _("Match file names by looking for the search text as a literal string")
        )
        row.addWidget(self.radPlainText)

        self.chkCaseInsensitive = QCheckBox(_("Case-insensitive"), parent)
        self.chkCaseInsensitive.setChecked(True)
        self.chkCaseInsensitive.setToolTip(_("Ignore case when searching"))
        self.chkCaseInsensitive.setStatusTip(
            _(
                "When checked, the search pattern matches file names"
                " regardless of letter case"
            )
        )
        row.addWidget(self.chkCaseInsensitive)

        row.addItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )
        return row

    def _make_replace_row(self, parent):
        row = QHBoxLayout()

        lbl = QLabel(_("Replace:"), parent)
        lbl.setMinimumWidth(60)
        row.addWidget(lbl)

        sp = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sp.setHorizontalStretch(1)

        self.cmbPatternDest = QComboBox(parent)
        self.cmbPatternDest.setEditable(True)
        self.cmbPatternDest.setSizePolicy(sp)
        self.cmbPatternDest.setToolTip(_("Replacement pattern"))
        self.cmbPatternDest.setStatusTip(
            _(
                "Replacement pattern."
                " Use {1} {2}… for capture groups, {num} for a counter,"
                " {date} for today's date, {dir} for the parent folder name"
            )
        )
        row.addWidget(self.cmbPatternDest)

        self.btnReplaceAdd = QToolButton(parent)
        self.btnReplaceAdd.setAutoRaise(True)
        self.btnReplaceAdd.setToolTip(_("Save to history"))
        self.btnReplaceAdd.setStatusTip(
            _("Add the current replacement pattern to the drop-down history")
        )
        row.addWidget(self.btnReplaceAdd)

        self.btnReplaceHelp = QToolButton(parent)
        self.btnReplaceHelp.setAutoRaise(True)
        self.btnReplaceHelp.setToolTip(_("Replacement pattern help"))
        self.btnReplaceHelp.setStatusTip(
            _(
                "Show help about replacement patterns"
                " (capture groups, counter, date, directory tokens)"
            )
        )
        row.addWidget(self.btnReplaceHelp)

        return row

    def _make_postprocess_group(self, parent):
        """Separator conversion, accent removal, duplicate removal, case change."""
        grp = QGroupBox(_("Post-processing"), parent)
        grid = QGridLayout(grp)

        # Row 0 — Separator: [label] [combo]   [chkRemoveAccents]
        grid.addWidget(QLabel(_("Separator:"), grp), 0, 0)

        self.cmbSpaces = QComboBox(grp)
        self.cmbSpaces.addItems(
            [
                _("No change"),
                _("Spaces → underscores"),
                _("Underscores → spaces"),
                _("Spaces → dots"),
                _("Dots → spaces"),
                _("Spaces → dashes"),
                _("Dashes → spaces"),
            ]
        )
        self.cmbSpaces.setToolTip(_("Separator conversion"))
        self.cmbSpaces.setStatusTip(
            _(
                "Apply a separator conversion to each renamed file name"
                " after applying the pattern"
            )
        )
        grid.addWidget(self.cmbSpaces, 0, 1)

        self.chkRemoveAccents = QCheckBox(_("Remove accents"), grp)
        self.chkRemoveAccents.setToolTip(_("Strip diacritical marks"))
        self.chkRemoveAccents.setStatusTip(
            _("Convert accented characters to their ASCII equivalents (é→e, ü→u, etc.)")
        )
        grid.addWidget(self.chkRemoveAccents, 0, 2)

        # Row 1 — Case:      [label] [combo]   [chkRemoveDuplicates]
        grid.addWidget(QLabel(_("Case:"), grp), 1, 0)

        self.cmbCaps = QComboBox(grp)
        self.cmbCaps.addItems(
            [
                _("No change"),
                _("UPPERCASE"),
                _("lowercase"),
                _("Capitalize first letter"),
                _("Title Case"),
            ]
        )
        self.cmbCaps.setToolTip(_("Capitalization mode"))
        self.cmbCaps.setStatusTip(
            _("Choose how to change the case of file names after applying the pattern")
        )
        grid.addWidget(self.cmbCaps, 1, 1)

        self.chkRemoveDuplicates = QCheckBox(_("Remove duplicate separators"), grp)
        self.chkRemoveDuplicates.setToolTip(_("Collapse consecutive separators"))
        self.chkRemoveDuplicates.setStatusTip(
            _(
                "Collapse runs of identical separator characters"
                " (spaces, dots, dashes, underscores) into one"
            )
        )
        grid.addWidget(self.chkRemoveDuplicates, 1, 2)

        # Column 1 (combos) stretches; columns 0 and 2 stay at natural size
        grid.setColumnStretch(1, 1)

        return grp

    def _make_save_row(self, parent):
        """Named preset save/load/delete row."""
        row = QHBoxLayout()

        lbl = QLabel(_("Save:"), parent)
        lbl.setMinimumWidth(60)
        row.addWidget(lbl)

        sp = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sp.setHorizontalStretch(1)

        self.cmbNamedSaves = QComboBox(parent)
        self.cmbNamedSaves.setEditable(True)
        self.cmbNamedSaves.setSizePolicy(sp)
        self.cmbNamedSaves.setToolTip(_("Named save"))
        self.cmbNamedSaves.setStatusTip(
            _(
                "Type a name (letters, digits, _ and -)"
                " to save or load all search/replace parameters"
            )
        )
        row.addWidget(self.cmbNamedSaves)

        self.btnSaveSave = QPushButton(_("Save"), parent)
        self.btnSaveSave.setToolTip(_("Save current settings under this name"))
        self.btnSaveSave.setStatusTip(
            _(
                "Save all search, replace and post-processing settings"
                " under the current name"
                " (overwrites any existing save with the same name)"
            )
        )
        row.addWidget(self.btnSaveSave)

        self.btnSaveDelete = QPushButton(_("Delete"), parent)
        self.btnSaveDelete.setToolTip(_("Delete this named save"))
        self.btnSaveDelete.setStatusTip(
            _("Permanently delete the named save matching the current name")
        )
        row.addWidget(self.btnSaveDelete)

        return row

    def _make_action_buttons(self, parent):
        """Vertical column of action buttons: Preview, Clear, [spacer], Undo, Rename."""
        col = QVBoxLayout()

        self.btnPreview = QPushButton(_("Preview"), parent)
        self.btnPreview.setToolTip(_("Compute rename preview"))
        self.btnPreview.setStatusTip(
            _(
                "Apply the current pattern to all listed files"
                " and show the result in the Preview column"
            )
        )
        col.addWidget(self.btnPreview)

        self.btnClearPreview = QPushButton(_("Clear"), parent)
        self.btnClearPreview.setToolTip(_("Clear the preview"))
        self.btnClearPreview.setStatusTip(
            _("Remove all preview values from the Preview column")
        )
        col.addWidget(self.btnClearPreview)

        col.addItem(
            QSpacerItem(
                20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
        )

        self.btnUndo = QPushButton(_("Undo"), parent)
        self.btnUndo.setEnabled(False)
        self.btnUndo.setToolTip(_("Undo last rename batch"))
        self.btnUndo.setStatusTip(
            _("Reverse the last batch of renames performed on disk")
        )
        col.addWidget(self.btnUndo)

        self.btnRenumber = QPushButton(_("Renumber"), parent)
        self.btnRenumber.setVisible(False)
        self.btnRenumber.setToolTip(_("Renumber from 1 in place"))
        self.btnRenumber.setStatusTip(
            _(
                "Renumber the selected files (all listed files if none is"
                " selected) from 1, in place, following the schema"
            )
        )
        col.addWidget(self.btnRenumber)

        self.btnRename = QPushButton(_("Rename"), parent)
        self.btnRename.setEnabled(False)
        self.btnRename.setShortcut(QKeySequence("F2"))
        self.btnRename.setToolTip(_("Apply renames on disk (F2)"))
        self.btnRename.setStatusTip(
            _(
                "Permanently rename the selected files (all listed files if"
                " none is selected) as shown in the Preview column"
                " (only enabled when there are no conflicts)"
            )
        )
        col.addWidget(self.btnRename)

        return col

    # ── Status bar ────────────────────────────────────────────────────────────

    def _setup_statusbar(self, window):
        self.statusbar = QStatusBar(window)
        window.setStatusBar(self.statusbar)

    # ── Menu bar ──────────────────────────────────────────────────────────────

    def _setup_menubar(self, window):
        menubar = QMenuBar(window)
        window.setMenuBar(menubar)

        # File menu
        menu_file = menubar.addMenu(_("File"))
        menu_file.addAction(self.actionOpenFolder)
        menu_file.addSeparator()
        menu_file.addAction(self.actionFileInfo)
        menu_file.addSeparator()
        menu_file.addAction(self.actionQuit)

        # Edit menu
        menu_edit = menubar.addMenu(_("Edit"))
        menu_edit.addAction(self.actionHistory)
        menu_edit.addSeparator()
        menu_edit.addAction(self.actionSidecarFiles)
        menu_edit.addAction(self.actionSettings)

        # Profile menu (profile list appended by MainWindow._build_profile_menu)
        self.menuProfile = menubar.addMenu(_("Profile"))
        self.menuProfile.addAction(self.actionProfileNew)
        self.menuProfile.addAction(self.actionProfileDuplicate)
        self.menuProfile.addAction(self.actionProfileRename)
        self.menuProfile.addAction(self.actionProfileDelete)
        self.menuProfile.addSeparator()
        self.menuProfile.addAction(self.actionProfileConfig)
        self.menuProfile.addSeparator()

        # Images menu (also the file list context menu)
        self.menuImages = menubar.addMenu(_("Images"))
        # Filled by ImageActions when the menu is shown: one entry per
        # sidecar suffix of the targeted files.
        self.menuOpenSidecar = QMenu(_("Open sidecar"), self.menuImages)
        self.menuOpenSidecar.menuAction().setEnabled(False)
        for act in (
            self.actionImgOpen,
            self.actionImgOpenWith,
            self.menuOpenSidecar.menuAction(),
            self.actionImgView,
            self.actionImgTemplate,
            None,
            self.actionImgDelete,
            self.actionImgOrphans,
            None,
            self.actionRotateLeft,
            self.actionRotate180,
            self.actionRotateRight,
            self.actionRotateExif,
            self.actionResetExif,
            None,
            self.actionFileInfo,
            self.actionRefresh,
        ):
            if act is None:
                self.menuImages.addSeparator()
            else:
                self.menuImages.addAction(act)
        for act in (self.actionImgView, self.actionImgDelete, self.actionImgOpen):
            self.tblFiles.addAction(act)

        # Shortcuts menu (populated dynamically by MainWindow._build_shortcuts_menu)
        self.menuShortcuts = menubar.addMenu(_("Shortcuts"))
        self.menuShortcuts.addAction(self.actionEditShortcuts)

        # Help menu
        menu_help = menubar.addMenu(_("Help"))
        menu_help.addAction(self.actionUserGuide)
        menu_help.addAction(self.actionKeyboardHelp)
        menu_help.addSeparator()
        menu_help.addAction(self.actionAbout)
