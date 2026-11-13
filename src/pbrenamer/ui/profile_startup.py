"""Ask for a profile at start-up when the default profile no longer exists.

The start-up profile is the default profile set in the settings, or the last
profile used.  When it is missing, ``profiles`` selects a fallback; the GUI
never keeps it silently but asks the user which profile to open.
"""

from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QWidget

from pbrenamer import profiles


def resolve_startup_profile(parent: QWidget | None = None) -> bool:
    """Make sure the start-up profile exists, asking for one otherwise.

    Return False when the user cancels the choice (the application quits).
    """
    missing = profiles.missing_startup()
    if missing is None:
        return True
    names = profiles.list_profiles()
    current = profiles.current()
    if profiles.get_default():
        reason = _("The default profile “{name}” was not found.")
    else:
        reason = _("The last profile used, “{name}”, was not found.")
    hint = _("The default profile can be set in the settings.")
    choice, ok = QInputDialog.getItem(
        parent,
        _("Profile not found"),
        "{reason}\n{hint}\n\n{label}".format(
            reason=reason.format(name=missing),
            hint=hint,
            label=_("Profile to open:"),
        ),
        names,
        names.index(current) if current in names else 0,
        False,
    )
    if not ok or not choice:
        return False
    profiles.use(choice)
    return True
