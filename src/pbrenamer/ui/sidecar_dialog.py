"""Standalone dialog for configuring sidecar-file categories."""

from __future__ import annotations

from functools import partial

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QMessageBox

from pbrenamer import settings
from pbrenamer.core.sidecar import BASE_CATEGORIES, CATEGORIES
from pbrenamer.resources import path as _resource
from pbrenamer.ui.geometry_mixin import GeometryMixin
from pbrenamer.ui.sidecar_dialog_ui import Ui_SidecarDialog


def _category_label(category: str) -> str:
    """Translated display label for a base-extension category.

    Computed on each call (not module-level) so it reflects whatever
    language is active when called, matching every other translated
    string in this file.
    """
    return {
        "image": _("Images"),
        "video": _("Video"),
        "audio": _("Audio"),
        "other": _("Other"),
    }[category]


class SidecarDialog(GeometryMixin, QDialog):
    """Configure per-category base extensions and sidecar suffixes."""

    def __init__(self, window_state, parent=None) -> None:
        super().__init__(parent)
        self._ui = Ui_SidecarDialog()
        self._ui.setupUi(self)
        self._init_geometry(window_state, "sidecar_dialog")

        icon_add = QIcon(_resource("add.svg"))
        icon_remove = QIcon(_resource("remove.svg"))
        icon_refresh = QIcon(_resource("refresh.svg"))

        for category in BASE_CATEGORIES:
            self._ui.btnBaseExtAdd[category].setIcon(icon_add)
            self._ui.btnBaseExtAdd[category].clicked.connect(
                partial(self._on_add_base_ext, category)
            )
            self._ui.edtBaseExt[category].returnPressed.connect(
                partial(self._on_add_base_ext, category)
            )
            self._ui.btnBaseExtRemove[category].setIcon(icon_remove)
            self._ui.btnBaseExtRemove[category].clicked.connect(
                partial(self._on_remove_base_ext, category)
            )
            self._ui.btnRestoreBaseExt[category].setIcon(icon_refresh)
            self._ui.btnRestoreBaseExt[category].clicked.connect(
                partial(self._on_restore_base_ext, category)
            )

        for category in CATEGORIES:
            self._ui.btnSidecarSuffixAdd[category].setIcon(icon_add)
            self._ui.btnSidecarSuffixAdd[category].clicked.connect(
                partial(self._on_add_sidecar_suffix, category)
            )
            self._ui.edtSidecarSuffix[category].returnPressed.connect(
                partial(self._on_add_sidecar_suffix, category)
            )
            self._ui.btnSidecarSuffixRemove[category].setIcon(icon_remove)
            self._ui.btnSidecarSuffixRemove[category].clicked.connect(
                partial(self._on_remove_sidecar_suffix, category)
            )
            self._ui.btnRestoreSidecarSuffix[category].setIcon(icon_refresh)
            self._ui.btnRestoreSidecarSuffix[category].clicked.connect(
                partial(self._on_restore_sidecar_suffix, category)
            )

        self._ui.btnSidecarCommonAdd.setIcon(icon_add)
        self._ui.btnSidecarCommonAdd.clicked.connect(self._on_add_sidecar_common)
        self._ui.edtSidecarCommon.returnPressed.connect(self._on_add_sidecar_common)
        self._ui.btnSidecarCommonRemove.setIcon(icon_remove)
        self._ui.btnSidecarCommonRemove.clicked.connect(self._on_remove_sidecar_common)
        self._ui.btnRestoreSidecarCommon.setIcon(icon_refresh)
        self._ui.btnRestoreSidecarCommon.clicked.connect(
            self._on_restore_sidecar_common
        )

        self._ui.buttonBox.rejected.connect(self.reject)

        self._reload_base_extensions()
        self._reload_sidecar_suffixes()

    # ── Base extensions ───────────────────────────────────────────────────────

    def _base_ext_category(self, ext: str) -> str | None:
        """Return the category *ext* is already assigned to, if any."""
        for category in BASE_CATEGORIES:
            if ext in settings.get_sidecar_base_extensions(category):
                return category
        return None

    def _reload_base_extensions(self) -> None:
        for category in BASE_CATEGORIES:
            lst = self._ui.lstBaseExt[category]
            lst.clear()
            for ext in settings.get_sidecar_base_extensions(category):
                lst.addItem(ext)

    def _on_add_base_ext(self, category: str) -> None:
        ext = self._ui.edtBaseExt[category].text().strip().lstrip(".").lower()
        if not ext:
            return
        existing_category = self._base_ext_category(ext)
        if existing_category is not None and existing_category != category:
            QMessageBox.warning(
                self,
                _("Duplicate extension"),
                _("{ext!r} is already assigned to the {category} category.").format(
                    ext=ext, category=_category_label(existing_category)
                ),
            )
            return
        exts = settings.get_sidecar_base_extensions(category)
        exts.append(ext)
        settings.set_sidecar_base_extensions(category, exts)
        self._ui.edtBaseExt[category].clear()
        self._reload_base_extensions()

    def _on_remove_base_ext(self, category: str) -> None:
        lst = self._ui.lstBaseExt[category]
        selected_rows = {lst.row(it) for it in lst.selectedItems()}
        exts = settings.get_sidecar_base_extensions(category)
        settings.set_sidecar_base_extensions(
            category, [e for i, e in enumerate(exts) if i not in selected_rows]
        )
        self._reload_base_extensions()

    def _on_restore_base_ext(self, category: str) -> None:
        settings.restore_sidecar_base_extensions_defaults(category)
        self._reload_base_extensions()

    # ── Sidecar suffixes ──────────────────────────────────────────────────────

    def _reload_sidecar_suffixes(self) -> None:
        for category in CATEGORIES:
            lst = self._ui.lstSidecarSuffix[category]
            lst.clear()
            for suffix in settings.get_sidecar_suffixes(category):
                lst.addItem(suffix)
        self._ui.lstSidecarCommon.clear()
        for suffix in settings.get_sidecar_common_suffixes():
            self._ui.lstSidecarCommon.addItem(suffix)

    def _on_add_sidecar_suffix(self, category: str) -> None:
        suffix = self._ui.edtSidecarSuffix[category].text().strip().lstrip(".")
        if not suffix:
            return
        suffixes = settings.get_sidecar_suffixes(category)
        suffixes.append(suffix)
        settings.set_sidecar_suffixes(category, suffixes)
        self._ui.edtSidecarSuffix[category].clear()
        self._reload_sidecar_suffixes()

    def _on_remove_sidecar_suffix(self, category: str) -> None:
        lst = self._ui.lstSidecarSuffix[category]
        selected_rows = {lst.row(it) for it in lst.selectedItems()}
        suffixes = settings.get_sidecar_suffixes(category)
        settings.set_sidecar_suffixes(
            category, [s for i, s in enumerate(suffixes) if i not in selected_rows]
        )
        self._reload_sidecar_suffixes()

    def _on_restore_sidecar_suffix(self, category: str) -> None:
        settings.restore_sidecar_suffixes_defaults(category)
        self._reload_sidecar_suffixes()

    def _on_add_sidecar_common(self) -> None:
        suffix = self._ui.edtSidecarCommon.text().strip().lstrip(".")
        if not suffix:
            return
        suffixes = settings.get_sidecar_common_suffixes()
        suffixes.append(suffix)
        settings.set_sidecar_common_suffixes(suffixes)
        self._ui.edtSidecarCommon.clear()
        self._reload_sidecar_suffixes()

    def _on_remove_sidecar_common(self) -> None:
        lst = self._ui.lstSidecarCommon
        selected_rows = {lst.row(it) for it in lst.selectedItems()}
        suffixes = settings.get_sidecar_common_suffixes()
        settings.set_sidecar_common_suffixes(
            [s for i, s in enumerate(suffixes) if i not in selected_rows]
        )
        self._reload_sidecar_suffixes()

    def _on_restore_sidecar_common(self) -> None:
        settings.restore_sidecar_common_suffixes_defaults()
        self._reload_sidecar_suffixes()
