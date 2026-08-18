"""UI layout for the Sidecar Files dialog."""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QSizePolicy,
    QSpacerItem,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

_BASE_EXT_CATEGORIES = ("image", "video", "audio")
_SUFFIX_CATEGORIES = ("image", "video", "audio", "other")


class Ui_SidecarDialog:
    def setupUi(self, dialog):
        dialog.setMinimumSize(440, 460)
        dialog.resize(480, 540)
        dialog.setWindowTitle(_("Sidecar Files"))

        layout = QVBoxLayout(dialog)

        lbl_intro = QLabel(
            _(
                "A sidecar file is associated with a base file by a name"
                ' suffix (e.g. "img.jpg" + "img.xmp"). Each tab configures'
                " one base-file category: which extensions count as its"
                " base files, and which suffixes identify its sidecars."
            ),
            dialog,
        )
        lbl_intro.setWordWrap(True)
        layout.addWidget(lbl_intro)

        self.tabs = QTabWidget(dialog)
        layout.addWidget(self.tabs)

        self.lstBaseExt: dict[str, QListWidget] = {}
        self.edtBaseExt: dict[str, QLineEdit] = {}
        self.btnBaseExtAdd: dict[str, QToolButton] = {}
        self.btnBaseExtRemove: dict[str, QToolButton] = {}
        self.btnRestoreBaseExt: dict[str, QToolButton] = {}

        self.lstSidecarSuffix: dict[str, QListWidget] = {}
        self.edtSidecarSuffix: dict[str, QLineEdit] = {}
        self.btnSidecarSuffixAdd: dict[str, QToolButton] = {}
        self.btnSidecarSuffixRemove: dict[str, QToolButton] = {}
        self.btnRestoreSidecarSuffix: dict[str, QToolButton] = {}

        category_labels = {
            "image": _("Images"),
            "video": _("Video"),
            "audio": _("Audio"),
            "other": _("Other"),
        }
        for category in _SUFFIX_CATEGORIES:
            self.tabs.addTab(
                self._make_category_tab(self.tabs, category),
                category_labels[category],
            )
        self.tabs.addTab(self._make_common_tab(self.tabs), _("Common"))

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        layout.addWidget(self.buttonBox)

    # ── Shared helper ─────────────────────────────────────────────────────────

    def _make_editable_list_row(self, parent, placeholder: str):
        """Build a QListWidget + QLineEdit + add/remove QToolButton row.

        Returns (container, list_widget, line_edit, add_button,
        remove_button) — the container wraps the list and the input row
        into one block ready to add to a layout.
        """
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        lst = QListWidget(container)
        lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(lst)

        row = QHBoxLayout()
        edt = QLineEdit(container)
        edt.setPlaceholderText(placeholder)
        row.addWidget(edt)

        add_btn = QToolButton(container)
        add_btn.setAutoRaise(True)
        row.addWidget(add_btn)

        remove_btn = QToolButton(container)
        remove_btn.setAutoRaise(True)
        row.addWidget(remove_btn)

        layout.addLayout(row)
        return container, lst, edt, add_btn, remove_btn

    def _make_restore_row(self, parent) -> tuple[QHBoxLayout, QToolButton]:
        row = QHBoxLayout()
        row.addItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )
        btn = QToolButton(parent)
        btn.setAutoRaise(True)
        row.addWidget(btn)
        return row, btn

    # ── Per-category tab ──────────────────────────────────────────────────────

    def _make_category_tab(self, parent, category: str):
        tab = QWidget(parent)
        layout = QVBoxLayout(tab)

        if category in _BASE_EXT_CATEGORIES:
            base_grp = QGroupBox(_("Base file extensions"), tab)
            base_layout = QVBoxLayout(base_grp)
            container, lst, edt, add_btn, remove_btn = self._make_editable_list_row(
                base_grp, "jpg"
            )
            add_btn.setToolTip(_("Add this extension"))
            remove_btn.setToolTip(_("Remove selected extensions"))
            base_layout.addWidget(container)
            restore_row, restore_btn = self._make_restore_row(base_grp)
            restore_btn.setToolTip(_("Restore default extensions for this category"))
            base_layout.addLayout(restore_row)
            self.lstBaseExt[category] = lst
            self.edtBaseExt[category] = edt
            self.btnBaseExtAdd[category] = add_btn
            self.btnBaseExtRemove[category] = remove_btn
            self.btnRestoreBaseExt[category] = restore_btn
            layout.addWidget(base_grp)
        else:
            lbl_other = QLabel(
                _(
                    "Other: any file whose extension doesn't match the"
                    " Images, Video, or Audio categories. No editable"
                    " extension list — it is the catch-all category."
                ),
                tab,
            )
            lbl_other.setWordWrap(True)
            layout.addWidget(lbl_other)

        suffix_grp = QGroupBox(_("Sidecar suffixes"), tab)
        suffix_layout = QVBoxLayout(suffix_grp)
        container, lst, edt, add_btn, remove_btn = self._make_editable_list_row(
            suffix_grp, "info.json"
        )
        add_btn.setToolTip(_("Add this sidecar suffix"))
        remove_btn.setToolTip(_("Remove selected sidecar suffixes"))
        suffix_layout.addWidget(container)
        restore_row, restore_btn = self._make_restore_row(suffix_grp)
        restore_btn.setToolTip(_("Restore default sidecar suffixes for this category"))
        suffix_layout.addLayout(restore_row)
        self.lstSidecarSuffix[category] = lst
        self.edtSidecarSuffix[category] = edt
        self.btnSidecarSuffixAdd[category] = add_btn
        self.btnSidecarSuffixRemove[category] = remove_btn
        self.btnRestoreSidecarSuffix[category] = restore_btn
        layout.addWidget(suffix_grp)

        layout.addStretch()
        return tab

    # ── Common tab ────────────────────────────────────────────────────────────

    def _make_common_tab(self, parent):
        tab = QWidget(parent)
        layout = QVBoxLayout(tab)

        lbl_intro = QLabel(
            _("These suffixes are added to every category's own sidecar suffix list."),
            tab,
        )
        lbl_intro.setWordWrap(True)
        layout.addWidget(lbl_intro)

        grp = QGroupBox(_("Common sidecar suffixes"), tab)
        grp_layout = QVBoxLayout(grp)
        container, lst, edt, add_btn, remove_btn = self._make_editable_list_row(
            grp, "meta"
        )
        add_btn.setToolTip(_("Add this common sidecar suffix"))
        remove_btn.setToolTip(_("Remove selected common sidecar suffixes"))
        grp_layout.addWidget(container)
        restore_row, restore_btn = self._make_restore_row(grp)
        restore_btn.setToolTip(_("Restore default common sidecar suffixes"))
        grp_layout.addLayout(restore_row)
        self.lstSidecarCommon = lst
        self.edtSidecarCommon = edt
        self.btnSidecarCommonAdd = add_btn
        self.btnSidecarCommonRemove = remove_btn
        self.btnRestoreSidecarCommon = restore_btn
        layout.addWidget(grp)

        layout.addStretch()
        return tab
