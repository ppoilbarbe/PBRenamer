"""Offer to delete the PBRenamer 1.x files left in the configuration.

The 1.x settings are copied into the ``default`` profile when the profiles
are created; that start stays silent.  At the following starts, while the
1.x files remain, the user is asked whether to delete them.  Answering no
creates a marker file in the configuration directory, so the question is
not asked again.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

import pbrenamer.settings as _cfg
from pbrenamer import migration, profiles


def offer_v1_cleanup(parent: QWidget | None) -> None:
    """Ask whether to delete the 1.x files, then delete or keep them."""
    if profiles.created_this_run():
        return
    config_home = _cfg.config_home()
    leftovers = migration.v1_leftovers(config_home)
    if not leftovers:
        return
    files = "\n".join(str(path) for path in leftovers)
    reply = QMessageBox.question(
        parent,
        _("Old settings"),
        _(
            "The settings of PBRenamer 1.x were copied into the profile"
            " “{profile}” and are no longer used:\n\n{files}\n\n"
            "Delete these files?"
        ).format(profile=profiles.DEFAULT, files=files),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        migration.keep_v1_leftovers(config_home)
        return
    failed = migration.remove_v1_leftovers(config_home, leftovers)
    if failed:
        QMessageBox.warning(
            parent,
            _("Old settings"),
            _("These files could not be deleted:\n\n{files}").format(
                files="\n".join(str(path) for path in failed)
            ),
        )
