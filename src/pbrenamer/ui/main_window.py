"""Main application window."""

from __future__ import annotations

import os
import re
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
    QStyledItemDelegate,
    QTreeWidgetItem,
)

from pbrenamer.core import filetools
from pbrenamer.core.undo import UndoManager
from pbrenamer.platform.fs import conflict_key, same_file_path
from pbrenamer.ui.main_window_ui import Ui_MainWindow
from pbrenamer.ui.pattern_help import (
    REPLACE_HTML,
    SEARCH_HTML,
    PatternHelpDialog,
    make_add_icon,
    make_help_icon,
)
from pbrenamer.ui.presets import PatternPresets
from pbrenamer.ui.settings_dialog import SettingsDialog


class _SearchModeDelegate(QStyledItemDelegate):
    """Appends a dimmed mode label on the right of each search history item."""

    _LABELS = {"pattern": "pat", "regex": "RE", "plain": "txt"}

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        mode = index.data(Qt.ItemDataRole.UserRole)
        label = self._LABELS.get(mode, "")
        if not label:
            return
        painter.save()
        color = option.palette.color(option.palette.ColorRole.Text)
        color.setAlphaF(0.5)
        painter.setPen(color)
        font = painter.font()
        font.setItalic(True)
        painter.setFont(font)
        painter.drawText(
            option.rect.adjusted(0, 0, -6, 0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            label,
        )
        painter.restore()


_PREVIEW_COLOR = QColor("#0066cc")
_UNCHANGED_COLOR = QColor("#888888")
_DIR_COLOR = QColor("#aa6600")
_CONFLICT_COLOR = QColor("#cc0000")
_INVALID_REGEX_STYLE = "QLineEdit { background-color: #ffaaaa; }"


class MainWindow(QMainWindow):
    """Top-level window for PBRenamer."""

    def __init__(self, start_dir: str | None = None) -> None:
        super().__init__()
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)

        self._current_dir: str | None = None
        self._undo = UndoManager()
        self._presets = PatternPresets()
        self._search_help: PatternHelpDialog | None = None
        self._replace_help: PatternHelpDialog | None = None

        self._setup_directory_tree()
        self._populate_pattern_combos()
        self._setup_help_buttons()
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

    def _setup_help_buttons(self) -> None:
        help_icon = make_help_icon()
        self._ui.btnSearchHelp.setIcon(help_icon)
        self._ui.btnReplaceHelp.setIcon(help_icon)
        add_icon = make_add_icon()
        self._ui.btnSearchAdd.setIcon(add_icon)
        self._ui.btnReplaceAdd.setIcon(add_icon)
        self._ui.cmbPatternSearch.view().setItemDelegate(
            _SearchModeDelegate(self._ui.cmbPatternSearch)
        )

    def _populate_pattern_combos(self) -> None:
        self._ui.cmbPatternSearch.clear()
        for mode, pattern in self._presets.get_search():
            self._ui.cmbPatternSearch.addItem(pattern, mode)
        self._ui.cmbPatternDest.clear()
        for pattern in self._presets.get_replace():
            self._ui.cmbPatternDest.addItem(pattern)
        self._update_add_buttons()

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

        # Patterns tab — post-processing
        self._ui.chkRemoveAccents.toggled.connect(self._on_post_process_changed)
        self._ui.chkRemoveDuplicates.toggled.connect(self._on_post_process_changed)
        self._ui.cmbCaps.currentIndexChanged.connect(self._on_post_process_changed)

        # Insert/Delete tab
        self._ui.btnInsert.clicked.connect(self._on_insert)
        self._ui.btnDelete.clicked.connect(self._on_delete)

        # Manual tab
        self._ui.btnApplyManual.clicked.connect(self._on_apply_manual)

        # Pattern add/help buttons
        self._ui.btnSearchAdd.clicked.connect(self._on_add_search)
        self._ui.btnReplaceAdd.clicked.connect(self._on_add_replace)
        self._ui.btnSearchHelp.clicked.connect(self._on_search_help)
        self._ui.btnReplaceHelp.clicked.connect(self._on_replace_help)

        # Search mode (Pattern / Regex / Plain text)
        for rad in (self._ui.radPattern, self._ui.radRegex, self._ui.radPlainText):
            rad.toggled.connect(lambda _: self._on_mode_changed())
        self._ui.cmbPatternSearch.activated.connect(self._on_search_preset_selected)
        self._ui.cmbPatternDest.activated.connect(self._on_replace_preset_selected)
        self._ui.cmbPatternSearch.currentTextChanged.connect(
            lambda _: self._on_search_text_changed()
        )
        self._ui.cmbPatternDest.currentTextChanged.connect(
            lambda _: self._update_replace_add_button()
        )

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

    def _validate_search_input(self) -> bool:
        """Validate the search combo when in regex mode; colour it red if invalid.

        Returns True if the input is valid for the active mode.
        """
        if not self._ui.radRegex.isChecked():
            self._ui.cmbPatternSearch.lineEdit().setStyleSheet("")
            return True
        pattern = self._ui.cmbPatternSearch.currentText()
        line_edit = self._ui.cmbPatternSearch.lineEdit()
        if not pattern:
            line_edit.setStyleSheet("")
            return True
        try:
            re.compile(pattern)
            line_edit.setStyleSheet("")
            return True
        except re.error:
            line_edit.setStyleSheet(_INVALID_REGEX_STYLE)
            return False

    def _on_search_text_changed(self) -> None:
        self._validate_search_input()
        self._update_search_add_button()

    def _on_mode_changed(self) -> None:
        self._validate_search_input()
        self._update_search_add_button()
        if self._ui.chkAutoPreview.isChecked():
            self._on_preview()

    def _update_add_buttons(self) -> None:
        self._update_search_add_button()
        self._update_replace_add_button()

    def _update_search_add_button(self) -> None:
        pattern = self._ui.cmbPatternSearch.currentText().strip()
        if not pattern:
            self._ui.btnSearchAdd.setEnabled(False)
            return
        if self._ui.radRegex.isChecked():
            try:
                re.compile(pattern)
            except re.error:
                self._ui.btnSearchAdd.setEnabled(False)
                return
        mode = self._current_search_mode()
        already = any(
            self._ui.cmbPatternSearch.itemText(i) == pattern
            and self._ui.cmbPatternSearch.itemData(i) == mode
            for i in range(self._ui.cmbPatternSearch.count())
        )
        self._ui.btnSearchAdd.setEnabled(not already)

    def _update_replace_add_button(self) -> None:
        pattern = self._ui.cmbPatternDest.currentText().strip()
        if not pattern:
            self._ui.btnReplaceAdd.setEnabled(False)
            return
        already = any(
            self._ui.cmbPatternDest.itemText(i) == pattern
            for i in range(self._ui.cmbPatternDest.count())
        )
        self._ui.btnReplaceAdd.setEnabled(not already)

    def _on_preview(self) -> None:
        if self._ui.tabWidget.currentIndex() != 0:
            return
        if not self._current_dir:
            return
        search = self._ui.cmbPatternSearch.currentText()
        replace = self._ui.cmbPatternDest.currentText()
        if not search:
            return

        use_regex = self._ui.radRegex.isChecked()
        use_plain = self._ui.radPlainText.isChecked()
        if use_regex and not self._validate_search_input():
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

            if use_regex:
                newname, _ = filetools.rename_using_regex(
                    stem, stem_path, search, replace
                )
            elif use_plain:
                newname, _ = filetools.rename_using_plain_text(
                    stem, stem_path, search, replace
                )
            else:
                newname, _ = filetools.rename_using_patterns(
                    stem, stem_path, search, replace, counter
                )

            if newname is not None:
                if self._ui.chkRemoveAccents.isChecked():
                    newname, _ = filetools.replace_accents(newname, stem_path)
                if self._ui.chkRemoveDuplicates.isChecked():
                    newname, _ = filetools.replace_duplicated(newname, stem_path)
                caps_idx = self._ui.cmbCaps.currentIndex()
                if caps_idx > 0:
                    newname, _ = filetools.replace_capitalization(
                        newname, stem_path, caps_idx - 1
                    )
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

    # ── Pattern help dialogs ──────────────────────────────────────────────────

    def _on_search_help(self) -> None:
        if self._search_help is None:
            self._search_help = PatternHelpDialog(SEARCH_HTML, _("Search — Help"), self)
        if self._search_help.isVisible():
            self._search_help.raise_()
            self._search_help.activateWindow()
        else:
            self._search_help.show()

    def _on_replace_help(self) -> None:
        if self._replace_help is None:
            self._replace_help = PatternHelpDialog(
                REPLACE_HTML, _("Replace — Help"), self
            )
        if self._replace_help.isVisible():
            self._replace_help.raise_()
            self._replace_help.activateWindow()
        else:
            self._replace_help.show()

    # ── Patterns tab — post-processing ───────────────────────────────────────

    def _on_post_process_changed(self) -> None:
        if self._ui.chkAutoPreview.isChecked():
            self._on_preview()

    # ── Pattern history ───────────────────────────────────────────────────────

    def _current_search_mode(self) -> str:
        if self._ui.radRegex.isChecked():
            return "regex"
        if self._ui.radPlainText.isChecked():
            return "plain"
        return "pattern"

    def _on_add_search(self) -> None:
        pattern = self._ui.cmbPatternSearch.currentText().strip()
        if not pattern:
            return
        mode = self._current_search_mode()
        self._presets.add_search(mode, pattern)
        self._populate_pattern_combos()
        self._ui.cmbPatternSearch.setCurrentIndex(0)

    def _on_add_replace(self) -> None:
        pattern = self._ui.cmbPatternDest.currentText().strip()
        if not pattern:
            return
        self._presets.add_replace(pattern)
        self._populate_pattern_combos()
        self._ui.cmbPatternDest.setCurrentIndex(0)

    def _on_search_preset_selected(self, index: int) -> None:
        if index < 0:
            return
        mode = self._ui.cmbPatternSearch.itemData(index)
        pattern = self._ui.cmbPatternSearch.itemText(index)
        if mode == "regex":
            self._ui.radRegex.setChecked(True)
        elif mode == "plain":
            self._ui.radPlainText.setChecked(True)
        elif mode == "pattern":
            self._ui.radPattern.setChecked(True)
        else:
            return  # unknown mode — do not promote
        self._presets.add_search(mode, pattern)
        self._populate_pattern_combos()
        self._ui.cmbPatternSearch.setCurrentIndex(0)

    def _on_replace_preset_selected(self, index: int) -> None:
        if index < 0:
            return
        pattern = self._ui.cmbPatternDest.itemText(index)
        if not pattern:
            return
        self._presets.add_replace(pattern)
        self._populate_pattern_combos()
        self._ui.cmbPatternDest.setCurrentIndex(0)

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
        from pbrenamer import __version__

        QMessageBox.about(
            self,
            _("About PBRenamer"),
            "<b>PBRenamer</b> {version}<br>"
            "{description}<br><br>"
            "© 2026 Marcel Spock &lt;mrspock@cardolan.net&gt;<br>"
            "{license}".format(
                version=__version__,
                description=_("A graphical batch file renaming utility."),
                license=_("License: GPLv3"),
            ),
        )
