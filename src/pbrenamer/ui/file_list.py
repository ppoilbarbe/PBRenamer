"""File list: directory listing, sidecar grouping, preview display, conflicts."""

from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Callable
from typing import NamedTuple

from PySide6.QtCore import (
    QFileSystemWatcher,
    QItemSelectionModel,
    QObject,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QColor, QCursor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTreeWidgetItem,
)

import pbrenamer.settings as _cfg
from pbrenamer import profiles
from pbrenamer.core import filetools, planner, sidecar
from pbrenamer.core.undo import CopyEntry, MoveEntry, UndoManager
from pbrenamer.platform.fs import same_file_path
from pbrenamer.ui.file_info_window import FileInfoWindow
from pbrenamer.ui.thumbnails import THUMB_COLUMN, ThumbnailLoader
from pbrenamer.ui.window_state import WindowState

_log = logging.getLogger(__name__)

_PREVIEW_COLOR = QColor("#0066cc")
_UNCHANGED_COLOR = QColor("#888888")
_DIR_COLOR = QColor("#aa6600")
_CONFLICT_COLOR = QColor("#cc0000")
_ERROR_COLOR = QColor("#cc0000")
_SIDECAR_COLOR = QColor("#0099aa")
_INDICATOR_COLOR = QColor("#0066cc")
_NO_SIDECAR_COLOR = QColor("#888888")
_SIDECAR_ACTIVE_EXT_MODES = ("keep", "lower", "upper")
# Column 1 data: UserRole = error flag, _TARGET_ROLE = absolute target path,
# _SKIPPED_ROLE = informative preview of a file that is not renamed.
_TARGET_ROLE = Qt.ItemDataRole.UserRole + 1
_SKIPPED_ROLE = Qt.ItemDataRole.UserRole + 2
_SIDECAR_COLUMN = 3
_FILTER_DEBOUNCE_MS = 400
_INVALID_FILTER_STYLE = "QLineEdit { border: 1px solid red; }"


class PreviewEntry(NamedTuple):
    """Preview column content for one file: new name or error message.

    *target* is the absolute target path when *text* is not relative to the
    file's directory (schema mode shows it relative to the destination).
    """

    text: str
    error: bool = False
    target: str | None = None
    # Shown for information only: the file is not renamed.
    skipped: bool = False


def _open_path(path: str) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def _exec_menu(menu: QMenu, pos=None) -> None:  # pragma: no cover — modal
    """Show *menu* at *pos*, by default the mouse cursor (a seam for the
    tests, which patch it)."""
    menu.exec(QCursor.pos() if pos is None else pos)


