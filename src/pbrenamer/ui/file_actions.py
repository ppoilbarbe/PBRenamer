"""Actions on the listed files (ported from PBPicat): the File menu, the
Images menu, the file list context menu, and the image viewer.

Any file: Open, Open with, Open or create sidecar, Template, Delete, Orphan sidecars,
Refresh.  Images and videos only: View (image viewer), lossless rotations
and EXIF orientation (undoable).  The actions apply to the selected files,
or to the current row when nothing is selected.
"""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QDialog, QMessageBox

import pbrenamer.settings as _cfg
from pbrenamer import profiles
from pbrenamer.core import filetools, image_ops, schema, sidecar
from pbrenamer.core.trash import CrossDeviceError, SessionTrash
from pbrenamer.core.undo import (
    DeleteEntry,
    ExifResetEntry,
    RotationEntry,
    UndoManager,
)
from pbrenamer.platform import open_with as _open_with
from pbrenamer.platform import trash as system_trash
from pbrenamer.ui.file_list import FileListController, _open_path
from pbrenamer.ui.image_viewer import ImageViewer
from pbrenamer.ui.orphan_sidecars_dialog import OrphanSidecarsDialog
from pbrenamer.ui.progress import FileProgress
from pbrenamer.ui.rule_panel_schema import field_title
from pbrenamer.ui.schema_proposal_dialog import SchemaProposalDialog

_log = logging.getLogger(__name__)

# Above this many images, EXIF orientations are not read to enable the
# "Apply / Force EXIF orientation" actions: they stay enabled.
_EXIF_CHECK_MAX = 50


def _exec_dialog(dialog: QDialog) -> int:  # pragma: no cover — modal, patched in tests
    return dialog.exec()


