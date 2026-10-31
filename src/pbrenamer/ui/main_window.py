"""Main application window."""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import QDir, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFileSystemModel,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
)

import pbrenamer.settings as _cfg
from pbrenamer import i18n, profiles
from pbrenamer.core import filetools
from pbrenamer.core.undo import RenameEntry, UndoError, UndoManager
from pbrenamer.platform import system_bookmarks
from pbrenamer.ui.about_dialog import AboutDialog
from pbrenamer.ui.action_bar import ActionBar
from pbrenamer.ui.file_list import FileListController, PreviewEntry
from pbrenamer.ui.history_dialog import HistoryDialog
from pbrenamer.ui.image_actions import ImageActions
from pbrenamer.ui.keyboard_help import keyboard_html
from pbrenamer.ui.main_window_ui import Ui_MainWindow
from pbrenamer.ui.pattern_help import PatternHelpDialog
from pbrenamer.ui.presets import PatternPresets
from pbrenamer.ui.profile_dialog import ProfileDialog
from pbrenamer.ui.rule_panel_pattern import PatternRulePanel, resolve_extension_mode
from pbrenamer.ui.rule_panel_schema import SchemaRulePanel
from pbrenamer.ui.settings_dialog import SettingsDialog
from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog
from pbrenamer.ui.sidecar_dialog import SidecarDialog
from pbrenamer.ui.window_state import WindowState

_log = logging.getLogger(__name__)

_PATTERN_TAB, _SCHEMA_TAB = 0, 1
_TAB_OF_MODE = {"pattern": _PATTERN_TAB, "schema": _SCHEMA_TAB}


