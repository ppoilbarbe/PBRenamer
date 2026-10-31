"""Non-modal image viewer (ported from PBPicat).

Zoom modes, a selection strip for multi-file selections, linear or circular
navigation through the list, a video placeholder, and the metadata tree
shared with the File information window as a side panel.  The viewer only
emits requests (navigate, open, rotate, delete…); the file list acts on them.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from enum import Enum, auto

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pbrenamer import settings
from pbrenamer.core import image_ops
from pbrenamer.core.image_io import load_pixmap, load_qimage
from pbrenamer.resources import path as _resource
from pbrenamer.ui.geometry_mixin import GeometryMixin
from pbrenamer.ui.metadata_view import MetadataView

_ICON_SIZE = 22
_METADATA_PANEL_DEFAULT_WIDTH = 320
_SELECTION_STRIP_THUMB = 56
_VIDEO_PLACEHOLDER_SIZE = 512
_SPLITTER_KEY = "image_viewer_splitter"


def _icon(name: str) -> QIcon:
    return QIcon(_resource(f"{name}.svg"))


def _ext(path: str) -> str:
    return os.path.splitext(path)[1][1:].lower()


class _ZoomMode(Enum):
    FIT_WINDOW = auto()
    FIT_WIDTH = auto()
    FIT_HEIGHT = auto()
    ONE_TO_ONE = auto()
    CUSTOM = auto()


class _ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


_STRIP_HIGHLIGHT_STYLE = (
    "border: 3px solid palette(highlight); border-radius: 4px; padding: 0px;"
)
_STRIP_PLAIN_STYLE = "border: 3px solid transparent; padding: 0px;"


class _SelectionStrip(QScrollArea):
    """Horizontal strip of thumbnails for a multi-file selection.

    Highlights the displayed file; a click on a thumbnail jumps to it, in
    addition to the viewer's arrow key shortcuts.  Thumbnails are loaded
    lazily, a few at a time, for the visible part of the strip only, so
    that a large selection opens at once.
    """

    thumbnail_clicked = Signal(int)

    _MARGIN = 4
    _SPACING = 4
    _BATCH = 4  # thumbnails loaded per event loop pass

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(_SELECTION_STRIP_THUMB + 16)

        container = QWidget()
        self._layout = QHBoxLayout(container)
        m = self._MARGIN
        self._layout.setContentsMargins(m, m, m, m)
        self._layout.setSpacing(self._SPACING)
        self._layout.addStretch()
        self.setWidget(container)

        self._labels: list[QLabel] = []
        self._paths: list[str] = []
        self._loaded: set[int] = set()
        self._video_extensions: frozenset[str] = frozenset()
        self.current_index = 0
        self._load_timer = QTimer(self)
        self._load_timer.setSingleShot(True)
        self._load_timer.setInterval(0)
        self._load_timer.timeout.connect(self._load_visible)
        self.horizontalScrollBar().valueChanged.connect(self._schedule_load)

    @staticmethod
    def _thumbnail_pixmap(path: str, video_extensions: frozenset[str]) -> QPixmap:
        if _ext(path) in video_extensions:
            return _icon("movie").pixmap(_SELECTION_STRIP_THUMB, _SELECTION_STRIP_THUMB)
        image = load_qimage(path, _SELECTION_STRIP_THUMB, _SELECTION_STRIP_THUMB)
        return QPixmap.fromImage(image) if not image.isNull() else QPixmap()

    def set_paths(
        self, paths: list[str], current_index: int, video_extensions: frozenset[str]
    ) -> None:
        # setParent(None) removes the label from the layout at once;
        # deleteLater() alone would leave it laid out until the event loop
        # runs, showing stale thumbnails next to the new ones.
        for label in self._labels:
            label.setParent(None)
            label.deleteLater()
        self._labels = []
        self._paths = list(paths)
        self._loaded = set()
        self._video_extensions = video_extensions

        for index, path in enumerate(paths):
            label = _ClickableLabel()
            label.setFixedSize(_SELECTION_STRIP_THUMB + 4, _SELECTION_STRIP_THUMB + 4)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.setToolTip(os.path.basename(path))
            label.clicked.connect(lambda i=index: self.thumbnail_clicked.emit(i))
            self._layout.insertWidget(self._layout.count() - 1, label)
            self._labels.append(label)

        self.set_current_index(current_index)
        self._schedule_load()

    def refresh_thumbnail(
        self, index: int, path: str, video_extensions: frozenset[str]
    ) -> None:
        """Regenerate one thumbnail in place (its pixels changed)."""
        if 0 <= index < len(self._labels):
            self._labels[index].setPixmap(
                self._thumbnail_pixmap(path, video_extensions)
            )
            self._loaded.add(index)

    def _schedule_load(self) -> None:
        if len(self._loaded) < len(self._labels):
            self._load_timer.start()

    def _wanted(self) -> list[int]:
        """Indexes to load: the visible thumbnails (plus one viewport on
        each side), the current one first, not loaded yet."""
        step = _SELECTION_STRIP_THUMB + 4 + self._SPACING
        width = max(self.viewport().width(), step)
        left = self.horizontalScrollBar().value() - width
        right = left + 3 * width
        first = max(0, (left - self._MARGIN) // step)
        last = min(len(self._labels) - 1, (right - self._MARGIN) // step)
        indexes = [self.current_index, *range(first, last + 1)]
        return [i for i in dict.fromkeys(indexes) if i not in self._loaded]

    def _load_visible(self) -> None:
        """Load a batch of wanted thumbnails; continue on the next pass."""
        wanted = [i for i in self._wanted() if 0 <= i < len(self._labels)]
        for index in wanted[: self._BATCH]:
            self._labels[index].setPixmap(
                self._thumbnail_pixmap(self._paths[index], self._video_extensions)
            )
            self._loaded.add(index)
        if len(wanted) > self._BATCH:
            self._load_timer.start()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._schedule_load()

    def set_current_index(self, index: int) -> None:
        self.current_index = index
        for i, label in enumerate(self._labels):
            label.setStyleSheet(
                _STRIP_HIGHLIGHT_STYLE if i == index else _STRIP_PLAIN_STYLE
            )
        if 0 <= index < len(self._labels):
            self.ensureWidgetVisible(self._labels[index])


class ImageViewer(GeometryMixin, QWidget):
    """Non-modal image viewer with a zoom toolbar.

    Zoom modes (toolbar, left to right):
      Window (default) | 1:1 | Width | Height, then zoom in / out.
    """

    navigate_prev = Signal()
    navigate_next = Signal()
    open_requested = Signal()
    open_with_requested = Signal()
    template_requested = Signal()
    delete_requested = Signal()
    rotate_requested = Signal(object)  # 90, -90, 180, "auto" or "reset_exif"
    field_requested = Signal(str)

    def __init__(
        self,
        window_state,
        parent=None,
        *,
        zoom_step_percent: int = 25,
        zoom_max_percent: int = 400,
        auto_rotate: bool = True,
        metadata_panel_side: str = "right",
        video_extensions: frozenset[str] = frozenset(),
        sidecars_of: Callable[[str], list[str]] = lambda _path: [],
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setMinimumSize(300, 200)
        self._init_geometry(window_state, "image_viewer")

        self._zoom_step = zoom_step_percent / 100.0
        self._zoom_max = zoom_max_percent / 100.0
        self._mode = _ZoomMode.FIT_WINDOW
        self._factor = 1.0  # used only in CUSTOM mode
        self._zoom_min = 0.01
        self._drag_pos: QPoint | None = None
        self._circular = settings.get_viewer_circular()
        self._auto_rotate = auto_rotate
        self._current_path: str | None = None
        self._metadata_side = metadata_panel_side
        self._video_extensions = video_extensions
        self._sidecars_of = sidecars_of
        self._video_mode = False
        self._selection_paths: list[str] = []
        self._selection_index = 0
        self._pixmap = QPixmap()

        self._setup_ui()
        self._setup_shortcuts()

        sizes = window_state.load_sizes(_SPLITTER_KEY)
        if sizes:
            self._splitter.setSizes(sizes)
        self._metadata_btn.setChecked(settings.get_viewer_metadata_visible())

        if window_state.load_geometry("image_viewer") is None:
            screen = self.screen()
            avail = screen.availableGeometry()
            self.resize(int(avail.width() * 0.75), int(avail.height() * 0.75))

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        root.addLayout(self._build_toolbar())

        self._scroll = QScrollArea()
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setWidgetResizable(False)

        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        self._label.installEventFilter(self)
        self._scroll.setWidget(self._label)

        self._metadata_panel = MetadataView()
        self._metadata_panel.field_requested.connect(self.field_requested)
        self._metadata_panel.setVisible(False)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._place_metadata_panel(self._metadata_side)
        root.addWidget(self._splitter, stretch=1)

        self._strip = _SelectionStrip()
        self._strip.setVisible(False)
        self._strip.thumbnail_clicked.connect(self._act_selection_goto)
        root.addWidget(self._strip)

    def _tool_button(self, icon: str, tip: str, slot, *, checkable=False):
        btn = QToolButton()
        btn.setIcon(_icon(icon))
        btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        btn.setToolTip(tip)
        btn.setCheckable(checkable)
        btn.clicked.connect(lambda _checked=False: slot())
        return btn

    @staticmethod
    def _separator() -> QToolButton:
        sep = QToolButton()
        sep.setEnabled(False)
        sep.setFixedWidth(8)
        return sep

    def _build_toolbar(self) -> QHBoxLayout:
        tb = QHBoxLayout()
        tb.setSpacing(2)

        self._zoom_buttons = [
            self._tool_button(icon, tip, slot, checkable=True)
            for icon, tip, slot in [
                ("zoom-fit", _("Fit window  0 / X"), self._act_fit_window),
                ("zoom-original", _("Actual size (1:1)  1 / Z"), self._act_1to1),
                ("zoom-width", _("Fit width  W"), self._act_fit_width),
                ("zoom-height", _("Fit height  H"), self._act_fit_height),
            ]
        ]
        self._zoom_buttons[0].setChecked(True)
        self._zoom_inout_buttons = [
            self._tool_button("zoom-in", _("Zoom in  +"), self._act_zoom_in),
            self._tool_button("zoom-out", _("Zoom out  −"), self._act_zoom_out),
        ]
        self._rotate_buttons = [
            self._tool_button(
                "object-rotate-left",
                _("Rotate 90° left  F6"),
                lambda: self.rotate_requested.emit(-90),
            ),
            self._tool_button(
                "object-flip-vertical",
                _("Rotate 180°  F7"),
                lambda: self.rotate_requested.emit(180),
            ),
            self._tool_button(
                "object-rotate-right",
                _("Rotate 90° right  F8"),
                lambda: self.rotate_requested.emit(90),
            ),
        ]
        self._rotate_auto_btn = self._tool_button(
            "auto-rotate",
            _("Apply EXIF orientation  F9"),
            lambda: self.rotate_requested.emit("auto"),
        )
        self._reset_exif_btn = self._tool_button(
            "reset-exif",
            _("Force EXIF orientation to 0°  F10"),
            lambda: self.rotate_requested.emit("reset_exif"),
        )
        self._rotate_auto_btn.setEnabled(False)
        self._reset_exif_btn.setEnabled(False)
        file_buttons = [
            self._tool_button(
                "open", _("Open") + "  Ctrl+Return", self.open_requested.emit
            ),
            self._tool_button(
                "open-with",
                _("Open with") + "  Ctrl+Shift+O",
                self.open_with_requested.emit,
            ),
            self._tool_button(
                "rename-template", _("Template"), self.template_requested.emit
            ),
            self._tool_button(
                "delete", _("Delete") + "  Del", self.delete_requested.emit
            ),
        ]
        self._metadata_btn = self._tool_button(
            "document-properties",
            _("Show metadata panel") + "  I",
            lambda: None,
            checkable=True,
        )
        self._metadata_btn.toggled.connect(self._on_metadata_toggled)
        self._circular_btn = self._tool_button(
            "list-circular", "", self._act_toggle_circular
        )
        self._update_circular_button()

        groups = [
            self._zoom_buttons,
            self._zoom_inout_buttons,
            [*self._rotate_buttons, self._rotate_auto_btn, self._reset_exif_btn],
            file_buttons,
        ]
        for group in groups:
            for btn in group:
                tb.addWidget(btn)
            tb.addWidget(self._separator())
        tb.addWidget(self._metadata_btn)
        tb.addWidget(self._circular_btn)

        tb.addStretch()
        self._zoom_label = QLabel()
        self._zoom_label.setMinimumWidth(180)
        self._zoom_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        tb.addWidget(self._zoom_label)
        return tb

    def _setup_shortcuts(self) -> None:
        keypad = Qt.KeyboardModifier.KeypadModifier
        ctrl = Qt.KeyboardModifier.ControlModifier
        shift = Qt.KeyboardModifier.ShiftModifier
        pairs = [
            (QKeySequence(Qt.Key.Key_0), self._act_fit_window),
            (QKeySequence(Qt.Key.Key_X), self._act_fit_window),
            (QKeySequence(Qt.Key.Key_1), self._act_1to1),
            (QKeySequence(Qt.Key.Key_Z), self._act_1to1),
            (QKeySequence(Qt.Key.Key_W), self._act_fit_width),
            (QKeySequence(Qt.Key.Key_H), self._act_fit_height),
            (QKeySequence(Qt.Key.Key_Plus), self._act_zoom_in),
            (QKeySequence(Qt.Key.Key_Equal), self._act_zoom_in),
            (QKeySequence(keypad | Qt.Key.Key_Plus), self._act_zoom_in),
            (QKeySequence(Qt.Key.Key_Minus), self._act_zoom_out),
            (QKeySequence(keypad | Qt.Key.Key_Minus), self._act_zoom_out),
            (QKeySequence(Qt.Key.Key_Up), self._act_prev),
            (QKeySequence(Qt.Key.Key_Left), self._act_prev),
            (QKeySequence(Qt.Key.Key_Down), self._act_next),
            (QKeySequence(Qt.Key.Key_Right), self._act_next),
            (QKeySequence(ctrl | Qt.Key.Key_Return), self.open_requested),
            (QKeySequence(ctrl | shift | Qt.Key.Key_O), self.open_with_requested),
            (QKeySequence(Qt.Key.Key_Delete), self.delete_requested),
            (QKeySequence(Qt.Key.Key_F6), lambda: self.rotate_requested.emit(-90)),
            (QKeySequence(Qt.Key.Key_F7), lambda: self.rotate_requested.emit(180)),
            (QKeySequence(Qt.Key.Key_F8), lambda: self.rotate_requested.emit(90)),
            (QKeySequence(Qt.Key.Key_F9), lambda: self.rotate_requested.emit("auto")),
            (
                QKeySequence(Qt.Key.Key_F10),
                lambda: self.rotate_requested.emit("reset_exif"),
            ),
            (QKeySequence(Qt.Key.Key_Escape), self.close),
            (QKeySequence(Qt.Key.Key_I), self._act_toggle_metadata),
        ]
        for seq, slot in pairs:
            QShortcut(seq, self).activated.connect(slot)

    # ── Public API ────────────────────────────────────────────────────────────

    def display(self, path: str) -> None:
        """Show *path*, as a video placeholder or as an image."""
        if _ext(path) in self._video_extensions:
            self.show_video(path)
        else:
            self.load_image(path)

    def load_image(self, path: str) -> None:
        self._set_video_mode(False)
        self._current_path = path
        self.setWindowTitle(os.path.basename(path))
        self._pixmap = load_pixmap(path, auto_rotate=self._auto_rotate)
        if not self._pixmap.isNull():
            min_dim = min(self._pixmap.width(), self._pixmap.height())
            self._zoom_min = (64 / min_dim) if min_dim >= 64 else 1.0
            self._label.setText("")
        else:
            self._zoom_min = 0.01
            self._label.setText(_("Cannot load image."))
        has_exif = image_ops.get_exif_orientation(path) is not None
        self._rotate_auto_btn.setEnabled(has_exif)
        self._reset_exif_btn.setEnabled(has_exif)
        self._apply_zoom(center=True)
        self._load_metadata()

    def show_video(self, path: str) -> None:
        self._current_path = path
        self.setWindowTitle(os.path.basename(path))
        self._pixmap = _icon("movie").pixmap(
            QSize(_VIDEO_PLACEHOLDER_SIZE, _VIDEO_PLACEHOLDER_SIZE)
        )
        self._zoom_min = 0.01
        self._label.setText("")
        self._mode = _ZoomMode.FIT_WINDOW
        self._set_video_mode(True)
        self._update_button_states()
        self._apply_zoom(center=True)
        self._load_metadata()

    def _load_metadata(self) -> None:
        if self._metadata_btn.isChecked() and self._current_path is not None:
            self._metadata_panel.show_file(
                self._current_path, self._sidecars_of(self._current_path)
            )

    def _set_video_mode(self, active: bool) -> None:
        self._video_mode = active
        for btn in self._zoom_buttons + self._zoom_inout_buttons + self._rotate_buttons:
            btn.setEnabled(not active)
        if active:
            self._rotate_auto_btn.setEnabled(False)
            self._reset_exif_btn.setEnabled(False)

    def set_selection(self, paths: list[str], current: str | None = None) -> None:
        """Set the files to browse with the arrow keys.  One file hides the
        strip; several show it and display *current* (or the first)."""
        self._selection_paths = list(paths)
        self._selection_index = paths.index(current) if current in paths else 0
        if len(paths) > 1:
            self._strip.set_paths(paths, self._selection_index, self._video_extensions)
            self._strip.setVisible(True)
        else:
            self._strip.setVisible(False)
        self.display(paths[self._selection_index])

    def refresh_paths(self, paths: set[str]) -> None:
        """Reload whatever shows the pixels of *paths* (after a rotation)."""
        if self._current_path in paths:
            self.display(self._current_path)
        for index, path in enumerate(self._selection_paths):
            if path in paths:
                self._strip.refresh_thumbnail(index, path, self._video_extensions)

    def _act_prev(self) -> None:
        """Up/Left: previous file of a multiple selection, otherwise ask
        for the previous media file of the list."""
        if len(self._selection_paths) > 1:
            self._step_selection(-1)
        else:
            self.navigate_prev.emit()

    def _act_next(self) -> None:
        """Down/Right: next file of a multiple selection, otherwise ask for
        the next media file of the list."""
        if len(self._selection_paths) > 1:
            self._step_selection(+1)
        else:
            self.navigate_next.emit()

    @property
    def selection_paths(self) -> list[str]:
        """Files browsed by the viewer (a copy)."""
        return list(self._selection_paths)

    def _step_selection(self, direction: int) -> None:
        """Move within a multiple selection: wraps around in circular mode,
        stops at the ends otherwise."""
        count = len(self._selection_paths)
        index = self._selection_index + direction
        index = index % count if self._circular else max(0, min(count - 1, index))
        if index != self._selection_index:
            self._act_selection_goto(index)

    def _act_selection_goto(self, index: int) -> None:
        if not 0 <= index < len(self._selection_paths):
            return
        self._selection_index = index
        self._strip.set_current_index(index)
        self.display(self._selection_paths[index])

    @property
    def current_path(self) -> str | None:
        return self._current_path

    @property
    def circular_navigation(self) -> bool:
        """True when navigation wraps from one end of the list to the other."""
        return self._circular

    def _act_toggle_circular(self) -> None:
        self._circular = not self._circular
        settings.set_viewer_circular(self._circular)
        self._update_circular_button()

    def _update_circular_button(self) -> None:
        # The button shows the mode a click switches to, not the current one.
        if self._circular:
            self._circular_btn.setIcon(_icon("list-linear"))
            self._circular_btn.setToolTip(
                _("Switch to linear navigation (stop at the ends of the list)")
            )
        else:
            self._circular_btn.setIcon(_icon("list-circular"))
            self._circular_btn.setToolTip(
                _("Switch to circular navigation (wrap around at the ends of the list)")
            )

    def set_metadata_panel_side(self, side: str) -> None:
        if side != self._metadata_side:
            self._metadata_side = side
            self._place_metadata_panel(side)

    def _place_metadata_panel(self, side: str) -> None:
        # insertWidget() moves a widget already in the splitter.
        first, second = (
            (self._metadata_panel, self._scroll)
            if side == "left"
            else (self._scroll, self._metadata_panel)
        )
        self._splitter.insertWidget(0, first)
        self._splitter.insertWidget(1, second)
        self._splitter.setStretchFactor(self._splitter.indexOf(self._scroll), 1)
        self._splitter.setStretchFactor(self._splitter.indexOf(self._metadata_panel), 0)

    def _on_metadata_toggled(self, checked: bool) -> None:
        self._metadata_panel.setVisible(checked)
        if checked:
            panel = self._splitter.indexOf(self._metadata_panel)
            if self._splitter.sizes()[panel] == 0:
                total = sum(self._splitter.sizes()) or self.width()
                sizes = [0, 0]
                sizes[panel] = _METADATA_PANEL_DEFAULT_WIDTH
                sizes[1 - panel] = max(1, total - _METADATA_PANEL_DEFAULT_WIDTH)
                self._splitter.setSizes(sizes)
            self._load_metadata()
        else:
            self._metadata_panel.clear()
        settings.set_viewer_metadata_visible(checked)

    def _act_toggle_metadata(self) -> None:
        self._metadata_btn.toggle()

    def set_auto_rotate(self, value: bool) -> None:
        if self._auto_rotate != value:
            self._auto_rotate = value
            if self._current_path is not None:
                self.display(self._current_path)

    # ── Zoom actions ──────────────────────────────────────────────────────────

    def _act_1to1(self) -> None:
        self._set_mode(_ZoomMode.ONE_TO_ONE)

    def _act_zoom_in(self) -> None:
        self._apply_custom(self._current_factor() + self._zoom_step)

    def _act_zoom_out(self) -> None:
        self._apply_custom(self._current_factor() - self._zoom_step)

    def _act_fit_width(self) -> None:
        self._set_mode(_ZoomMode.FIT_WIDTH)

    def _act_fit_height(self) -> None:
        self._set_mode(_ZoomMode.FIT_HEIGHT)

    def _act_fit_window(self) -> None:
        self._set_mode(_ZoomMode.FIT_WINDOW)

    # ── Zoom engine ───────────────────────────────────────────────────────────

    def _set_mode(self, mode: _ZoomMode) -> None:
        if self._video_mode and mode != _ZoomMode.FIT_WINDOW:
            return
        self._mode = mode
        self._update_button_states()
        self._apply_zoom(center=True)

    def _apply_custom(self, factor: float) -> None:
        if self._video_mode:
            return
        self._factor = max(self._zoom_min, min(self._zoom_max, factor))
        self._mode = _ZoomMode.CUSTOM
        self._update_button_states()
        self._apply_zoom()

    def _current_factor(self) -> float:
        """Return the effective zoom factor regardless of mode."""
        if self._pixmap.isNull():
            return 1.0
        vp = self._scroll.viewport()
        w, h = self._pixmap.width(), self._pixmap.height()
        if self._mode == _ZoomMode.FIT_WINDOW:
            return min(vp.width() / w, vp.height() / h) if w and h else 1.0
        if self._mode == _ZoomMode.FIT_WIDTH:
            return vp.width() / w if w else 1.0
        if self._mode == _ZoomMode.FIT_HEIGHT:
            return vp.height() / h if h else 1.0
        if self._mode == _ZoomMode.ONE_TO_ONE:
            return 1.0
        return self._factor  # CUSTOM

    def _apply_zoom(self, center: bool = False) -> None:
        if self._pixmap.isNull():
            return
        vp = self._scroll.viewport()
        orig_w, orig_h = self._pixmap.width(), self._pixmap.height()
        smooth = Qt.TransformationMode.SmoothTransformation
        keep = Qt.AspectRatioMode.KeepAspectRatio

        if self._mode == _ZoomMode.FIT_WINDOW:
            scaled = self._pixmap.scaled(vp.size(), keep, smooth)
        elif self._mode == _ZoomMode.FIT_WIDTH:
            scaled = self._pixmap.scaledToWidth(vp.width(), smooth)
        elif self._mode == _ZoomMode.FIT_HEIGHT:
            scaled = self._pixmap.scaledToHeight(vp.height(), smooth)
        elif self._mode == _ZoomMode.ONE_TO_ONE:
            scaled = self._pixmap
        else:  # CUSTOM
            tw = max(1, int(orig_w * self._factor))
            th = max(1, int(orig_h * self._factor))
            scaled = self._pixmap.scaled(tw, th, keep, smooth)

        hbar = self._scroll.horizontalScrollBar()
        vbar = self._scroll.verticalScrollBar()
        # Zooming in or out keeps the scroll position, as a percentage.
        hpct = hbar.value() / (hbar.maximum() or 1)
        vpct = vbar.value() / (vbar.maximum() or 1)

        self._label.setPixmap(scaled)
        self._label.resize(scaled.size())

        if self._mode == _ZoomMode.CUSTOM:
            hbar.setValue(int(hpct * hbar.maximum()))
            vbar.setValue(int(vpct * vbar.maximum()))
        elif center:
            if self._mode in (_ZoomMode.ONE_TO_ONE, _ZoomMode.FIT_HEIGHT):
                hbar.setValue(hbar.maximum() // 2)
            if self._mode in (_ZoomMode.ONE_TO_ONE, _ZoomMode.FIT_WIDTH):
                vbar.setValue(vbar.maximum() // 2)

        if self._video_mode:
            self._zoom_label.setText("")
        else:
            factor = scaled.width() / orig_w if orig_w else 1.0
            at_max = self._mode == _ZoomMode.CUSTOM and self._factor >= self._zoom_max
            suffix = _(" (max)") if at_max else ""
            self._zoom_label.setText(f"{orig_w}×{orig_h}  {factor * 100:.0f}%{suffix}")

    def _update_button_states(self) -> None:
        modes = [
            _ZoomMode.FIT_WINDOW,
            _ZoomMode.ONE_TO_ONE,
            _ZoomMode.FIT_WIDTH,
            _ZoomMode.FIT_HEIGHT,
        ]
        for btn, mode in zip(self._zoom_buttons, modes, strict=True):
            btn.setChecked(self._mode == mode)

    # ── Mouse: drag to pan, Ctrl+click to zoom, double-click to centre ────────

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is not self._label:
            return super().eventFilter(obj, event)
        etype = event.type()
        left = Qt.MouseButton.LeftButton
        ctrl = Qt.KeyboardModifier.ControlModifier
        if etype == QEvent.Type.MouseButtonPress:
            if event.button() == left:
                if event.modifiers() & ctrl:
                    self._zoom_to_point(event.position().toPoint())
                    return True
                self._drag_pos = event.globalPosition().toPoint()
                self._label.setCursor(Qt.CursorShape.OpenHandCursor)
                return False
            if event.button() == Qt.MouseButton.RightButton and (
                event.modifiers() & ctrl
            ):
                self._zoom_to_point(event.position().toPoint(), direction=-1)
                return True
        elif (
            etype == QEvent.Type.MouseMove
            and event.buttons() & left
            and self._drag_pos is not None
        ):
            pos = event.globalPosition().toPoint()
            delta = pos - self._drag_pos
            self._drag_pos = pos
            self._label.setCursor(Qt.CursorShape.ClosedHandCursor)
            hbar = self._scroll.horizontalScrollBar()
            vbar = self._scroll.verticalScrollBar()
            hbar.setValue(hbar.value() - delta.x())
            vbar.setValue(vbar.value() - delta.y())
            return True
        elif etype == QEvent.Type.MouseButtonRelease and event.button() == left:
            self._drag_pos = None
            self._label.setCursor(Qt.CursorShape.ArrowCursor)
        elif etype == QEvent.Type.MouseButtonDblClick and event.button() == left:
            self._drag_pos = None
            self._center_on_label_pos(event.position().toPoint())
            return True
        return False

    def _center_on_label_pos(self, label_pos) -> None:
        """Scroll to centre the viewport on a label-coordinate point."""
        vp = self._scroll.viewport()
        self._scroll.horizontalScrollBar().setValue(int(label_pos.x() - vp.width() / 2))
        self._scroll.verticalScrollBar().setValue(int(label_pos.y() - vp.height() / 2))

    def _zoom_to_point(self, label_pos, direction: int = 1) -> None:
        if self._video_mode:
            return
        label_w, label_h = self._label.width(), self._label.height()
        if label_w == 0 or label_h == 0:
            self._act_zoom_in() if direction > 0 else self._act_zoom_out()
            return
        fx = label_pos.x() / label_w
        fy = label_pos.y() / label_h
        self._factor = max(
            self._zoom_min,
            min(self._zoom_max, self._current_factor() + direction * self._zoom_step),
        )
        self._mode = _ZoomMode.CUSTOM
        self._update_button_states()
        self._apply_zoom()
        vp = self._scroll.viewport()
        self._scroll.horizontalScrollBar().setValue(
            int(fx * self._label.width() - vp.width() / 2)
        )
        self._scroll.verticalScrollBar().setValue(
            int(fy * self._label.height() - vp.height() / 2)
        )

    # ── Qt overrides ──────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802
        self._window_state.save_sizes(_SPLITTER_KEY, self._splitter.sizes())
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._mode in (
            _ZoomMode.FIT_WINDOW,
            _ZoomMode.FIT_WIDTH,
            _ZoomMode.FIT_HEIGHT,
        ):
            self._apply_zoom()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_zoom(center=True)
