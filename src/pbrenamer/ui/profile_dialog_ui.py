"""UI layout for the Profile configuration dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class Ui_ProfileDialog:
    def setupUi(self, dialog):
        dialog.setMinimumSize(420, 440)
        dialog.resize(460, 520)

        layout = QVBoxLayout(dialog)

        self.tabs = QTabWidget(dialog)
        self.tabs.addTab(self._make_schema_tab(dialog), _("Schema"))
        self.tabs.addTab(self._make_display_tab(dialog), _("Display"))
        self.tabs.addTab(self._make_files_tab(dialog), _("Files"))
        self.tabs.addTab(self._make_viewer_tab(dialog), _("Image viewer"))
        layout.addWidget(self.tabs)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            dialog,
        )
        self.buttonBox.rejected.connect(dialog.reject)
        layout.addWidget(self.buttonBox)

    # ── Schema tab ────────────────────────────────────────────────────────────

    def _make_schema_tab(self, dialog):
        tab = QWidget(dialog)
        layout = QVBoxLayout(tab)

        form = QFormLayout()
        self.spnFieldCount = QSpinBox(tab)
        self.spnFieldCount.setRange(1, 12)
        self.spnFieldCount.setToolTip(_("Number of fields of the rename schema"))
        form.addRow(_("Number of fields:"), self.spnFieldCount)

        self.edtVideoMarker = QLineEdit(tab)
        self.edtVideoMarker.setToolTip(_("Text inserted in the name of video files"))
        self.edtVideoMarker.setStatusTip(
            _(
                "Inserted at the position chosen with the radio buttons of the"
                " Schema tab; leave empty for no marker"
            )
        )
        form.addRow(_("Video marker:"), self.edtVideoMarker)

        self.chkRenameDirs = QCheckBox(_("Rename directories too"), tab)
        self.chkRenameDirs.setToolTip(
            _(
                "When checked, the listed directories are moved and renamed by"
                " the schema like files; otherwise they are left alone"
            )
        )
        form.addRow(self.chkRenameDirs)

        layout.addLayout(form)

        layout.addWidget(QLabel(_("Field titles:"), tab))
        scroll = QScrollArea(tab)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.StyledPanel)
        self.titlesContainer = QWidget(scroll)
        self.titlesLayout = QFormLayout(self.titlesContainer)
        scroll.setWidget(self.titlesContainer)
        layout.addWidget(scroll, 1)
        return tab

    # ── Display tab ───────────────────────────────────────────────────────────

    def _make_display_tab(self, dialog):
        tab = QWidget(dialog)
        layout = QVBoxLayout(tab)

        thumbs = QGroupBox(_("Thumbnails"), tab)
        form = QFormLayout(thumbs)
        self.chkThumbnails = QCheckBox(_("Show thumbnails"), thumbs)
        self.chkThumbnails.setToolTip(_("Show a thumbnail column in the file list"))
        form.addRow(self.chkThumbnails)
        self.spnThumbWidth = QSpinBox(thumbs)
        self.spnThumbWidth.setRange(16, 1024)
        self.spnThumbWidth.setSuffix(" px")
        form.addRow(_("Maximum width:"), self.spnThumbWidth)
        self.spnThumbHeight = QSpinBox(thumbs)
        self.spnThumbHeight.setRange(16, 1024)
        self.spnThumbHeight.setSuffix(" px")
        form.addRow(_("Maximum height:"), self.spnThumbHeight)
        layout.addWidget(thumbs)

        sidecars = QGroupBox(_("Sidecar files"), tab)
        form = QFormLayout(sidecars)
        self.chkSidecarColumn = QCheckBox(_("Show the sidecar column"), sidecars)
        self.chkSidecarColumn.setToolTip(
            _(
                "Show which files have sidecars; double-click the column to"
                " open a sidecar or create one"
            )
        )
        form.addRow(self.chkSidecarColumn)
        self.chkSidecarFilter = QCheckBox(
            _("Show the sidecar content filter"), sidecars
        )
        self.chkSidecarFilter.setToolTip(
            _("Filter the file list on the content of the sidecar files")
        )
        form.addRow(self.chkSidecarFilter)
        self.edtSidecarExtension = QLineEdit(sidecars)
        self.edtSidecarExtension.setToolTip(
            _("Extension of the sidecar created by a double-click, without dot")
        )
        form.addRow(_("New sidecar extension:"), self.edtSidecarExtension)
        self.chkDeleteEmptySidecars = QCheckBox(
            _("Delete empty sidecar files when loading a directory"), sidecars
        )
        self.chkDeleteEmptySidecars.setToolTip(
            _(
                "Empty files named like a sidecar are deleted when the"
                " directory is listed, except a sidecar just created"
            )
        )
        form.addRow(self.chkDeleteEmptySidecars)
        layout.addWidget(sidecars)

        form = QFormLayout()
        self.spnHistoryMax = QSpinBox(tab)
        self.spnHistoryMax.setRange(1, 200)
        self.spnHistoryMax.setToolTip(
            _("Maximum number of values kept in each field history")
        )
        form.addRow(_("Max history entries:"), self.spnHistoryMax)
        layout.addLayout(form)
        layout.addStretch()
        return tab

    # ── Image viewer tab ──────────────────────────────────────────────────────

    def _make_viewer_tab(self, dialog):
        tab = QWidget(dialog)
        layout = QVBoxLayout(tab)

        viewer = QWidget(tab)
        form = QFormLayout(viewer)
        form.setContentsMargins(0, 0, 0, 0)
        self.spnZoomStep = QSpinBox(viewer)
        self.spnZoomStep.setRange(5, 100)
        self.spnZoomStep.setSuffix(" %")
        self.spnZoomStep.setToolTip(_("Zoom change of each zoom in or zoom out"))
        form.addRow(_("Zoom step:"), self.spnZoomStep)
        self.spnZoomMax = QSpinBox(viewer)
        self.spnZoomMax.setRange(100, 3200)
        self.spnZoomMax.setSuffix(" %")
        self.spnZoomMax.setToolTip(_("Largest zoom of the image viewer"))
        form.addRow(_("Maximum zoom:"), self.spnZoomMax)
        self.cmbMetadataSide = QComboBox(viewer)
        self.cmbMetadataSide.addItem(_("Right"), userData="right")
        self.cmbMetadataSide.addItem(_("Left"), userData="left")
        self.cmbMetadataSide.setToolTip(
            _("Side of the image viewer where the metadata panel is shown")
        )
        form.addRow(_("Metadata panel:"), self.cmbMetadataSide)
        self.chkExifAutoRotate = QCheckBox(
            _("Show images turned as their EXIF orientation says"), viewer
        )
        self.chkExifAutoRotate.setToolTip(
            _("Applies to the thumbnails and to the image viewer")
        )
        form.addRow(self.chkExifAutoRotate)
        layout.addWidget(viewer)
        layout.addStretch()
        return tab

    # ── Files tab ─────────────────────────────────────────────────────────────

    def _make_files_tab(self, dialog):
        tab = QWidget(dialog)
        layout = QVBoxLayout(tab)

        deletion = QGroupBox(_("Deletion"), tab)
        form = QFormLayout(deletion)
        self.cmbDeletionMode = QComboBox(deletion)
        self.cmbDeletionMode.addItem(_("Delete permanently"), userData="delete")
        self.cmbDeletionMode.addItem(_("Move to the system trash"), userData="system")
        self.cmbDeletionMode.addItem(_("Move to the session trash"), userData="session")
        self.cmbDeletionMode.setToolTip(
            _(
                "Deletions to a trash can be undone. The session trash is "
                "private to PBRenamer and emptied when it closes; files on "
                "another file system than it can only be deleted permanently"
            )
        )
        form.addRow(_("Deleted files:"), self.cmbDeletionMode)
        self.chkConfirmDeletions = QCheckBox(_("Confirm deletions"), deletion)
        self.chkConfirmDeletions.setToolTip(
            _("Ask for a confirmation before deleting files")
        )
        form.addRow(self.chkConfirmDeletions)
        self.spnDeleteListMax = QSpinBox(deletion)
        self.spnDeleteListMax.setRange(1, 100)
        self.spnDeleteListMax.setToolTip(
            _("Above this number of files, the confirmation only gives the count")
        )
        form.addRow(_("Files listed in the confirmation:"), self.spnDeleteListMax)
        layout.addWidget(deletion)

        empty = QGroupBox(_("Remove the folders left empty"), tab)
        empty.setToolTip(
            _(
                "The displayed folder is removed too when it is left empty; "
                "the home folder and the root of a disk never are"
            )
        )
        form = QFormLayout(empty)
        self.chkPruneOnDelete = QCheckBox(_("After a deletion"), empty)
        self.chkPruneOnDelete.setToolTip(
            _("Remove the folders that deleting files leaves empty")
        )
        form.addRow(self.chkPruneOnDelete)
        self.chkPruneOnRename = QCheckBox(_("After a rename"), empty)
        self.chkPruneOnRename.setToolTip(
            _(
                "Remove the folders that renaming files leaves empty, "
                "schema mode included"
            )
        )
        form.addRow(self.chkPruneOnRename)
        self.chkPruneOnMove = QCheckBox(_("After a move by drag and drop"), empty)
        self.chkPruneOnMove.setToolTip(
            _("Remove the folders that moving files by drag and drop leaves empty")
        )
        form.addRow(self.chkPruneOnMove)
        self.chkPruneParents = QCheckBox(_("Also their parents left empty"), empty)
        self.chkPruneParents.setToolTip(
            _("Then remove the parent folders that become empty in turn")
        )
        form.addRow(self.chkPruneParents)
        layout.addWidget(empty)
        layout.addStretch()
        return tab
