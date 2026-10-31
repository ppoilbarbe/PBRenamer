"""Pattern rule panel: search / replace patterns, post-processing, named saves."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QStyledItemDelegate

import pbrenamer.settings as _cfg
from pbrenamer.core import filetools, planner
from pbrenamer.core import replacement as _repl
from pbrenamer.resources import path as _resource
from pbrenamer.ui.file_list import FileListController, PreviewEntry
from pbrenamer.ui.pattern_help import PatternHelpDialog, replace_html, search_html
from pbrenamer.ui.presets import PatternPresets
from pbrenamer.ui.widgets import WhitespaceLineEdit
from pbrenamer.ui.window_state import WindowState

_log = logging.getLogger(__name__)
_SAVE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_INVALID_STYLE = "QLineEdit { background-color: #ffaaaa; }"


def resolve_extension_mode(cfg: dict) -> str | None:
    """Return the extension mode from *cfg*, or None if absent.

    Reads the current ``"extension_mode"`` key if present, else migrates the
    legacy ``"keep_extension"`` bool (``True`` -> "keep", ``False`` ->
    "modify") from configs saved before the enum was introduced.
    """
    if "extension_mode" in cfg:
        return str(cfg["extension_mode"])
    if "keep_extension" in cfg:
        return "keep" if cfg["keep_extension"] else "modify"
    return None


def error_text(error: Exception) -> str:
    """Return the preview text of a name-computation *error*."""
    if isinstance(error, filetools.TargetPathError):
        _log.debug("Preview: %s", error)
        if error.reason == filetools.TargetPathError.NO_DEST:
            return _("⚠ no destination for {dest}")
        if error.reason == filetools.TargetPathError.DEST_POSITION:
            return _("⚠ {dest} must start the name")
        if error.reason == filetools.TargetPathError.ABSOLUTE:
            return _("⚠ absolute path")
        if error.reason == filetools.TargetPathError.EXT_SEPARATOR:
            return _("⚠ extension separator removed")
        return _("⚠ invalid path")
    if error.namespaces:
        types = "/".join(ns.rstrip(":") for ns in sorted(error.namespaces))
        return _("⚠ no matching type ({types})").format(types=types)
    return _("⚠ {field} unavailable").format(field=error.field)


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


class PatternRulePanel(QObject):
    """Rule panel of the Pattern mode: computes new names from the search and
    replace patterns, the post-processing options and the extension mode.

    Emits :attr:`edited` when a pattern text changes (debounced preview) and
    :attr:`changed` when an option changes (immediate preview).
    """

    edited = Signal()
    changed = Signal()

    def __init__(
        self,
        ui,
        presets: PatternPresets,
        window_state: WindowState,
        files: FileListController,
        parent: QMainWindow,
    ) -> None:
        super().__init__(parent)
        self._ui = ui
        self._window = parent
        self._presets = presets
        self._window_state = window_state
        self._files = files
        self._search_help: PatternHelpDialog | None = None
        self._replace_help: PatternHelpDialog | None = None

        self.populate_pattern_combos()
        self._populate_named_saves()
        self._setup_help_buttons()
        self._connect_signals()

    # ── Initial setup ─────────────────────────────────────────────────────────

    def _setup_help_buttons(self) -> None:
        help_icon = QIcon(_resource("question.svg"))
        self._ui.btnSearchHelp.setIcon(help_icon)
        self._ui.btnReplaceHelp.setIcon(help_icon)
        add_icon = QIcon(_resource("add.svg"))
        self._ui.btnSearchAdd.setIcon(add_icon)
        self._ui.btnReplaceAdd.setIcon(add_icon)
        self._ui.cmbPatternSearch.view().setItemDelegate(
            _SearchModeDelegate(self._ui.cmbPatternSearch)
        )
        self._ui.cmbPatternSearch.setLineEdit(WhitespaceLineEdit())
        self._ui.cmbPatternDest.setLineEdit(WhitespaceLineEdit())

    def populate_pattern_combos(self) -> None:
        self._populate_search_combo()
        self._populate_replace_combo()

    def _populate_search_combo(self) -> None:
        self._ui.cmbPatternSearch.clear()
        for mode, pattern in self._presets.get_search():
            self._ui.cmbPatternSearch.addItem(pattern, mode)
        self._update_search_add_button()

    def _populate_replace_combo(self) -> None:
        self._ui.cmbPatternDest.clear()
        for pattern in self._presets.get_replace():
            self._ui.cmbPatternDest.addItem(pattern)
        self._update_replace_add_button()

    def _connect_signals(self) -> None:
        # Post-processing and extension mode
        self._ui.cmbSpaces.currentIndexChanged.connect(self._on_post_process_changed)
        self._ui.chkRemoveAccents.toggled.connect(self._on_post_process_changed)
        self._ui.chkRemoveDuplicates.toggled.connect(self._on_post_process_changed)
        self._ui.cmbCaps.currentIndexChanged.connect(self._on_post_process_changed)
        self._ui.cmbExtensionMode.currentIndexChanged.connect(
            self._on_extension_mode_changed
        )

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

    # ── Public interface ──────────────────────────────────────────────────────

    def set_presets(self, presets: PatternPresets) -> None:
        """Use *presets* (those of another profile) and repopulate the combos."""
        self._presets = presets
        self.populate_pattern_combos()
        self._populate_named_saves()

    def extension_mode(self) -> str | None:
        return self._ui.cmbExtensionMode.currentData()

    def insert_field(self, field: str) -> None:
        self._ui.cmbPatternDest.lineEdit().insert(field)

    def record_history(self) -> None:
        """Promote the current patterns in the history after a rename."""
        search = self._ui.cmbPatternSearch.currentText()
        replace = self._ui.cmbPatternDest.currentText()
        if search:
            self._presets.add_search(self._current_search_mode(), search)
        if replace:
            self._presets.add_replace(replace)
        self.populate_pattern_combos()
        self._ui.cmbPatternSearch.setCurrentIndex(0)
        self._ui.cmbPatternDest.setCurrentIndex(0)

    def preview(
        self,
        paths: list[str],
        followers: Mapping[str, list[tuple[str, str]]] | None = None,
    ) -> list[PreviewEntry] | None:
        """Return the preview entry of each path in *paths*, or None when the
        rule is incomplete or invalid (nothing to display).  *followers* maps
        base paths to the sidecars following them (see
        planner.compute_names); those sidecars get an empty entry."""
        rule = self.rule()
        if rule is None:
            return None
        _log.info(
            "Preview: %d item(s), mode=%s, search=%r, replace=%r",
            len(paths),
            rule.mode,
            rule.search,
            rule.replace,
        )
        entries: list[PreviewEntry] = []
        for path, entry in zip(
            paths,
            planner.compute_names(
                rule,
                paths,
                followers=followers,
            ),
            strict=True,
        ):
            if entry.error is not None:
                entries.append(PreviewEntry(error_text(entry.error), error=True))
            else:
                _log.debug("Preview: %r → %r", path, entry.new_name)
                entries.append(PreviewEntry(entry.new_name or ""))
        return entries

    def rule(self) -> planner.Rule | None:
        """Return the rule described by the panel, or None when it is
        incomplete or invalid."""
        search = self._ui.cmbPatternSearch.currentText()
        if not search:
            return None
        if not self._validate_search_input() or not self._validate_replace_input():
            return None
        sep_idx = self._ui.cmbSpaces.currentIndex()
        caps_idx = self._ui.cmbCaps.currentIndex()
        return planner.Rule(
            search=search,
            replace=self._ui.cmbPatternDest.currentText(),
            mode=self._current_search_mode(),
            case_insensitive=self._ui.chkCaseInsensitive.isChecked(),
            ext_mode=self._ui.cmbExtensionMode.currentData(),
            normalization=_cfg.get_extension_normalization_map(),
            spaces=sep_idx - 1 if sep_idx > 0 else None,
            remove_accents=self._ui.chkRemoveAccents.isChecked(),
            remove_duplicates=self._ui.chkRemoveDuplicates.isChecked(),
            capitalization=caps_idx - 1 if caps_idx > 0 else None,
            sidecar_config=_cfg.get_sidecar_config(),
        )

    # ── Validation ────────────────────────────────────────────────────────────

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
        self.edited.emit()

    def _on_replace_text_changed(self) -> None:
        self._validate_replace_input()
        self._update_replace_add_button()
        self.edited.emit()

    def _on_mode_changed(self) -> None:
        self._validate_search_input()
        self._validate_replace_input()
        self._update_search_add_button()
        self.changed.emit()

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

    # ── Pattern help dialogs ──────────────────────────────────────────────────

    def _on_search_help(self) -> None:
        if self._search_help is None:
            self._search_help = PatternHelpDialog(
                search_html(),
                _("Search — Help"),
                "help_search",
                self._window_state,
                self._window,
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
                self._window,
            )
        if self._replace_help.isVisible():
            self._replace_help.raise_()
            self._replace_help.activateWindow()
        else:
            self._replace_help.show()

    # ── Post-processing and extension mode ────────────────────────────────────

    def _on_post_process_changed(self) -> None:
        self.changed.emit()

    def _on_extension_mode_changed(self) -> None:
        self._files.update_sidecar_checkbox_state()
        if self._ui.chkSidecarMode.isChecked():
            self._files.reload()
        else:
            self.changed.emit()

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
        self._populate_search_combo()
        self._ui.cmbPatternSearch.setCurrentIndex(0)

    def _on_add_replace(self) -> None:
        pattern = self._ui.cmbPatternDest.currentText()
        if not pattern:
            return
        self._presets.add_replace(pattern)
        self._populate_replace_combo()
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
        self._populate_search_combo()
        self._ui.cmbPatternSearch.setCurrentIndex(0)

    def _on_replace_preset_selected(self, index: int) -> None:
        if index < 0:
            return
        pattern = self._ui.cmbPatternDest.itemText(index)
        if not pattern:
            return
        self._presets.add_replace(pattern)
        self._populate_replace_combo()
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
            "extension_mode": self._ui.cmbExtensionMode.currentData(),
            "sidecar_mode": self._ui.chkSidecarMode.isChecked(),
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
        ext_mode = resolve_extension_mode(cfg)
        if ext_mode is not None:
            idx = self._ui.cmbExtensionMode.findData(ext_mode)
            if idx >= 0:
                self._ui.cmbExtensionMode.setCurrentIndex(idx)
        if "sidecar_mode" in cfg:
            self._ui.chkSidecarMode.setChecked(bool(cfg["sidecar_mode"]))
        self._files.update_sidecar_checkbox_state()
        current_filter = self._ui.edtFilter.text()
        new_filter = cfg.get("filter", "")
        self._ui.edtFilter.setText(new_filter)
        if new_filter != current_filter:
            self._files.reload()

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
