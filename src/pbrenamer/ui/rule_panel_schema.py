"""Schema rule panel: PBPicat-style fields, destination, video marker position."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import pbrenamer.settings as _cfg
from pbrenamer import profiles
from pbrenamer.core import planner, schema
from pbrenamer.ui.file_list import PreviewEntry
from pbrenamer.ui.rule_panel_pattern import error_text

_log = logging.getLogger(__name__)
_MESSAGE_STYLE = "QLabel { color: #cc0000; }"


class ForbiddenCharValidator(QValidator):
    """Reject any text containing one of *chars*."""

    def __init__(self, chars: str, parent=None) -> None:
        super().__init__(parent)
        self._chars = chars

    def validate(self, text: str, pos: int):
        if any(ch in text for ch in self._chars):
            return (QValidator.State.Invalid, text, pos)
        return (QValidator.State.Acceptable, text, pos)


def field_title(titles: list[str], index: int) -> str:
    """Title of the schema field *index* (0-based), with a default."""
    if index < len(titles) and titles[index]:
        return titles[index]
    return _("Field {n}").format(n=index + 1)


class _SchemaField(QWidget):
    """One schema field: its title above an editable combo with history."""

    def __init__(self, title: str, index: int, parent=None) -> None:
        super().__init__(parent)
        self._key = f"field_{index}"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        self.label = QLabel(title, self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.label)

        self.combo = QComboBox(self)
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo.lineEdit().setValidator(
            ForbiddenCharValidator(schema.FORBIDDEN_FIELD_CHARS, self.combo)
        )
        self.combo.setToolTip(
            _(
                "Schema field “{title}”: a directory level and a part of the"
                " name; “###” is the counter, an empty field is skipped"
            ).format(title=title)
        )
        layout.addWidget(self.combo)

        self.combo.addItems(profiles.get_history(self._key) or [""])

    def value(self) -> str:
        return self.combo.currentText().strip()

    def push_history(self, value: str, history_max: int) -> None:
        """Put *value* first in the history (LRU), at most *history_max*."""
        idx = self.combo.findText(value)
        if idx == 0:
            return
        if idx > 0:
            self.combo.removeItem(idx)
        self.combo.insertItem(0, value)
        while self.combo.count() > history_max:
            self.combo.removeItem(self.combo.count() - 1)
        self.combo.setCurrentIndex(0)
        profiles.set_history(
            self._key, [self.combo.itemText(i) for i in range(self.combo.count())]
        )


class SchemaRulePanel(QWidget):
    """Rule panel of the Schema mode: computes destination paths from the
    schema fields of the current profile.

    Emits :attr:`edited` when a text changes (debounced preview) and
    :attr:`changed` when an option changes (immediate preview).
    """

    edited = Signal()
    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._fields: list[_SchemaField] = []
        self._marker_group: QButtonGroup | None = None
        self._schema: dict = {}
        self._history_max = profiles.DEFAULTS["display"]["history_max"]

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.addLayout(self._make_dest_row())
        self._fields_row = QHBoxLayout()
        outer.addLayout(self._fields_row)
        self.lblMessage = QLabel(self)
        self.lblMessage.setStyleSheet(_MESSAGE_STYLE)
        self.lblMessage.setWordWrap(True)
        outer.addWidget(self.lblMessage)
        outer.addStretch()

        self.reload_profile()

    def _make_dest_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(_("Destination:"), self))

        self.edtDest = QLineEdit(self)
        self.edtDest.setPlaceholderText(_("Destination root directory…"))
        self.edtDest.setToolTip(_("Root of the destination tree"))
        self.edtDest.setStatusTip(
            _(
                "Files are moved under this directory, in sub-directories"
                " named after the fields"
            )
        )
        self.edtDest.textChanged.connect(lambda _text: self.edited.emit())
        row.addWidget(self.edtDest, 1)

        self.btnBrowse = QPushButton(_("Browse…"), self)
        self.btnBrowse.setToolTip(_("Choose the destination directory"))
        self.btnBrowse.clicked.connect(self._on_browse)
        row.addWidget(self.btnBrowse)

        self.chkFillGaps = QCheckBox(_("Fill gaps"), self)
        self.chkFillGaps.setToolTip(
            _("Fill numbering gaps instead of continuing after the highest number")
        )
        self.chkFillGaps.toggled.connect(self._on_fill_gaps_toggled)
        row.addWidget(self.chkFillGaps)
        return row

    # ── Profile ───────────────────────────────────────────────────────────────

    def reload_profile(self) -> None:
        """Rebuild the panel from the settings of the current profile."""
        data = profiles.load()
        self._schema = data["schema"]
        self._history_max = data["display"]["history_max"]
        self.edtDest.blockSignals(True)
        self.edtDest.setText(self._schema["dest"])
        self.edtDest.blockSignals(False)
        self.chkFillGaps.blockSignals(True)
        self.chkFillGaps.setChecked(self._schema["fill_gaps"])
        self.chkFillGaps.blockSignals(False)
        self._build_fields()
        self.lblMessage.clear()

    def _build_fields(self) -> None:
        while self._fields_row.count():
            widget = self._fields_row.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        self._fields.clear()
        if self._marker_group is not None:
            self._marker_group.deleteLater()

        count = max(1, self._schema["field_count"])
        titles = self._schema["field_titles"]
        position = self._schema["video_marker_pos"]
        self._marker_group = QButtonGroup(self)
        tooltip = _("Video marker position")
        for i in range(count + 1):
            radio = QRadioButton(self)
            radio.setToolTip(tooltip)
            radio.setChecked(i == position)
            self._marker_group.addButton(radio, i)
            self._fields_row.addWidget(radio)
            if i < count:
                field = _SchemaField(field_title(titles, i), i, self)
                field.combo.currentTextChanged.connect(lambda _t: self.edited.emit())
                self._fields.append(field)
                self._fields_row.addWidget(field, 1)
        self._marker_group.idToggled.connect(self._on_marker_toggled)

    def _on_marker_toggled(self, button_id: int, checked: bool) -> None:
        if checked:
            profiles.set_schema(video_marker_pos=button_id)
            self._schema["video_marker_pos"] = button_id
            self.changed.emit()

    def _on_fill_gaps_toggled(self, checked: bool) -> None:
        profiles.set_schema(fill_gaps=checked)
        self._schema["fill_gaps"] = checked
        self.changed.emit()

    def _on_browse(self) -> None:
        current = self.dest() or str(Path.home())
        path = QFileDialog.getExistingDirectory(
            self, _("Choose destination directory"), current
        )
        if path:
            self.edtDest.setText(path)
            self.save_dest()
            self.changed.emit()

    def save_dest(self) -> None:
        """Store the destination in the current profile."""
        profiles.set_schema(dest=self.dest())

    # ── Public interface ──────────────────────────────────────────────────────

    def dest(self) -> str:
        return os.path.expanduser(self.edtDest.text().strip())

    def fields(self) -> list[str]:
        return [f.value() for f in self._fields]

    def set_fields(self, values: list[str]) -> None:
        for field, value in zip(self._fields, values, strict=False):
            field.combo.setCurrentText(value)

    def video_marker_pos(self) -> int:
        checked = self._marker_group.checkedId() if self._marker_group else -1
        return max(checked, 0)

    def has_counter(self) -> bool:
        return any(schema.is_numeric(v) for v in self.fields())

    def record_history(self) -> None:
        """Promote the current field values in their histories after a rename."""
        for field in self._fields:
            field.push_history(field.value(), self._history_max)

    def rule(self, *, renumber: bool = False) -> planner.Rule | None:
        """Return the rule described by the panel, or None when it is
        incomplete or invalid (the reason is shown in the panel)."""
        dest = self.dest()
        if not renumber:
            if not dest:
                self.lblMessage.setText(_("Choose a destination directory."))
                return None
            if not os.path.isabs(dest):
                self.lblMessage.setText(_("The destination must be an absolute path."))
                return None
        try:
            rule = schema.compile_rule(
                self.fields(),
                dest_root=dest,
                video_marker=self._schema["video_marker"],
                video_marker_pos=self.video_marker_pos(),
                fill_gaps=self.chkFillGaps.isChecked(),
                renumber=renumber,
                sidecar_config=_cfg.get_sidecar_config(),
            )
        except schema.SchemaError as exc:
            self.lblMessage.setText(str(exc))
            return None
        self.lblMessage.clear()
        return rule

    def preview(
        self,
        paths: list[str],
        followers: Mapping[str, list[tuple[str, str]]] | None = None,
    ) -> list[PreviewEntry] | None:
        """Return the preview entry of each path in *paths* (target shown
        relative to the destination), or None when the rule is invalid."""
        rule = self.rule()
        if rule is None:
            return None
        _log.info("Schema preview: %d item(s), template=%r", len(paths), rule.replace)
        entries: list[PreviewEntry] = []
        for entry in planner.compute_names(rule, paths, followers=followers):
            if entry.error is not None:
                entries.append(PreviewEntry(error_text(entry.error), error=True))
            elif entry.target:
                text = os.path.relpath(entry.target, rule.dest_root)
                entries.append(PreviewEntry(text, target=entry.target))
            else:
                entries.append(PreviewEntry(""))
        return entries

    def renumber_plan(
        self,
        paths: list[str],
        followers: Mapping[str, list[tuple[str, str]]] | None = None,
    ) -> list[tuple[str, str]] | None:
        """Return the (source, target) pairs renumbering *paths* from 1 in
        place, sidecars included, or None when the schema cannot renumber
        or a name cannot be computed (the reason is shown in the panel)."""
        rule = self.rule(renumber=True)
        if rule is None:
            return None
        followers = followers or {}
        pairs: list[tuple[str, str]] = []
        for path, entry in zip(
            paths, planner.compute_names(rule, paths, followers=followers), strict=True
        ):
            if entry.error is not None:
                self.lblMessage.setText(
                    f"{os.path.basename(path)}: {error_text(entry.error)}"
                )
                return None
            if not entry.target:
                continue
            pairs.append((path, entry.target))
            pairs.extend(
                (sc, planner.sidecar_target(entry.target, suffix))
                for sc, suffix in followers.get(path, [])
            )
        return [(src, dst) for src, dst in pairs if src != dst]
