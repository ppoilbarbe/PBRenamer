"""Mixin providing persistent geometry save/restore for Qt windows."""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


class GeometryMixin:
    """Persist and restore window geometry via explicit x/y/w/h coordinates.

    Usage::

        class MyDialog(GeometryMixin, QDialog):
            def __init__(self, window_state, ...):
                super().__init__(...)
                self._init_geometry(window_state, "my_dialog")

    The subclass must call ``_init_geometry`` in its ``__init__``.  If it also
    overrides ``showEvent`` or ``closeEvent`` it must call ``super()``.

    For QDialog subclasses the geometry is saved via the ``finished`` signal,
    which fires on accept(), reject(), close(), and the window X button.
    For QWidget subclasses (no finished signal) it is saved in closeEvent.
    """

    def _init_geometry(self, window_state, state_key: str) -> None:
        self._window_state = window_state
        self._geo_state_key = state_key
        self._geometry_restored = False
        if hasattr(self, "finished"):
            self.finished.connect(self._geo_save)

    def _geo_save(self, *_args) -> None:
        x, y, w, h = self.x(), self.y(), self.width(), self.height()
        _log.debug(
            "%s: save geometry x=%d y=%d w=%d h=%d",
            type(self).__name__,
            x,
            y,
            w,
            h,
        )
        self._window_state.save_geometry(self._geo_state_key, x, y, w, h)

    def showEvent(self, event) -> None:  # noqa: N802
        if not self._geometry_restored:
            self._geometry_restored = True
            result = self._window_state.load_geometry(self._geo_state_key)
            if result is not None:
                x, y, w, h = result
                _log.debug(
                    "%s: restore geometry x=%d y=%d w=%d h=%d",
                    type(self).__name__,
                    x,
                    y,
                    w,
                    h,
                )
                # move() BEFORE super().showEvent() so that WA_Moved is set
                # when QDialog::showEvent runs — preventing Qt from centering
                # the dialog over its parent and overriding our position.
                self.move(x, y)
                self.resize(w, h)
            else:
                _log.debug("%s: no saved geometry, using defaults", type(self).__name__)
        super().showEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        if not hasattr(self, "finished"):
            self._geo_save()
        super().closeEvent(event)
