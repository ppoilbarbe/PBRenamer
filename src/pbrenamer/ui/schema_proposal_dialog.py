"""Read-only preview of the schema fields inferred by "Template" (ported
from PBPicat); the user confirms or cancels."""

from __future__ import annotations

import html

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)


class SchemaProposalDialog(QDialog):
    def __init__(self, titles: list[str], proposed: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Proposed template"))
        self.setMinimumWidth(360)
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.addWidget(QLabel(_("Detected template, confirm to fill the fields:")))

        form = QFormLayout()
        form.setSpacing(6)
        for title, value in zip(titles, proposed, strict=True):
            if value:
                label = QLabel(f"<b>{html.escape(value)}</b>")
            else:
                label = QLabel(f"<i style='color:gray'>{_('(empty)')}</i>")
            form.addRow(title, label)
        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
