"""Action bar: Preview / Clear / Undo / Rename buttons, their Edit menu
actions, and auto-preview."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence

import pbrenamer.settings as _cfg
from pbrenamer.core.undo import UndoManager


def _with_shortcut(text: str, action: QAction) -> str:
    """*text* followed by the shortcut of *action*, in the platform's
    notation (⌘ on macOS)."""
    keys = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
    return f"{text} ({keys})" if keys else text


class ActionBar(QObject):
    """Drive the action buttons and the auto-preview checkbox.

    The bar never computes anything itself: it emits a request signal and
    the main window performs the work.  Every preview request — button,
    debounce timer or auto-preview trigger — goes through
    :attr:`preview_requested`.
    """

    preview_requested = Signal()
    clear_requested = Signal()
    undo_requested = Signal()
    rename_requested = Signal()

    def __init__(self, ui, undo: UndoManager, parent: QObject) -> None:
        super().__init__(parent)
        self._ui = ui
        self._undo = undo
        self._held = False
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self.preview_requested)

        self._ui.btnPreview.clicked.connect(self.preview_requested)
        self._ui.btnClearPreview.clicked.connect(self.clear_requested)
        self._ui.btnUndo.clicked.connect(self.undo_requested)
        self._ui.btnRename.clicked.connect(self.rename_requested)
        self._ui.actionPreview.triggered.connect(self.preview_requested)
        self._ui.actionClearPreview.triggered.connect(self.clear_requested)
        self._ui.actionUndo.triggered.connect(self.undo_requested)
        self._ui.actionRename.triggered.connect(self.rename_requested)
        self._ui.chkAutoPreview.toggled.connect(self._on_auto_preview_toggled)
        self._ui.btnPreview.setToolTip(
            _with_shortcut(self._ui.btnPreview.toolTip(), self._ui.actionPreview)
        )
        self._ui.btnUndo.setToolTip(
            _with_shortcut(self._ui.btnUndo.toolTip(), self._ui.actionUndo)
        )

    def auto_preview(self) -> bool:
        return self._ui.chkAutoPreview.isChecked()

    def set_auto_preview(self, enabled: bool) -> None:
        self._ui.chkAutoPreview.setChecked(enabled)

    @contextmanager
    def auto_preview_held(self) -> Iterator[None]:
        """Ignore the auto-preview triggers inside the block, so that a
        sequence of changes (reload, then new selection) can be followed by a
        single explicit request."""
        self._held = True
        try:
            yield
        finally:
            self._held = False

    def request_auto_preview(self) -> None:
        """Request a preview right away if auto-preview is on."""
        if self.auto_preview() and not self._held:
            self.preview_requested.emit()

    def schedule_preview(self) -> None:
        """Request a debounced preview if auto-preview is on."""
        if self.auto_preview() and not self._held:
            self._preview_timer.start(_cfg.get_preview_delay())

    def set_rename_count(self, n: int) -> None:
        """Show the number of files Rename would rename; 0 disables it."""
        text = _("Rename ({n})").format(n=n) if n else _("Rename")
        for widget in (self._ui.btnRename, self._ui.actionRename):
            widget.setEnabled(n > 0)
            widget.setText(text)

    def refresh_undo(self) -> None:
        n = len(self._undo)
        if n > 0:
            text = _("Undo (%d)") % n
            tip = _("Undo last rename batch (%d level(s) available)") % n
        else:
            text, tip = _("Undo"), _("Undo last rename batch")
        for widget in (self._ui.btnUndo, self._ui.actionUndo):
            widget.setEnabled(n > 0)
            widget.setText(text)
        self._ui.actionUndo.setToolTip(tip)
        self._ui.btnUndo.setToolTip(_with_shortcut(tip, self._ui.actionUndo))

    def _on_auto_preview_toggled(self, checked: bool) -> None:
        if checked:
            self.preview_requested.emit()
        else:
            self._preview_timer.stop()
