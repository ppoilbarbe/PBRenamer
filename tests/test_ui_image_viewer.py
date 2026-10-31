"""Tests for pbrenamer.ui.image_viewer (ported from PBPicat).

``ImageViewer`` below wraps the real class with PBPicat's constructor, which
displayed its file at once, so that the ported tests read as before.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QKeySequence, QMouseEvent

from pbrenamer.ui import image_viewer
from pbrenamer.ui.image_viewer import _ZoomMode
from pbrenamer.ui.window_state import WindowState


def ImageViewer(path, *, video_extensions=None, sidecar_extensions=None, **kw):  # noqa: N802
    exts = frozenset(e.lstrip(".").lower() for e in video_extensions or [])

    def sidecars_of(p):
        stem = os.path.splitext(p)[0]
        return [stem + e for e in sidecar_extensions or [] if os.path.exists(stem + e)]

    viewer = image_viewer.ImageViewer(
        WindowState(), video_extensions=exts, sidecars_of=sidecars_of, **kw
    )
    viewer.display(str(path))
    return viewer


@pytest.fixture
def sample_png(sample_png):
    """The viewer works on ``str`` paths."""
    return str(sample_png)


# ---------------------------------------------------------------------------
# ImageViewer construction
# ---------------------------------------------------------------------------


def test_image_viewer_with_valid_image(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    assert viewer.windowTitle() == "test.png"
    assert not viewer._pixmap.isNull()


def test_image_viewer_with_missing_image(qtbot, tmp_path):
    missing = tmp_path / "missing.png"
    viewer = ImageViewer(missing)
    qtbot.addWidget(viewer)
    assert viewer._pixmap.isNull()


def test_image_viewer_restores_geometry(qtbot, sample_png):
    WindowState().save_geometry("image_viewer", 10, 20, 640, 480)
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    assert (viewer.width(), viewer.height()) == (640, 480)


def test_image_viewer_default_size(qtbot, sample_png):
    """Without a saved geometry the viewer takes 75 % of the screen."""
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    avail = viewer.screen().availableGeometry()
    assert viewer.width() == int(avail.width() * 0.75)
    assert viewer.height() == int(avail.height() * 0.75)


# ---------------------------------------------------------------------------
# load_image
# ---------------------------------------------------------------------------


def test_load_image_null_pixmap(qtbot, sample_png, tmp_path):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.load_image(tmp_path / "nonexistent.png")
    assert viewer._pixmap.isNull()


def test_load_image_small_dimension(qtbot, tmp_path):
    """min_dim < 64 → _zoom_min = 1.0."""
    tiny = tmp_path / "tiny.png"
    Image.new("RGB", (10, 10)).save(str(tiny))
    viewer = ImageViewer(tiny)
    qtbot.addWidget(viewer)
    assert viewer._zoom_min == 1.0


# ---------------------------------------------------------------------------
# Zoom modes
# ---------------------------------------------------------------------------


def test_act_fit_window(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_fit_window()
    assert viewer._mode == _ZoomMode.FIT_WINDOW


def test_act_1to1(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_1to1()
    assert viewer._mode == _ZoomMode.ONE_TO_ONE


def test_act_fit_width(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_fit_width()
    assert viewer._mode == _ZoomMode.FIT_WIDTH


def test_act_fit_height(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_fit_height()
    assert viewer._mode == _ZoomMode.FIT_HEIGHT


def test_act_zoom_in(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_zoom_in()
    assert viewer._mode == _ZoomMode.CUSTOM


def test_act_zoom_out(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_zoom_out()
    assert viewer._mode == _ZoomMode.CUSTOM


def test_apply_custom_clamps_to_max(qtbot, sample_png):
    viewer = ImageViewer(sample_png, zoom_max_percent=100)
    qtbot.addWidget(viewer)
    viewer._apply_custom(999.0)
    assert viewer._factor == 1.0


def test_apply_custom_clamps_to_min(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._apply_custom(0.0)
    assert viewer._factor == viewer._zoom_min


def test_current_factor_null_pixmap(qtbot, tmp_path):
    viewer = ImageViewer(tmp_path / "missing.png")
    qtbot.addWidget(viewer)
    assert viewer._current_factor() == 1.0


def test_current_factor_fit_width_zero_width(qtbot, sample_png, monkeypatch):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._mode = _ZoomMode.FIT_WIDTH
    monkeypatch.setattr(viewer._pixmap, "width", lambda: 0)
    assert viewer._current_factor() == 1.0


def test_current_factor_fit_height_zero_height(qtbot, sample_png, monkeypatch):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._mode = _ZoomMode.FIT_HEIGHT
    monkeypatch.setattr(viewer._pixmap, "height", lambda: 0)
    assert viewer._current_factor() == 1.0


def test_current_factor_fit_window_zero_dims(qtbot, sample_png, monkeypatch):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._mode = _ZoomMode.FIT_WINDOW
    monkeypatch.setattr(viewer._pixmap, "width", lambda: 0)
    monkeypatch.setattr(viewer._pixmap, "height", lambda: 0)
    assert viewer._current_factor() == 1.0


def test_apply_zoom_null_pixmap(qtbot, tmp_path):
    viewer = ImageViewer(tmp_path / "missing.png")
    qtbot.addWidget(viewer)
    viewer._apply_zoom()  # should not crash


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


def test_navigate_prev_signal(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with qtbot.waitSignal(viewer.navigate_prev, timeout=500):
        viewer.navigate_prev.emit()


def test_navigate_next_signal(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with qtbot.waitSignal(viewer.navigate_next, timeout=500):
        viewer.navigate_next.emit()


def test_open_requested_signal(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with qtbot.waitSignal(viewer.open_requested, timeout=500):
        viewer.open_requested.emit()


def test_delete_requested_signal(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with qtbot.waitSignal(viewer.delete_requested, timeout=500):
        viewer.delete_requested.emit()


# ---------------------------------------------------------------------------
# eventFilter and _zoom_to_point
# ---------------------------------------------------------------------------


def test_event_filter_mouse_press(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()

    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPoint(10, 10),
        viewer._label.mapToGlobal(QPoint(10, 10)),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    viewer.eventFilter(viewer._label, press)
    assert viewer._drag_pos is not None


def test_event_filter_mouse_release(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer._drag_pos = QPoint(5, 5)
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPoint(10, 10),
        viewer._label.mapToGlobal(QPoint(10, 10)),
        Qt.LeftButton,
        Qt.NoButton,
        Qt.NoModifier,
    )
    viewer.eventFilter(viewer._label, release)
    assert viewer._drag_pos is None


def test_event_filter_mouse_move(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer._drag_pos = QPoint(5, 5)
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPoint(15, 15),
        viewer._label.mapToGlobal(QPoint(15, 15)),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    viewer.eventFilter(viewer._label, move)


def test_event_filter_double_click(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer.resize(600, 400)
    dbl = QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        QPoint(50, 50),
        viewer._label.mapToGlobal(QPoint(50, 50)),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    viewer.eventFilter(viewer._label, dbl)


def test_event_filter_other_object(qtbot, sample_png):
    from PySide6.QtGui import QKeyEvent

    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    # Pass a non-label object → super().eventFilter is called → returns False
    other_label = viewer._scroll  # a real QObject
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.NoModifier)
    result = viewer.eventFilter(other_label, event)
    assert result is False


def test_zoom_to_point_zero_size(qtbot, sample_png, monkeypatch):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    monkeypatch.setattr(viewer._label, "width", lambda: 0)
    monkeypatch.setattr(viewer._label, "height", lambda: 0)
    viewer._zoom_to_point(QPoint(10, 10))
    assert viewer._mode == _ZoomMode.CUSTOM


# ---------------------------------------------------------------------------
# close / resize / show events
# ---------------------------------------------------------------------------


def test_close_event_saves_geometry(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer.close()
    assert WindowState().load_geometry("image_viewer") is not None
    assert WindowState().load_sizes("image_viewer_splitter") is not None


def test_resize_event_triggers_apply_zoom(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_fit_window()
    viewer.resize(500, 400)  # triggers resizeEvent


def test_show_event_triggers_apply_zoom(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer.hide()


def test_apply_zoom_custom_mode(qtbot, sample_png):
    """Cover CUSTOM mode in _apply_zoom (lines 327-330)."""
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer.resize(400, 300)
    viewer._apply_custom(2.0)  # sets CUSTOM mode and calls _apply_zoom
    assert viewer._mode == _ZoomMode.CUSTOM


def test_current_factor_one_to_one_mode(qtbot, sample_png):
    """Cover lines 308-309: _current_factor returns 1.0 in ONE_TO_ONE mode."""
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_1to1()  # mode = ONE_TO_ONE
    factor = viewer._current_factor()
    assert factor == 1.0


def test_current_factor_custom_mode(qtbot, sample_png):
    """Cover line 310: _current_factor returns self._factor in CUSTOM mode."""
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._apply_custom(2.0)  # mode = CUSTOM, _factor = 2.0
    factor = viewer._current_factor()
    assert factor == 2.0


# ---------------------------------------------------------------------------
# set_auto_rotate
# ---------------------------------------------------------------------------


def test_set_auto_rotate_same_value_no_reload(qtbot, sample_png):
    viewer = ImageViewer(sample_png, auto_rotate=True)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "load_image") as mock_load:
        viewer.set_auto_rotate(True)
    mock_load.assert_not_called()


def test_set_auto_rotate_different_value_reloads(qtbot, sample_png):
    viewer = ImageViewer(sample_png, auto_rotate=True)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "load_image") as mock_load:
        viewer.set_auto_rotate(False)
    mock_load.assert_called_once_with(sample_png)


# ---------------------------------------------------------------------------
# Ctrl+Click → _zoom_to_point (lines 400-401, 439-449)
# ---------------------------------------------------------------------------


def test_event_filter_ctrl_click_zooms_to_point(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer.resize(600, 400)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPoint(50, 50),
        viewer._label.mapToGlobal(QPoint(50, 50)),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.ControlModifier,
    )
    result = viewer.eventFilter(viewer._label, press)
    assert result is True
    assert viewer._mode == _ZoomMode.CUSTOM


def test_event_filter_ctrl_right_click_zooms_out_to_point(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer.resize(600, 400)
    viewer._apply_custom(2.0)
    factor_before = viewer._current_factor()
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPoint(50, 50),
        viewer._label.mapToGlobal(QPoint(50, 50)),
        Qt.RightButton,
        Qt.RightButton,
        Qt.ControlModifier,
    )
    result = viewer.eventFilter(viewer._label, press)
    assert result is True
    assert viewer._mode == _ZoomMode.CUSTOM
    assert viewer._current_factor() < factor_before


def test_zoom_to_point_zero_size_zoom_out(qtbot, sample_png, monkeypatch):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._apply_custom(2.0)
    factor_before = viewer._current_factor()
    monkeypatch.setattr(viewer._label, "width", lambda: 0)
    monkeypatch.setattr(viewer._label, "height", lambda: 0)
    viewer._zoom_to_point(QPoint(10, 10), direction=-1)
    assert viewer._mode == _ZoomMode.CUSTOM
    assert viewer._current_factor() < factor_before


# ---------------------------------------------------------------------------
# Metadata panel
# ---------------------------------------------------------------------------


def test_metadata_panel_hidden_by_default(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    assert viewer._metadata_btn.isChecked() is False
    assert viewer._metadata_panel.isHidden() is True


def test_metadata_panel_not_loaded_while_hidden(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._metadata_panel.show_file = MagicMock()
    viewer.load_image(str(sample_png))
    viewer._metadata_panel.show_file.assert_not_called()


def test_toggling_metadata_button_shows_and_loads_panel(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._metadata_btn.setChecked(True)
    assert viewer._metadata_panel.isHidden() is False
    assert viewer._metadata_panel.topLevelItemCount() > 0


def test_unchecking_metadata_button_clears_panel(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._metadata_btn.setChecked(True)
    viewer._metadata_btn.setChecked(False)
    assert viewer._metadata_panel.isHidden() is True
    assert viewer._metadata_panel.topLevelItemCount() == 0


def test_load_image_refreshes_visible_metadata_panel(qtbot, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._metadata_btn.setChecked(True)
    loaded = []
    viewer._metadata_panel.show_file = lambda p, sidecars: loaded.append(p)
    viewer.load_image(str(other))
    assert loaded == [str(other)]


def test_shortcut_i_toggles_metadata_panel(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_toggle_metadata()
    assert viewer._metadata_btn.isChecked() is True


def test_metadata_panel_side_right_by_default(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    assert viewer._splitter.widget(0) is viewer._scroll
    assert viewer._splitter.widget(1) is viewer._metadata_panel


def test_metadata_panel_side_left(qtbot, sample_png):
    viewer = ImageViewer(sample_png, metadata_panel_side="left")
    qtbot.addWidget(viewer)
    assert viewer._splitter.widget(0) is viewer._metadata_panel
    assert viewer._splitter.widget(1) is viewer._scroll


def test_set_metadata_panel_side_live_update(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_metadata_panel_side("left")
    assert viewer._splitter.widget(0) is viewer._metadata_panel
    assert viewer._splitter.widget(1) is viewer._scroll


def test_set_metadata_panel_side_noop_when_unchanged(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    splitter = viewer._splitter
    viewer.set_metadata_panel_side("right")
    assert viewer._splitter is splitter
    assert viewer._splitter.widget(0) is viewer._scroll


def test_metadata_state_saved(qtbot, sample_png):
    from pbrenamer import settings

    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._metadata_btn.setChecked(True)
    assert settings.get_viewer_metadata_visible() is True
    reopened = ImageViewer(sample_png)
    qtbot.addWidget(reopened)
    assert reopened._metadata_btn.isChecked() is True


def test_saved_splitter_sizes_restored(qtbot, sample_png):
    WindowState().save_sizes("image_viewer_splitter", [300, 100])
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    assert viewer._splitter.sizes() != []


def test_metadata_field_forwarded(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    received = []
    viewer.field_requested.connect(received.append)
    viewer._metadata_panel.field_requested.emit("{date}")
    assert received == ["{date}"]


def test_sidecar_extensions_passed_to_metadata_panel(qtbot, tmp_path):
    from PIL import Image as _Image

    image = tmp_path / "photo.png"
    _Image.new("RGB", (5, 5)).save(str(image))
    (tmp_path / "photo.xmp").write_text(
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<dc:title><rdf:Alt><rdf:li xml:lang="x-default">Hi</rdf:li></rdf:Alt>'
        "</dc:title>"
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
    )
    viewer = ImageViewer(image, sidecar_extensions=[".xmp"])
    qtbot.addWidget(viewer)
    received = []
    viewer._metadata_panel.show_file = lambda p, sidecars: received.append(sidecars)
    viewer._metadata_btn.setChecked(True)
    assert received == [[str(tmp_path / "photo.xmp")]]


# ---------------------------------------------------------------------------
# display() dispatch / show_video / video mode
# ---------------------------------------------------------------------------


def _video(tmp_path, name="clip.mp4"):
    path = tmp_path / name
    path.write_bytes(b"fake")
    return path


def test_display_dispatches_image(qtbot, sample_png):
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    with (
        patch.object(viewer, "load_image") as mock_load,
        patch.object(viewer, "show_video") as mock_video,
    ):
        viewer.display(sample_png)
    mock_load.assert_called_once_with(sample_png)
    mock_video.assert_not_called()


def test_display_dispatches_video(qtbot, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    with (
        patch.object(viewer, "load_image") as mock_load,
        patch.object(viewer, "show_video") as mock_video,
    ):
        viewer.display(video)
    mock_video.assert_called_once_with(video)
    mock_load.assert_not_called()


def test_show_video_enters_video_mode(qtbot, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.show_video(video)

    assert viewer._video_mode is True
    assert viewer._mode == _ZoomMode.FIT_WINDOW
    assert viewer.current_path == video
    assert viewer.windowTitle() == video.name
    assert not viewer._pixmap.isNull()
    assert viewer._zoom_label.text() == ""
    for btn in (
        viewer._zoom_buttons + viewer._zoom_inout_buttons + viewer._rotate_buttons
    ):
        assert btn.isEnabled() is False
    assert viewer._rotate_auto_btn.isEnabled() is False
    assert viewer._reset_exif_btn.isEnabled() is False


def test_load_image_after_show_video_restores_controls(qtbot, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.show_video(video)
    viewer.load_image(sample_png)

    assert viewer._video_mode is False
    for btn in (
        viewer._zoom_buttons + viewer._zoom_inout_buttons + viewer._rotate_buttons
    ):
        assert btn.isEnabled() is True


def test_video_mode_blocks_set_mode(qtbot, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.show_video(video)
    viewer._act_1to1()
    assert viewer._mode == _ZoomMode.FIT_WINDOW


def test_video_mode_allows_set_mode_fit_window(qtbot, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.show_video(video)
    viewer._act_fit_window()  # same mode, must not be blocked
    assert viewer._mode == _ZoomMode.FIT_WINDOW


def test_video_mode_blocks_apply_custom(qtbot, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.show_video(video)
    viewer._act_zoom_in()
    assert viewer._mode == _ZoomMode.FIT_WINDOW


def test_video_mode_blocks_zoom_to_point(qtbot, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.show_video(video)
    viewer._zoom_to_point(QPoint(10, 10))
    assert viewer._mode == _ZoomMode.FIT_WINDOW


def test_video_extensions_defaults_to_empty(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    assert viewer._video_extensions == set()


# ---------------------------------------------------------------------------
# set_selection / selection-strip navigation
# ---------------------------------------------------------------------------


def test_set_selection_single_hides_strip(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._strip.setVisible(
        True
    )  # simulate strip left over from a previous multi-selection
    with patch.object(viewer, "display") as mock_display:
        viewer.set_selection([sample_png])
    mock_display.assert_called_once_with(sample_png)
    assert viewer._strip.isVisible() is False


def test_set_selection_multiple_shows_strip_and_first_file(qtbot, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "display") as mock_display:
        viewer.set_selection([sample_png, other])
    mock_display.assert_called_once_with(sample_png)
    assert viewer._strip.isHidden() is False
    assert viewer._selection_index == 0
    assert len(viewer._strip._labels) == 2


def test_set_selection_with_current_displays_and_highlights_it(
    qtbot, sample_png, tmp_path
):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "display") as mock_display:
        viewer.set_selection([sample_png, other], current=other)
    mock_display.assert_called_once_with(other)
    assert viewer._selection_index == 1
    assert viewer._strip.current_index == 1


def test_set_selection_current_not_in_paths_falls_back_to_first(
    qtbot, sample_png, tmp_path
):
    other = tmp_path / "other.png"
    unrelated = tmp_path / "unrelated.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "display") as mock_display:
        viewer.set_selection([sample_png, other], current=unrelated)
    mock_display.assert_called_once_with(sample_png)
    assert viewer._selection_index == 0


def test_selection_next_prev_clamped(qtbot, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, other])

    viewer._act_prev()  # already at index 0 → no-op
    assert viewer._selection_index == 0

    viewer._act_next()
    assert viewer._selection_index == 1
    assert viewer.current_path == other

    viewer._act_next()  # already at last index → no-op
    assert viewer._selection_index == 1

    viewer._act_prev()
    assert viewer._selection_index == 0
    assert viewer.current_path == sample_png


def test_selection_next_prev_wraps_in_circular_mode(qtbot, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_toggle_circular()
    viewer.set_selection([sample_png, other])

    viewer._act_prev()  # index 0 → wraps to last
    assert viewer._selection_index == 1
    assert viewer.current_path == other

    viewer._act_next()  # last → wraps to first
    assert viewer._selection_index == 0
    assert viewer.current_path == sample_png


def test_circular_mode_defaults_to_linear(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    assert viewer.circular_navigation is False
    assert "circular" in viewer._circular_btn.toolTip()


def test_toggle_circular_updates_button_and_persists(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._circular_btn.click()
    assert viewer.circular_navigation is True
    assert "linear" in viewer._circular_btn.toolTip()

    reopened = ImageViewer(sample_png)
    qtbot.addWidget(reopened)
    assert reopened.circular_navigation is True

    reopened._circular_btn.click()
    assert reopened.circular_navigation is False
    assert "circular" in reopened._circular_btn.toolTip()


def _arrow(viewer, key):
    from PySide6.QtGui import QShortcut

    shortcuts = [
        sc for sc in viewer.findChildren(QShortcut) if sc.key() == QKeySequence(key)
    ]
    assert len(shortcuts) == 1
    shortcuts[0].activated.emit()


@pytest.mark.parametrize(
    ("key", "signal"),
    [
        (Qt.Key.Key_Up, "navigate_prev"),
        (Qt.Key.Key_Left, "navigate_prev"),
        (Qt.Key.Key_Down, "navigate_next"),
        (Qt.Key.Key_Right, "navigate_next"),
    ],
)
def test_arrows_with_single_file_ask_for_list_navigation(
    qtbot, sample_png, key, signal
):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png])
    with qtbot.waitSignal(getattr(viewer, signal), timeout=500):
        _arrow(viewer, key)
    assert viewer._selection_index == 0


@pytest.mark.parametrize(
    ("forward", "backward"),
    [(Qt.Key.Key_Right, Qt.Key.Key_Left), (Qt.Key.Key_Down, Qt.Key.Key_Up)],
)
def test_arrows_with_selection_browse_it(
    qtbot, sample_png, tmp_path, forward, backward
):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, other])
    emitted = []
    viewer.navigate_prev.connect(lambda: emitted.append("prev"))
    viewer.navigate_next.connect(lambda: emitted.append("next"))

    _arrow(viewer, forward)
    assert viewer.current_path == other
    _arrow(viewer, forward)  # linear: stays on the last one
    assert viewer.current_path == other
    _arrow(viewer, backward)
    assert viewer.current_path == sample_png
    assert viewer.selection_paths == [sample_png, other]
    assert emitted == []


def test_selection_strip_renders_video_icon(qtbot, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, video])
    assert len(viewer._strip._labels) == 2
    qtbot.waitUntil(lambda: not viewer._strip._labels[1].pixmap().isNull())


def test_selection_strip_highlights_current_thumbnail(qtbot, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, other])

    assert "palette(highlight)" in viewer._strip._labels[0].styleSheet()
    assert "palette(highlight)" not in viewer._strip._labels[1].styleSheet()

    viewer._act_next()
    assert "palette(highlight)" not in viewer._strip._labels[0].styleSheet()
    assert "palette(highlight)" in viewer._strip._labels[1].styleSheet()


def test_clicking_strip_thumbnail_navigates(qtbot, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, other])

    viewer._strip._labels[1].clicked.emit()

    assert viewer._selection_index == 1
    assert viewer.current_path == other
    assert "palette(highlight)" in viewer._strip._labels[1].styleSheet()


def test_selection_goto_out_of_range_ignored(qtbot, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, other])
    viewer._act_selection_goto(5)
    assert viewer._selection_index == 0
    assert viewer.current_path == sample_png


def test_clickable_label_emits_on_left_click(qtbot):
    from pbrenamer.ui.image_viewer import _ClickableLabel

    label = _ClickableLabel()
    qtbot.addWidget(label)
    with qtbot.waitSignal(label.clicked, timeout=500):
        qtbot.mouseClick(label, Qt.LeftButton)


# ---------------------------------------------------------------------------
# refresh_paths (e.g. after an external rotation)
# ---------------------------------------------------------------------------


def test_refresh_paths_reloads_current_single_file(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "display") as mock_display:
        viewer.refresh_paths({sample_png})
    mock_display.assert_called_once_with(sample_png)


def test_refresh_paths_ignores_unrelated_path(qtbot, sample_png, tmp_path):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "display") as mock_display:
        viewer.refresh_paths({tmp_path / "other.png"})
    mock_display.assert_not_called()


def test_refresh_paths_updates_matching_strip_thumbnail(qtbot, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, other])  # displays sample_png, index 0

    with patch.object(viewer._strip, "refresh_thumbnail") as mock_refresh:
        viewer.refresh_paths({other})
    mock_refresh.assert_called_once_with(1, other, viewer._video_extensions)


def test_refresh_paths_updates_both_viewport_and_strip_for_displayed_file(
    qtbot, sample_png, tmp_path
):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, other])  # displays sample_png, index 0

    with (
        patch.object(viewer, "display") as mock_display,
        patch.object(viewer._strip, "refresh_thumbnail") as mock_refresh,
    ):
        viewer.refresh_paths({sample_png})
    mock_display.assert_called_once_with(sample_png)
    mock_refresh.assert_called_once_with(0, sample_png, viewer._video_extensions)


def test_selection_strip_refresh_thumbnail_out_of_range(qtbot, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._strip.refresh_thumbnail(0, sample_png, set())  # no labels yet — no crash


def test_strip_video_thumbnail_and_refresh(qtbot, sample_png, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, str(video)])
    qtbot.waitUntil(lambda: not viewer._strip._labels[1].pixmap().isNull())
    viewer._strip.refresh_thumbnail(5, sample_png, frozenset())  # out of range
    viewer._strip.refresh_thumbnail(0, sample_png, frozenset())
    viewer.set_selection([str(video), sample_png])  # rebuilt, old labels dropped
    assert len(viewer._strip._labels) == 2


def test_strip_unreadable_image(qtbot, sample_png, tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a png")
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, str(bad)])
    qtbot.waitUntil(lambda: 1 in viewer._strip._loaded)
    assert viewer._strip._labels[1].pixmap().isNull()


class TestLazyStrip:
    """The selection strip loads its thumbnails lazily (7.2 #9)."""

    def _viewer(self, qtbot, tmp_path, count):
        paths = []
        for i in range(count):
            path = tmp_path / f"img{i:03}.png"
            Image.new("RGB", (8, 8)).save(str(path))
            paths.append(str(path))
        viewer = ImageViewer(paths[0])
        qtbot.addWidget(viewer)
        viewer.resize(400, 300)
        viewer.show()
        return viewer, paths

    def test_nothing_loaded_synchronously(self, qtbot, tmp_path, monkeypatch):
        viewer, paths = self._viewer(qtbot, tmp_path, 3)
        loads = []
        original = image_viewer._SelectionStrip._thumbnail_pixmap
        monkeypatch.setattr(
            image_viewer._SelectionStrip,
            "_thumbnail_pixmap",
            staticmethod(lambda p, v: loads.append(p) or original(p, v)),
        )
        viewer.set_selection(paths)
        assert loads == []
        qtbot.waitUntil(lambda: len(loads) == 3)

    def test_only_visible_part_loaded(self, qtbot, tmp_path):
        viewer, paths = self._viewer(qtbot, tmp_path, 200)
        strip = viewer._strip
        viewer.set_selection(paths)
        qtbot.waitUntil(lambda: 0 in strip._loaded)
        qtbot.wait(50)
        assert 0 < len(strip._loaded) < 200
        assert 199 not in strip._loaded
        strip.horizontalScrollBar().setValue(strip.horizontalScrollBar().maximum())
        qtbot.waitUntil(lambda: 199 in strip._loaded)
        assert len(strip._loaded) < 200

    def test_current_file_loaded_first(self, qtbot, tmp_path):
        viewer, paths = self._viewer(qtbot, tmp_path, 200)
        strip = viewer._strip
        viewer.set_selection(paths, current=paths[150])
        assert strip._wanted()[0] == 150
        strip._load_visible()
        assert 150 in strip._loaded

    def test_new_selection_resets_loading(self, qtbot, tmp_path):
        viewer, paths = self._viewer(qtbot, tmp_path, 3)
        strip = viewer._strip
        viewer.set_selection(paths)
        qtbot.waitUntil(lambda: len(strip._loaded) == 3)
        viewer.set_selection(paths[:2])
        assert strip._loaded == set()
        qtbot.waitUntil(lambda: strip._loaded == {0, 1})
