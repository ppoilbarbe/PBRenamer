"""Main application window."""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Callable

from PySide6.QtCore import QDir, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFileSystemModel,
    QMainWindow,
    QMessageBox,
    QTreeWidgetItem,
)

from pbrenamer.core import filetools
from pbrenamer.core.undo import UndoManager
from pbrenamer.platform.fs import conflict_key, same_file_path
from pbrenamer.ui.main_window_ui import Ui_MainWindow
from pbrenamer.ui.presets import PatternPresets
from pbrenamer.ui.settings_dialog import SettingsDialog

_PREVIEW_COLOR = QColor("#0066cc")
_UNCHANGED_COLOR = QColor("#888888")
_DIR_COLOR = QColor("#aa6600")
_CONFLICT_COLOR = QColor("#cc0000")


class MainWindow(QMainWindow):
    """Top-level window for PBRenamer."""

    def __init__(self, start_dir: str | None = None) -> None:
        super().__init__()
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)

        self._current_dir: str | None = None
        self._undo = UndoManager()
        self._presets = PatternPresets()

        self._setup_directory_tree()
        self._populate_pattern_combos()
        self._connect_signals()
        self._ui.splitterMain.setSizes([220, 880])
        self._ui.splitterRight.setSizes([380, 200])
        self._navigate_to(start_dir or os.getcwd())

    # ── Initial setup ─────────────────────────────────────────────────────────

    def _setup_directory_tree(self) -> None:
        self._fs_model = QFileSystemModel(self)
        root_idx = self._fs_model.setRootPath(QDir.rootPath())
        self._fs_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot)
        self._ui.treeDirectory.setModel(self._fs_model)
        self._ui.treeDirectory.setRootIndex(root_idx)
        for col in range(1, self._fs_model.columnCount()):
            self._ui.treeDirectory.hideColumn(col)

    def _navigate_to(self, path: str) -> None:
        if not os.path.isdir(path):
            return
        idx = self._fs_model.index(path)
        self._ui.treeDirectory.setCurrentIndex(idx)
        self._ui.treeDirectory.scrollTo(idx)
        self._ui.treeDirectory.expand(idx)

    def _populate_pattern_combos(self) -> None:
        self._ui.cmbPatternSearch.clear()
        self._ui.cmbPatternDest.clear()
        for p in self._presets.get("search"):
            self._ui.cmbPatternSearch.addItem(p)
        for p in self._presets.get("replace"):
            self._ui.cmbPatternDest.addItem(p)

    def _connect_signals(self) -> None:
        self._ui.actionOpenFolder.triggered.connect(self._on_open)
        self._ui.btnPreview.clicked.connect(self._on_preview)
        self._ui.btnClearPreview.clicked.connect(self._on_clear_preview)
        self._ui.btnUndo.clicked.connect(self._on_undo)
        self._ui.btnRename.clicked.connect(self._on_rename)

        sel_model = self._ui.treeDirectory.selectionModel()
        sel_model.selectionChanged.connect(lambda *_: self._on_directory_selected())

        # Substitution tab
        self._ui.btnApplySpaces.clicked.connect(self._on_apply_spaces)
        self._ui.btnApplyCaps.clicked.connect(self._on_apply_caps)
        self._ui.btnApplyReplace.clicked.connect(self._on_apply_replace)
        self._ui.btnRemoveAccents.clicked.connect(self._on_remove_accents)
        self._ui.btnRemoveDuplicates.clicked.connect(self._on_remove_duplicates)

        # Insert/Delete tab
        self._ui.btnInsert.clicked.connect(self._on_insert)
        self._ui.btnDelete.clicked.connect(self._on_delete)

        # Manual tab
        self._ui.btnApplyManual.clicked.connect(self._on_apply_manual)

        # Pattern presets
        self._ui.btnSavePattern.clicked.connect(self._on_save_pattern)

        # Options that trigger a file list reload
        self._ui.cmbMode.currentIndexChanged.connect(self._reload_files)
        self._ui.chkRecursive.toggled.connect(self._reload_files)
        self._ui.edtFilter.editingFinished.connect(self._reload_files)

        # Auto-preview
        self._ui.chkAutoPreview.toggled.connect(self._on_auto_preview_toggled)
        self._ui.tabWidget.currentChanged.connect(self._on_tab_changed)

        # Menu bar
        self._ui.actionQuit.triggered.connect(self._on_quit)
        self._ui.actionSettings.triggered.connect(self._on_settings)
        self._ui.actionAbout.triggered.connect(self._on_about)

    # ── Directory / file loading ──────────────────────────────────────────────

    def _on_open(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, _("Select folder"))
        if not folder:
            return
        self._current_dir = folder
        idx = self._fs_model.index(folder)
        self._ui.treeDirectory.setCurrentIndex(idx)
        self._ui.treeDirectory.scrollTo(idx)
        self._reload_files()

    def _on_directory_selected(self) -> None:
        indexes = self._ui.treeDirectory.selectionModel().selectedIndexes()
        if not indexes:
            return
        path = self._fs_model.filePath(indexes[0])
        if not os.path.isdir(path):
            return
        self._current_dir = path
        self._reload_files()

    def _reload_files(self) -> None:
        if not self._current_dir or not os.path.isdir(self._current_dir):
            return
        mode = self._ui.cmbMode.currentIndex()
        recursive = self._ui.chkRecursive.isChecked()
        pattern = self._ui.edtFilter.text().strip() or None

        if recursive:
            entries = filetools.get_file_listing_recursive(
                self._current_dir, mode, pattern
            )
        else:
            entries = filetools.get_file_listing(self._current_dir, mode, pattern)

        self._ui.tblFiles.clear()
        self._ui.tblFiles.setHeaderLabels([_("Original"), _("Preview")])
        for name, path in entries:
            display = os.path.relpath(path, self._current_dir) if recursive else name
            item = QTreeWidgetItem([display, ""])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            if os.path.isdir(path):
                item.setForeground(0, _DIR_COLOR)
            self._ui.tblFiles.addTopLevelItem(item)
        self._ui.tblFiles.resizeColumnToContents(0)

        count = self._ui.tblFiles.topLevelItemCount()
        self.statusBar().showMessage(
            _("{path} — {n} item(s)").format(path=self._current_dir, n=count)
        )
        self._ui.btnRename.setEnabled(False)

        auto = self._ui.chkAutoPreview.isChecked()
        if auto and self._ui.tabWidget.currentIndex() == 0:
            self._on_preview()

    # ── Preview (pattern tab only) ────────────────────────────────────────────

    def _active_items(self) -> list[QTreeWidgetItem]:
        """Return selected top-level items, or all if nothing is selected."""
        selected = self._ui.tblFiles.selectedItems()
        if selected:
            return selected
        root = self._ui.tblFiles.invisibleRootItem()
        return [root.child(i) for i in range(root.childCount())]

    def _on_preview(self) -> None:
        if self._ui.tabWidget.currentIndex() != 0:
            return
        if not self._current_dir:
            return
        search = self._ui.cmbPatternSearch.currentText()
        replace = self._ui.cmbPatternDest.currentText()
        if not search:
            return

        keep_ext = self._ui.chkKeepExtension.isChecked()
        items = self._active_items()

        for counter, item in enumerate(items, start=1):
            path = item.data(0, Qt.ItemDataRole.UserRole)
            name = os.path.basename(path)

            if keep_ext:
                stem, stem_path, ext = filetools.cut_extension(name, path)
            else:
                stem, stem_path, ext = name, path, ""

            newname, _ = filetools.rename_using_patterns(
                stem, stem_path, search, replace, counter
            )

            if newname is not None:
                if keep_ext:
                    newname, _ = filetools.add_extension(newname, stem_path, ext)
                item.setText(1, newname)
            else:
                item.setText(1, "")

        self._ui.tblFiles.resizeColumnToContents(1)
        self._refresh_conflicts()

    def _refresh_conflicts(self) -> None:
        """Recompute conflict coloring and enable/disable Rename."""
        root = self._ui.tblFiles.invisibleRootItem()
        n = root.childCount()

        previews: list[tuple[str, str, QTreeWidgetItem]] = []
        for i in range(n):
            item = root.child(i)
            preview = item.text(1)
            if not preview:
                continue
            path = item.data(0, Qt.ItemDataRole.UserRole)
            previews.append((preview, path, item))

        if not previews:
            self._ui.btnRename.setEnabled(False)
            return

        # Detect duplicate targets (two entries → same destination path).
        # Use a case-normalised key so that on case-insensitive filesystems
        # "File.txt" and "file.txt" are treated as the same destination.
        target_map: dict[str, list[int]] = defaultdict(list)
        for idx, (preview, path, _) in enumerate(previews):
            parent = os.path.dirname(path)
            target = os.path.join(parent, preview)
            target_map[conflict_key(target, parent)].append(idx)

        conflict_indices: set[int] = set()
        for indices in target_map.values():
            if len(indices) > 1:
                conflict_indices.update(indices)

        # Detect targets that already exist on disk.
        # On case-insensitive filesystems a pure case-change ("File.txt" →
        # "file.txt") is a valid rename, not a conflict.
        for idx, (preview, path, _) in enumerate(previews):
            parent = os.path.dirname(path)
            target = os.path.join(parent, preview)
            if not same_file_path(target, path, parent) and os.path.exists(target):
                conflict_indices.add(idx)

        has_conflict = bool(conflict_indices)
        any_changed = False
        for idx, (preview, path, item) in enumerate(previews):
            if idx in conflict_indices:
                item.setForeground(1, _CONFLICT_COLOR)
            elif preview != os.path.basename(path):
                item.setForeground(1, _PREVIEW_COLOR)
                any_changed = True
            else:
                item.setForeground(1, _UNCHANGED_COLOR)

        self._ui.btnRename.setEnabled(any_changed and not has_conflict)

    def _on_clear_preview(self) -> None:
        root = self._ui.tblFiles.invisibleRootItem()
        for i in range(root.childCount()):
            root.child(i).setText(1, "")
        self._ui.btnRename.setEnabled(False)

    # ── Generic transformation applier ───────────────────────────────────────

    def _apply_to_all(self, transform: Callable[[str, str], str | None]) -> None:
        """Apply *transform(stem, stem_path) → newname* to selected rows (or all)."""
        keep_ext = self._ui.chkKeepExtension.isChecked()

        for item in self._active_items():
            path = item.data(0, Qt.ItemDataRole.UserRole)
            name = os.path.basename(path)

            if keep_ext:
                stem, stem_path, ext = filetools.cut_extension(name, path)
            else:
                stem, stem_path, ext = name, path, ""

            newname = transform(stem, stem_path)
            if newname is None:
                continue

            if keep_ext:
                newname, _ = filetools.add_extension(newname, stem_path, ext)

            item.setText(1, newname)

        self._ui.tblFiles.resizeColumnToContents(1)
        self._refresh_conflicts()

    # ── Substitution tab handlers ─────────────────────────────────────────────

    def _on_apply_spaces(self) -> None:
        mode = self._ui.cmbSpaces.currentIndex()
        self._apply_to_all(lambda n, p: filetools.replace_spaces(n, p, mode)[0])

    def _on_apply_caps(self) -> None:
        mode = self._ui.cmbCaps.currentIndex()
        self._apply_to_all(lambda n, p: filetools.replace_capitalization(n, p, mode)[0])

    def _on_apply_replace(self) -> None:
        orig = self._ui.edtReplaceOrig.text()
        dest = self._ui.edtReplaceDest.text()
        self._apply_to_all(lambda n, p: filetools.replace_with(n, p, orig, dest)[0])

    def _on_remove_accents(self) -> None:
        self._apply_to_all(lambda n, p: filetools.replace_accents(n, p)[0])

    def _on_remove_duplicates(self) -> None:
        self._apply_to_all(lambda n, p: filetools.replace_duplicated(n, p)[0])

    # ── Insert / Delete tab handlers ──────────────────────────────────────────

    def _on_insert(self) -> None:
        text = self._ui.edtInsertText.text()
        pos = self._ui.spnInsertPos.value()
        self._apply_to_all(lambda n, p: filetools.insert_at(n, p, text, pos)[0])

    def _on_delete(self) -> None:
        frm = self._ui.spnDeleteFrom.value()
        to = self._ui.spnDeleteTo.value()
        self._apply_to_all(lambda n, p: filetools.delete_from(n, p, frm, to)[0])

    # ── Manual tab handler ────────────────────────────────────────────────────

    def _on_apply_manual(self) -> None:
        selected = self._ui.tblFiles.selectedItems()
        if not selected:
            return
        # Get the top-level item (column 0 of the selected row)
        item = selected[0]
        while item.parent():
            item = item.parent()
        text = self._ui.edtManualName.text().strip()
        if text:
            item.setText(1, text)
            item.setForeground(1, _PREVIEW_COLOR)
            self._refresh_conflicts()

    # ── Pattern presets ───────────────────────────────────────────────────────

    def _on_save_pattern(self) -> None:
        search = self._ui.cmbPatternSearch.currentText()
        replace = self._ui.cmbPatternDest.currentText()
        if search:
            self._presets.add("search", search)
        if replace:
            self._presets.add("replace", replace)
        self._populate_pattern_combos()

    # ── Rename / Undo ─────────────────────────────────────────────────────────

    def _on_rename(self) -> None:
        renames: list[tuple[str, str]] = []
        for item in self._active_items():
            preview = item.text(1)
            if not preview:
                continue
            original_path: str = item.data(0, Qt.ItemDataRole.UserRole)
            new_path = os.path.join(os.path.dirname(original_path), preview)
            if original_path != new_path:
                renames.append((original_path, new_path))

        if not renames:
            return

        errors: list[str] = []
        done: list[tuple[str, str]] = []
        for original, new in renames:
            ok, err = filetools.rename_file(original, new)
            if ok:
                done.append((original, new))
            else:
                errors.append(f"{os.path.basename(original)}: {err}")

        if done:
            self._undo.add_batch(done)
            self._ui.btnUndo.setEnabled(True)

        if errors:
            QMessageBox.warning(
                self,
                _("Rename errors"),
                "\n".join(errors),
                QMessageBox.StandardButton.Ok,
            )

        self._on_clear_preview()
        self._reload_files()

    def _on_undo(self) -> None:
        self._undo.undo()
        self._ui.btnUndo.setEnabled(self._undo.can_undo())
        self._reload_files()

    # ── Auto-preview / tab change ─────────────────────────────────────────────

    def _on_auto_preview_toggled(self, checked: bool) -> None:
        if checked:
            self._on_preview()

    def _on_tab_changed(self, _idx: int) -> None:
        if self._ui.chkAutoPreview.isChecked():
            self._on_preview()

    # ── Menu handlers ─────────────────────────────────────────────────────────

    def _on_quit(self) -> None:
        QApplication.quit()

    def _on_settings(self) -> None:
        SettingsDialog(self).exec()

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            _("About PBRenamer"),
            "<b>PBRenamer</b> 0.1.0<br>"
            "A graphical batch file renaming utility.<br><br>"
            "© 2024 Marcel Spock &lt;mrspock@cardolan.net&gt;<br>"
            "License: GPLv3",
        )