class MainWindow(QMainWindow):
    """Top-level window for PBRenamer.

    Wires together the file list, the rule panels (Pattern and Schema tabs)
    and the action bar, and owns the directory tree, the menus, the current
    profile and the window state.
    """

    def __init__(self, start_dir: str | None = None) -> None:
        super().__init__()
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)

        self._undo = UndoManager()
        self._presets = PatternPresets()
        self._window_state = WindowState()
        self._keyboard_help: PatternHelpDialog | None = None
        self._geometry_restored = False

        self._schema = SchemaRulePanel(self._ui.tabSchema)
        self._ui.tabSchema.layout().addWidget(self._schema)
        self._files = FileListController(
            self._ui,
            self._undo,
            self._window_state,
            self._extension_mode,
            self,
            sidecars_forced=self._schema_mode,
        )
        self._pattern = PatternRulePanel(
            self._ui, self._presets, self._window_state, self._files, self
        )
        self._actions = ActionBar(self._ui, self._undo, self)
        self._images = ImageActions(
            self._ui, self._files, self._undo, self._window_state, self
        )
        self._profile_actions: list = []

        self._ui.tabRules.setCurrentIndex(_TAB_OF_MODE[profiles.load()["mode"]])
        self._setup_directory_tree()
        self._connect_signals()
        self._apply_mode_state()
        self._files.apply_display()
        self._update_title()
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
        the file list is never reloaded).  Fall back to a direct assignment."""
        self._navigate_to(path)
        if os.path.isdir(path) and self._files.current_dir != path:
            self._files.set_directory(path)

    def _navigate_to(self, path: str) -> None:
        if not os.path.isdir(path):
            return
        idx = self._fs_model.index(path)
        self._ui.treeDirectory.setCurrentIndex(idx)
        self._ui.treeDirectory.scrollTo(idx)
        self._ui.treeDirectory.expand(idx)

    def _connect_signals(self) -> None:
        self._ui.actionOpenFolder.triggered.connect(self._on_open)

        sel_model = self._ui.treeDirectory.selectionModel()
        sel_model.selectionChanged.connect(lambda *_: self._on_directory_selected())

        # Components
        self._actions.preview_requested.connect(self._on_preview)
        self._actions.clear_requested.connect(self._files.clear_preview)
        self._actions.undo_requested.connect(self._on_undo)
        self._actions.rename_requested.connect(self._on_rename)
        self._ui.btnRenumber.clicked.connect(self._on_renumber)
        self._ui.tabRules.currentChanged.connect(self._on_mode_changed)
        self._ui.chkThumbnails.toggled.connect(self._on_thumbnails_toggled)
        self._pattern.edited.connect(self._actions.schedule_preview)
        self._pattern.changed.connect(self._actions.request_auto_preview)
        self._schema.edited.connect(self._actions.schedule_preview)
        self._schema.edited.connect(self._update_renumber_button)
        self._schema.changed.connect(self._actions.request_auto_preview)
        self._files.files_reloaded.connect(self._on_files_reloaded)
        self._files.selection_changed.connect(self._actions.request_auto_preview)
        self._files.rename_count_changed.connect(self._actions.set_rename_count)
        self._files.rename_count_changed.connect(self._update_renumber_button)
        self._files.undo_stack_changed.connect(self._actions.refresh_undo)
        self._files.field_requested.connect(self._pattern.insert_field)
        self._images.undo_stack_changed.connect(self._actions.refresh_undo)
        self._images.status_message.connect(self.statusBar().showMessage)
        self._images.template_accepted.connect(self._on_template_accepted)

        # Menu bar
        self._ui.actionQuit.triggered.connect(self._on_quit)
        self._ui.actionHistory.triggered.connect(self._on_history)
        self._ui.actionSidecarFiles.triggered.connect(self._on_sidecar_files)
        self._ui.actionSettings.triggered.connect(self._on_settings)
        self._ui.actionAbout.triggered.connect(self._on_about)
        self._ui.actionKeyboardHelp.triggered.connect(self._on_keyboard_help)
        self._ui.actionUserGuide.triggered.connect(self._on_user_guide)
        self._ui.actionEditShortcuts.triggered.connect(self._on_edit_shortcuts)
        self._ui.menuShortcuts.aboutToShow.connect(self._build_shortcuts_menu)
        self._ui.actionProfileNew.triggered.connect(self._on_profile_new)
        self._ui.actionProfileDuplicate.triggered.connect(self._on_profile_duplicate)
        self._ui.actionProfileRename.triggered.connect(self._on_profile_rename)
        self._ui.actionProfileDelete.triggered.connect(self._on_profile_delete)
        self._ui.actionProfileConfig.triggered.connect(self._on_profile_config)
        self._ui.menuProfile.aboutToShow.connect(self._build_profile_menu)

        # Directory tree context menu
        self._ui.treeDirectory.customContextMenuRequested.connect(
            self._on_tree_context_menu
        )

    # ── Directory selection ───────────────────────────────────────────────────

    def _on_open(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, _("Select folder"))
        if not folder:
            return
        self._files.current_dir = folder
        idx = self._fs_model.index(folder)
        self._ui.treeDirectory.setCurrentIndex(idx)
        self._ui.treeDirectory.scrollTo(idx)
        self._files.reload()

    def _on_directory_selected(self) -> None:
        indexes = self._ui.treeDirectory.selectionModel().selectedIndexes()
        if not indexes:
            return
        path = self._fs_model.filePath(indexes[0])
        if not os.path.isdir(path):
            return
        if path == self._files.current_dir:
            return
        _log.info("Directory selected: %s", path)
        self._files.set_directory(path)

    def _on_files_reloaded(self) -> None:
        count = self._ui.tblFiles.topLevelItemCount()
        self.statusBar().showMessage(
            _("{path} — {n} item(s)").format(path=self._files.current_dir, n=count)
        )
        self._update_renumber_button()
        self._actions.request_auto_preview()

    # ── Rule mode (Pattern / Schema tabs) ─────────────────────────────────────

    def _schema_mode(self) -> bool:
        return self._ui.tabRules.currentIndex() == _SCHEMA_TAB

    def _extension_mode(self) -> str | None:
        """Extension mode of the active rule (the schema lowercases it)."""
        return "lower" if self._schema_mode() else self._pattern.extension_mode()

    def _on_mode_changed(self, index: int) -> None:
        data = profiles.load()
        data["mode"] = "schema" if index == _SCHEMA_TAB else "pattern"
        profiles.save(data)
        _log.info("Rule mode: %s", data["mode"])
        self._apply_mode_state()
        if self._files.current_dir:
            self._files.reload()

    def _on_thumbnails_toggled(self, checked: bool) -> None:
        data = profiles.load()
        data["display"]["thumbnails"] = checked
        profiles.save(data)
        self._files.apply_display()

    def _apply_mode_state(self) -> None:
        """Enable the controls of the active mode."""
        self._ui.cmbExtensionMode.setEnabled(not self._schema_mode())
        self._files.update_sidecar_checkbox_state()
        self._update_renumber_button()

    def _update_renumber_button(self) -> None:
        """Renumber shows with a schema counter and, like Rename, stays
        disabled until a preview is displayed."""
        self._ui.btnRenumber.setVisible(
            self._schema_mode() and self._schema.has_counter()
        )
        self._ui.btnRenumber.setEnabled(
            any(item.text(1) for item in self._files.all_items())
        )

    # ── Preview / Rename / Undo ───────────────────────────────────────────────

    def _on_preview(self) -> None:
        if not self._files.current_dir:
            return
        items = self._files.active_items()
        panel = self._schema if self._schema_mode() else self._pattern
        orphans = self._schema_orphans()
        kept = [i for i in items if i.data(0, Qt.ItemDataRole.UserRole) not in orphans]
        entries = panel.preview(
            [item.data(0, Qt.ItemDataRole.UserRole) for item in kept],
            self._files.sidecar_followers(),
        )
        if entries is None:
            if self._schema_mode():
                self._files.clear_preview()
            return
        skipped = [i for i in items if i not in kept]
        note = PreviewEntry(_("⚠ orphan sidecar, not renamed"), skipped=True)
        self._files.show_previews(kept + skipped, entries + [note] * len(skipped))

    def _schema_orphans(self) -> set[str]:
        """Schema mode: the orphan sidecars are left alone (numbered like a
        base file, they would get attached to another file)."""
        return self._files.listed_orphan_sidecars() if self._schema_mode() else set()

    def _execute(self, pairs: list[tuple[str, str]], title: str) -> bool:
        """Rename *pairs* all or nothing, record the undo entry and reload
        the list, selecting the renamed files still listed (else the row
        that followed them); on failure show why under *title*.  Return
        True on success."""
        next_path = self._files.next_path_after([src for src, _dst in pairs])
        try:
            result = filetools.execute_renames(
                pairs, prune_root=self._files.current_dir
            )
        except filetools.RenameError as exc:
            _log.warning("Rename refused or rolled back: %s", exc)
            if exc.conflicts:
                detail = "\n".join(
                    f"{os.path.basename(src)} → {dst}" for src, dst in exc.conflicts
                )
                message = _("Target(s) already taken:") + "\n" + detail
            else:
                message = str(exc)
            QMessageBox.warning(
                self,
                title,
                _("Nothing was renamed.") + "\n\n" + message,
                QMessageBox.StandardButton.Ok,
            )
            self._files.clear_preview()
            self._files.reload()
            return False
        _log.info("Renamed %d file(s)", len(result.pairs))
        self._undo.add(RenameEntry.from_result(result))
        self._actions.refresh_undo()
        # The preview stays empty after a rename, even with auto-preview on.
        with self._actions.auto_preview_held():
            self._files.clear_preview()
            self._files.reload()
            self._files.select_after_change(
                [dst for _src, dst in result.pairs], next_path
            )
        self.statusBar().showMessage(
            _("{n} file(s) renamed.").format(n=len(result.pairs))
        )
        return True

    def _on_rename(self) -> None:
        renames = self._files.pending_renames()
        if not renames:
            return

        _log.info("Renaming %d file(s)", len(renames))
        if self._execute(renames, _("Rename errors")):
            if self._schema_mode():
                self._schema.record_history()
                self._schema.save_dest()
            else:
                self._pattern.record_history()

    def _on_renumber(self) -> None:
        if not self._files.current_dir:
            return
        orphans = self._schema_orphans()
        paths = [
            path
            for item in self._files.active_items()
            if (path := item.data(0, Qt.ItemDataRole.UserRole)) not in orphans
        ]
        pairs = self._schema.renumber_plan(paths, self._files.sidecar_followers())
        if pairs is None:
            QMessageBox.warning(
                self,
                _("Renumber"),
                self._schema.lblMessage.text(),
                QMessageBox.StandardButton.Ok,
            )
            return
        if not pairs:
            self.statusBar().showMessage(_("Files are already correctly numbered."))
            return
        reply = QMessageBox.question(
            self,
            _("Confirm renumber"),
            _("Renumber {n} file(s) starting from 1?").format(n=len(pairs)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        _log.info("Renumbering %d file(s)", len(pairs))
        if self._execute(pairs, _("Renumber errors")):
            self._schema.record_history()

    def _on_undo(self) -> None:
        _log.info("Undoing last batch")
        try:
            self._undo.undo()
        except UndoError as exc:
            _log.warning("Undo failed: %s", exc)
            QMessageBox.warning(
                self,
                _("Undo errors"),
                str(exc),
                QMessageBox.StandardButton.Ok,
            )
        self._actions.refresh_undo()
        self._files.reload()

    # ── Window state (geometry + splitters) ──────────────────────────────────

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._geometry_restored:
            self._geometry_restored = True
            self._restore_window_state()

    def _restore_window_state(self) -> None:
        geo, sm, sr = self._window_state.load()
        if geo is not None:
            x, y, w, h = geo
            _log.debug("MainWindow: restore geometry x=%d y=%d w=%d h=%d", x, y, w, h)
            self.move(x, y)
            self.resize(w, h)
        else:
            _log.debug("MainWindow: no saved geometry, using defaults")
        self._restore_splitters(sm, sr)

    def _restore_splitters(self, sm, sr) -> None:
        if sm is not None:
            _log.debug("MainWindow: restore splitter_main sizes=%s", sm)
            self._ui.splitterMain.setSizes(sm)
        else:
            _log.debug("MainWindow: no saved splitter_main")
        if sr is not None:
            _log.debug("MainWindow: restore splitter_right sizes=%s", sr)
            self._ui.splitterRight.setSizes(sr)
        else:
            _log.debug("MainWindow: no saved splitter_right")

    def closeEvent(self, event) -> None:  # noqa: N802
        self._window_state.save(
            self.x(),
            self.y(),
            self.width(),
            self.height(),
            list(self._ui.splitterMain.sizes()),
            list(self._ui.splitterRight.sizes()),
        )
        self._save_profile_state()
        super().closeEvent(event)

    def _save_profile_state(self) -> None:
        """Store the directory, toolbar state and destination in the profile."""
        if self._files.current_dir:
            _cfg.set_last_dir(self._files.current_dir)
        if _cfg.get_restore_toolbar_state():
            _cfg.set_toolbar_state(self._collect_toolbar_state())
        self._schema.save_dest()

    def _collect_toolbar_state(self) -> dict:
        return {
            "mode": self._ui.cmbMode.currentIndex(),
            "recursive": self._ui.chkRecursive.isChecked(),
            "extension_mode": self._pattern.extension_mode(),
            "sidecar_mode": self._ui.chkSidecarMode.isChecked(),
            "auto_preview": self._actions.auto_preview(),
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
        ext_mode = resolve_extension_mode(state)
        if ext_mode is not None:
            idx = self._ui.cmbExtensionMode.findData(ext_mode)
            if idx >= 0:
                self._ui.cmbExtensionMode.setCurrentIndex(idx)
        if "sidecar_mode" in state:
            self._ui.chkSidecarMode.setChecked(bool(state["sidecar_mode"]))
        self._files.update_sidecar_checkbox_state()
        if "auto_preview" in state:
            self._actions.set_auto_preview(bool(state["auto_preview"]))
        if "filter" in state:
            self._ui.edtFilter.setText(str(state["filter"]))

    # ── Menu handlers ─────────────────────────────────────────────────────────

    def _on_quit(self) -> None:
        QApplication.quit()

    def _on_history(self) -> None:
        values = self._schema.fields()
        self._schema.save_dest()
        HistoryDialog(self._presets, self._window_state, self).exec()
        self._pattern.populate_pattern_combos()
        self._files.reload_filter_history()
        self._schema.reload_profile()
        self._schema.set_fields(values)

    def _on_settings(self) -> None:
        SettingsDialog(self._window_state, self).exec()
        if self._pattern.extension_mode() == "normalize":
            self._actions.request_auto_preview()

    def _on_sidecar_files(self) -> None:
        SidecarDialog(self._window_state, self).exec()
        # Categories drive the thumbnails, the sidecar column and grouping.
        self._files.apply_display()

    def _on_about(self) -> None:
        AboutDialog(self).exec()

    def _on_user_guide(self) -> None:
        QDesktopServices.openUrl(QUrl(i18n.user_guide_url()))

    def _on_keyboard_help(self) -> None:
        """Non-modal, kept between calls (geometry restored)."""
        if self._keyboard_help is None:
            self._keyboard_help = PatternHelpDialog(
                keyboard_html(),
                _("Keyboard and mouse shortcuts"),
                "keyboard_help",
                self._window_state,
                self,
            )
        self._keyboard_help.show()
        self._keyboard_help.raise_()
        self._keyboard_help.activateWindow()

    # ── Profiles ──────────────────────────────────────────────────────────────

    def _update_title(self) -> None:
        name = profiles.current()
        if name == profiles.DEFAULT:
            self.setWindowTitle("PBRenamer")
        else:
            self.setWindowTitle(f"PBRenamer [{name}]")

    def _build_profile_menu(self) -> None:
        menu = self._ui.menuProfile
        for action in self._profile_actions:
            menu.removeAction(action)
        self._profile_actions.clear()
        current = profiles.current()
        names = profiles.list_profiles()
        if current not in names:
            names = sorted([*names, current])
        for name in names:
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name == current)
            action.setStatusTip(_("Switch to the profile “{name}”").format(name=name))
            action.triggered.connect(lambda _checked, n=name: self._switch_profile(n))
            self._profile_actions.append(action)

    def _ask_profile_name(self, title: str, label: str, text: str = "") -> str | None:
        name, ok = QInputDialog.getText(
            self, title, label, QLineEdit.EchoMode.Normal, text
        )
        name = name.strip()
        return name if ok and name else None

    def _on_profile_new(self) -> None:
        title = _("New profile")
        name = self._ask_profile_name(
            title,
            _("Profile name (letters, digits, “-” and “_”):"),
        )
        if name is None:
            return
        try:
            profiles.validate_new_name(name)
            profiles.create(name)
        except profiles.ProfileError as exc:
            QMessageBox.warning(self, title, str(exc))
            return
        self._switch_profile(name)

    def _on_profile_duplicate(self) -> None:
        title = _("Duplicate profile")
        source = profiles.current()
        name = self._ask_profile_name(
            title, _("New profile name (copy of “{source}”):").format(source=source)
        )
        if name is None:
            return
        self._save_profile_state()
        try:
            profiles.validate_new_name(name)
            profiles.duplicate(source, name)
        except profiles.ProfileError as exc:
            QMessageBox.warning(self, title, str(exc))
            return
        self._switch_profile(name)

    def _on_profile_rename(self) -> None:
        title = _("Rename profile")
        old = profiles.current()
        name = self._ask_profile_name(
            title,
            _(
                "New name of the profile “{name}” (letters, digits, “-” and “_”):"
            ).format(name=old),
            old,
        )
        if name is None or name == old:
            return
        self._save_profile_state()
        try:
            profiles.validate_new_name(name)
            profiles.rename(old, name)
        except profiles.ProfileError as exc:
            QMessageBox.warning(self, title, str(exc))
            return
        _log.info("Profile renamed: %s -> %s", old, name)
        # The presets point into the profile directory, which has moved.
        self._presets = PatternPresets()
        self._pattern.set_presets(self._presets)
        self._update_title()
        self.statusBar().showMessage(
            _("Profile “{old}” renamed to “{name}”.").format(old=old, name=name)
        )

    def _on_profile_delete(self) -> None:
        title = _("Delete profile")
        # Hidden profiles are never offered: they stay hidden.
        names = profiles.list_profiles()
        if len(names) < 2:
            QMessageBox.information(
                self,
                title,
                _(
                    "There is no profile to delete:"
                    " at least one visible profile must remain."
                ),
            )
            return
        current = profiles.current()
        index = names.index(current) if current in names else 0
        name, ok = QInputDialog.getItem(
            self, title, _("Profile to delete:"), names, index, False
        )
        if not ok:
            return
        reply = QMessageBox.question(
            self,
            title,
            _(
                "Delete the profile “{name}” and all its settings?"
                " This cannot be undone."
            ).format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if name == current:
            self._switch_profile(profiles.fallback([n for n in names if n != name]))
        profiles.delete(name)
        self.statusBar().showMessage(_("Profile “{name}” deleted.").format(name=name))

    def _switch_profile(self, name: str) -> None:
        """Make *name* the current profile and load its settings.  The undo
        stack is kept: it only concerns files."""
        if name == profiles.current():
            return
        self._save_profile_state()
        profiles.use(name)
        _log.info("Profile: %s", name)

        self._presets = PatternPresets()
        self._pattern.set_presets(self._presets)
        self._schema.reload_profile()
        self._ui.tabRules.blockSignals(True)
        self._ui.tabRules.setCurrentIndex(_TAB_OF_MODE[profiles.load()["mode"]])
        self._ui.tabRules.blockSignals(False)
        if _cfg.get_restore_toolbar_state():
            self._restore_toolbar_state()
        self._apply_mode_state()
        self._update_title()

        last_dir = _cfg.get_last_dir()
        if last_dir and os.path.isdir(last_dir) and last_dir != self._files.current_dir:
            self._files.current_dir = last_dir
            self._navigate_to(last_dir)
        self._files.clear_preview()
        self._images.apply_profile()
        self._files.apply_display()
        self.statusBar().showMessage(_("Profile “{name}” loaded.").format(name=name))

    def _on_profile_config(self) -> None:
        values = self._schema.fields()
        self._schema.save_dest()
        if (
            ProfileDialog(self._window_state, self).exec()
            != ProfileDialog.DialogCode.Accepted
        ):
            return
        self._schema.reload_profile()
        self._schema.set_fields(values)
        self._apply_mode_state()
        self._images.apply_profile()
        self._files.apply_display()

    def _on_template_accepted(self, fields: list[str]) -> None:
        """Template: fill the schema fields and switch to the Schema tab."""
        self._schema.set_fields(fields)
        self._ui.tabRules.setCurrentIndex(_SCHEMA_TAB)

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
        self._files.current_dir = path
        self._navigate_to(path)
        self._files.reload()

    def _on_tree_context_menu(self, pos) -> None:
        index = self._ui.treeDirectory.indexAt(pos)
        path = (
            self._fs_model.filePath(index)
            if index.isValid()
            else self._files.current_dir
        )
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
