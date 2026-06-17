"""Main application window."""

from __future__ import annotations

import logging
import os
import re
import time
from collections import defaultdict

from PySide6.QtCore import QDir, QFileSystemWatcher, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFileSystemModel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStyledItemDelegate,
    QTreeWidgetItem,
)

import pbrenamer.settings as _cfg
from pbrenamer.core import filetools
from pbrenamer.core import replacement as _repl
from pbrenamer.core.undo import UndoManager
from pbrenamer.platform import system_bookmarks
from pbrenamer.platform.fs import conflict_key, same_file_path
from pbrenamer.ui.about_dialog import AboutDialog
from pbrenamer.ui.file_info_window import FileInfoWindow
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
from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog
from pbrenamer.ui.widgets import WhitespaceLineEdit
from pbrenamer.ui.window_state import WindowState

_log = logging.getLogger(__name__)
_SAVE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


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
        self._file_info: FileInfoWindow | None = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._on_preview)

        self._fs_watcher = QFileSystemWatcher(self)
        self._fs_watcher.directoryChanged.connect(self._on_dir_changed_external)
        self._fs_change_timer = QTimer(self)
        self._fs_change_timer.setSingleShot(True)
        self._fs_change_timer.timeout.connect(self._on_fs_change)
        self._last_internal_reload: float = 0.0

        self._geometry_restored = False

        self._setup_directory_tree()
        self._populate_pattern_combos()
        self._populate_named_saves()
        self._setup_help_buttons()
        self._connect_signals()
        self._ui.splitterMain.setSizes([220, 880])
        self._ui.splitterRight.setSizes([380, 200])
        if _cfg.get_restore_toolbar_state():
            self._restore_toolbar_state()
        if start_dir:
            initial_dir = start_dir
        elif _cfg.get_restore_last_dir():
            initial_dir = _cfg.get_last_dir() or os.getcwd()
        else:
            initial_dir = os.getcwd()
        QTimer.singleShot(0, lambda: self._startup_navigate(initial_dir))

    # ── Initial setup ─────────────────────────────────────────────────────────

    def _setup_directory_tree(self) -> None:
        self._fs_model = QFileSystemModel(self)
        root_idx = self._fs_model.setRootPath(QDir.rootPath())
        self._fs_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot)
        self._ui.treeDirectory.setModel(self._fs_model)
        self._ui.treeDirectory.setRootIndex(root_idx)
        for col in range(1, self._fs_model.columnCount()):
            self._ui.treeDirectory.hideColumn(col)

    def _startup_navigate(self, path: str) -> None:
        """Navigate to *path* at startup, loading the file list even when the
        QFileSystemModel hasn't populated the index for *path* yet (deep paths
        are loaded lazily in background threads; index() returns invalid until
        each ancestor has been fetched, so selectionChanged never fires and
        _reload_files is never called).  Fall back to a direct assignment."""
        self._navigate_to(path)
        if os.path.isdir(path) and self._current_dir != path:
            self._current_dir = path
            self._reload_files()

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

        # Patterns tab — post-processing
        self._ui.cmbSpaces.currentIndexChanged.connect(self._on_post_process_changed)
        self._ui.chkRemoveAccents.toggled.connect(self._on_post_process_changed)
        self._ui.chkRemoveDuplicates.toggled.connect(self._on_post_process_changed)
        self._ui.cmbCaps.currentIndexChanged.connect(self._on_post_process_changed)

        # Pattern add/help buttons
        self._ui.btnSearchAdd.clicked.connect(self._on_add_search)
        self._ui.btnReplaceAdd.clicked.connect(self._on_add_replace)
        self._ui.btnSearchHelp.clicked.connect(self._on_search_help)
        self._ui.btnReplaceHelp.clicked.connect(self._on_replace_help)

        # Named saves
        self._ui.cmbNamedSaves.currentTextChanged.connect(self._on_save_name_changed)
        self._ui.cmbNamedSaves.activated.connect(self._on_named_save_selected)
        self._ui.btnSaveSave.clicked.connect(self._on_save_save)
        self._ui.btnSaveDelete.clicked.connect(self._on_save_delete)

        # Search mode (Pattern / Regex / Plain text) + case sensitivity
        for rad in (self._ui.radPattern, self._ui.radRegex, self._ui.radPlainText):
            rad.toggled.connect(lambda _: self._on_mode_changed())
        self._ui.chkCaseInsensitive.toggled.connect(lambda _: self._on_mode_changed())
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
        self._ui.actionEditShortcuts.triggered.connect(self._on_edit_shortcuts)
        self._ui.actionFileInfo.triggered.connect(self._on_file_info)
        self._ui.menuShortcuts.aboutToShow.connect(self._build_shortcuts_menu)

        # Directory tree context menu
        self._ui.treeDirectory.customContextMenuRequested.connect(
            self._on_tree_context_menu
        )

        # File list context menu + selection tracking for info window
        self._ui.tblFiles.customContextMenuRequested.connect(
            self._on_files_context_menu
        )
        self._ui.tblFiles.itemSelectionChanged.connect(self._on_file_selection_changed)
        self._ui.tblFiles.itemDoubleClicked.connect(self._on_file_double_clicked)

    # ── Filesystem change notifications ──────────────────────────────────────

    def _on_dir_changed_external(self) -> None:
        if time.monotonic() - self._last_internal_reload < 0.5:
            return
        self._fs_change_timer.start(200)

    def _on_fs_change(self) -> None:
        if not self._current_dir or not os.path.isdir(self._current_dir):
            return
        selected_paths = {
            item.data(0, Qt.ItemDataRole.UserRole)
            for item in self._ui.tblFiles.selectedItems()
        }
        self._reload_files()
        if selected_paths:
            root = self._ui.tblFiles.invisibleRootItem()
            self._ui.tblFiles.blockSignals(True)
            for i in range(root.childCount()):
                item = root.child(i)
                if item.data(0, Qt.ItemDataRole.UserRole) in selected_paths:
                    item.setSelected(True)
            self._ui.tblFiles.blockSignals(False)
            self._on_file_selection_changed()

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
        if path == self._current_dir:
            return
        _log.info("Directory selected: %s", path)
        self._current_dir = path
        self._reload_files()

    def _reload_files(self) -> None:
        if not self._current_dir or not os.path.isdir(self._current_dir):
            return
        self._last_internal_reload = time.monotonic()
        self._fs_change_timer.stop()
        watched = self._fs_watcher.directories()
        if list(watched) != [self._current_dir]:
            if watched:
                self._fs_watcher.removePaths(list(watched))
            self._fs_watcher.addPath(self._current_dir)
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
        if self._ui.chkAutoPreview.isChecked():
            self._preview_timer.start(_cfg.get_preview_delay())

    def _on_replace_text_changed(self) -> None:
        self._validate_replace_input()
        self._update_replace_add_button()
        if self._ui.chkAutoPreview.isChecked():
            self._preview_timer.start(_cfg.get_preview_delay())

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
        case_insensitive: bool = False,
    ) -> tuple[str | None, str | None]:
        """Dispatch to the appropriate filetools rename function.

        *orig_path* must be the actual file path (with extension) so that
        metadata fields such as {mdatetime} and {im:…}/{au:…} can stat the file.
        """
        if use_regex:
            return filetools.rename_using_regex(
                stem,
                orig_path,
                search,
                replace,
                newnum=newnum,
                case_insensitive=case_insensitive,
            )
        if use_plain:
            return filetools.rename_using_plain_text(
                stem,
                orig_path,
                search,
                replace,
                newnum=newnum,
                case_insensitive=case_insensitive,
            )
        return filetools.rename_using_patterns(
            stem,
            orig_path,
            search,
            replace,
            counter,
            newnum=newnum,
            case_insensitive=case_insensitive,
        )

    def _apply_postproc(self, name: str, path: str) -> str:
        """Apply active post-processing options."""
        sep_idx = self._ui.cmbSpaces.currentIndex()
        if sep_idx > 0:
            name, _op = filetools.replace_spaces(name, path, sep_idx - 1)
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
        case_insensitive = self._ui.chkCaseInsensitive.isChecked()
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

        root = self._ui.tblFiles.invisibleRootItem()
        for i in range(root.childCount()):
            root.child(i).setText(1, "")

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
                            case_insensitive=case_insensitive,
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
                        case_insensitive=case_insensitive,
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

    # ── Named saves ──────────────────────────────────────────────────────────

    def _populate_named_saves(self) -> None:
        combo = self._ui.cmbNamedSaves
        current_text = combo.currentText()
        # Block the embedded QLineEdit too: combo.blockSignals() alone does not
        # stop the QCompleter from receiving textChanged events, which can queue
        # a deferred activated() and corrupt the LRU order.
        le = combo.lineEdit()
        combo.blockSignals(True)
        if le is not None:
            le.blockSignals(True)
        combo.clear()
        for name in self._presets.get_saves():
            combo.addItem(name)
        idx = combo.findText(current_text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentText(current_text)
        if le is not None:
            le.blockSignals(False)
        combo.blockSignals(False)
        self._update_save_buttons()

    def _update_save_buttons(self) -> None:
        name = self._ui.cmbNamedSaves.currentText()
        valid_name = bool(name and _SAVE_NAME_RE.match(name))
        self._ui.btnSaveSave.setEnabled(valid_name)
        self._ui.btnSaveDelete.setEnabled(name in self._presets.get_saves())

    def _on_save_name_changed(self) -> None:
        self._update_save_buttons()

    def _on_named_save_selected(self, index: int) -> None:
        if index < 0:
            return
        name = self._ui.cmbNamedSaves.itemText(index)
        cfg = self._presets.get_saves().get(name)
        if cfg is None:
            return
        self._apply_save_config(cfg)
        self._presets.use_save(name)
        self._populate_named_saves()
        self._ui.cmbNamedSaves.setCurrentText(name)

    def _collect_save_config(self) -> dict:
        cfg: dict = {
            "search_pattern": self._ui.cmbPatternSearch.currentText(),
            "search_mode": self._current_search_mode(),
            "case_insensitive": self._ui.chkCaseInsensitive.isChecked(),
            "replace_pattern": self._ui.cmbPatternDest.currentText(),
            "separator": self._ui.cmbSpaces.currentIndex(),
            "remove_accents": self._ui.chkRemoveAccents.isChecked(),
            "remove_duplicates": self._ui.chkRemoveDuplicates.isChecked(),
            "case": self._ui.cmbCaps.currentIndex(),
            "keep_extension": self._ui.chkKeepExtension.isChecked(),
        }
        f = self._ui.edtFilter.text()
        if f:
            cfg["filter"] = f
        return cfg

    def _apply_save_config(self, cfg: dict) -> None:
        if "search_pattern" in cfg:
            self._ui.cmbPatternSearch.setCurrentText(cfg["search_pattern"])
        mode = cfg.get("search_mode", "")
        if mode == "regex":
            self._ui.radRegex.setChecked(True)
        elif mode == "plain":
            self._ui.radPlainText.setChecked(True)
        elif mode == "pattern":
            self._ui.radPattern.setChecked(True)
        if "case_insensitive" in cfg:
            self._ui.chkCaseInsensitive.setChecked(bool(cfg["case_insensitive"]))
        if "replace_pattern" in cfg:
            self._ui.cmbPatternDest.setCurrentText(cfg["replace_pattern"])
        if "separator" in cfg:
            self._ui.cmbSpaces.setCurrentIndex(int(cfg["separator"]))
        if "remove_accents" in cfg:
            self._ui.chkRemoveAccents.setChecked(bool(cfg["remove_accents"]))
        if "remove_duplicates" in cfg:
            self._ui.chkRemoveDuplicates.setChecked(bool(cfg["remove_duplicates"]))
        if "case" in cfg:
            self._ui.cmbCaps.setCurrentIndex(int(cfg["case"]))
        if "keep_extension" in cfg:
            self._ui.chkKeepExtension.setChecked(bool(cfg["keep_extension"]))
        current_filter = self._ui.edtFilter.text()
        new_filter = cfg.get("filter", "")
        self._ui.edtFilter.setText(new_filter)
        if new_filter != current_filter:
            self._reload_files()

    def _on_save_save(self) -> None:
        name = self._ui.cmbNamedSaves.currentText()
        if not _SAVE_NAME_RE.match(name):
            return
        self._presets.set_save(name, self._collect_save_config())
        self._populate_named_saves()
        self._ui.cmbNamedSaves.setCurrentText(name)

    def _on_save_delete(self) -> None:
        name = self._ui.cmbNamedSaves.currentText()
        if name not in self._presets.get_saves():
            return
        self._presets.delete_save(name)
        self._populate_named_saves()
        self._ui.cmbNamedSaves.setCurrentText("")

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
            self._refresh_undo_button()
            search = self._ui.cmbPatternSearch.currentText()
            replace = self._ui.cmbPatternDest.currentText()
            if search:
                self._presets.add_search(self._current_search_mode(), search)
            if replace:
                self._presets.add_replace(replace)
            self._populate_pattern_combos()
            self._ui.cmbPatternSearch.setCurrentIndex(0)
            self._ui.cmbPatternDest.setCurrentIndex(0)

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
        self._refresh_undo_button()
        self._reload_files()

    def _refresh_undo_button(self) -> None:
        n = len(self._undo)
        self._ui.btnUndo.setEnabled(n > 0)
        if n > 0:
            self._ui.btnUndo.setText(_("Undo (%d)") % n)
            self._ui.btnUndo.setToolTip(
                _("Undo last rename batch (%d level(s) available)") % n
            )
        else:
            self._ui.btnUndo.setText(_("Undo"))
            self._ui.btnUndo.setToolTip(_("Undo last rename batch"))

    # ── Window state (geometry + splitters) ──────────────────────────────────

    def _restore_window_state(self) -> None:
        geo, sm, sr = self._window_state.load()
        if geo:
            self.restoreGeometry(geo)
        if sm:
            self._ui.splitterMain.restoreState(sm)
        if sr:
            self._ui.splitterRight.restoreState(sr)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._geometry_restored:
            self._geometry_restored = True
            self._restore_window_state()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._window_state.save(
            self.saveGeometry(),
            self._ui.splitterMain.saveState(),
            self._ui.splitterRight.saveState(),
        )
        if self._current_dir:
            _cfg.set_last_dir(self._current_dir)
        if _cfg.get_restore_toolbar_state():
            _cfg.set_toolbar_state(self._collect_toolbar_state())
        super().closeEvent(event)

    def _collect_toolbar_state(self) -> dict:
        return {
            "mode": self._ui.cmbMode.currentIndex(),
            "recursive": self._ui.chkRecursive.isChecked(),
            "keep_extension": self._ui.chkKeepExtension.isChecked(),
            "auto_preview": self._ui.chkAutoPreview.isChecked(),
            "filter": self._ui.edtFilter.text(),
        }

    def _restore_toolbar_state(self) -> None:
        state = _cfg.get_toolbar_state()
        if not state:
            return
        if "mode" in state:
            idx = int(state["mode"])
            if 0 <= idx < self._ui.cmbMode.count():
                self._ui.cmbMode.setCurrentIndex(idx)
        if "recursive" in state:
            self._ui.chkRecursive.setChecked(bool(state["recursive"]))
        if "keep_extension" in state:
            self._ui.chkKeepExtension.setChecked(bool(state["keep_extension"]))
        if "auto_preview" in state:
            self._ui.chkAutoPreview.setChecked(bool(state["auto_preview"]))
        if "filter" in state:
            self._ui.edtFilter.setText(str(state["filter"]))

    # ── Auto-preview / tab change ─────────────────────────────────────────────

    def _on_auto_preview_toggled(self, checked: bool) -> None:
        if checked:
            self._on_preview()
        else:
            self._preview_timer.stop()

    # ── Menu handlers ─────────────────────────────────────────────────────────

    def _on_quit(self) -> None:
        QApplication.quit()

    def _on_history(self) -> None:
        HistoryDialog(self._presets, self._window_state, self).exec()
        self._populate_pattern_combos()

    def _on_settings(self) -> None:
        SettingsDialog(self._window_state, self).exec()

    def _on_about(self) -> None:
        AboutDialog(self).exec()

    # ── Shortcuts menu ────────────────────────────────────────────────────────

    def _build_shortcuts_menu(self) -> None:
        menu = self._ui.menuShortcuts
        menu.clear()

        sys_bookmarks = system_bookmarks()
        for name, path in sys_bookmarks:
            action = menu.addAction(name)
            action.setStatusTip(path)
            action.triggered.connect(lambda _checked, p=path: self._on_shortcut(p))

        menu.addSeparator()

        prog_shortcuts = _cfg.get_shortcuts()
        for name, path in prog_shortcuts:
            action = menu.addAction(name)
            action.setStatusTip(path)
            action.triggered.connect(lambda _checked, p=path: self._on_shortcut(p))

        menu.addSeparator()
        menu.addAction(self._ui.actionEditShortcuts)

    def _on_shortcut(self, path: str) -> None:
        if not os.path.isdir(path):
            return
        self._navigate_to(path)
        self._current_dir = path
        self._reload_files()

    def _on_tree_context_menu(self, pos) -> None:
        index = self._ui.treeDirectory.indexAt(pos)
        path = self._fs_model.filePath(index) if index.isValid() else self._current_dir
        if not path or not os.path.isdir(path):
            return

        menu = QMenu(self)
        add_action = menu.addAction(_("Add as shortcut"))
        add_action.setStatusTip(path)
        chosen = menu.exec(self._ui.treeDirectory.viewport().mapToGlobal(pos))
        if chosen is add_action:
            self._add_shortcut(path)

    def _add_shortcut(self, path: str) -> None:
        name = os.path.basename(path) or path
        shortcuts = _cfg.get_shortcuts()
        if any(p == path for _, p in shortcuts):
            return
        shortcuts.append((name, path))
        _cfg.set_shortcuts(shortcuts)

    def _on_edit_shortcuts(self) -> None:
        ShortcutsDialog(self._window_state, self).exec()

    # ── File information window ───────────────────────────────────────────────

    def _on_file_info(self) -> None:
        if self._file_info is None:
            self._file_info = FileInfoWindow(self._window_state, self)
            self._file_info.field_requested.connect(self._on_field_requested)
        self._refresh_file_info()
        self._file_info.show()
        self._file_info.raise_()
        self._file_info.activateWindow()

    def _on_file_selection_changed(self) -> None:
        if self._file_info is not None and self._file_info.isVisible():
            self._refresh_file_info()

    def _refresh_file_info(self) -> None:
        if self._file_info is None:
            return
        items = self._ui.tblFiles.selectedItems()
        if len(items) > 1:
            self._file_info.show_multiple()
        elif len(items) == 1:
            path = items[0].data(0, Qt.ItemDataRole.UserRole)
            if path:
                self._file_info.update_file(path)
            else:
                self._file_info.show_empty()
        else:
            self._file_info.show_empty()

    def _on_field_requested(self, field: str) -> None:
        self._ui.cmbPatternDest.lineEdit().insert(field)

    def _on_file_double_clicked(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _on_files_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction(self._ui.actionFileInfo)
        menu.exec(self._ui.tblFiles.viewport().mapToGlobal(pos))
