"""Dialog listing the sidecar files of the folder that have no base file
(ported from PBPicat)."""

from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

from pbrenamer.ui.geometry_mixin import GeometryMixin


class OrphanSidecarsDialog(GeometryMixin, QDialog):
    """List of orphan sidecars; *delete* removes the given files (after its
    own confirmation) and returns those actually deleted."""

    def __init__(
        self,
        orphans: list[str],
        delete: Callable[[list[str]], list[str]],
        window_state,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Orphan sidecars"))
        self.setMinimumWidth(420)
        self._init_geometry(window_state, "orphan_sidecars_dialog")
        self._orphans = list(orphans)
        self._delete = delete

        root = QVBoxLayout(self)
        self._label = QLabel()
        root.addWidget(self._label)
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        root.addWidget(self._list)

        buttons = QHBoxLayout()
        self._del_sel_btn = QPushButton(_("Delete selected"))
        self._del_sel_btn.clicked.connect(self._delete_selected)
        buttons.addWidget(self._del_sel_btn)
        self._del_all_btn = QPushButton(_("Delete all"))
        self._del_all_btn.clicked.connect(self._delete_all)
        buttons.addWidget(self._del_all_btn)
        buttons.addStretch()
        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)
        self._refresh_list()

    def _refresh_list(self) -> None:
        self._label.setText(
            _("{n} orphan sidecar file(s):").format(n=len(self._orphans))
        )
        self._list.clear()
        for path in self._orphans:
            self._list.addItem(os.path.basename(path))
        self._del_sel_btn.setEnabled(bool(self._orphans))
        self._del_all_btn.setEnabled(bool(self._orphans))

    def _delete_selected(self) -> None:
        rows = sorted({idx.row() for idx in self._list.selectedIndexes()})
        if rows:
            self._delete_files([self._orphans[r] for r in rows])

    def _delete_all(self) -> None:
        self._delete_files(list(self._orphans))

    def _delete_files(self, files: list[str]) -> None:
        deleted = set(self._delete(files))
        self._orphans = [p for p in self._orphans if p not in deleted]
        self._refresh_list()
        if not self._orphans:
            self.accept()