def _ask(parent, title: str, text: str) -> bool:  # pragma: no cover — modal
    reply = QMessageBox.question(
        parent,
        title,
        text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    return reply == QMessageBox.StandardButton.Yes


def _warn(parent, title: str, text: str, details: str = "") -> None:  # pragma: no cover
    box = QMessageBox(QMessageBox.Icon.Warning, title, text, parent=parent)
    if details:
        box.setDetailedText(details)
    box.exec()


def _ext(path: str) -> str:
    return os.path.splitext(path)[1][1:].lower()


class FileActions(QObject):
    """Wire the file and image actions of *ui* to the file list *files*."""

    undo_stack_changed = Signal()
    template_accepted = Signal(list)
    status_message = Signal(str)

    def __init__(
        self,
        ui,
        files: FileListController,
        undo: UndoManager,
        window_state,
        parent,
        trash: SessionTrash | None = None,
    ) -> None:
        super().__init__(parent)
        self._trash = trash or SessionTrash(_cfg.cache_home() / "trash")
        self._ui = ui
        self._files = files
        self._undo = undo
        self._window_state = window_state
        self._window = parent
        self._viewer: ImageViewer | None = None

        ui.actionFileOpen.triggered.connect(self.open_selected)
        ui.actionFileOpenWith.triggered.connect(self.open_with_selected)
        ui.actionImageView.triggered.connect(self.view_selected)
        ui.actionFileTemplate.triggered.connect(self.template_selected)
        ui.actionFileDelete.triggered.connect(self.delete_selected)
        ui.actionFileOrphans.triggered.connect(self.show_orphans)
        ui.actionRotateLeft.triggered.connect(lambda: self.rotate_selected(-90))
        ui.actionRotate180.triggered.connect(lambda: self.rotate_selected(180))
        ui.actionRotateRight.triggered.connect(lambda: self.rotate_selected(90))
        ui.actionRotateExif.triggered.connect(lambda: self.rotate_selected("auto"))
        ui.actionResetExif.triggered.connect(self.reset_exif_selected)
        ui.actionRefresh.triggered.connect(self._files.reload)
        # Menus holding Orphan sidecars and Open sidecar.
        for menu in (ui.menuFile, ui.menuContext):
            menu.aboutToShow.connect(self._update_orphans_action)
            menu.aboutToShow.connect(self._fill_open_sidecar_menu)
        files.selection_changed.connect(self.update_enabled)
        files.selection_changed.connect(self._sync_viewer)
        files.files_reloaded.connect(self._on_files_reloaded)
        files.view_requested.connect(self.show_in_viewer)

    # ── Targets ───────────────────────────────────────────────────────────────

    def targets(self) -> list[str]:
        """Selected files (a sidecar group counts as its base file), or the
        current row when nothing is selected."""
        paths = self._files.selected_bases()
        if not paths:
            item = self._ui.tblFiles.currentItem()
            if item is not None:
                paths = [item.data(0, Qt.ItemDataRole.UserRole)]
        return [p for p in paths if p and os.path.isfile(p)]

    @staticmethod
    def _extensions(category: str) -> frozenset[str]:
        return _cfg.get_sidecar_config().base_extensions.get(category, frozenset())

    def _images(self, paths: list[str]) -> list[str]:
        exts = self._extensions("image")
        return [p for p in paths if _ext(p) in exts]

    def _media(self, paths: list[str]) -> list[str]:
        exts = self._extensions("image") | self._extensions("video")
        return [p for p in paths if _ext(p) in exts]

    def _rotatable(self, images: list[str]) -> list[str]:
        if not image_ops.pillow_available():
            return []
        if image_ops.jpegtran_available():
            return images
        return [p for p in images if not image_ops.is_jpeg(p)]

    def update_enabled(self) -> None:
        """Enable the actions according to the targets."""
        ui = self._ui
        paths = self.targets()
        for act in (ui.actionFileOpen, ui.actionFileOpenWith, ui.actionFileDelete):
            act.setEnabled(bool(paths))
        ui.actionImageView.setEnabled(bool(self._media(paths)))
        ui.actionFileTemplate.setEnabled(len(paths) == 1)
        rotatable = self._rotatable(self._images(paths))
        for act in (ui.actionRotateLeft, ui.actionRotate180, ui.actionRotateRight):
            act.setEnabled(bool(rotatable))
        if len(rotatable) > _EXIF_CHECK_MAX:
            has_exif = True
        else:
            has_exif = any(image_ops.get_exif_orientation(p) for p in rotatable)
        ui.actionRotateExif.setEnabled(has_exif)
        ui.actionResetExif.setEnabled(has_exif and image_ops.pyexiv2_available())

    def _update_orphans_action(self) -> None:
        self._ui.actionFileOrphans.setEnabled(bool(self._files.orphan_sidecars()))

    def _on_files_reloaded(self) -> None:
        self.update_enabled()
        if self._viewer is not None and self._viewer.isVisible():
            current = self._viewer.current_path
            if current is not None and os.path.isfile(current):
                self._viewer.refresh_paths({current})

    # ── Open, Open with ───────────────────────────────────────────────────────

    def open_selected(self) -> None:
        for path in self.targets():
            _open_path(path)

    def open_with_selected(self) -> None:
        for path in self.targets():
            _open_with.open_with(path, self._window)

    def sidecars_by_suffix(self) -> dict[str, list[str]]:
        """Sidecars the targeted files can have, existing or not, grouped by
        suffix (``xmp``, ``info.json``…): every suffix of the category of
        each file, whatever the sidecar mode; nothing for a file that is
        itself a sidecar.  Suffixes and paths sorted."""
        config = _cfg.get_sidecar_config()
        found: dict[str, list[str]] = {}
        for base in self.targets():
            for suffix in sidecar.suffixes_for(os.path.basename(base), config):
                path = sidecar.sidecar_path(base, suffix)
                found.setdefault(suffix.lower(), []).append(path)
        return {s: sorted(found[s]) for s in sorted(found)}

    def _fill_open_sidecar_menu(self) -> None:
        """One "Open or create sidecar" entry per suffix; disabled when the
        targeted files have no sidecar suffix or are sidecars themselves."""
        menu = self._ui.menuOpenSidecar
        menu.clear()
        by_suffix = self.sidecars_by_suffix()
        for suffix, paths in by_suffix.items():
            if len(paths) > 1:
                label = f"{suffix} ({len(paths)})"
            elif os.path.isfile(paths[0]):
                label = suffix
            else:
                label = _("{suffix} (new)").format(suffix=suffix)
            action = menu.addAction(label)
            action.setStatusTip(", ".join(os.path.basename(p) for p in paths))
            action.triggered.connect(
                lambda _checked=False, p=paths: self.open_sidecars(p)
            )
        menu.menuAction().setEnabled(bool(by_suffix))

    def open_sidecars(self, paths: list[str]) -> None:
        """Open the sidecars *paths*, creating the missing ones empty."""
        self._files.open_or_create_sidecars(paths)

    # ── Viewer ────────────────────────────────────────────────────────────────

    def view_selected(self) -> None:
        media = self._media(self.targets())
        if media:
            self.show_in_viewer(media[0])

    def show_in_viewer(self, path: str) -> None:
        """Open (or reuse) the viewer on *path*; with several media files
        selected, it browses them with its selection strip."""
        media = self._media(self._files.selected_bases())
        if self._viewer is None:
            self._viewer = self._create_viewer()
        if path in media and len(media) > 1:
            self._viewer.set_selection(media, current=path)
        else:
            self._viewer.set_selection([path])
        self._viewer.show()
        self._viewer.raise_()
        self._viewer.activateWindow()

    def _sync_viewer(self) -> None:
        """Selection changed while the viewer is shown: it browses the
        selected media files.  It shows the current row when selected (the
        file just added), else keeps its file if still selected, else the
        first one.  An empty or media-less selection leaves it unchanged."""
        viewer = self._viewer
        if viewer is None or not viewer.isVisible():
            return
        media = self._media(self._files.selected_bases())
        if not media:
            return
        item = self._ui.tblFiles.currentItem()
        row = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        row = self._files.base_of(row) if row else None
        if row in media:
            current = row
        elif viewer.current_path in media:
            current = viewer.current_path
        else:
            current = media[0]
        if media == viewer.selection_paths and current == viewer.current_path:
            return
        viewer.set_selection(media, current=current)

    def _create_viewer(self) -> ImageViewer:
        options = profiles.load()["viewer"]
        viewer = ImageViewer(
            self._window_state,
            self._window,
            zoom_step_percent=options["zoom_step_percent"],
            zoom_max_percent=options["zoom_max_percent"],
            auto_rotate=options["exif_auto_rotate"],
            metadata_panel_side=options["metadata_panel_side"],
            video_extensions=self._extensions("video"),
            sidecars_of=lambda p: self._files.sidecars_map([p])[p],
        )
        viewer.navigate_prev.connect(lambda: self._navigate_viewer(-1))
        viewer.navigate_next.connect(lambda: self._navigate_viewer(+1))
        viewer.open_requested.connect(lambda: self._on_viewer(_open_path))
        viewer.open_with_requested.connect(
            lambda: self._on_viewer(lambda p: _open_with.open_with(p, viewer))
        )
        viewer.template_requested.connect(lambda: self._on_viewer(self.template))
        viewer.delete_requested.connect(self._delete_from_viewer)
        viewer.rotate_requested.connect(self._rotate_from_viewer)
        viewer.field_requested.connect(self._files.field_requested)
        return viewer

    def apply_profile(self) -> None:
        """Profile changed: the viewer is rebuilt with its settings."""
        if self._viewer is not None:
            self._viewer.close()
            self._viewer.deleteLater()
            self._viewer = None

    def _on_viewer(self, action) -> None:
        path = self._viewer.current_path if self._viewer is not None else None
        if path is not None:
            action(path)

    def _rotate_from_viewer(self, op) -> None:
        path = self._viewer.current_path if self._viewer is not None else None
        if path is None:
            return
        if op == "reset_exif":
            self.reset_exif([path])
        else:
            self.rotate([path], op)

    def _navigate_viewer(self, direction: int) -> None:
        """Arrow keys in the viewer showing a single file: select the
        previous/next media file of the list (wrapping around in circular
        mode); the viewer follows the selection."""
        if self._viewer is None or self._viewer.current_path is None:
            return
        listed = self._files.listed_paths()
        media = set(self._media(listed))
        try:
            start = listed.index(self._viewer.current_path)
        except ValueError:
            return
        count = len(listed)
        for step in range(1, count):
            row = start + step * direction
            if self._viewer.circular_navigation:
                row %= count
            elif not 0 <= row < count:
                return
            if listed[row] in media:
                self._files.select_paths([listed[row]])
                self._ui.tblFiles.scrollToItem(self._ui.tblFiles.currentItem())
                return

    # ── Template ──────────────────────────────────────────────────────────────

    def template_selected(self) -> None:
        paths = self.targets()
        if len(paths) == 1:
            self.template(paths[0])

    def template(self, path: str) -> None:
        """Infer the schema fields from *path*; on confirmation, emit them."""
        settings = profiles.get_schema()
        count = settings["field_count"]
        proposed = schema.infer_fields(path, count, profiles.get_all_history())
        if proposed is None:
            QMessageBox.information(
                self._window,
                _("Template"),
                _(
                    "Could not determine a template for “{name}”.\n"
                    "No part of the file name matches any field history."
                ).format(name=os.path.basename(path)),
            )
            return
        titles = [field_title(settings["field_titles"], i) for i in range(count)]
        dialog = SchemaProposalDialog(titles, proposed, self._window)
        if _exec_dialog(dialog) == QDialog.DialogCode.Accepted:
            self.template_accepted.emit(proposed)

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_selected(self) -> None:
        self.delete(self.targets(), self._window)

    def delete(self, paths: list[str], parent=None) -> list[str]:
        """Delete *paths*, with their sidecars in sidecar mode; return the
        deleted files.

        When nothing stays selected, the next file of the list is selected
        (the previous one after the last row), and the viewer follows."""
        if not paths:
            return []
        files = self._with_sidecars(paths)
        return self._delete_and_select(
            files, parent or self._window, self._files.next_path_after(files)
        )

    def _with_sidecars(self, paths: list[str]) -> list[str]:
        """*paths* followed by their sidecars in sidecar mode; outside it,
        sidecars are independent files and *paths* alone are returned."""
        if not self._files.sidecar_mode_active():
            return list(dict.fromkeys(paths))
        sidecars = self._files.sidecars_map(paths)
        return list(dict.fromkeys(f for p in paths for f in [p, *sidecars[p]]))

    def _delete_and_select(
        self, files: list[str], parent, next_path: str | None
    ) -> list[str]:
        """Delete *files*, then select *next_path* unless part of the
        selection remains.  A viewer left on a deleted file (the selected
        file is no media) moves to the nearest media file, or closes."""
        viewer = self._viewer
        if viewer is not None and not viewer.isVisible():
            viewer = None
        shown = viewer.current_path if viewer is not None else None
        fallback = self._neighbour_media(shown, set(files)) if shown in files else None
        deleted = self.delete_files(files, parent)
        if not deleted:
            return deleted
        self._files.reload()
        if self._files.selected_paths():
            self._files.set_current_path(next_path)
        elif next_path is not None:
            self._files.select_paths([next_path])
        if viewer is not None and viewer.current_path in deleted:
            if fallback is None:
                viewer.close()
            else:
                viewer.set_selection([fallback])
        return deleted

    def _neighbour_media(self, path: str, gone: set[str]) -> str | None:
        """The media file of the list following *path*, else the one
        preceding it, ignoring the files of *gone*."""
        listed = self._files.listed_paths()
        if path not in listed:
            return None
        row = listed.index(path)
        media = set(self._media(listed)) - gone
        after = [p for p in listed[row + 1 :] if p in media]
        if after:
            return after[0]
        before = [p for p in listed[:row] if p in media]
        return before[-1] if before else None

    def _delete_from_viewer(self) -> None:
        """Delete the file shown by the viewer.  Browsing a multiple
        selection, it then shows the next file of the selection; after the
        last one, the first in circular mode, else the new last one.
        Showing a single file, the next media file of the list is selected
        (the previous one after the last), and the viewer shows it; without
        any media file left, the next file is selected and the viewer closes.

        The viewer is then activated again: the confirmation box leaves no
        active window behind, and its keyboard shortcuts need one."""
        viewer = self._viewer
        path = viewer.current_path if viewer is not None else None
        if path is None:
            return
        self._delete_viewer_file(viewer, path)
        if viewer.isVisible():
            viewer.raise_()
            viewer.activateWindow()

    def _delete_viewer_file(self, viewer: ImageViewer, path: str) -> None:
        selection = viewer.selection_paths
        if len(selection) < 2 or path not in selection:
            files = self._with_sidecars([path])
            target = self._neighbour_media(path, set(files))
            if target is None:
                target = self._files.next_path_after(files)
            self._delete_and_select(files, viewer, target)
            return
        index = selection.index(path)
        deleted = set(self.delete([path], viewer))
        remaining = [p for p in selection if p not in deleted]
        if path not in deleted or not remaining:
            return
        if index < len(remaining):
            current = remaining[index]
        elif viewer.circular_navigation:
            current = remaining[0]
        else:
            current = remaining[-1]
        viewer.set_selection(remaining, current=current)
        self._files.set_current_path(current)

    def delete_files(self, files: list[str], parent) -> list[str]:
        """Confirm (per profile), then delete *files* as the profile's
        deletion mode says; return the deleted ones.

        Files moved to a trash (system or session) form one undoable batch.
        Errors are reported together."""
        options = profiles.load()["files"]
        mode = options["deletion_mode"]
        if options["confirm_deletions"] and not _ask(
            parent, _("Confirm deletion"), self._confirm_text(files, options)
        ):
            return []
        done: set[str] = set()
        trashed: list[tuple[str, str]] = []
        foreign: list[str] = []
        errors: list[str] = []
        for path in files:
            name = os.path.basename(path)
            if mode == "system":
                where = system_trash.move_to_trash(path)
                if where is None:
                    message = _("Could not move to trash: {name}")
                    errors.append(message.format(name=name))
                else:
                    trashed.append((os.path.abspath(path), where))
                    done.add(path)
                continue
            if mode == "session":
                try:
                    trashed.append((os.path.abspath(path), self._trash.put(path)))
                    done.add(path)
                except CrossDeviceError:
                    foreign.append(path)
                except OSError as exc:
                    errors.append(f"{name}: {exc}")
                continue
            self._remove_file(path, done, errors)
        if foreign and _ask(
            parent, _("Confirm deletion"), self._foreign_text(foreign, options)
        ):
            for path in foreign:
                self._remove_file(path, done, errors)
        deleted = [path for path in files if path in done]
        _log.info("Deleted %d file(s), mode=%s", len(deleted), mode)
        if trashed:
            self._undo.add(DeleteEntry(trashed, system=mode == "system"))
            self.undo_stack_changed.emit()
        root = self._files.current_dir
        if options["prune_dirs_on_delete"] and root:
            filetools.prune_empty_dirs(
                deleted, root, ancestors=options["prune_parent_dirs"]
            )
        if errors:
            _warn(parent, _("Deletion error"), "\n".join(errors))
        return deleted

    @staticmethod
    def _remove_file(path: str, done: set[str], errors: list[str]) -> None:
        try:
            os.remove(path)
            done.add(path)
        except OSError as exc:
            errors.append(f"{os.path.basename(path)}: {exc}")

    @staticmethod
    def _foreign_text(files: list[str], options: dict) -> str:
        if len(files) > options["delete_list_max_files"]:
            text = _(
                "{count} files are on another file system than the session "
                "trash and cannot be moved to it.\n"
                "Delete them permanently? This cannot be undone."
            )
            return text.format(count=len(files))
        names = "\n".join(os.path.basename(f) for f in files)
        text = _(
            "These files are on another file system than the session trash "
            "and cannot be moved to it:\n{names}\n"
            "Delete them permanently? This cannot be undone."
        )
        return text.format(names=names)

    @staticmethod
    def _confirm_text(files: list[str], options: dict) -> str:
        many = len(files) > options["delete_list_max_files"]
        names = "\n".join(os.path.basename(f) for f in files)
        mode = options["deletion_mode"]
        if mode == "system":
            if many:
                return _("Move {count} files to trash?").format(count=len(files))
            return _("Move to trash:\n{names}").format(names=names)
        if mode == "session":
            if many:
                text = _("Move {count} files to the session trash?")
                return text.format(count=len(files))
            return _("Move to the session trash:\n{names}").format(names=names)
        if many:
            return _("Permanently delete {count} files?").format(count=len(files))
        return _("Permanently delete:\n{names}").format(names=names)

    # ── Orphan sidecars ───────────────────────────────────────────────────────

    def show_orphans(self) -> None:
        dialog = OrphanSidecarsDialog(
            self._files.orphan_sidecars(),
            lambda files: self.delete_files(files, dialog),
            self._window_state,
            self._window,
        )
        _exec_dialog(dialog)
        self._files.reload()

    # ── Rotations and EXIF orientation ────────────────────────────────────────

    def rotate_selected(self, op: image_ops.Op) -> None:
        self.rotate(self._rotatable(self._images(self.targets())), op)

    def rotate(self, paths: list[str], op: image_ops.Op) -> None:
        """Rotate *paths* without loss (undoable); report the failures."""
        done: list[tuple[str, image_ops.Op, int | None]] = []
        errors: list[str] = []
        label = _("Rotating images…")
        with FileProgress(self._window, label, len(paths)) as progress:
            for path in paths:
                if not progress.step():
                    break
                orientation = image_ops.get_exif_orientation(path)
                if op == "auto" and orientation is None:
                    continue
                try:
                    inverse = image_ops.rotate_lossless(path, op)
                except (OSError, RuntimeError, ValueError) as exc:
                    errors.append(f"{os.path.basename(path)}\n{exc}")
                    continue
                done.append((path, inverse, orientation))
        if errors:
            _warn(
                self._window,
                _("Rotation unavailable"),
                _("{n} file(s) could not be rotated.").format(n=len(errors)),
                "\n\n".join(errors),
            )
        if done:
            self._undo.add(RotationEntry(done))
            self.undo_stack_changed.emit()
            self.status_message.emit(_("{n} file(s) rotated.").format(n=len(done)))
            self._files.reload()

    def reset_exif_selected(self) -> None:
        self.reset_exif(self._images(self.targets()))

    def reset_exif(self, paths: list[str]) -> None:
        """Set the EXIF orientation of *paths* to 1 (undoable)."""
        done: list[tuple[str, int]] = []
        label = _("Resetting EXIF orientations…")
        with FileProgress(self._window, label, len(paths)) as progress:
            for path in paths:
                if not progress.step():
                    break
                orientation = image_ops.get_exif_orientation(path)
                if orientation is None:
                    continue
                image_ops.set_exif_orientation(path, 1)
                done.append((path, orientation))
        if done:
            self._undo.add(ExifResetEntry(done))
            self.undo_stack_changed.emit()
            self.status_message.emit(
                _("{n} EXIF orientation tag(s) reset.").format(n=len(done))
            )
            self._files.reload()
