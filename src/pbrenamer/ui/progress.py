"""Modal progress window for the long operations that rewrite file contents
(rotations, EXIF orientation, and their undo).

The window only shows up from PROGRESS_THRESHOLD files on; below it the
operation runs as before, without any window.  The work stays in the GUI
thread: step() is called before each file and keeps the interface alive
between two files.  In sidecar mode the count is the number of main files.
"""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QProgressDialog, QWidget

# From this many files on, the progress window is shown.
PROGRESS_THRESHOLD = 50


class FileProgress:
    """Progress over *total* files, with a Cancel button.

    Usage::

        with FileProgress(parent, _("Rotating images…"), len(paths)) as progress:
            for path in paths:
                if not progress.step():
                    break
                ...
    """

    def __init__(
        self,
        parent: QWidget | None,
        label: str,
        total: int,
        threshold: int = PROGRESS_THRESHOLD,
    ) -> None:
        self._label = label
        self._total = total
        self._done = 0
        self._cancelled = False
        self._dialog: QProgressDialog | None = None
        if total >= threshold:
            self._dialog = self._create_dialog(parent)

    def _create_dialog(self, parent: QWidget | None) -> QProgressDialog:
        dialog = QProgressDialog(parent)
        dialog.setWindowTitle(_("Please wait"))
        dialog.setCancelButtonText(_("Cancel"))
        dialog.setRange(0, self._total)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setMinimumWidth(360)
        dialog.canceled.connect(self.cancel)
        dialog.setLabelText(self._text())
        dialog.setValue(0)
        dialog.show()
        QCoreApplication.processEvents()
        return dialog

    def _text(self) -> str:
        count = _("{done} / {total} file(s)").format(done=self._done, total=self._total)
        return f"{self._label}\n{count}"

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def visible(self) -> bool:
        """True when the progress window is shown (threshold reached)."""
        return self._dialog is not None

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    def step(self) -> bool:
        """Account for the next file; False once Cancel has been pressed.

        Called before each file: the files already processed are shown, the
        pending events (Cancel button, repaints) are handled.
        """
        if self._dialog is not None:
            self._dialog.setLabelText(self._text())
            self._dialog.setValue(self._done)
            QCoreApplication.processEvents()
        if self._cancelled:
            return False
        self._done += 1
        return True

    def close(self) -> None:
        if self._dialog is not None:
            self._dialog.close()
            self._dialog.deleteLater()
            self._dialog = None

    def __enter__(self) -> FileProgress:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
