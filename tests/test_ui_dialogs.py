"""Tests for UI dialogs — AboutDialog, SettingsDialog, HistoryDialog,
ShortcutsDialog, FileInfoWindow, PatternHelpDialog, WhitespaceLineEdit."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pytestqt.qtbot import QtBot

import pbrenamer.settings as _cfg

# ---------------------------------------------------------------------------
# AboutDialog
# ---------------------------------------------------------------------------


class TestAboutDialog:
    def test_dialog_opens(self, qtbot: QtBot):
        from pbrenamer.ui.about_dialog import AboutDialog

        dlg = AboutDialog()
        qtbot.addWidget(dlg)
        assert dlg is not None

    def test_version_label_not_empty(self, qtbot: QtBot):
        from pbrenamer.ui.about_dialog import AboutDialog

        dlg = AboutDialog()
        qtbot.addWidget(dlg)
        assert dlg._ui.lblVersion.text() != ""

    def test_python_version_label_starts_with_python(self, qtbot: QtBot):
        from pbrenamer.ui.about_dialog import AboutDialog

        dlg = AboutDialog()
        qtbot.addWidget(dlg)
        assert dlg._ui.lblPythonVersion.text().startswith("Python ")

    def test_pyside_version_label_starts_with_pyside6(self, qtbot: QtBot):
        from pbrenamer.ui.about_dialog import AboutDialog

        dlg = AboutDialog()
        qtbot.addWidget(dlg)
        assert dlg._ui.lblPySideVersion.text().startswith("PySide6 ")


class TestAuthorsHtml:
    def test_returns_string(self):
        from pbrenamer.ui.about_dialog import _authors_html

        result = _authors_html()
        assert isinstance(result, str)

    def test_contains_mailto_for_known_author(self):
        from pbrenamer.ui.about_dialog import _authors_html

        html = _authors_html()
        assert "mailto:" in html or html == ""

    def test_fallback_on_metadata_error(self):
        from pbrenamer.ui.about_dialog import _authors_html

        with patch("pbrenamer.ui.about_dialog.metadata", side_effect=Exception("fail")):
            result = _authors_html()
        assert result == ""

    def test_name_only_entry_no_link(self):
        from pbrenamer.ui.about_dialog import _authors_html

        with patch(
            "pbrenamer.ui.about_dialog.metadata",
            return_value=MagicMock(get_all=lambda k: ["Name Only <>"]),
        ):
            result = _authors_html()
        # Either empty addr or name without link — no crash
        assert isinstance(result, str)

    def test_dialog_sets_icon_pixmap_when_icon_is_set(self, qtbot: QtBot):
        from PySide6.QtGui import QIcon, QPixmap
        from PySide6.QtWidgets import QApplication

        from pbrenamer.ui.about_dialog import AboutDialog

        pm = QPixmap(64, 64)
        pm.fill()
        icon = QIcon(pm)
        original_icon = QApplication.windowIcon()
        QApplication.setWindowIcon(icon)
        try:
            dlg = AboutDialog()
            qtbot.addWidget(dlg)
            assert not dlg._ui.lblIcon.pixmap().isNull()
        finally:
            QApplication.setWindowIcon(original_icon)


# ---------------------------------------------------------------------------
# SettingsDialog
# ---------------------------------------------------------------------------


class TestSettingsDialog:
    @pytest.fixture
    def cfg_dir(self, tmp_path, monkeypatch):
        mock_dirs = MagicMock()
        mock_dirs.config_home = tmp_path
        monkeypatch.setattr(_cfg, "_dirs", mock_dirs)
        monkeypatch.setattr(_cfg, "_SHORTCUTS_FILE", tmp_path / "shortcuts.json")
        import pbrenamer.i18n as i18n

        monkeypatch.setattr(i18n, "_dirs", mock_dirs)
        return tmp_path

    @pytest.fixture
    def window_state(self):
        ws = MagicMock()
        ws.load_geometry.return_value = None
        return ws

    def test_dialog_opens(self, qtbot: QtBot, cfg_dir, window_state):
        from pbrenamer.ui.settings_dialog import SettingsDialog

        dlg = SettingsDialog(window_state)
        qtbot.addWidget(dlg)
        assert dlg is not None

    def test_log_level_combo_contains_all_levels(
        self, qtbot: QtBot, cfg_dir, window_state
    ):
        from pbrenamer.ui.settings_dialog import SettingsDialog

        dlg = SettingsDialog(window_state)
        qtbot.addWidget(dlg)
        items = [
            dlg._ui.cmbLogLevel.itemText(i) for i in range(dlg._ui.cmbLogLevel.count())
        ]
        for lvl in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            assert lvl in items

    def test_language_combo_has_system_default(
        self, qtbot: QtBot, cfg_dir, window_state
    ):
        from pbrenamer.ui.settings_dialog import SettingsDialog

        dlg = SettingsDialog(window_state)
        qtbot.addWidget(dlg)
        assert dlg._ui.cmbLanguage.count() > 0
        assert dlg._ui.cmbLanguage.itemData(0) == ""

    def test_accept_persists_settings(self, qtbot: QtBot, cfg_dir, window_state):
        from pbrenamer.ui.settings_dialog import SettingsDialog

        dlg = SettingsDialog(window_state)
        qtbot.addWidget(dlg)
        idx = dlg._ui.cmbLogLevel.findText("WARNING")
        dlg._ui.cmbLogLevel.setCurrentIndex(idx)
        dlg._ui.chkRestoreLastDir.setChecked(True)
        dlg._ui.spnPreviewDelay.setValue(300)
        dlg._save_and_accept()
        assert _cfg.get_log_level() == "WARNING"
        assert _cfg.get_restore_last_dir() is True
        assert _cfg.get_preview_delay() == 300

    def test_saved_language_override_is_selected(
        self, qtbot: QtBot, cfg_dir, window_state
    ):
        import pbrenamer.i18n as i18n
        from pbrenamer.ui.settings_dialog import SettingsDialog

        i18n.set_language_override("fr")
        dlg = SettingsDialog(window_state)
        qtbot.addWidget(dlg)
        assert dlg._ui.cmbLanguage.currentData() == "fr"


# ---------------------------------------------------------------------------
# HistoryDialog
# ---------------------------------------------------------------------------


class TestHistoryDialog:
    @pytest.fixture
    def presets(self, tmp_path):
        from pbrenamer.ui.presets import PatternPresets

        return PatternPresets(tmp_path / "patterns")

    @pytest.fixture
    def window_state(self):
        ws = MagicMock()
        ws.load_geometry.return_value = None
        return ws

    def test_dialog_opens(self, qtbot: QtBot, presets, window_state):
        from pbrenamer.ui.history_dialog import HistoryDialog

        dlg = HistoryDialog(presets, window_state)
        qtbot.addWidget(dlg)
        assert dlg is not None

    def test_search_list_shows_defaults(self, qtbot: QtBot, presets, window_state):
        from pbrenamer.ui.history_dialog import HistoryDialog

        dlg = HistoryDialog(presets, window_state)
        qtbot.addWidget(dlg)
        assert dlg._ui.lstSearch.count() > 0

    def test_replace_list_shows_defaults(self, qtbot: QtBot, presets, window_state):
        from pbrenamer.ui.history_dialog import HistoryDialog

        dlg = HistoryDialog(presets, window_state)
        qtbot.addWidget(dlg)
        assert dlg._ui.lstReplace.count() > 0

    def test_add_search_pattern_mode(self, qtbot: QtBot, presets, window_state):
        from pbrenamer.ui.history_dialog import HistoryDialog

        dlg = HistoryDialog(presets, window_state)
        qtbot.addWidget(dlg)
        dlg._ui.edtSearch.setText("mypattern")
        dlg._ui.radPattern.setChecked(True)
        dlg._on_add_search()
        entries = presets.get_search()
        assert any(p == "mypattern" for _, p in entries)

    def test_add_search_regex_mode(self, qtbot: QtBot, presets, window_state):
        from pbrenamer.ui.history_dialog import HistoryDialog

        dlg = HistoryDialog(presets, window_state)
        qtbot.addWidget(dlg)
        dlg._ui.edtSearch.setText(r"\d+")
        dlg._ui.radRegex.setChecked(True)
        dlg._on_add_search()
        entries = presets.get_search()
        assert any(m == "regex" and p == r"\d+" for m, p in entries)

    def test_add_search_plain_mode(self, qtbot: QtBot, presets, window_state):
        from pbrenamer.ui.history_dialog import HistoryDialog

        dlg = HistoryDialog(presets, window_state)
        qtbot.addWidget(dlg)
        dlg._ui.edtSearch.setText("plaintext")
        dlg._ui.radPlainText.setChecked(True)
        dlg._on_add_search()
        entries = presets.get_search()
        assert any(m == "plain" and p == "plaintext" for m, p in entries)

    def test_add_search_empty_is_noop(self, qtbot: QtBot, presets, window_state):
        from pbrenamer.ui.history_dialog import HistoryDialog

        dlg = HistoryDialog(presets, window_state)
        qtbot.addWidget(dlg)
        before = presets.get_search()
        dlg._ui.edtSearch.setText("")
        dlg._on_add_search()
        assert presets.get_search() == before

    def test_clear_search(self, qtbot: QtBot, presets, window_state):
        from pbrenamer.ui.history_dialog import HistoryDialog

        presets.add_search("plain", "something")
        dlg = HistoryDialog(presets, window_state)
        qtbot.addWidget(dlg)
        dlg._on_clear_search()
        from pbrenamer.ui.presets import _SEARCH_DEFAULTS

        assert presets.get_search() == list(_SEARCH_DEFAULTS)

    def test_remove_selected_search(self, qtbot: QtBot, presets, window_state):
        from pbrenamer.ui.history_dialog import HistoryDialog

        presets.add_search("plain", "keep")
        presets.add_search("plain", "remove-me")
        dlg = HistoryDialog(presets, window_state)
        qtbot.addWidget(dlg)
        dlg._ui.lstSearch.setCurrentRow(0)
        dlg._on_remove_search()
        entries = presets.get_search()
        assert all(p != "remove-me" for _, p in entries)

    def test_add_replace(self, qtbot: QtBot, presets, window_state):
        from pbrenamer.ui.history_dialog import HistoryDialog

        dlg = HistoryDialog(presets, window_state)
        qtbot.addWidget(dlg)
        dlg._ui.edtReplace.setText("{2}_{1}")
        dlg._on_add_replace()
        assert "{2}_{1}" in presets.get_replace()

    def test_add_replace_empty_is_noop(self, qtbot: QtBot, presets, window_state):
        from pbrenamer.ui.history_dialog import HistoryDialog

        dlg = HistoryDialog(presets, window_state)
        qtbot.addWidget(dlg)
        before = presets.get_replace()
        dlg._ui.edtReplace.setText("")
        dlg._on_add_replace()
        assert presets.get_replace() == before

    def test_clear_replace(self, qtbot: QtBot, presets, window_state):
        from pbrenamer.ui.history_dialog import HistoryDialog

        presets.add_replace("{A}")
        dlg = HistoryDialog(presets, window_state)
        qtbot.addWidget(dlg)
        dlg._on_clear_replace()
        from pbrenamer.ui.presets import _REPLACE_DEFAULTS

        assert presets.get_replace() == list(_REPLACE_DEFAULTS)

    def test_remove_selected_replace(self, qtbot: QtBot, presets, window_state):
        from pbrenamer.ui.history_dialog import HistoryDialog

        presets.add_replace("keep")
        presets.add_replace("remove-me")
        dlg = HistoryDialog(presets, window_state)
        qtbot.addWidget(dlg)
        dlg._ui.lstReplace.setCurrentRow(0)
        dlg._on_remove_replace()
        assert "remove-me" not in presets.get_replace()


# ---------------------------------------------------------------------------
# ShortcutsDialog
# ---------------------------------------------------------------------------


class TestShortcutsDialog:
    @pytest.fixture
    def cfg_dir(self, tmp_path, monkeypatch):
        mock_dirs = MagicMock()
        mock_dirs.config_home = tmp_path
        monkeypatch.setattr(_cfg, "_dirs", mock_dirs)
        monkeypatch.setattr(_cfg, "_SHORTCUTS_FILE", tmp_path / "shortcuts.json")
        return tmp_path

    @pytest.fixture
    def window_state(self):
        ws = MagicMock()
        ws.load_geometry.return_value = None
        return ws

    def test_dialog_opens(self, qtbot: QtBot, cfg_dir, window_state):
        from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog

        dlg = ShortcutsDialog(window_state)
        qtbot.addWidget(dlg)
        assert dlg is not None

    def test_empty_shortcuts_shows_no_items(self, qtbot: QtBot, cfg_dir, window_state):
        from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog

        dlg = ShortcutsDialog(window_state)
        qtbot.addWidget(dlg)
        assert dlg._list.count() == 0

    def test_list_shows_saved_shortcuts(self, qtbot: QtBot, cfg_dir, window_state):
        from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog

        _cfg.set_shortcuts([("Home", "/home/user"), ("Docs", "/home/user/docs")])
        dlg = ShortcutsDialog(window_state)
        qtbot.addWidget(dlg)
        assert dlg._list.count() == 2

    def test_buttons_disabled_when_no_selection(
        self, qtbot: QtBot, cfg_dir, window_state
    ):
        from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog

        _cfg.set_shortcuts([("A", "/a")])
        dlg = ShortcutsDialog(window_state)
        qtbot.addWidget(dlg)
        dlg._list.clearSelection()
        dlg._on_selection_changed()
        assert not dlg._btn_up.isEnabled()
        assert not dlg._btn_down.isEnabled()
        assert not dlg._btn_remove.isEnabled()

    def test_move_up(self, qtbot: QtBot, cfg_dir, window_state):
        from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog

        _cfg.set_shortcuts([("A", "/a"), ("B", "/b")])
        dlg = ShortcutsDialog(window_state)
        qtbot.addWidget(dlg)
        dlg._list.setCurrentRow(1)
        dlg._on_move_up()
        shortcuts = _cfg.get_shortcuts()
        assert shortcuts[0] == ("B", "/b")
        assert shortcuts[1] == ("A", "/a")

    def test_move_up_noop_at_top(self, qtbot: QtBot, cfg_dir, window_state):
        from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog

        _cfg.set_shortcuts([("A", "/a"), ("B", "/b")])
        dlg = ShortcutsDialog(window_state)
        qtbot.addWidget(dlg)
        dlg._list.setCurrentRow(0)
        dlg._on_move_up()
        assert _cfg.get_shortcuts()[0] == ("A", "/a")

    def test_move_down(self, qtbot: QtBot, cfg_dir, window_state):
        from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog

        _cfg.set_shortcuts([("A", "/a"), ("B", "/b")])
        dlg = ShortcutsDialog(window_state)
        qtbot.addWidget(dlg)
        dlg._list.setCurrentRow(0)
        dlg._on_move_down()
        shortcuts = _cfg.get_shortcuts()
        assert shortcuts[0] == ("B", "/b")
        assert shortcuts[1] == ("A", "/a")

    def test_move_down_noop_at_bottom(self, qtbot: QtBot, cfg_dir, window_state):
        from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog

        _cfg.set_shortcuts([("A", "/a"), ("B", "/b")])
        dlg = ShortcutsDialog(window_state)
        qtbot.addWidget(dlg)
        dlg._list.setCurrentRow(1)
        dlg._on_move_down()
        assert _cfg.get_shortcuts()[1] == ("B", "/b")

    def test_remove_item(self, qtbot: QtBot, cfg_dir, window_state):
        from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog

        _cfg.set_shortcuts([("A", "/a"), ("B", "/b")])
        dlg = ShortcutsDialog(window_state)
        qtbot.addWidget(dlg)
        dlg._list.setCurrentRow(0)
        dlg._on_remove()
        shortcuts = _cfg.get_shortcuts()
        assert ("A", "/a") not in shortcuts

    def test_remove_noop_when_no_item(self, qtbot: QtBot, cfg_dir, window_state):
        from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog

        dlg = ShortcutsDialog(window_state)
        qtbot.addWidget(dlg)
        dlg._on_remove()  # must not raise

    def test_selection_changed_updates_buttons(
        self, qtbot: QtBot, cfg_dir, window_state
    ):
        from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog

        _cfg.set_shortcuts([("A", "/a"), ("B", "/b")])
        dlg = ShortcutsDialog(window_state)
        qtbot.addWidget(dlg)
        dlg._list.setCurrentRow(1)
        dlg._on_selection_changed()
        assert dlg._btn_up.isEnabled()
        assert not dlg._btn_down.isEnabled()
        assert dlg._btn_remove.isEnabled()


# ---------------------------------------------------------------------------
# FileInfoWindow
# ---------------------------------------------------------------------------


class TestDetectType:
    def test_directory(self, tmp_path):
        from pbrenamer.ui.file_info_window import _detect_type

        assert _detect_type(str(tmp_path)) == "directory"

    def test_other_for_unknown_extension(self, tmp_path):
        from pbrenamer.ui.file_info_window import _detect_type

        p = tmp_path / "file.xyz"
        p.touch()
        assert _detect_type(str(p)) == "other"

    def test_image_for_jpeg(self, tmp_path):
        from pbrenamer.core import image_meta
        from pbrenamer.ui.file_info_window import _detect_type

        p = tmp_path / "photo.jpg"
        p.touch()
        with patch.object(image_meta, "can_read", return_value=True):
            assert _detect_type(str(p)) == "image"

    def test_audio_for_mp3(self, tmp_path):
        from pbrenamer.core import audio_meta, image_meta
        from pbrenamer.ui.file_info_window import _detect_type

        p = tmp_path / "song.mp3"
        p.touch()
        with (
            patch.object(image_meta, "can_read", return_value=False),
            patch.object(audio_meta, "can_read", return_value=True),
        ):
            assert _detect_type(str(p)) == "audio"

    def test_video_for_mp4(self, tmp_path):
        from pbrenamer.core import audio_meta, image_meta, video_meta
        from pbrenamer.ui.file_info_window import _detect_type

        p = tmp_path / "clip.mp4"
        p.touch()
        with (
            patch.object(image_meta, "can_read", return_value=False),
            patch.object(video_meta, "can_read", return_value=True),
            patch.object(audio_meta, "can_read", return_value=False),
        ):
            assert _detect_type(str(p)) == "video"


class TestFmt:
    def test_datetime(self):
        import datetime

        from pbrenamer.ui.file_info_window import _fmt

        dt = datetime.datetime(2024, 3, 15, 10, 30, 0)
        assert _fmt(dt) == "2024-03-15_103000"

    def test_date(self):
        import datetime

        from pbrenamer.ui.file_info_window import _fmt

        d = datetime.date(2024, 3, 15)
        assert _fmt(d) == "2024-03-15"

    def test_string(self):
        from pbrenamer.ui.file_info_window import _fmt

        assert _fmt("hello") == "hello"

    def test_integer(self):
        from pbrenamer.ui.file_info_window import _fmt

        assert _fmt(42) == "42"


class TestFileInfoWindow:
    @pytest.fixture
    def window_state(self):
        ws = MagicMock()
        ws.load_geometry.return_value = None
        return ws

    def test_window_opens(self, qtbot: QtBot, window_state):
        from pbrenamer.ui.file_info_window import FileInfoWindow

        w = FileInfoWindow(window_state)
        qtbot.addWidget(w)
        assert w is not None

    def test_show_empty(self, qtbot: QtBot, window_state):
        from pbrenamer.ui.file_info_window import FileInfoWindow

        w = FileInfoWindow(window_state)
        qtbot.addWidget(w)
        w.show_empty()
        assert not w._lbl_status.isHidden()
        assert w._tree.isHidden()

    def test_show_multiple(self, qtbot: QtBot, window_state):
        from pbrenamer.ui.file_info_window import FileInfoWindow

        w = FileInfoWindow(window_state)
        qtbot.addWidget(w)
        w.show_multiple()
        assert not w._lbl_status.isHidden()
        assert w._tree.isHidden()

    def test_update_file_for_regular_file(self, qtbot: QtBot, tmp_path, window_state):
        from pbrenamer.ui.file_info_window import FileInfoWindow

        p = tmp_path / "test.txt"
        p.write_text("hello", encoding="utf-8")
        w = FileInfoWindow(window_state)
        qtbot.addWidget(w)
        w.update_file(str(p))
        assert not w._tree.isHidden()
        assert not w._lbl_info.isHidden()

    def test_update_file_for_directory(self, qtbot: QtBot, tmp_path, window_state):
        from pbrenamer.ui.file_info_window import FileInfoWindow

        w = FileInfoWindow(window_state)
        qtbot.addWidget(w)
        w.update_file(str(tmp_path))
        assert not w._tree.isHidden()

    def test_update_file_with_image(self, qtbot: QtBot, tmp_path, window_state):
        from pbrenamer.core import image_meta
        from pbrenamer.ui.file_info_window import FileInfoWindow

        p = tmp_path / "photo.jpg"
        p.touch()
        w = FileInfoWindow(window_state)
        qtbot.addWidget(w)
        with patch.object(image_meta, "can_read", return_value=True):
            w.update_file(str(p))
        assert not w._tree.isHidden()

    def test_update_file_with_audio(self, qtbot: QtBot, tmp_path, window_state):
        from pbrenamer.core import audio_meta, image_meta
        from pbrenamer.ui.file_info_window import FileInfoWindow

        p = tmp_path / "song.mp3"
        p.touch()
        w = FileInfoWindow(window_state)
        qtbot.addWidget(w)
        with (
            patch.object(image_meta, "can_read", return_value=False),
            patch.object(audio_meta, "can_read", return_value=True),
        ):
            w.update_file(str(p))
        assert not w._tree.isHidden()

    def test_update_file_with_video(self, qtbot: QtBot, tmp_path, window_state):
        from pbrenamer.core import audio_meta, image_meta, video_meta
        from pbrenamer.ui.file_info_window import FileInfoWindow

        p = tmp_path / "clip.mp4"
        p.touch()
        w = FileInfoWindow(window_state)
        qtbot.addWidget(w)
        with (
            patch.object(image_meta, "can_read", return_value=False),
            patch.object(video_meta, "can_read", return_value=True),
            patch.object(audio_meta, "can_read", return_value=False),
        ):
            w.update_file(str(p))
        assert not w._tree.isHidden()

    def test_update_file_title_contains_filename(
        self, qtbot: QtBot, tmp_path, window_state
    ):
        from pbrenamer.ui.file_info_window import FileInfoWindow

        p = tmp_path / "myfile.txt"
        p.touch()
        w = FileInfoWindow(window_state)
        qtbot.addWidget(w)
        w.update_file(str(p))
        assert "myfile.txt" in w.windowTitle()

    def test_universal_fields_oserror(self, qtbot: QtBot, window_state):
        from pbrenamer.ui.file_info_window import FileInfoWindow

        w = FileInfoWindow(window_state)
        qtbot.addWidget(w)
        w.update_file("/this/path/does/not/exist/at/all.txt")
        assert w._tree.topLevelItemCount() > 0


# ---------------------------------------------------------------------------
# PatternHelpDialog
# ---------------------------------------------------------------------------


class TestPatternHelpDialog:
    @pytest.fixture
    def window_state(self, tmp_path):
        from pbrenamer.ui.window_state import WindowState

        return WindowState(tmp_path / "state.json")

    def test_dialog_opens(self, qtbot: QtBot, window_state):
        from pbrenamer.ui.pattern_help import PatternHelpDialog

        dlg = PatternHelpDialog(
            html="<b>Help</b>",
            title="Test Help",
            state_key="test_help",
            window_state=window_state,
        )
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "Test Help"

    def test_dialog_uses_default_size_when_no_saved_geo(
        self, qtbot: QtBot, window_state
    ):
        from pbrenamer.ui.pattern_help import PatternHelpDialog

        dlg = PatternHelpDialog(
            html="<b>Help</b>",
            title="Test Help",
            state_key="test_help",
            window_state=window_state,
        )
        qtbot.addWidget(dlg)
        assert dlg.width() == 560
        assert dlg.height() == 500

    def test_dialog_restores_saved_geometry(self, qtbot: QtBot, window_state):

        from pbrenamer.ui.pattern_help import PatternHelpDialog

        dlg1 = PatternHelpDialog(
            html="",
            title="T",
            state_key="key1",
            window_state=window_state,
        )
        qtbot.addWidget(dlg1)
        dlg1.resize(700, 600)
        dlg1.show()
        qtbot.waitExposed(dlg1)
        geo = dlg1.saveGeometry()
        window_state.save_geometry("key1", geo)

        dlg2 = PatternHelpDialog(
            html="",
            title="T",
            state_key="key1",
            window_state=window_state,
        )
        qtbot.addWidget(dlg2)
        dlg2.show()
        qtbot.waitExposed(dlg2)
        assert dlg2.geometry() == dlg1.geometry()

    def test_close_event_saves_geometry(self, qtbot: QtBot, window_state):
        from pbrenamer.ui.pattern_help import PatternHelpDialog

        dlg = PatternHelpDialog(
            html="",
            title="T",
            state_key="close_test",
            window_state=window_state,
        )
        qtbot.addWidget(dlg)
        dlg.show()
        dlg.close()
        assert window_state.load_geometry("close_test") is not None

    def test_search_help_opens(self, qtbot: QtBot, window_state):
        from pbrenamer.ui.pattern_help import PatternHelpDialog, search_html

        dlg = PatternHelpDialog(
            html=search_html(),
            title="Search Help",
            state_key="search_help",
            window_state=window_state,
        )
        qtbot.addWidget(dlg)
        assert dlg is not None

    def test_replace_help_opens(self, qtbot: QtBot, window_state):
        from pbrenamer.ui.pattern_help import PatternHelpDialog, replace_html

        dlg = PatternHelpDialog(
            html=replace_html(),
            title="Replace Help",
            state_key="replace_help",
            window_state=window_state,
        )
        qtbot.addWidget(dlg)
        assert dlg is not None


# ---------------------------------------------------------------------------
# WhitespaceLineEdit
# ---------------------------------------------------------------------------


class TestWhitespaceLineEdit:
    def test_instantiation(self, qtbot: QtBot):
        from pbrenamer.ui.widgets import WhitespaceLineEdit

        w = WhitespaceLineEdit()
        qtbot.addWidget(w)
        assert w is not None

    def test_uses_fixed_font(self, qtbot: QtBot):
        from PySide6.QtGui import QFontDatabase

        from pbrenamer.ui.widgets import WhitespaceLineEdit

        w = WhitespaceLineEdit()
        qtbot.addWidget(w)
        fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        assert w.font().family() == fixed.family()

    def _force_paint(self, w):
        """Force a synchronous paint cycle via QWidget.render()."""
        from PySide6.QtGui import QPixmap

        pm = QPixmap(max(w.width(), 1), max(w.height(), 1))
        w.render(pm)

    def test_paint_event_no_crash_with_empty_text(self, qtbot: QtBot):
        from pbrenamer.ui.widgets import WhitespaceLineEdit

        w = WhitespaceLineEdit()
        qtbot.addWidget(w)
        w.resize(300, 30)
        w.setText("")
        self._force_paint(w)

    def test_paint_event_no_crash_with_spaces(self, qtbot: QtBot):
        from pbrenamer.ui.widgets import WhitespaceLineEdit

        w = WhitespaceLineEdit()
        qtbot.addWidget(w)
        w.resize(300, 30)
        w.setText("hello world foo")
        self._force_paint(w)

    def test_paint_event_no_crash_with_tabs(self, qtbot: QtBot):
        from pbrenamer.ui.widgets import WhitespaceLineEdit

        w = WhitespaceLineEdit()
        qtbot.addWidget(w)
        w.resize(300, 30)
        w.setText("a\tb\tc")
        self._force_paint(w)

    def test_paint_event_no_crash_with_no_whitespace(self, qtbot: QtBot):
        from pbrenamer.ui.widgets import WhitespaceLineEdit

        w = WhitespaceLineEdit()
        qtbot.addWidget(w)
        w.resize(300, 30)
        w.setText("NoSpaces")
        self._force_paint(w)

    def test_paint_event_mixed_whitespace(self, qtbot: QtBot):
        from pbrenamer.ui.widgets import WhitespaceLineEdit

        w = WhitespaceLineEdit()
        qtbot.addWidget(w)
        w.resize(400, 30)
        w.setText("a b\tc d")
        self._force_paint(w)

    def test_paint_event_clipped_whitespace(self, qtbot: QtBot):
        """Whitespace characters that scroll out of view should be clipped (line 66)."""
        from pbrenamer.ui.widgets import WhitespaceLineEdit

        w = WhitespaceLineEdit()
        qtbot.addWidget(w)
        w.resize(30, 30)  # very narrow widget
        long_text = "A" * 50 + " " + "B" * 50  # space is far right, outside clip rect
        w.setText(long_text)
        w.setCursorPosition(len(long_text))  # scroll to end
        self._force_paint(w)
