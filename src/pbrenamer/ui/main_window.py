"""Main application window."""

from __future__ import annotations

import logging
import os
import re
from collections import defaultdict

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
from pbrenamer.core import replacement as _repl
from pbrenamer.core.undo import UndoManager
from pbrenamer.platform.fs import conflict_key, same_file_path
from pbrenamer.ui.about_dialog import AboutDialog
from pbrenamer.ui.history_dialog import HistoryDialog
from pbrenamer.ui.main_window_ui import Ui_MainWindow
from pbrenamer.ui.pattern_help import (
    PatternHelpDialog,
    make_add_icon,
    make_help_icon,
    replace_html,
    search_html,
)
from pbrenamer.ui.presets import PatternPresets
from pbrenamer.ui.settings_dialog import SettingsDialog
from pbrenamer.ui.widgets import WhitespaceLineEdit
from pbrenamer.ui.window_state import WindowState

_log = logging.getLogger(__name__)


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
_ERROR_COLOR = QColor("#cc0000")
_INVALID_STYLE = "QLineEdit { background-color: #ffaaaa; }"


class MainWindow(QMainWindow):
    """Top-level window for PBRenamer."""

    def __init__(self, start_dir: str | None = None) -> None:
        super().__init__()
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)

        self._current_dir: str | None = None
        self._undo = UndoManager()
        self._presets = PatternPresets()
        self._window_state = WindowState()
        self._search_help: PatternHelpDialog | None = None
        self._replace_help: PatternHelpDialog | None = None

        self._setup_directory_tree()
        self._populate_pattern_combos()
        self._setup_help_buttons()
        self._connect_signals()
        self._ui.splitterMain.setSizes([220, 880])
        self._ui.splitterRight.setSizes([380, 200])
        self._restore_window_state()
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
        self._ui.cmbPatternSearch.setLineEdit(WhitespaceLineEdit())
        self._ui.cmbPatternDest.setLineEdit(WhitespaceLineEdit())

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

        # Patterns tab — separator shortcuts
        self._ui.cmbSpaces.activated.connect(self._on_spaces_shortcut)

        # Patterns tab — post-processing
        self._ui.chkRemoveAccents.toggled.connect(self._on_post_process_changed)
        self._ui.chkRemoveDuplicates.toggled.connect(self._on_post_process_changed)
        self._ui.cmbCaps.currentIndexChanged.connect(self._on_post_process_changed)

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
            lambda _: self._on_replace_text_changed()
        )

        # Options that trigger a file list reload
        self._ui.cmbMode.currentIndexChanged.connect(self._reload_files)
        self._ui.chkRecursive.toggled.connect(self._reload_files)
        self._ui.edtFilter.editingFinished.connect(self._reload_files)

        # Auto-preview
        self._ui.chkAutoPreview.toggled.connect(self._on_auto_preview_toggled)

        # Menu bar
        self._ui.actionQuit.triggered.connect(self._on_quit)
        self._ui.actionHistory.triggered.connect(self._on_history)
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
        _log.info("Directory selected: %s", path)
        self._current_dir = path
        self._reload_files()

    def _reload_files(self) -> None:
        if not self._current_dir or not os.path.isdir(self._current_dir):
            return
        mode = self._ui.cmbMode.currentIndex()
        recursive = self._ui.chkRecursive.isChecked()
        pattern = self._ui.edtFilter.text().strip() or None

        _log.debug(
            "Reloading files: dir=%s mode=%d recursive=%s pattern=%r",
            self._current_dir,
            mode,
            recursive,
            pattern,
        )

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
        _log.debug("Loaded %d item(s) from %s", count, self._current_dir)
        self.statusBar().showMessage(
            _("{path} — {n} item(s)").format(path=self._current_dir, n=count)
        )
        self._ui.btnRename.setEnabled(False)

        if self._ui.chkAutoPreview.isChecked():
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
        """Validate the search field when in regex mode; colour it red if invalid.

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
            line_edit.setStyleSheet(_INVALID_STYLE)
            return False

    def _validate_replace_input(self) -> bool:
        """Validate the replacement field syntax and mode compatibility.

        Returns True if valid.
        """
        template = self._ui.cmbPatternDest.currentText()
        line_edit = self._ui.cmbPatternDest.lineEdit()
        if not template:
            line_edit.setStyleSheet("")
            return True
        try:
            tokens = _repl.parse(template)
        except _repl.ReplacementSyntaxError:
            line_edit.setStyleSheet(_INVALID_STYLE)
            return False
        errors = _repl.validate(tokens, self._current_search_mode())
        if errors:
            line_edit.setStyleSheet(_INVALID_STYLE)
            return False
        line_edit.setStyleSheet("")
        return True

    def _on_search_text_changed(self) -> None:
        self._validate_search_input()
        self._update_search_add_button()

    def _on_replace_text_changed(self) -> None:
        self._validate_replace_input()
        self._update_replace_add_button()

    def _on_mode_changed(self) -> None:
        self._validate_search_input()
        self._validate_replace_input()
        self._update_search_add_button()
        if self._ui.chkAutoPreview.isChecked():
            self._on_preview()

    def _update_add_buttons(self) -> None:
        self._update_search_add_button()
        self._update_replace_add_button()

    def _update_search_add_button(self) -> None:
        pattern = self._ui.cmbPatternSearch.currentText()
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
        pattern = self._ui.cmbPatternDest.currentText()
        if not pattern or not self._validate_replace_input():
            self._ui.btnReplaceAdd.setEnabled(False)
            return
        already = any(
            self._ui.cmbPatternDest.itemText(i) == pattern
            for i in range(self._ui.cmbPatternDest.count())
        )
        self._ui.btnReplaceAdd.setEnabled(not already)

    def _do_rename(
        self,
        use_regex: bool,
        use_plain: bool,
        stem: str,
        orig_path: str,
        search: str,
        replace: str,
        counter: int,
        *,
        newnum: int | None = None,
    ) -> tuple[str | None, str | None]:
        """Dispatch to the appropriate filetools rename function.

        *orig_path* must be the actual file path (with extension) so that
        metadata fields such as {mdatetime} and {ex:…} can stat the file.
        """
        if use_regex:
            return filetools.rename_using_regex(
                stem, orig_path, search, replace, newnum=newnum
            )
        if use_plain:
            return filetools.rename_using_plain_text(
                stem, orig_path, search, replace, newnum=newnum
            )
        return filetools.rename_using_patterns(
            stem, orig_path, search, replace, counter, newnum=newnum
        )

    def _apply_postproc(self, name: str, path: str) -> str:
        """Apply active post-processing options (accents, duplicates, caps)."""
        if self._ui.chkRemoveAccents.isChecked():
            name, _op = filetools.replace_accents(name, path)
        if self._ui.chkRemoveDuplicates.isChecked():
            name, _op = filetools.replace_duplicated(name, path)
        caps_idx = self._ui.cmbCaps.currentIndex()
        if caps_idx > 0:
            name, _op = filetools.replace_capitalization(name, path, caps_idx - 1)
        return name

    def _make_newnum_state(self, replace: str) -> _repl.NewNumState | None:
        """Return a NewNumState if *replace* contains {newnum}, else None."""
        try:
            segments = _repl.parse(replace)
        except _repl.ReplacementSyntaxError:
            return None
        for seg in segments:
            if isinstance(seg, _repl.FieldSegment) and seg.name == "newnum":
                start = 1
                if seg.default is not None:
                    try:
                        start = int(seg.default)
                    except ValueError:
                        pass
                return _repl.NewNumState(start)
        return None

    def _on_preview(self) -> None:
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
        if not self._validate_replace_input():
            return

        mode_label = "regex" if use_regex else ("plain" if use_plain else "pattern")
        keep_ext = self._ui.chkKeepExtension.isChecked()
        items = self._active_items()
        _log.info(
            "Preview: %d item(s), mode=%s, search=%r, replace=%r",
            len(items),
            mode_label,
            search,
            replace,
        )
        newnum_state = self._make_newnum_state(replace)

        for counter, item in enumerate(items, start=1):
            path = item.data(0, Qt.ItemDataRole.UserRole)
            name = os.path.basename(path)

            if keep_ext:
                stem, stem_path, ext = filetools.cut_extension(name, path)
            else:
                stem, stem_path, ext = name, path, ""

            field_error = False
            field_error_name = ""
            newname = None

            if newnum_state is not None:
                dir_path = os.path.dirname(path)
                k = newnum_state.current
                while True:
                    try:
                        raw, _op = self._do_rename(
                            use_regex,
                            use_plain,
                            stem,
                            path,
                            search,
                            replace,
                            counter,
                            newnum=k,
                        )
                    except _repl.FieldResolutionError as err:
                        field_error = True
                        field_error_name = err.field
                        break
                    if raw is None:
                        break
                    processed = self._apply_postproc(raw, stem_path)
                    candidate = filetools.add_extension(processed, stem_path, ext)[0]
                    cand_path = os.path.join(dir_path, candidate)
                    if candidate not in newnum_state.reserved and (
                        not os.path.exists(cand_path)
                        or same_file_path(cand_path, path, dir_path)
                    ):
                        newnum_state.reserved.add(candidate)
                        newnum_state.current = k + 1
                        newname = candidate
                        break
                    k += 1
            else:
                try:
                    raw, _op = self._do_rename(
                        use_regex,
                        use_plain,
                        stem,
                        path,
                        search,
                        replace,
                        counter,
                    )
                except _repl.FieldResolutionError as err:
                    field_error = True
                    field_error_name = err.field
                    raw = None
                if raw is not None:
                    processed = self._apply_postproc(raw, stem_path)
                    newname = filetools.add_extension(processed, stem_path, ext)[0]

            if newname is not None:
                _log.debug("Preview: %r → %r", name, newname)
                item.setText(1, newname)
                item.setData(1, Qt.ItemDataRole.UserRole, False)
            elif field_error:
                _log.debug("Preview: %r — field %r unavailable", name, field_error_name)
                item.setText(
                    1, _("⚠ {field} unavailable").format(field=field_error_name)
                )
                item.setData(1, Qt.ItemDataRole.UserRole, True)
            else:
                item.setText(1, "")
                item.setData(1, Qt.ItemDataRole.UserRole, False)

        self._ui.tblFiles.resizeColumnToContents(1)
        self._refresh_conflicts()

    def _refresh_conflicts(self) -> None:
        """Recompute conflict coloring and enable/disable Rename."""
        root = self._ui.tblFiles.invisibleRootItem()
        n = root.childCount()

        previews: list[tuple[str, str, QTreeWidgetItem, bool]] = []
        has_field_error = False
        for i in range(n):
            item = root.child(i)
            preview = item.text(1)
            if not preview:
                continue
            path = item.data(0, Qt.ItemDataRole.UserRole)
            is_error = bool(item.data(1, Qt.ItemDataRole.UserRole))
            if is_error:
                has_field_error = True
                item.setForeground(1, _ERROR_COLOR)
            previews.append((preview, path, item, is_error))

        if not previews or all(e for *_, e in previews):
            self._ui.btnRename.setEnabled(False)
            return

        # Detect duplicate targets among non-error entries.
        valid = [(p, path, item, e) for p, path, item, e in previews if not e]

        target_map: dict[str, list[int]] = defaultdict(list)
        for idx, (preview, path, _, _) in enumerate(valid):
            parent = os.path.dirname(path)
            target = os.path.join(parent, preview)
            target_map[conflict_key(target, parent)].append(idx)

        conflict_indices: set[int] = set()
        for indices in target_map.values():
            if len(indices) > 1:
                conflict_indices.update(indices)

        for idx, (preview, path, _, _) in enumerate(valid):
            parent = os.path.dirname(path)
            target = os.path.join(parent, preview)
            if not same_file_path(target, path, parent) and os.path.exists(target):
                conflict_indices.add(idx)

        has_conflict = bool(conflict_indices)
        any_changed = False
        for idx, (preview, path, item, _) in enumerate(valid):
            if idx in conflict_indices:
                item.setForeground(1, _CONFLICT_COLOR)
            elif preview != os.path.basename(path):
                item.setForeground(1, _PREVIEW_COLOR)
                any_changed = True
            else:
                item.setForeground(1, _UNCHANGED_COLOR)

        self._ui.btnRename.setEnabled(
            any_changed and not has_conflict and not has_field_error
        )

    def _on_clear_preview(self) -> None:
        root = self._ui.tblFiles.invisibleRootItem()
        for i in range(root.childCount()):
            root.child(i).setText(1, "")
        self._ui.btnRename.setEnabled(False)

    # ── Patterns tab — separator shortcuts ───────────────────────────────────

    # (search regex, replacement) indexed to match cmbSpaces items 1..6
    _SPACES_SHORTCUTS: tuple[tuple[str, str], ...] = (
        (" ", "_"),
        ("_", " "),
        (" ", "."),
        (r"\.", " "),
        (" ", "-"),
        ("-", " "),
    )

    def _on_spaces_shortcut(self, index: int) -> None:
        if index <= 0:
            return
        search, replace = self._SPACES_SHORTCUTS[index - 1]
        self._ui.radRegex.setChecked(True)
        self._ui.cmbPatternSearch.setCurrentText(search)
        self._ui.cmbPatternDest.setCurrentText(replace)
        self._ui.cmbSpaces.setCurrentIndex(0)

    # ── Pattern help dialogs ──────────────────────────────────────────────────

    def _on_search_help(self) -> None:
        if self._search_help is None:
            self._search_help = PatternHelpDialog(
                search_html(),
                _("Search — Help"),
                "help_search",
                self._window_state,
                self,
            )
        if self._search_help.isVisible():
            self._search_help.raise_()
            self._search_help.activateWindow()
        else:
            self._search_help.show()

    def _on_replace_help(self) -> None:
        if self._replace_help is None:
            self._replace_help = PatternHelpDialog(
                replace_html(),
                _("Replace — Help"),
                "help_replace",
                self._window_state,
                self,
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
        pattern = self._ui.cmbPatternSearch.currentText()
        if not pattern:
            return
        mode = self._current_search_mode()
        self._presets.add_search(mode, pattern)
        self._populate_pattern_combos()
        self._ui.cmbPatternSearch.setCurrentIndex(0)

    def _on_add_replace(self) -> None:
        pattern = self._ui.cmbPatternDest.currentText()
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

        _log.info("Renaming %d file(s)", len(renames))
        errors: list[str] = []
        done: list[tuple[str, str]] = []
        for original, new in renames:
            ok, err = filetools.rename_file(original, new)
            if ok:
                done.append((original, new))
            else:
                errors.append(f"{os.path.basename(original)}: {err}")

        _log.info("Renamed %d file(s), %d error(s)", len(done), len(errors))
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
        _log.info("Undoing last rename batch")
        self._undo.undo()
        self._ui.btnUndo.setEnabled(self._undo.can_undo())
        self._reload_files()

    # ── Window state (geometry + splitters) ──────────────────────────────────

    def _restore_window_state(self) -> None:
        geo, sm, sr = self._window_state.load()
        if geo:
            self.restoreGeometry(geo)
        if sm:
            self._ui.splitterMain.restoreState(sm)
        if sr:
            self._ui.splitterRight.restoreState(sr)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._window_state.save(
            self.saveGeometry(),
            self._ui.splitterMain.saveState(),
            self._ui.splitterRight.saveState(),
        )
        super().closeEvent(event)

    # ── Auto-preview / tab change ─────────────────────────────────────────────

    def _on_auto_preview_toggled(self, checked: bool) -> None:
        if checked:
            self._on_preview()

    # ── Menu handlers ─────────────────────────────────────────────────────────

    def _on_quit(self) -> None:
        QApplication.quit()

    def _on_history(self) -> None:
        HistoryDialog(self._presets, self).exec()
        self._populate_pattern_combos()

    def _on_settings(self) -> None:
        SettingsDialog(self).exec()

    def _on_about(self) -> None:
        AboutDialog(self).exec()
