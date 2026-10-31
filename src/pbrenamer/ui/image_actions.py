"""Image tools of the file list (ported from PBPicat): the Images menu,
which is also the file list context menu, and the image viewer.

Open, Open with, Open sidecar, View, Template, Delete, Orphan sidecars, lossless
rotations and EXIF orientation (undoable), Refresh.  The actions apply to
the selected files, or to the current row when nothing is selected.
"""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import QFile, QObject, Qt, Signal
from PySide6.QtWidgets import QDialog, QMessageBox

import pbrenamer.settings as _cfg
from pbrenamer import profiles
from pbrenamer.core import filetools, image_ops, schema
from pbrenamer.core.undo import ExifResetEntry, RotationEntry, UndoManager
from pbrenamer.platform import open_with as _open_with
from pbrenamer.ui.file_list import FileListController, _open_path
from pbrenamer.ui.image_viewer import ImageViewer
from pbrenamer.ui.orphan_sidecars_dialog import OrphanSidecarsDialog
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


class ImageActions(QObject):
    """Wire the image actions of *ui* to the file list *files*."""

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
    ) -> None:
        super().__init__(parent)
        self._ui = ui
        self._files = files
        self._undo = undo
        self._window_state = window_state
        self._window = parent
        self._viewer: ImageViewer | None = None

        ui.actionImgOpen.triggered.connect(self.open_selected)
        ui.actionImgOpenWith.triggered.connect(self.open_with_selected)
        ui.actionImgView.triggered.connect(self.view_selected)
        ui.actionImgTemplate.triggered.connect(self.template_selected)
        ui.actionImgDelete.triggered.connect(self.delete_selected)
        ui.actionImgOrphans.triggered.connect(self.show_orphans)
        ui.actionRotateLeft.triggered.connect(lambda: self.rotate_selected(-90))
        ui.actionRotate180.triggered.connect(lambda: self.rotate_selected(180))
        ui.actionRotateRight.triggered.connect(lambda: self.rotate_selected(90))
        ui.actionRotateExif.triggered.connect(lambda: self.rotate_selected("auto"))
        ui.actionResetExif.triggered.connect(self.reset_exif_selected)
        ui.actionRefresh.triggered.connect(self._files.reload)
        ui.menuImages.aboutToShow.connect(self._update_orphans_action)
        ui.menuImages.aboutToShow.connect(self._fill_open_sidecar_menu)
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
        for act in (ui.actionImgOpen, ui.actionImgOpenWith, ui.actionImgDelete):
            act.setEnabled(bool(paths))
        ui.actionImgView.setEnabled(bool(self._media(paths)))
        ui.actionImgTemplate.setEnabled(len(paths) == 1)
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
        self._ui.actionImgOrphans.setEnabled(bool(self._files.orphan_sidecars()))

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
        """Sidecars of the targeted files, grouped by suffix (``xmp``,
        ``info.json``…), suffixes and paths sorted."""
        bases = self.targets()
        found: dict[str, list[str]] = {}
        for base, sidecars in self._files.sidecars_map(bases).items():
            stem = os.path.splitext(os.path.basename(base))[0]
            for path in sidecars:
                suffix = os.path.basename(path)[len(stem) + 1 :]
                found.setdefault(suffix.lower(), []).append(path)
        return {s: sorted(found[s]) for s in sorted(found)}

    def _fill_open_sidecar_menu(self) -> None:
        """One "Open sidecar" entry per suffix; disabled without sidecars."""
        menu = self._ui.menuOpenSidecar
        menu.clear()
        by_suffix = self.sidecars_by_suffix()
        for suffix, paths in by_suffix.items():
            label = suffix if len(paths) == 1 else f"{suffix} ({len(paths)})"
            action = menu.addAction(label)
            action.setStatusTip(", ".join(os.path.basename(p) for p in paths))
            action.triggered.connect(
                lambda _checked=False, p=paths: self.open_sidecars(p)
            )
        menu.menuAction().setEnabled(bool(by_suffix))

    def open_sidecars(self, paths: list[str]) -> None:
        for path in paths:
            _open_path(path)

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
        images = profiles.load()["images"]
        viewer = ImageViewer(
            self._window_state,
            self._window,
            zoom_step_percent=images["zoom_step_percent"],
            zoom_max_percent=images["zoom_max_percent"],
            auto_rotate=images["exif_auto_rotate"],
            metadata_panel_side=images["metadata_panel_side"],
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
        viewer.delete_requested.connect(
            lambda: self._on_viewer(lambda p: self.delete([p], viewer))
        )
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

    def delete(self, paths: list[str], parent=None) -> None:
        """Delete *paths* with their sidecars, then select the next row."""
        if not paths:
            return
        sidecars = self._files.sidecars_map(paths)
        files = list(dict.fromkeys(f for p in paths for f in [p, *sidecars[p]]))
        next_path = self._files.next_path_after(files)
        if self.delete_files(files, parent or self._window):
            self._files.reload()
            self._files.select_after_change([], next_path)

    def delete_files(self, files: list[str], parent) -> list[str]:
        """Confirm (per profile), then delete *files*: to the trash or for
        good; return the deleted ones.  Errors are reported together."""
        images = profiles.load()["images"]
        trash = images["use_trash"]
        if images["confirm_deletions"] and not _ask(
            parent, _("Confirm deletion"), self._confirm_text(files, images)
        ):
            return []
        deleted: list[str] = []
        errors: list[str] = []
        for path in files:
            name = os.path.basename(path)
            if trash:
                if QFile.moveToTrash(path):
                    deleted.append(path)
                else:
                    message = _("Could not move to trash: {name}")
                    errors.append(message.format(name=name))
                continue
            try:
                os.remove(path)
                deleted.append(path)
            except OSError as exc:
                errors.append(f"{name}: {exc}")
        _log.info("Deleted %d file(s), trash=%s", len(deleted), trash)
        if not trash:
            self._remove_empty_dirs(deleted)
        if errors:
            _warn(parent, _("Deletion error"), "\n".join(errors))
        return deleted

    @staticmethod
    def _confirm_text(files: list[str], images: dict) -> str:
        many = len(files) > images["delete_list_max_files"]
        names = "\n".join(os.path.basename(f) for f in files)
        if images["use_trash"]:
            if many:
                return _("Move {count} files to trash?").format(count=len(files))
            return _("Move to trash:\n{names}").format(names=names)
        if many:
            return _("Permanently delete {count} files?").format(count=len(files))
        return _("Permanently delete:\n{names}").format(names=names)

    def _remove_empty_dirs(self, deleted: list[str]) -> None:
        """Remove the folders left empty below the displayed one."""
        root = os.path.abspath(self._files.current_dir or "")
        dirs: set[str] = set()
        for path in deleted:
            directory = os.path.dirname(os.path.abspath(path))
            while directory != root and directory.startswith(root + os.sep):
                dirs.add(directory)
                directory = os.path.dirname(directory)
        for directory in sorted(dirs, key=len, reverse=True):
            if not os.listdir(directory):
                filetools.remove_empty_dirs([directory])

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
        for path in paths:
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
        for path in paths:
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