class FileListController(QObject):
    """Own the file list: listing, sidecar groups, previews and conflicts.

    *extension_mode* returns the extension mode of the active rule; sidecar
    grouping is only possible when it leaves extensions untouched.
    *sidecars_forced* returns True when the active rule always groups
    sidecars (schema mode), whatever the Sidecar mode checkbox.
    """

    files_reloaded = Signal()
    selection_changed = Signal()
    rename_count_changed = Signal(int)
    undo_stack_changed = Signal()
    field_requested = Signal(str)
    view_requested = Signal(str)

    def __init__(
        self,
        ui,
        undo: UndoManager,
        window_state: WindowState,
        extension_mode: Callable[[], str | None],
        parent: QMainWindow,
        sidecars_forced: Callable[[], bool] = lambda: False,
    ) -> None:
        super().__init__(parent)
        self._ui = ui
        self._window = parent
        self._undo = undo
        self._window_state = window_state
        self._extension_mode = extension_mode
        self._sidecars_forced = sidecars_forced

        self.current_dir: str | None = None
        self._loaded_dir: str | None = None
        # Groups used for grouped renaming (sidecar mode active only) …
        self._sidecar_result: sidecar.SidecarGroupResult | None = None
        # … and for the sidecar column, the sidecar filter and drag and drop.
        self._groups: sidecar.SidecarGroupResult | None = None
        self._content_cache = sidecar.ContentCache()
        self._content_filter: re.Pattern[str] | None = None
        # Sidecars created by a double-click: kept while still empty.
        self._pending_edit: set[str] = set()
        self._sidecar_column = False
        self._filter_shown = False
        self._delete_empty_sidecars = False
        self._new_sidecar_ext = profiles.DEFAULTS["images"]["sidecar_new_extension"]
        self._sort_by_date = False
        self._sort_reverse = False
        self._thumbs = ThumbnailLoader(self._ui.tblFiles, self)
        self._linking_selection = False
        self._prev_group_selection: set[str] = set()
        self._file_info: FileInfoWindow | None = None

        self._fs_watcher = QFileSystemWatcher(self)
        self._fs_watcher.directoryChanged.connect(self._on_dir_changed_external)
        self._fs_change_timer = QTimer(self)
        self._fs_change_timer.setSingleShot(True)
        self._fs_change_timer.timeout.connect(self._on_fs_change)
        self._last_internal_reload: float = 0.0

        # Drag'n'drop
        self._ui.treeDirectory.files_dropped.connect(self._on_files_dropped)
        self._ui.tblFiles.files_dropped.connect(self._on_files_dropped)
        self._ui.tblFiles.current_dir_getter = lambda: self.current_dir
        self._ui.tblFiles.sidecars_of = self._sidecars_of

        # Options that trigger a file list reload
        self._ui.chkSidecarMode.toggled.connect(self.reload)
        self._ui.cmbMode.currentIndexChanged.connect(self.reload)
        self._ui.chkRecursive.toggled.connect(self.reload)
        self._ui.edtFilter.editingFinished.connect(self.reload)
        self._ui.chkSortByDate.toggled.connect(self._on_sort_toggled)
        self._ui.chkSortReverse.toggled.connect(self._on_sort_toggled)

        # Sidecar content filter
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(_FILTER_DEBOUNCE_MS)
        self._filter_timer.timeout.connect(self._apply_content_filter)
        self._ui.cmbSidecarFilter.editTextChanged.connect(self._on_filter_edited)
        self._ui.cmbSidecarFilter.lineEdit().returnPressed.connect(
            self._on_filter_return
        )

        # Context menu, selection tracking, file information window
        self._ui.actionFileInfo.triggered.connect(self.show_file_info)
        self._ui.tblFiles.customContextMenuRequested.connect(self._on_context_menu)
        self._ui.tblFiles.itemSelectionChanged.connect(self._on_selection_changed)
        self._ui.tblFiles.itemDoubleClicked.connect(self._on_item_double_clicked)

    # ── Filesystem change notifications ──────────────────────────────────────

    def _on_dir_changed_external(self) -> None:
        if time.monotonic() - self._last_internal_reload < 0.5:
            return
        self._fs_change_timer.start(200)

    def _listing_unchanged(self) -> bool:
        """Return True if the on-disk listing still matches what's displayed.

        QFileSystemWatcher notifications can be spurious — e.g. a desktop
        indexer or thumbnailer touching directory metadata without actually
        adding/removing/renaming any entry. Rebuilding the tree for those
        causes a visible flicker (clear + repopulate) for no reason, so
        _on_fs_change skips the reload entirely when nothing really changed.
        """
        new_paths = [path for _, path in self._list_entries()]
        root = self._ui.tblFiles.invisibleRootItem()
        current_paths = [
            root.child(i).data(0, Qt.ItemDataRole.UserRole)
            for i in range(root.childCount())
        ]
        return new_paths == current_paths

    def _on_fs_change(self) -> None:
        if not self.current_dir or not os.path.isdir(self.current_dir):
            return
        if self._listing_unchanged():
            return
        self.reload()

    # ── Display settings (current profile) ────────────────────────────────────

    def apply_display(self) -> None:
        """Apply the display settings of the current profile and reload."""
        data = profiles.load()
        display, images = data["display"], data["images"]
        self._sidecar_column = display["sidecar_column"]
        self._filter_shown = display["sidecar_filter"]
        self._delete_empty_sidecars = images["delete_empty_sidecars"]
        self._new_sidecar_ext = images["sidecar_new_extension"]
        self._sort_by_date = display["sort_by_date"]
        self._sort_reverse = display["sort_reverse"]
        for box, value in (
            (self._ui.chkSortByDate, self._sort_by_date),
            (self._ui.chkSortReverse, self._sort_reverse),
        ):
            box.blockSignals(True)
            box.setChecked(value)
            box.blockSignals(False)
        config = _cfg.get_sidecar_config()
        self._thumbs.configure(
            display["thumbnails"],
            display["thumbnail_max_width"],
            display["thumbnail_max_height"],
            images["exif_auto_rotate"],
            config.base_extensions.get("image", frozenset()),
            config.base_extensions.get("video", frozenset()),
        )
        self._ui.chkThumbnails.blockSignals(True)
        self._ui.chkThumbnails.setChecked(display["thumbnails"])
        self._ui.chkThumbnails.blockSignals(False)
        self._ui.tblFiles.setColumnHidden(_SIDECAR_COLUMN, not self._sidecar_column)
        self._ui.cmbSidecarFilter.setVisible(self._filter_shown)
        if not self._filter_shown:
            self._clear_content_filter()
        self.reload_filter_history()
        self.reload()

    def _on_sort_toggled(self) -> None:
        """Sort by date / reversed: saved in the profile, then reload."""
        self._sort_by_date = self._ui.chkSortByDate.isChecked()
        self._sort_reverse = self._ui.chkSortReverse.isChecked()
        data = profiles.load()
        data["display"].update(
            sort_by_date=self._sort_by_date, sort_reverse=self._sort_reverse
        )
        profiles.save(data)
        self.reload()

    # ── Directory / file loading ──────────────────────────────────────────────

    def set_directory(self, path: str) -> None:
        self.current_dir = path
        self.reload()

    def _list_entries(self) -> list[tuple[str, str]]:
        mode = self._ui.cmbMode.currentIndex()
        pattern = self._ui.edtFilter.text().strip() or None
        if self._ui.chkRecursive.isChecked():
            entries = filetools.get_file_listing_recursive(
                self.current_dir, mode, pattern
            )
        else:
            entries = filetools.get_file_listing(self.current_dir, mode, pattern)
        if self._content_filter is not None:
            groups = sidecar.build_sidecar_groups(entries, _cfg.get_sidecar_config())
            entries = sidecar.filter_by_content(
                entries, groups, self._content_filter, self._content_cache
            )
        return self._sorted(entries)

    def _sorted(self, entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Apply the sort options to a by-name listing; folders stay first."""
        if not self._sort_by_date and not self._sort_reverse:
            return entries
        dirs = [e for e in entries if os.path.isdir(e[1])]
        files = [e for e in entries if not os.path.isdir(e[1])]
        if self._sort_by_date:

            def mtime(entry: tuple[str, str]) -> float:
                try:
                    return os.path.getmtime(entry[1])
                except OSError:
                    return 0.0

            dirs.sort(key=mtime)
            files.sort(key=mtime)  # stable: by name within a same mtime
        if self._sort_reverse:
            dirs.reverse()
            files.reverse()
        return dirs + files

    def _grouped_order(self, entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Sidecar mode: put each base file's sidecars right after it, sorted
        by name (hence by suffix); only the other entries keep the sort order
        of the listing."""
        result = self._sidecar_result
        by_path = {path: (name, path) for name, path in entries}
        ordered: list[tuple[str, str]] = []
        for name, path in entries:
            if path in result.sidecar_of:
                continue
            ordered.append((name, path))
            sidecars = sorted(
                (p for p in result.groups.get(path, ()) if p in by_path),
                key=lambda p: os.path.basename(p),
            )
            ordered.extend(by_path[p] for p in sidecars)
        return ordered

    def _delete_empty_sidecars_now(self) -> None:
        """Remove the empty sidecar files of the displayed directory, except
        those created by a double-click and not edited yet."""
        try:
            names = os.listdir(self.current_dir)
        except OSError:
            return
        self._pending_edit = {
            p
            for p in self._pending_edit
            if os.path.isfile(p) and not os.path.getsize(p)
        }
        paths = [os.path.join(self.current_dir, n) for n in names]
        for path in sidecar.empty_sidecars(paths, _cfg.get_sidecar_config()):
            if path in self._pending_edit:
                continue
            try:
                os.remove(path)
                _log.info("Empty sidecar deleted: %s", path)
            except OSError as exc:
                _log.warning("Cannot delete empty sidecar %s: %s", path, exc)

    def _needs_groups(self) -> bool:
        return (
            self.sidecar_mode_active()
            or self._sidecar_column
            or self._content_filter is not None
        )

    def reload(self) -> None:
        """List the current directory.  Reloading the same directory keeps
        the selection and the current row; a new directory starts with the
        first row current and nothing selected (Rename then applies to all)."""
        if not self.current_dir or not os.path.isdir(self.current_dir):
            return
        same_dir = self.current_dir == self._loaded_dir
        selected, current = self._capture_state() if same_dir else (set(), None)
        if not same_dir:
            self._clear_content_filter()
        self._last_internal_reload = time.monotonic()
        self._fs_change_timer.stop()
        watched = self._fs_watcher.directories()
        if list(watched) != [self.current_dir]:
            if watched:
                self._fs_watcher.removePaths(list(watched))
            self._fs_watcher.addPath(self.current_dir)
        recursive = self._ui.chkRecursive.isChecked()

        _log.debug(
            "Reloading files: dir=%s mode=%d recursive=%s pattern=%r",
            self.current_dir,
            self._ui.cmbMode.currentIndex(),
            recursive,
            self._ui.edtFilter.text().strip() or None,
        )

        if self._delete_empty_sidecars:
            self._delete_empty_sidecars_now()
        entries = self._list_entries()
        self._recompute_sidecar_grouping(entries)
        if self._sidecar_result is not None:
            entries = self._grouped_order(entries)

        tree = self._ui.tblFiles
        self._thumbs.stop()
        # The selection is restored below; files_reloaded notifies the change.
        tree.blockSignals(True)
        tree.clear()
        tree.blockSignals(False)
        tree.setHeaderLabels(
            [_("Original"), _("Preview"), _("Thumbnail"), _("Sidecar")]
        )
        for name, path in entries:
            display = os.path.relpath(path, self.current_dir) if recursive else name
            item = QTreeWidgetItem([display, ""])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            if os.path.isdir(path):
                item.setForeground(0, _DIR_COLOR)
            tree.addTopLevelItem(item)
        self._apply_sidecar_coloring()
        self._show_sidecar_indicators()
        self._thumbs.populate()
        tree.resizeColumnToContents(0)
        self._loaded_dir = self.current_dir
        self._restore_state(selected, current)

        _log.debug(
            "Loaded %d item(s) from %s",
            tree.topLevelItemCount(),
            self.current_dir,
        )
        self.rename_count_changed.emit(0)
        self.files_reloaded.emit()

    # ── Selection and current row ─────────────────────────────────────────────

    def _items_by_path(self) -> dict[str, QTreeWidgetItem]:
        root = self._ui.tblFiles.invisibleRootItem()
        return {
            root.child(i).data(0, Qt.ItemDataRole.UserRole): root.child(i)
            for i in range(root.childCount())
        }

    def _capture_state(self) -> tuple[set[str], str | None]:
        tree = self._ui.tblFiles
        selected = {i.data(0, Qt.ItemDataRole.UserRole) for i in tree.selectedItems()}
        item = tree.currentItem()
        current = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        return selected, current

    def _set_current_item(self, item: QTreeWidgetItem | None) -> None:
        """Make *item* the current row without changing the selection."""
        tree = self._ui.tblFiles
        if item is None:
            return
        index = tree.indexFromItem(item)
        tree.selectionModel().setCurrentIndex(
            index, QItemSelectionModel.SelectionFlag.NoUpdate
        )
        tree.scrollToItem(item)

    def _restore_state(self, selected: set[str], current: str | None) -> None:
        """Reselect *selected* and make *current* the current row, without
        emitting selection_changed (the reload already notifies)."""
        tree = self._ui.tblFiles
        items = self._items_by_path()
        if self._sidecar_result is not None:
            # Entering sidecar mode: a selected file pulls its whole group.
            selected = self._expand_to_groups(selected)
        tree.blockSignals(True)
        for path in selected:
            if path in items:
                items[path].setSelected(True)
        tree.blockSignals(False)
        self._prev_group_selection = {p for p in selected if p in items}
        if current in items:
            self._set_current_item(items[current])
        elif self._prev_group_selection:
            first = next(item for item in self.all_items() if item.isSelected())
            self._set_current_item(first)
        elif tree.topLevelItemCount():
            self._set_current_item(tree.topLevelItem(0))

    def all_items(self) -> list[QTreeWidgetItem]:
        root = self._ui.tblFiles.invisibleRootItem()
        return [root.child(i) for i in range(root.childCount())]

    def select_paths(self, paths) -> bool:
        """Select the listed rows of *paths* (first one current); return
        False when none of them is listed."""
        items = self._items_by_path()
        found = [items[p] for p in paths if p in items]
        if not found:
            return False
        tree = self._ui.tblFiles
        tree.blockSignals(True)
        tree.clearSelection()
        for item in found:
            item.setSelected(True)
        tree.blockSignals(False)
        first = min(found, key=tree.indexOfTopLevelItem)
        self._set_current_item(first)
        self._on_selection_changed()
        return True

    def set_current_path(self, path: str | None) -> None:
        """Make the row of *path* current, without selecting it."""
        item = self._items_by_path().get(path) if path else None
        self._set_current_item(item)

    def next_path_after(self, paths) -> str | None:
        """Return the first listed path following the last of *paths*,
        skipping *paths* themselves; or the last remaining one before."""
        gone = set(paths)
        listed = [i.data(0, Qt.ItemDataRole.UserRole) for i in self.all_items()]
        rows = [r for r, p in enumerate(listed) if p in gone]
        if not rows:
            return None
        after = [p for p in listed[rows[-1] + 1 :] if p not in gone]
        if after:
            return after[0]
        before = [p for p in listed[: rows[-1]] if p not in gone]
        return before[-1] if before else None

    def select_after_change(self, targets: list[str], next_path: str | None) -> None:
        """After files were renamed or moved: select the *targets* still
        listed, otherwise make *next_path* the current row."""
        if not self.select_paths(targets):
            self.set_current_path(next_path)

    # ── Preview display and conflicts ─────────────────────────────────────────

    def active_items(self) -> list[QTreeWidgetItem]:
        """Return selected top-level items, or all if nothing is selected."""
        selected = self._ui.tblFiles.selectedItems()
        if selected:
            return selected
        root = self._ui.tblFiles.invisibleRootItem()
        return [root.child(i) for i in range(root.childCount())]

    def show_previews(
        self, items: list[QTreeWidgetItem], entries: list[PreviewEntry]
    ) -> None:
        """Display *entries* for *items*, clear the preview of every other row,
        propagate base renames to their sidecars and refresh conflicts."""
        root = self._ui.tblFiles.invisibleRootItem()
        for i in range(root.childCount()):
            root.child(i).setText(1, "")
            root.child(i).setData(1, _TARGET_ROLE, None)
            root.child(i).setData(1, _SKIPPED_ROLE, None)

        for item, entry in zip(items, entries, strict=True):
            item.setText(1, entry.text)
            item.setData(1, Qt.ItemDataRole.UserRole, entry.error)
            item.setData(1, _TARGET_ROLE, entry.target)
            item.setData(1, _SKIPPED_ROLE, entry.skipped or None)

        if self.sidecar_mode_active() and self._sidecar_result:
            path_to_item = {
                root.child(i).data(0, Qt.ItemDataRole.UserRole): root.child(i)
                for i in range(root.childCount())
            }
            for sidecar_path, base_path in self._sidecar_result.sidecar_of.items():
                sidecar_item = path_to_item[sidecar_path]
                base_item = path_to_item[base_path]
                base_new_name = base_item.text(1)
                base_had_error = bool(base_item.data(1, Qt.ItemDataRole.UserRole))
                if not base_new_name or base_had_error:
                    sidecar_item.setText(1, "")
                    sidecar_item.setData(1, Qt.ItemDataRole.UserRole, False)
                    continue
                base_stem, _stem_path, _ext = filetools.cut_extension(
                    base_new_name, base_path
                )
                suffix = self._sidecar_result.sidecar_suffix[sidecar_path]
                sidecar_item.setText(1, f"{base_stem}.{suffix}")
                sidecar_item.setData(1, Qt.ItemDataRole.UserRole, False)
                base_target = base_item.data(1, _TARGET_ROLE)
                if base_target:
                    sidecar_item.setData(
                        1, _TARGET_ROLE, planner.sidecar_target(base_target, suffix)
                    )
        self._apply_sidecar_coloring()

        self._ui.tblFiles.resizeColumnToContents(1)
        self.refresh_conflicts()

    @staticmethod
    def _target_of(item: QTreeWidgetItem) -> str:
        """Absolute target path of the previewed *item*."""
        target = item.data(1, _TARGET_ROLE)
        if target:
            return target
        path = item.data(0, Qt.ItemDataRole.UserRole)
        return os.path.join(os.path.dirname(path), item.text(1))

    def refresh_conflicts(self) -> None:
        """Recompute conflict coloring and emit the number of renames that
        Rename would perform (0 when blocked by a conflict or an error)."""
        root = self._ui.tblFiles.invisibleRootItem()
        n = root.childCount()

        previews: list[tuple[str, str, QTreeWidgetItem, bool]] = []
        has_field_error = False
        for i in range(n):
            item = root.child(i)
            preview = item.text(1)
            if not preview:
                continue
            if item.data(1, _SKIPPED_ROLE):
                item.setForeground(1, _UNCHANGED_COLOR)
                continue
            path = item.data(0, Qt.ItemDataRole.UserRole)
            is_error = bool(item.data(1, Qt.ItemDataRole.UserRole))
            if is_error:
                has_field_error = True
                item.setForeground(1, _ERROR_COLOR)
            previews.append((preview, path, item, is_error))

        if not previews or all(e for *_, e in previews):
            self.rename_count_changed.emit(0)
            return

        # Conflicts among non-error entries: shared or already taken targets.
        valid = [(p, path, item) for p, path, item, e in previews if not e]
        pairs = [(path, self._target_of(item)) for _preview, path, item in valid]
        conflicting = {
            src
            for src, _dst in filetools.find_rename_conflicts(
                [(src, dst) for src, dst in pairs if src != dst]
            )
        }

        has_conflict = bool(conflicting)
        any_changed = False
        for (_preview, path, item), (_src, dst) in zip(valid, pairs, strict=True):
            if path in conflicting:
                item.setForeground(1, _CONFLICT_COLOR)
            elif dst != path:
                item.setForeground(1, _PREVIEW_COLOR)
                any_changed = True
            else:
                item.setForeground(1, _UNCHANGED_COLOR)

        allowed = any_changed and not has_conflict and not has_field_error
        self.rename_count_changed.emit(len(self.pending_renames()) if allowed else 0)

    def clear_preview(self) -> None:
        root = self._ui.tblFiles.invisibleRootItem()
        for i in range(root.childCount()):
            root.child(i).setText(1, "")
            root.child(i).setData(1, _TARGET_ROLE, None)
            root.child(i).setData(1, _SKIPPED_ROLE, None)
        self.rename_count_changed.emit(0)

    def pending_renames(self) -> list[tuple[str, str]]:
        """Return (original, new) paths for active rows with a valid preview."""
        renames: list[tuple[str, str]] = []
        for item in self.active_items():
            preview = item.text(1)
            if not preview or item.data(1, Qt.ItemDataRole.UserRole):
                continue
            if item.data(1, _SKIPPED_ROLE):
                continue
            original_path: str = item.data(0, Qt.ItemDataRole.UserRole)
            new_path = self._target_of(item)
            if original_path != new_path:
                renames.append((original_path, new_path))
        return renames

    # ── Sidecar files ─────────────────────────────────────────────────────────

    def sidecar_followers(self) -> dict[str, list[tuple[str, str]]]:
        """Map each base path to the (path, suffix) of the sidecars that
        follow its new name; empty when sidecar mode is inactive."""
        if not self.sidecar_mode_active() or not self._sidecar_result:
            return {}
        return sidecar.followers(self._sidecar_result)

    def sidecar_mode_active(self) -> bool:
        """True if sidecar grouping should be applied: always in schema
        mode, otherwise when the checkbox is checked and the current
        extension mode is compatible with it (Keep/Lowercase/Uppercase —
        Normalize/Modify rewrite the extension, which is incompatible with
        leaving sidecar suffixes untouched)."""
        if self._sidecars_forced():
            return True
        if not self._ui.chkSidecarMode.isChecked():
            return False
        return self._extension_mode() in _SIDECAR_ACTIVE_EXT_MODES

    def update_sidecar_checkbox_state(self) -> None:
        allowed = self._extension_mode() in _SIDECAR_ACTIVE_EXT_MODES
        self._ui.chkSidecarMode.setEnabled(allowed and not self._sidecars_forced())

    def _recompute_sidecar_grouping(self, entries: list[tuple[str, str]]) -> None:
        self._prev_group_selection = set()
        if not self._needs_groups():
            self._groups = self._sidecar_result = None
            return
        config = _cfg.get_sidecar_config()
        self._groups = sidecar.build_sidecar_groups(entries, config)
        self._sidecar_result = self._groups if self.sidecar_mode_active() else None

    def _sidecars_of(self, path: str) -> list[str]:
        """Sidecars of the listed file *path* (empty if none or unknown)."""
        if self._groups is None:
            return []
        return list(self._groups.groups.get(path, []))

    def sidecars_map(self, paths: list[str]) -> dict[str, list[str]]:
        """Sidecars of each file of *paths*: from the listing's groups when
        computed, else read from the disk."""
        if self._groups is not None:
            return {p: self._sidecars_of(p) for p in paths}
        found = sidecar.sidecars_on_disk(paths, _cfg.get_sidecar_config())
        return {p: found.get(p, []) for p in paths}

    def orphan_sidecars(self) -> list[str]:
        """Sidecar files of the displayed folder that have no base file."""
        if not self.current_dir or not os.path.isdir(self.current_dir):
            return []
        entries = filetools.get_file_listing(self.current_dir, 0)
        config = _cfg.get_sidecar_config()
        groups = sidecar.build_sidecar_groups(entries, config)
        return sidecar.orphan_sidecars(entries, groups, config)

    def listed_orphan_sidecars(self) -> set[str]:
        """Listed files named like a sidecar that sidecar mode attached to
        no base file (empty outside sidecar mode)."""
        if self._sidecar_result is None:
            return set()
        entries = [(os.path.basename(p), p) for p in self.listed_paths()]
        config = _cfg.get_sidecar_config()
        return set(sidecar.orphan_sidecars(entries, self._sidecar_result, config))

    def selected_paths(self) -> list[str]:
        """Paths of the selected rows, in list order."""
        tree = self._ui.tblFiles
        items = sorted(tree.selectedItems(), key=tree.indexOfTopLevelItem)
        return [i.data(0, Qt.ItemDataRole.UserRole) for i in items]

    def selected_bases(self) -> list[str]:
        """Selected paths, each sidecar replaced by its base file in sidecar
        mode (a selected group counts as its single main file)."""
        paths = self.selected_paths()
        if self._sidecar_result is None:
            return paths
        return list(dict.fromkeys(self.base_of(p) for p in paths))

    def base_of(self, path: str) -> str:
        """Base file of *path* when it is a sidecar in sidecar mode, else
        *path* itself."""
        if self._sidecar_result is None:
            return path
        return self._sidecar_result.sidecar_of.get(path, path)

    def listed_paths(self) -> list[str]:
        return [i.data(0, Qt.ItemDataRole.UserRole) for i in self.all_items()]

    def _show_sidecar_indicators(self) -> None:
        """Fill the sidecar column: "● suffixes" on base files having
        sidecars, "○" on images, videos and audio files without any."""
        if not self._sidecar_column or self._groups is None:
            return
        config = _cfg.get_sidecar_config()
        for item in self.all_items():
            path = item.data(0, Qt.ItemDataRole.UserRole)
            sidecars = self._groups.groups.get(path)
            if sidecars:
                suffixes = "  ".join(
                    self._groups.sidecar_suffix[sc] for sc in sorted(sidecars)
                )
                item.setText(_SIDECAR_COLUMN, f"● {suffixes}")
                item.setForeground(_SIDECAR_COLUMN, _INDICATOR_COLOR)
                item.setToolTip(_SIDECAR_COLUMN, "\n".join(sorted(sidecars)))
            elif path not in self._groups.sidecar_of and os.path.isfile(path):
                ext = os.path.splitext(path)[1][1:]
                if config.category_of_extension(ext) in sidecar.BASE_CATEGORIES:
                    item.setText(_SIDECAR_COLUMN, "○")
                    item.setForeground(_SIDECAR_COLUMN, _NO_SIDECAR_COLOR)
                    item.setToolTip(
                        _SIDECAR_COLUMN,
                        _("No sidecar: double-click to create one"),
                    )
            item.setTextAlignment(_SIDECAR_COLUMN, Qt.AlignmentFlag.AlignCenter)
        self._ui.tblFiles.resizeColumnToContents(_SIDECAR_COLUMN)

    def _open_sidecar(self, item: QTreeWidgetItem) -> None:
        """Open the sidecar of *item* (choosing among several), or create
        an empty one with the profile's extension and open it."""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        sidecars = sorted(self._sidecars_of(path))
        if len(sidecars) == 1:
            _open_path(sidecars[0])
            return
        if sidecars:
            menu = QMenu(self._window)
            for sc in sidecars:
                action = menu.addAction(os.path.basename(sc))
                action.triggered.connect(lambda _checked=False, p=sc: _open_path(p))
            _exec_menu(menu)
            return
        if item.text(_SIDECAR_COLUMN) != "○" or not self._new_sidecar_ext:
            return
        new = f"{os.path.splitext(path)[0]}.{self._new_sidecar_ext}"
        try:
            with open(new, "x"):
                pass
        except OSError as exc:
            QMessageBox.warning(
                self._window,
                _("Sidecar"),
                _("Cannot create {name}: {error}").format(
                    name=os.path.basename(new), error=exc
                ),
            )
            return
        _log.info("Sidecar created: %s", new)
        self._pending_edit.add(new)
        _open_path(new)
        self.reload()

    # ── Sidecar content filter ────────────────────────────────────────────────

    def _on_filter_edited(self, text: str) -> None:
        line = self._ui.cmbSidecarFilter.lineEdit()
        try:
            sidecar.compile_content_filter(text)
        except re.error:
            line.setStyleSheet(_INVALID_FILTER_STYLE)
            self._filter_timer.stop()
            return
        line.setStyleSheet("")
        self._filter_timer.start()

    def _apply_content_filter(self) -> None:
        text = self._ui.cmbSidecarFilter.currentText()
        try:
            regex = sidecar.compile_content_filter(text) if text else None
        except re.error:
            return
        old = self._content_filter.pattern if self._content_filter else None
        if (regex.pattern if regex else None) == old:
            return
        _log.info("Sidecar filter: %r", text)
        self._content_filter = regex
        self.reload()

    def _on_filter_return(self) -> None:
        self._filter_timer.stop()
        self._apply_content_filter()
        text = self._ui.cmbSidecarFilter.currentText().strip()
        if not text or self._content_filter is None:
            return
        history = [h for h in profiles.get_history("sidecar_filter") if h != text]
        history.insert(0, text)
        del history[profiles.load()["display"]["history_max"] :]
        profiles.set_history("sidecar_filter", history)
        self.reload_filter_history()

    def reload_filter_history(self) -> None:
        """Refill the sidecar filter list from the profile, keeping the text."""
        combo = self._ui.cmbSidecarFilter
        text = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(profiles.get_history("sidecar_filter"))
        combo.setCurrentIndex(-1)
        combo.setEditText(text)
        combo.blockSignals(False)

    def _clear_content_filter(self) -> None:
        self._filter_timer.stop()
        self._content_filter = None
        combo = self._ui.cmbSidecarFilter
        combo.blockSignals(True)
        combo.setEditText("")
        combo.lineEdit().setStyleSheet("")
        combo.blockSignals(False)

    def _apply_sidecar_coloring(self) -> None:
        """Tint sidecar rows (column 0) and surface ambiguity errors for
        the current self._sidecar_result. No-op when sidecar mode is
        inactive (self._sidecar_result is None)."""
        if self._sidecar_result is None:
            return
        root = self._ui.tblFiles.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path in self._sidecar_result.sidecar_of:
                item.setForeground(0, _SIDECAR_COLOR)
        self._apply_sidecar_errors()

    def _apply_sidecar_errors(self) -> None:
        """Tint every sidecar_result.errors row's filename (column 0), and
        additionally set the ambiguity-error text/color on column 1 — which
        refresh_conflicts treats as a field error blocking Rename — only
        for rows that are part of the current selection (active_items()).
        An ambiguous file the user hasn't selected must not block renaming
        an unrelated selection, same as any other field-resolution error is
        already scoped to active_items() by the preview.

        Called right after listing (so the tint/error is visible even
        before Preview is run — at that point nothing is selected yet, so
        active_items() returns every row) and again at the tail of
        show_previews, which clears column 1 for every row before
        recomputing it — errors always win over a computed preview for
        selected rows. Only called from _apply_sidecar_coloring, which
        already guarantees self._sidecar_result is not None."""
        active_paths = {
            item.data(0, Qt.ItemDataRole.UserRole) for item in self.active_items()
        }
        root = self._ui.tblFiles.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path in self._sidecar_result.errors:
                item.setForeground(0, _ERROR_COLOR)
                if path in active_paths:
                    item.setText(1, self._sidecar_result.errors[path])
                    item.setData(1, Qt.ItemDataRole.UserRole, True)

    def _group_of(self, path: str) -> set[str]:
        """Return {base, *sidecars} for the group *path* belongs to, or
        {path} if it belongs to no group."""
        base = self._sidecar_result.sidecar_of.get(path, path)
        return {base, *self._sidecar_result.groups.get(base, [])}

    def _expand_to_groups(self, paths) -> set[str]:
        """*paths* plus every member of the sidecar groups they belong to."""
        expanded: set[str] = set()
        for path in paths:
            expanded |= self._group_of(path)
        return expanded

    def _link_group_selection(self) -> None:
        """Keep whole sidecar groups selected/deselected together.

        A plain click (no modifier) or Shift range-select *replaces* the
        whole selection with whatever Qt just computed — it is never a
        per-item toggle, even when the click lands on a file that was
        already selected as part of a group (re-clicking any member of an
        already-selected group must keep the whole group selected, just
        like re-clicking a lone, ungrouped file leaves it selected). In
        that case every newly selected file simply pulls its whole group
        in, with no reference to what was selected before.

        Only a genuine Ctrl+click is a toggle of a single item against the
        existing selection. There, comparing against the selection left by
        the previous call (``self._prev_group_selection``) is required:
        every newly *deselected* file pushes its whole group back out,
        even though other members of that group are still individually
        selected. Without tracking what changed, a Ctrl+click meant to
        deselect one member of an already-fully-selected group would be
        immediately undone: the remaining selected siblings would still
        resolve to the same group and re-select it whole.
        """
        if self._sidecar_result is None:
            return
        root = self._ui.tblFiles.invisibleRootItem()
        path_to_item = {
            root.child(i).data(0, Qt.ItemDataRole.UserRole): root.child(i)
            for i in range(root.childCount())
        }
        new_selected = {
            i.data(0, Qt.ItemDataRole.UserRole)
            for i in self._ui.tblFiles.selectedItems()
        }

        toggling = bool(
            QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier
        )
        if toggling:
            to_select = set(new_selected)
            for path in self._prev_group_selection - new_selected:
                to_select -= self._group_of(path)
            to_select |= self._expand_to_groups(
                new_selected - self._prev_group_selection
            )
        else:
            to_select = self._expand_to_groups(new_selected)

        if to_select != new_selected:
            self._linking_selection = True
            self._ui.tblFiles.blockSignals(True)
            for path, item in path_to_item.items():
                item.setSelected(path in to_select)
            self._ui.tblFiles.blockSignals(False)
            self._linking_selection = False

        self._prev_group_selection = to_select

    # ── Drag'n'drop ───────────────────────────────────────────────────────────

    def _with_sidecars(self, paths: list[str]) -> list[list[str]]:
        """Group dropped *paths* with the sidecars that follow them: each
        unit is [path, *sidecars], moved or skipped as a whole.  Sidecars
        come from the listing, or from the disk for files dropped from
        another application."""
        paths = list(dict.fromkeys(paths))
        listed = self._items_by_path()
        on_disk = sidecar.sidecars_on_disk(
            [p for p in paths if self._groups is None or p not in listed],
            _cfg.get_sidecar_config(),
        )
        followers = {p: self._sidecars_of(p) or on_disk.get(p, []) for p in paths}
        claimed = {sc for p in paths for sc in followers[p]}
        return [[p, *followers[p]] for p in paths if p not in claimed]

    def _on_files_dropped(self, paths: list[str], target_dir: str, move: bool) -> None:
        if not paths or not os.path.isdir(target_dir):
            return

        units: list[list[tuple[str, str]]] = []
        errors: list[str] = []
        for unit in self._with_sidecars(paths):
            pairs: list[tuple[str, str]] = []
            for src in unit:
                if not os.path.exists(src):
                    continue
                dest = os.path.join(target_dir, os.path.basename(src.rstrip(os.sep)))
                if same_file_path(dest, src, target_dir):
                    continue
                if os.path.isdir(src):
                    src_abs = os.path.abspath(src)
                    target_abs = os.path.abspath(target_dir)
                    if target_abs == src_abs or target_abs.startswith(src_abs + os.sep):
                        errors.append(
                            f"{os.path.basename(src)}: "
                            + _("cannot move/copy a folder into itself")
                        )
                        continue
                pairs.append((src, dest))
            if pairs:
                units.append(pairs)

        if not units:
            if errors:
                QMessageBox.warning(
                    self._window,
                    _("Move errors") if move else _("Copy errors"),
                    "\n".join(errors),
                    QMessageBox.StandardButton.Ok,
                )
            return

        conflicts = [(s, d) for unit in units for s, d in unit if os.path.exists(d)]
        overwrite_all = False
        if conflicts:
            box = QMessageBox(self._window)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(_("Confirm overwrite"))
            msg = _("{n} item(s) already exist in {dir} and would be overwritten.")
            box.setText(msg.format(n=len(conflicts), dir=target_dir))
            overwrite_btn = box.addButton(
                _("Overwrite"), QMessageBox.ButtonRole.YesRole
            )
            skip_btn = box.addButton(_("Skip"), QMessageBox.ButtonRole.NoRole)
            cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(cancel_btn)
            box.exec()
            clicked = box.clickedButton()
            if clicked is cancel_btn:
                return
            overwrite_all = clicked is overwrite_btn
            if clicked is skip_btn:
                # A file and its sidecars are skipped together.
                conflict_set = set(conflicts)
                units = [u for u in units if not conflict_set.intersection(u)]

        pending = [pair for unit in units for pair in unit]
        _log.info(
            "%s %d file(s) into %s",
            "Moving" if move else "Copying",
            len(pending),
            target_dir,
        )
        next_path = self.next_path_after([src for src, _dest in pending])
        done: list[tuple[str, str]] = []
        any_success = False
        for src, dest in pending:
            existed = os.path.lexists(dest)
            op = filetools.move_path if move else filetools.copy_path
            ok, err = op(src, dest, overwrite=overwrite_all)
            if ok:
                any_success = True
                # An overwritten copy cannot be undone by deleting it.
                if move or not existed:
                    done.append((src, dest))
            else:
                errors.append(f"{os.path.basename(src)}: {err}")

        if done:
            self._undo.add(MoveEntry(done) if move else CopyEntry(done))
            self.undo_stack_changed.emit()

        if errors:
            QMessageBox.warning(
                self._window,
                _("Move errors") if move else _("Copy errors"),
                "\n".join(errors),
                QMessageBox.StandardButton.Ok,
            )

        if any_success:
            self.reload()
            if move and not self._ui.tblFiles.selectedItems():
                self.set_current_path(next_path)

    # ── Selection, context menu, file information window ─────────────────────

    def _on_selection_changed(self) -> None:
        if self.sidecar_mode_active() and not self._linking_selection:
            self._link_group_selection()
        if self._file_info is not None and self._file_info.isVisible():
            self._refresh_file_info()
        self.selection_changed.emit()

    def show_file_info(self) -> None:
        if self._file_info is None:
            self._file_info = FileInfoWindow(self._window_state, self._window)
            self._file_info.field_requested.connect(self.field_requested)
        self._refresh_file_info()
        self._file_info.show()
        self._file_info.raise_()
        self._file_info.activateWindow()

    def _refresh_file_info(self) -> None:
        if self._file_info is None:
            return
        paths = self.selected_bases()
        if len(paths) > 1:
            self._file_info.show_multiple()
        elif paths and paths[0]:
            self._file_info.update_file(paths[0])
        else:
            self._file_info.show_empty()

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if column == _SIDECAR_COLUMN:
            self._open_sidecar(item)
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        # The thumbnail shows the picture in the viewer; the name opens the
        # file with its default application.
        if column == THUMB_COLUMN and self._is_media(path):
            self.view_requested.emit(path)
        else:
            _open_path(path)

    @staticmethod
    def _is_media(path: str) -> bool:
        ext = os.path.splitext(path)[1][1:].lower()
        config = _cfg.get_sidecar_config()
        media = config.base_extensions.get("image", frozenset()) | (
            config.base_extensions.get("video", frozenset())
        )
        return ext in media and os.path.isfile(path)

    def _on_context_menu(self, pos) -> None:
        """The context menu is the Images menu."""
        _exec_menu(self._ui.menuImages, self._ui.tblFiles.viewport().mapToGlobal(pos))
