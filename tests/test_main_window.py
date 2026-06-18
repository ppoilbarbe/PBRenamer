"""Tests for MainWindow — full business logic coverage."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QPainter,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
    QStyleOptionViewItem,
)

import pbrenamer.ui.main_window as _mwmod
from pbrenamer.core import replacement as _repl
from pbrenamer.settings import (
    get_last_dir,
    get_shortcuts,
    get_toolbar_state,
    set_last_dir,
    set_restore_last_dir,
    set_restore_toolbar_state,
    set_shortcuts,
    set_toolbar_state,
)
from pbrenamer.ui.main_window import MainWindow, _SearchModeDelegate

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_qmenu(monkeypatch):
    """Patch QMenu in main_window so menu.exec() never blocks in any test.

    By default exec() returns None (cancel).  Tests that need a specific return
    value can configure the mock, e.g. to simulate choosing the first action:
        mock_qmenu.exec.return_value = mock_qmenu.addAction.return_value
    """
    mock = MagicMock()
    mock.exec.return_value = None
    monkeypatch.setattr(_mwmod, "QMenu", lambda *a, **kw: mock)
    return mock


@pytest.fixture
def window(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    return w


def _find_item(window, full_path: str):
    """Return the QTreeWidgetItem whose UserRole data matches full_path."""
    root = window._ui.tblFiles.invisibleRootItem()
    for i in range(root.childCount()):
        item = root.child(i)
        if item.data(0, Qt.ItemDataRole.UserRole) == full_path:
            return item
    return None


# ---------------------------------------------------------------------------
# _SearchModeDelegate.paint  (lines 56-73)
# ---------------------------------------------------------------------------


class TestSearchModeDelegate:
    def test_paint_all_modes(self, qtbot):
        from PySide6.QtWidgets import QComboBox

        combo = QComboBox()
        qtbot.addWidget(combo)
        delegate = _SearchModeDelegate(combo)

        model = QStandardItemModel()
        for text, mode in [
            ("^foo$", "regex"),
            ("hello world", "plain"),
            ("{L}", "pattern"),
            ("unlabelled", "other"),  # unknown mode → empty label → early return
        ]:
            item = QStandardItem(text)
            item.setData(mode, Qt.ItemDataRole.UserRole)
            model.appendRow(item)

        px = QPixmap(300, 24)
        painter = QPainter(px)
        opt = QStyleOptionViewItem()
        opt.rect = px.rect()
        opt.palette = QApplication.palette()

        for row in range(model.rowCount()):
            idx = model.index(row, 0)
            delegate.paint(painter, opt, idx)

        painter.end()


# ---------------------------------------------------------------------------
# __init__ branches  (lines 112, 114, 116, 118)
# ---------------------------------------------------------------------------


class TestInit:
    def test_with_start_dir(self, qtbot, tmp_path):
        w = MainWindow(start_dir=str(tmp_path))
        qtbot.addWidget(w)
        # No crash; _startup_navigate will run after singleShot fires

    def test_restore_last_dir_branch(self, qtbot, tmp_path):
        set_restore_last_dir(True)
        set_last_dir(str(tmp_path))
        w = MainWindow()
        qtbot.addWidget(w)

    def test_else_branch(self, qtbot):
        # Neither start_dir nor restore_last_dir → os.getcwd()
        set_restore_last_dir(False)
        w = MainWindow()
        qtbot.addWidget(w)

    def test_restore_toolbar_state_branch(self, qtbot):
        set_restore_toolbar_state(True)
        set_toolbar_state(
            {
                "mode": 0,
                "recursive": False,
                "keep_extension": True,
                "auto_preview": False,
                "filter": "",
            }
        )
        w = MainWindow()
        qtbot.addWidget(w)


# ---------------------------------------------------------------------------
# _startup_navigate / _navigate_to  (lines 132-149)
# ---------------------------------------------------------------------------


class TestNavigation:
    def test_startup_navigate_loads_new_dir(self, window, tmp_path):
        window._current_dir = None
        window._startup_navigate(str(tmp_path))
        assert window._current_dir == str(tmp_path)

    def test_startup_navigate_same_dir_no_extra_reload(self, window, tmp_path):
        # When _current_dir == path, the explicit reload branch (lines 140-141)
        # is not taken (the signal path may still fire from _navigate_to).
        window._current_dir = str(tmp_path)
        window._startup_navigate(str(tmp_path))
        assert window._current_dir == str(tmp_path)

    def test_startup_navigate_reload_branch(self, window, tmp_path, monkeypatch):
        # Lines 140-141: explicit reload when QFileSystemModel hasn't loaded the
        # index yet (lazy load); simulate by making _navigate_to a no-op so the
        # selectionChanged signal never fires and _current_dir is not updated.
        window._current_dir = None
        monkeypatch.setattr(window, "_navigate_to", lambda path: None)
        called = []
        monkeypatch.setattr(window, "_reload_files", lambda: called.append(1))
        window._startup_navigate(str(tmp_path))
        assert window._current_dir == str(tmp_path)
        assert called

    def test_startup_navigate_nonexistent(self, window):
        window._current_dir = None
        window._startup_navigate("/nonexistent/path/xyz")
        assert window._current_dir is None

    def test_navigate_to_nonexistent(self, window):
        window._navigate_to("/nonexistent/path/xyz")  # returns early, no crash

    def test_navigate_to_valid(self, window, tmp_path):
        window._navigate_to(str(tmp_path))  # no crash


# ---------------------------------------------------------------------------
# _on_open  (lines 246-253)
# ---------------------------------------------------------------------------


class TestOnOpen:
    def test_selects_folder(self, window, tmp_path, monkeypatch):
        monkeypatch.setattr(
            QFileDialog,
            "getExistingDirectory",
            staticmethod(lambda *a, **kw: str(tmp_path)),
        )
        window._on_open()
        assert window._current_dir == str(tmp_path)

    def test_cancel_noop(self, window, monkeypatch):
        original = window._current_dir
        monkeypatch.setattr(
            QFileDialog,
            "getExistingDirectory",
            staticmethod(lambda *a, **kw: ""),
        )
        window._on_open()
        assert window._current_dir == original


# ---------------------------------------------------------------------------
# _on_directory_selected  (lines 256-264)
# ---------------------------------------------------------------------------


class TestOnDirectorySelected:
    def test_no_selection_returns_early(self, window):
        window._ui.treeDirectory.clearSelection()
        window._on_directory_selected()  # no crash

    def test_valid_dir_via_mocked_model(self, window, tmp_path, monkeypatch):
        mock_idx = MagicMock()
        mock_idx.isValid.return_value = True
        monkeypatch.setattr(
            window._ui.treeDirectory.selectionModel(),
            "selectedIndexes",
            lambda: [mock_idx],
        )
        monkeypatch.setattr(window._fs_model, "filePath", lambda idx: str(tmp_path))
        window._on_directory_selected()
        assert window._current_dir == str(tmp_path)

    def test_non_directory_path_ignored(self, window, tmp_path, monkeypatch):
        f = tmp_path / "file.txt"
        f.write_text("x")
        mock_idx = MagicMock()
        monkeypatch.setattr(
            window._ui.treeDirectory.selectionModel(),
            "selectedIndexes",
            lambda: [mock_idx],
        )
        monkeypatch.setattr(window._fs_model, "filePath", lambda idx: str(f))
        prev = window._current_dir
        window._on_directory_selected()
        assert window._current_dir == prev  # unchanged


# ---------------------------------------------------------------------------
# _reload_files  (lines 266-307)
# ---------------------------------------------------------------------------


class TestReloadFiles:
    def test_no_current_dir(self, window):
        window._current_dir = None
        window._reload_files()  # early return, no crash

    def test_nonexistent_dir(self, window):
        window._current_dir = "/nonexistent/path/xyz"
        window._reload_files()  # early return, no crash

    def test_loads_files(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / "b.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        assert window._ui.tblFiles.topLevelItemCount() == 2

    def test_loads_with_subdir(self, window, tmp_path):
        work = tmp_path / "work"
        work.mkdir()
        (work / "file.txt").write_text("x")
        (work / "sub").mkdir()
        window._current_dir = str(work)
        window._ui.cmbMode.setCurrentIndex(2)  # files + dirs
        window._reload_files()
        assert window._ui.tblFiles.topLevelItemCount() == 2

    def test_recursive_mode(self, window, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._ui.chkRecursive.setChecked(True)
        window._reload_files()
        assert window._ui.tblFiles.topLevelItemCount() >= 1
        window._ui.chkRecursive.setChecked(False)

    def test_filter_pattern(self, window, tmp_path):
        (tmp_path / "abc.txt").write_text("x")
        (tmp_path / "xyz.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._ui.edtFilter.setText("abc*")
        window._reload_files()
        assert window._ui.tblFiles.topLevelItemCount() == 1
        window._ui.edtFilter.setText("")

    def test_auto_preview_triggered(self, window, tmp_path, monkeypatch):
        window._current_dir = str(tmp_path)
        window._ui.chkAutoPreview.setChecked(True)
        called = []
        monkeypatch.setattr(window, "_on_preview", lambda: called.append(1))
        window._reload_files()
        assert called
        window._ui.chkAutoPreview.setChecked(False)

    def test_rename_button_disabled_after_reload(self, window, tmp_path):
        (tmp_path / "f.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._ui.btnRename.setEnabled(True)
        window._reload_files()
        assert not window._ui.btnRename.isEnabled()


# ---------------------------------------------------------------------------
# _validate_search_input  (lines 319-338)
# ---------------------------------------------------------------------------


class TestValidateSearchInput:
    def test_pattern_mode_always_valid(self, window):
        window._ui.radPattern.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("[{#}]")
        assert window._validate_search_input() is True
        assert window._ui.cmbPatternSearch.lineEdit().styleSheet() == ""

    def test_regex_mode_empty_is_valid(self, window):
        window._ui.radRegex.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("")
        assert window._validate_search_input() is True

    def test_regex_mode_valid_pattern(self, window):
        window._ui.radRegex.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("^foo.*")
        assert window._validate_search_input() is True
        assert window._ui.cmbPatternSearch.lineEdit().styleSheet() == ""

    def test_regex_mode_invalid_pattern(self, window):
        window._ui.radRegex.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("[invalid")
        assert window._validate_search_input() is False
        assert window._ui.cmbPatternSearch.lineEdit().styleSheet() != ""


# ---------------------------------------------------------------------------
# _validate_replace_input  (lines 340-360)
# ---------------------------------------------------------------------------


class TestValidateReplaceInput:
    def test_empty_is_valid(self, window):
        window._ui.cmbPatternDest.setCurrentText("")
        assert window._validate_replace_input() is True
        assert window._ui.cmbPatternDest.lineEdit().styleSheet() == ""

    def test_valid_template(self, window):
        window._ui.cmbPatternDest.setCurrentText("{0}")
        assert window._validate_replace_input() is True
        assert window._ui.cmbPatternDest.lineEdit().styleSheet() == ""

    def test_syntax_error(self, window):
        window._ui.cmbPatternDest.setCurrentText("{bad{nested}}")
        assert window._validate_replace_input() is False
        assert window._ui.cmbPatternDest.lineEdit().styleSheet() != ""

    def test_mode_incompatibility(self, window):
        # {1} (group reference) is invalid in plain-text mode
        window._ui.radPlainText.setChecked(True)
        window._ui.cmbPatternDest.setCurrentText("{1}")
        assert window._validate_replace_input() is False
        assert window._ui.cmbPatternDest.lineEdit().styleSheet() != ""


# ---------------------------------------------------------------------------
# Signal handlers  (lines 362-379)
# ---------------------------------------------------------------------------


class TestSignalHandlers:
    def test_on_search_text_changed_no_auto(self, window):
        window._ui.chkAutoPreview.setChecked(False)
        window._ui.cmbPatternSearch.setCurrentText("test")
        # no crash, timer not started

    def test_on_search_text_changed_with_auto(self, window):
        window._ui.chkAutoPreview.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("test")
        assert window._preview_timer.isActive()
        window._preview_timer.stop()
        window._ui.chkAutoPreview.setChecked(False)

    def test_on_replace_text_changed_no_auto(self, window):
        window._ui.chkAutoPreview.setChecked(False)
        window._ui.cmbPatternDest.setCurrentText("{0}")

    def test_on_replace_text_changed_with_auto(self, window):
        window._ui.chkAutoPreview.setChecked(True)
        window._ui.cmbPatternDest.setCurrentText("{0}")
        assert window._preview_timer.isActive()
        window._preview_timer.stop()
        window._ui.chkAutoPreview.setChecked(False)

    def test_on_mode_changed_no_auto(self, window):
        window._ui.chkAutoPreview.setChecked(False)
        window._ui.radRegex.setChecked(True)
        window._on_mode_changed()

    def test_on_mode_changed_with_auto(self, window, monkeypatch):
        window._ui.chkAutoPreview.setChecked(True)
        called = []
        monkeypatch.setattr(window, "_on_preview", lambda: called.append(1))
        window._on_mode_changed()
        assert called
        window._ui.chkAutoPreview.setChecked(False)


# ---------------------------------------------------------------------------
# _update_search_add_button / _update_replace_add_button  (lines 385-413)
# ---------------------------------------------------------------------------


class TestUpdateAddButtons:
    def test_search_empty_pattern_disabled(self, window):
        window._ui.cmbPatternSearch.setCurrentText("")
        window._update_search_add_button()
        assert not window._ui.btnSearchAdd.isEnabled()

    def test_search_invalid_regex_disabled(self, window):
        window._ui.radRegex.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("[invalid")
        window._update_search_add_button()
        assert not window._ui.btnSearchAdd.isEnabled()

    def test_search_already_in_combo_disabled(self, window):
        window._ui.radPattern.setChecked(True)
        window._ui.cmbPatternSearch.addItem("existing", "pattern")
        window._ui.cmbPatternSearch.setCurrentText("existing")
        window._update_search_add_button()
        assert not window._ui.btnSearchAdd.isEnabled()

    def test_search_new_pattern_enabled(self, window):
        window._ui.radPattern.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("brand_new_xyz_pattern")
        window._update_search_add_button()
        assert window._ui.btnSearchAdd.isEnabled()

    def test_replace_empty_disabled(self, window):
        window._ui.cmbPatternDest.setCurrentText("")
        window._update_replace_add_button()
        assert not window._ui.btnReplaceAdd.isEnabled()

    def test_replace_invalid_syntax_disabled(self, window):
        window._ui.cmbPatternDest.setCurrentText("{bad{")
        window._update_replace_add_button()
        assert not window._ui.btnReplaceAdd.isEnabled()

    def test_replace_already_in_combo_disabled(self, window):
        window._ui.cmbPatternDest.addItem("existing_repl")
        window._ui.cmbPatternDest.setCurrentText("existing_repl")
        window._update_replace_add_button()
        assert not window._ui.btnReplaceAdd.isEnabled()

    def test_replace_new_pattern_enabled(self, window):
        window._ui.cmbPatternDest.setCurrentText("brand_new_xyz_replace")
        window._update_replace_add_button()
        assert window._ui.btnReplaceAdd.isEnabled()


# ---------------------------------------------------------------------------
# _do_rename  (lines 415-459)
# ---------------------------------------------------------------------------


class TestDoRename:
    def test_pattern_mode(self, window, tmp_path):
        path = str(tmp_path / "MyFile.txt")
        result = window._do_rename(False, False, "MyFile", path, "{L}", "kept", 1)
        assert result[0] == "kept"

    def test_regex_mode(self, window, tmp_path):
        path = str(tmp_path / "old.txt")
        result = window._do_rename(True, False, "old", path, "old", "new", 1)
        assert result[0] == "new"

    def test_plain_mode(self, window, tmp_path):
        path = str(tmp_path / "old.txt")
        result = window._do_rename(False, True, "old", path, "old", "new", 1)
        assert result[0] == "new"

    def test_no_match_returns_none(self, window, tmp_path):
        path = str(tmp_path / "file.txt")
        result = window._do_rename(False, False, "file", path, "nomatch{#}", "x", 1)
        assert result == (None, None)


# ---------------------------------------------------------------------------
# _apply_postproc  (lines 461-473)
# ---------------------------------------------------------------------------


class TestApplyPostproc:
    def test_no_processing(self, window, tmp_path):
        window._ui.cmbSpaces.setCurrentIndex(0)
        window._ui.chkRemoveAccents.setChecked(False)
        window._ui.chkRemoveDuplicates.setChecked(False)
        window._ui.cmbCaps.setCurrentIndex(0)
        assert (
            window._apply_postproc("file name", str(tmp_path / "file name"))
            == "file name"
        )

    def test_space_replacement(self, window, tmp_path):
        window._ui.cmbSpaces.setCurrentIndex(1)  # index 1 = mode 0 = space→underscore
        result = window._apply_postproc("file name", str(tmp_path / "file name"))
        assert result == "file_name"
        window._ui.cmbSpaces.setCurrentIndex(0)

    def test_remove_accents(self, window, tmp_path):
        window._ui.chkRemoveAccents.setChecked(True)
        result = window._apply_postproc("café", str(tmp_path / "café"))
        assert result == "cafe"
        window._ui.chkRemoveAccents.setChecked(False)

    def test_remove_duplicates(self, window, tmp_path):
        window._ui.chkRemoveDuplicates.setChecked(True)
        result = window._apply_postproc("file..txt", str(tmp_path / "file..txt"))
        assert result == "file.txt"
        window._ui.chkRemoveDuplicates.setChecked(False)

    def test_capitalize(self, window, tmp_path):
        window._ui.cmbCaps.setCurrentIndex(1)  # index 1 = mode 0 = UPPERCASE
        result = window._apply_postproc("hello", str(tmp_path / "hello"))
        assert result == "HELLO"
        window._ui.cmbCaps.setCurrentIndex(0)


# ---------------------------------------------------------------------------
# _make_newnum_state  (lines 475-490)
# ---------------------------------------------------------------------------


class TestMakeNewnumState:
    def test_no_newnum_token(self, window):
        assert window._make_newnum_state("{0}") is None

    def test_plain_literal_no_token(self, window):
        assert window._make_newnum_state("prefix") is None

    def test_with_newnum_default_start(self, window):
        state = window._make_newnum_state("{newnum}")
        assert state is not None
        assert state.current == 1

    def test_with_newnum_custom_start(self, window):
        # {newnum::5} → default="5" → start=5
        state = window._make_newnum_state("{newnum::5}")
        assert state is not None
        assert state.current == 5

    def test_with_newnum_invalid_start_falls_back(self, window):
        # {newnum::abc} → int("abc") raises ValueError → start=1
        state = window._make_newnum_state("{newnum::abc}")
        assert state is not None
        assert state.current == 1

    def test_syntax_error_returns_none(self, window):
        assert window._make_newnum_state("{bad{") is None


# ---------------------------------------------------------------------------
# _on_clear_preview  (lines 666-670)
# ---------------------------------------------------------------------------


class TestOnClearPreview:
    def test_clears_column_and_disables_button(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        item = window._ui.tblFiles.topLevelItem(0)
        item.setText(1, "preview")
        window._ui.btnRename.setEnabled(True)
        window._on_clear_preview()
        assert not window._ui.btnRename.isEnabled()
        assert item.text(1) == ""

    def test_noop_when_empty(self, window):
        window._on_clear_preview()  # no crash when no items


# ---------------------------------------------------------------------------
# Pattern help dialogs  (lines 674-702)
# ---------------------------------------------------------------------------


class TestPatternHelp:
    def test_search_help_created_on_first_call(self, window):
        window._on_search_help()
        assert window._search_help is not None

    def test_search_help_raised_if_visible(self, window, monkeypatch):
        window._on_search_help()
        dlg = window._search_help
        monkeypatch.setattr(dlg, "isVisible", lambda: True)
        raised = []
        monkeypatch.setattr(dlg, "raise_", lambda: raised.append(1))
        window._on_search_help()
        assert raised

    def test_search_help_shown_if_hidden(self, window, monkeypatch):
        window._on_search_help()
        dlg = window._search_help
        monkeypatch.setattr(dlg, "isVisible", lambda: False)
        shown = []
        monkeypatch.setattr(dlg, "show", lambda: shown.append(1))
        window._on_search_help()
        assert shown

    def test_replace_help_created_on_first_call(self, window):
        window._on_replace_help()
        assert window._replace_help is not None

    def test_replace_help_raised_if_visible(self, window, monkeypatch):
        window._on_replace_help()
        dlg = window._replace_help
        monkeypatch.setattr(dlg, "isVisible", lambda: True)
        raised = []
        monkeypatch.setattr(dlg, "raise_", lambda: raised.append(1))
        window._on_replace_help()
        assert raised


# ---------------------------------------------------------------------------
# Post-process changed / current search mode  (lines 706-716)
# ---------------------------------------------------------------------------


class TestPostProcessAndMode:
    def test_post_process_no_auto(self, window):
        window._ui.chkAutoPreview.setChecked(False)
        window._on_post_process_changed()  # no crash

    def test_post_process_with_auto(self, window, monkeypatch):
        window._ui.chkAutoPreview.setChecked(True)
        called = []
        monkeypatch.setattr(window, "_on_preview", lambda: called.append(1))
        window._on_post_process_changed()
        assert called
        window._ui.chkAutoPreview.setChecked(False)

    def test_current_mode_regex(self, window):
        window._ui.radRegex.setChecked(True)
        assert window._current_search_mode() == "regex"

    def test_current_mode_plain(self, window):
        window._ui.radPlainText.setChecked(True)
        assert window._current_search_mode() == "plain"

    def test_current_mode_pattern(self, window):
        window._ui.radPattern.setChecked(True)
        assert window._current_search_mode() == "pattern"


# ---------------------------------------------------------------------------
# Pattern history add / preset selection  (lines 719-761)
# ---------------------------------------------------------------------------


class TestPatternHistory:
    def test_on_add_search(self, window):
        window._ui.radPattern.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("unique_test_pattern_xyz")
        window._on_add_search()
        assert window._ui.cmbPatternSearch.itemText(0) == "unique_test_pattern_xyz"

    def test_on_add_search_empty_noop(self, window):
        count_before = window._ui.cmbPatternSearch.count()
        window._ui.cmbPatternSearch.setCurrentText("")
        window._on_add_search()
        assert window._ui.cmbPatternSearch.count() == count_before

    def test_on_add_replace(self, window):
        window._ui.cmbPatternDest.setCurrentText("unique_replace_xyz")
        window._on_add_replace()
        assert window._ui.cmbPatternDest.itemText(0) == "unique_replace_xyz"

    def test_on_add_replace_empty_noop(self, window):
        count_before = window._ui.cmbPatternDest.count()
        window._ui.cmbPatternDest.setCurrentText("")
        window._on_add_replace()
        assert window._ui.cmbPatternDest.count() == count_before

    def test_on_search_preset_selected_negative_noop(self, window):
        window._on_search_preset_selected(-1)  # no crash

    def test_on_search_preset_selected_regex(self, window):
        window._ui.cmbPatternSearch.addItem("^test$", "regex")
        idx = window._ui.cmbPatternSearch.count() - 1
        window._on_search_preset_selected(idx)
        assert window._ui.radRegex.isChecked()

    def test_on_search_preset_selected_plain(self, window):
        window._ui.cmbPatternSearch.addItem("hello", "plain")
        idx = window._ui.cmbPatternSearch.count() - 1
        window._on_search_preset_selected(idx)
        assert window._ui.radPlainText.isChecked()

    def test_on_search_preset_selected_pattern(self, window):
        window._ui.cmbPatternSearch.addItem("{L}", "pattern")
        idx = window._ui.cmbPatternSearch.count() - 1
        window._on_search_preset_selected(idx)
        assert window._ui.radPattern.isChecked()

    def test_on_search_preset_selected_unknown_mode_noop(self, window):
        window._ui.cmbPatternSearch.addItem("test", "unknown_mode")
        idx = window._ui.cmbPatternSearch.count() - 1
        window._on_search_preset_selected(idx)  # no crash

    def test_on_replace_preset_selected_negative_noop(self, window):
        window._on_replace_preset_selected(-1)  # no crash

    def test_on_replace_preset_selected(self, window):
        window._ui.cmbPatternDest.addItem("my_replace")
        idx = window._ui.cmbPatternDest.count() - 1
        window._on_replace_preset_selected(idx)
        assert window._ui.cmbPatternDest.currentIndex() == 0

    def test_on_replace_preset_selected_empty_noop(self, window):
        window._ui.cmbPatternDest.addItem("")
        idx = window._ui.cmbPatternDest.count() - 1
        window._on_replace_preset_selected(idx)  # no crash


# ---------------------------------------------------------------------------
# Named saves  (lines 765-855)
# ---------------------------------------------------------------------------


class TestNamedSaves:
    def test_populate_named_saves_empty(self, window):
        window._populate_named_saves()  # no crash

    def test_populate_named_saves_with_entries(self, window):
        window._presets.set_save("preset_a", {"search_pattern": "x"})
        window._populate_named_saves()
        texts = [
            window._ui.cmbNamedSaves.itemText(i)
            for i in range(window._ui.cmbNamedSaves.count())
        ]
        assert "preset_a" in texts

    def test_update_save_buttons_empty_name(self, window):
        window._ui.cmbNamedSaves.setCurrentText("")
        window._update_save_buttons()
        assert not window._ui.btnSaveSave.isEnabled()
        assert not window._ui.btnSaveDelete.isEnabled()

    def test_update_save_buttons_invalid_name(self, window):
        window._ui.cmbNamedSaves.setCurrentText("invalid name!")
        window._update_save_buttons()
        assert not window._ui.btnSaveSave.isEnabled()

    def test_update_save_buttons_valid_new_name(self, window):
        window._ui.cmbNamedSaves.setCurrentText("valid_name")
        window._update_save_buttons()
        assert window._ui.btnSaveSave.isEnabled()
        assert not window._ui.btnSaveDelete.isEnabled()

    def test_update_save_buttons_existing_name(self, window):
        window._presets.set_save("exists", {"search_pattern": "x"})
        window._populate_named_saves()
        window._ui.cmbNamedSaves.setCurrentText("exists")
        window._update_save_buttons()
        assert window._ui.btnSaveDelete.isEnabled()

    def test_on_save_name_changed(self, window):
        window._ui.cmbNamedSaves.setCurrentText("test")
        window._on_save_name_changed()  # no crash

    def test_on_named_save_selected_negative_noop(self, window):
        window._on_named_save_selected(-1)  # no crash

    def test_on_named_save_selected_missing_noop(self, window):
        window._ui.cmbNamedSaves.addItem("ghost")
        window._on_named_save_selected(window._ui.cmbNamedSaves.count() - 1)

    def test_on_named_save_selected_applies_config(self, window):
        window._presets.set_save(
            "saved", {"search_pattern": "hello", "search_mode": "plain"}
        )
        window._populate_named_saves()
        idx = next(
            i
            for i in range(window._ui.cmbNamedSaves.count())
            if window._ui.cmbNamedSaves.itemText(i) == "saved"
        )
        window._on_named_save_selected(idx)
        assert window._ui.cmbPatternSearch.currentText() == "hello"
        assert window._ui.radPlainText.isChecked()

    def test_collect_save_config_keys(self, window):
        cfg = window._collect_save_config()
        for key in (
            "search_pattern",
            "replace_pattern",
            "search_mode",
            "case_insensitive",
        ):
            assert key in cfg

    def test_collect_save_config_with_filter(self, window):
        window._ui.edtFilter.setText("*.jpg")
        cfg = window._collect_save_config()
        assert cfg.get("filter") == "*.jpg"
        window._ui.edtFilter.setText("")

    def test_collect_save_config_no_filter_when_empty(self, window):
        window._ui.edtFilter.setText("")
        cfg = window._collect_save_config()
        assert "filter" not in cfg

    def test_apply_save_config_regex(self, window):
        window._apply_save_config({"search_mode": "regex"})
        assert window._ui.radRegex.isChecked()

    def test_apply_save_config_plain(self, window):
        window._apply_save_config({"search_mode": "plain"})
        assert window._ui.radPlainText.isChecked()

    def test_apply_save_config_pattern(self, window):
        window._apply_save_config({"search_mode": "pattern"})
        assert window._ui.radPattern.isChecked()

    def test_apply_save_config_full(self, window):
        cfg = {
            "search_pattern": "hello",
            "search_mode": "plain",
            "case_insensitive": True,
            "replace_pattern": "{0}",
            "separator": 1,
            "remove_accents": True,
            "remove_duplicates": True,
            "case": 1,
            "keep_extension": True,
        }
        window._apply_save_config(cfg)
        assert window._ui.cmbPatternSearch.currentText() == "hello"
        assert window._ui.chkCaseInsensitive.isChecked()
        assert window._ui.chkRemoveAccents.isChecked()
        assert window._ui.chkRemoveDuplicates.isChecked()
        assert window._ui.chkKeepExtension.isChecked()
        assert window._ui.cmbSpaces.currentIndex() == 1
        assert window._ui.cmbCaps.currentIndex() == 1

    def test_apply_save_config_filter_triggers_reload(
        self, window, tmp_path, monkeypatch
    ):
        window._current_dir = str(tmp_path)
        called = []
        monkeypatch.setattr(window, "_reload_files", lambda: called.append(1))
        window._apply_save_config({"filter": "*.txt"})
        assert called

    def test_apply_save_config_filter_unchanged_no_reload(
        self, window, tmp_path, monkeypatch
    ):
        window._current_dir = str(tmp_path)
        window._ui.edtFilter.setText("*.txt")
        called = []
        monkeypatch.setattr(window, "_reload_files", lambda: called.append(1))
        window._apply_save_config({"filter": "*.txt"})
        assert not called

    def test_on_save_save(self, window):
        window._ui.cmbNamedSaves.setCurrentText("mypreset")
        window._on_save_save()
        assert "mypreset" in window._presets.get_saves()

    def test_on_save_save_invalid_name_noop(self, window):
        window._ui.cmbNamedSaves.setCurrentText("invalid!")
        window._on_save_save()  # no crash

    def test_on_save_delete(self, window):
        window._presets.set_save("to_del", {"search_pattern": "x"})
        window._populate_named_saves()
        window._ui.cmbNamedSaves.setCurrentText("to_del")
        window._on_save_delete()
        assert "to_del" not in window._presets.get_saves()

    def test_on_save_delete_missing_noop(self, window):
        window._ui.cmbNamedSaves.setCurrentText("ghost")
        window._on_save_delete()  # no crash


# ---------------------------------------------------------------------------
# Rename / Undo  (lines 859-915)
# ---------------------------------------------------------------------------


class TestRenameUndo:
    def test_on_rename_with_selection_uses_selection(self, window, tmp_path):
        # Line 315: _active_items() returns selected items when a selection exists.
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / "b.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        # Select only the first item
        item0 = window._ui.tblFiles.topLevelItem(0)
        item1 = window._ui.tblFiles.topLevelItem(1)
        window._ui.tblFiles.setCurrentItem(item0)
        item0.setSelected(True)
        item1.setSelected(False)
        assert len(window._active_items()) == 1
        assert window._active_items()[0] is item0

    def test_on_rename_no_preview_noop(self, window, tmp_path):
        (tmp_path / "file.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._on_rename()  # all items have empty preview → early return

    def test_on_rename_same_name_noop(self, window, tmp_path):
        (tmp_path / "file.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        item = window._ui.tblFiles.topLevelItem(0)
        item.setText(1, "file.txt")  # same name → no rename needed
        window._on_rename()

    def test_on_rename_success(self, window, tmp_path):
        f = tmp_path / "original.txt"
        f.write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        item = _find_item(window, str(f))
        assert item is not None
        item.setText(1, "renamed.txt")
        window._on_rename()
        assert (tmp_path / "renamed.txt").exists()
        assert not (tmp_path / "original.txt").exists()

    def test_on_rename_adds_to_undo(self, window, tmp_path):
        f = tmp_path / "orig.txt"
        f.write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        item = _find_item(window, str(f))
        item.setText(1, "new.txt")
        assert len(window._undo) == 0
        window._on_rename()
        assert len(window._undo) == 1

    def test_on_rename_error_shows_warning(self, window, tmp_path, monkeypatch):
        (tmp_path / "source.txt").write_text("x")
        (tmp_path / "conflict.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        item = _find_item(window, str(tmp_path / "source.txt"))
        assert item is not None
        item.setText(1, "conflict.txt")
        with patch.object(QMessageBox, "warning", return_value=None) as mock_warn:
            window._on_rename()
        mock_warn.assert_called_once()
        assert (tmp_path / "source.txt").exists()

    def test_on_undo(self, window, tmp_path, monkeypatch):
        window._current_dir = str(tmp_path)
        called = []
        monkeypatch.setattr(window._undo, "undo", lambda: called.append(1))
        window._on_undo()
        assert called

    def test_refresh_undo_button_empty(self, window):
        window._refresh_undo_button()
        assert not window._ui.btnUndo.isEnabled()

    def test_refresh_undo_button_with_entry(self, window, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("x")
        f1.rename(f2)
        window._undo.add_batch([(str(f1), str(f2))])
        window._refresh_undo_button()
        assert window._ui.btnUndo.isEnabled()
        assert "1" in window._ui.btnUndo.text()

    def test_refresh_undo_button_multiple(self, window, tmp_path):
        for i in range(3):
            f = tmp_path / f"f{i}.txt"
            f.write_text("x")
            window._undo.add_batch([(str(f), str(tmp_path / f"g{i}.txt"))])
        window._refresh_undo_button()
        assert "3" in window._ui.btnUndo.text()


# ---------------------------------------------------------------------------
# Window / toolbar state  (lines 919-964)
# ---------------------------------------------------------------------------


class TestWindowState:
    def test_restore_window_state_no_saved_state(self, window):
        window._restore_window_state()  # no crash when nothing saved

    def test_close_event_saves_last_dir(self, window, tmp_path):
        window._current_dir = str(tmp_path)
        window.close()
        assert get_last_dir() == str(tmp_path)

    def test_close_event_no_dir_does_not_crash(self, window):
        window._current_dir = None
        window.close()  # no crash

    def test_close_event_saves_toolbar_when_enabled(self, window):
        set_restore_toolbar_state(True)
        window._ui.cmbMode.setCurrentIndex(1)
        window.close()
        state = get_toolbar_state()
        assert state.get("mode") == 1

    def test_collect_toolbar_state_keys(self, window):
        state = window._collect_toolbar_state()
        for key in ("mode", "recursive", "keep_extension", "auto_preview", "filter"):
            assert key in state

    def test_restore_toolbar_state_empty(self, window):
        window._restore_toolbar_state()  # no crash with empty state

    def test_restore_toolbar_state_full(self, window):
        set_toolbar_state(
            {
                "mode": 1,
                "recursive": True,
                "keep_extension": True,
                "auto_preview": False,
                "filter": "*.jpg",
            }
        )
        window._restore_toolbar_state()
        assert window._ui.cmbMode.currentIndex() == 1
        assert window._ui.chkRecursive.isChecked()
        assert window._ui.chkKeepExtension.isChecked()
        assert window._ui.edtFilter.text() == "*.jpg"
        # restore defaults
        window._ui.cmbMode.setCurrentIndex(0)
        window._ui.chkRecursive.setChecked(False)
        window._ui.edtFilter.setText("")

    def test_restore_toolbar_state_invalid_mode_ignored(self, window):
        set_toolbar_state({"mode": 999})
        window._restore_toolbar_state()  # out-of-range index → not set


# ---------------------------------------------------------------------------
# Auto-preview toggle  (lines 968-972)
# ---------------------------------------------------------------------------


class TestAutoPreviewToggle:
    def test_toggled_on_calls_preview(self, window, monkeypatch):
        called = []
        monkeypatch.setattr(window, "_on_preview", lambda: called.append(1))
        window._on_auto_preview_toggled(True)
        assert called

    def test_toggled_off_stops_timer(self, window):
        window._preview_timer.start(10000)
        window._on_auto_preview_toggled(False)
        assert not window._preview_timer.isActive()


# ---------------------------------------------------------------------------
# Menu handlers  (lines 976-987)
# ---------------------------------------------------------------------------


class TestMenuHandlers:
    def test_on_quit(self, window, monkeypatch):
        called = []
        monkeypatch.setattr(
            QApplication, "quit", staticmethod(lambda: called.append(1))
        )
        window._on_quit()
        assert called

    def test_on_history(self, window, monkeypatch):
        from pbrenamer.ui.history_dialog import HistoryDialog

        monkeypatch.setattr(HistoryDialog, "exec", lambda self: 0)
        window._on_history()

    def test_on_settings(self, window, monkeypatch):
        from pbrenamer.ui.settings_dialog import SettingsDialog

        monkeypatch.setattr(SettingsDialog, "exec", lambda self: 0)
        window._on_settings()

    def test_on_about(self, window, monkeypatch):
        from pbrenamer.ui.about_dialog import AboutDialog

        monkeypatch.setattr(AboutDialog, "exec", lambda self: 0)
        window._on_about()


# ---------------------------------------------------------------------------
# Shortcuts menu  (lines 991-1041)
# ---------------------------------------------------------------------------


class TestShortcutsMenu:
    def test_build_shortcuts_menu_empty(self, window, monkeypatch):
        monkeypatch.setattr("pbrenamer.ui.main_window.system_bookmarks", lambda: [])
        window._build_shortcuts_menu()
        # Should have at least the separator + edit shortcuts action
        menu = window._ui.menuShortcuts
        assert any(a is window._ui.actionEditShortcuts for a in menu.actions())

    def test_build_shortcuts_menu_with_entries(self, window, monkeypatch):
        home = os.path.expanduser("~")
        monkeypatch.setattr("pbrenamer.ui.main_window.system_bookmarks", lambda: [])
        set_shortcuts([("Home", home)])
        window._build_shortcuts_menu()
        menu = window._ui.menuShortcuts
        tips = [a.statusTip() for a in menu.actions() if not a.isSeparator()]
        assert home in tips

    def test_build_shortcuts_menu_with_sys_bookmarks(self, window, monkeypatch):
        home = os.path.expanduser("~")
        monkeypatch.setattr(
            "pbrenamer.ui.main_window.system_bookmarks", lambda: [("Home", home)]
        )
        window._build_shortcuts_menu()
        menu = window._ui.menuShortcuts
        tips = [a.statusTip() for a in menu.actions() if not a.isSeparator()]
        assert home in tips

    def test_on_shortcut_valid_dir(self, window, tmp_path, monkeypatch):
        called = []
        monkeypatch.setattr(window, "_reload_files", lambda: called.append(1))
        window._on_shortcut(str(tmp_path))
        assert window._current_dir == str(tmp_path)
        assert called

    def test_on_shortcut_nonexistent_noop(self, window):
        original = window._current_dir
        window._on_shortcut("/nonexistent/xyz/abc")
        assert window._current_dir == original

    def test_on_tree_context_menu_early_return(self, window, monkeypatch):
        # Line 1023: path is not a directory → early return before menu is shown.
        from PySide6.QtCore import QModelIndex, QPoint

        monkeypatch.setattr(
            window._ui.treeDirectory, "indexAt", lambda pos: QModelIndex()
        )
        window._current_dir = "/nonexistent/not_a_dir_xyz"
        window._on_tree_context_menu(QPoint(0, 0))  # early return, no menu

    def test_on_tree_context_menu_no_current_dir(self, window):
        window._current_dir = None
        window._on_tree_context_menu(window._ui.treeDirectory.pos())

    def test_on_tree_context_menu_shows_menu(self, window, tmp_path):
        window._current_dir = str(tmp_path)
        window._on_tree_context_menu(window._ui.treeDirectory.pos())

    def test_on_tree_context_menu_add_chosen(
        self, window, tmp_path, mock_qmenu, monkeypatch
    ):
        # Simulate the user choosing "Add as shortcut": exec returns the action
        # so that (chosen is add_action) is True → _add_shortcut is called.
        mock_qmenu.exec.return_value = mock_qmenu.addAction.return_value
        window._current_dir = str(tmp_path)
        called = []
        monkeypatch.setattr(window, "_add_shortcut", lambda path: called.append(path))
        window._on_tree_context_menu(window._ui.treeDirectory.pos())
        assert called

    def test_add_shortcut(self, window, tmp_path):
        window._add_shortcut(str(tmp_path))
        assert any(p == str(tmp_path) for _, p in get_shortcuts())

    def test_add_shortcut_duplicate_noop(self, window, tmp_path):
        window._add_shortcut(str(tmp_path))
        window._add_shortcut(str(tmp_path))
        assert sum(1 for _, p in get_shortcuts() if p == str(tmp_path)) == 1

    def test_add_shortcut_root_uses_path(self, window):
        # os.path.basename("/") = "" → name falls back to path itself
        window._add_shortcut("/")
        assert any(p == "/" for _, p in get_shortcuts())

    def test_on_edit_shortcuts(self, window, monkeypatch):
        from pbrenamer.ui.shortcuts_dialog import ShortcutsDialog

        monkeypatch.setattr(ShortcutsDialog, "exec", lambda self: 0)
        window._on_edit_shortcuts()


# ---------------------------------------------------------------------------
# File info window  (lines 1045-1080)
# ---------------------------------------------------------------------------


class TestFileInfoWindow:
    def test_on_file_info_creates_window(self, window):
        window._on_file_info()
        assert window._file_info is not None

    def test_on_file_info_reuses_existing(self, window):
        window._on_file_info()
        first = window._file_info
        window._on_file_info()
        assert window._file_info is first

    def test_on_file_selection_changed_no_info(self, window):
        assert window._file_info is None
        window._on_file_selection_changed()  # no crash

    def test_on_file_selection_changed_hidden_no_refresh(self, window, monkeypatch):
        window._on_file_info()
        window._file_info.hide()
        called = []
        monkeypatch.setattr(window, "_refresh_file_info", lambda: called.append(1))
        window._on_file_selection_changed()
        assert not called

    def test_on_file_selection_changed_visible_refreshes(self, window, monkeypatch):
        window._on_file_info()
        monkeypatch.setattr(window._file_info, "isVisible", lambda: True)
        called = []
        monkeypatch.setattr(window, "_refresh_file_info", lambda: called.append(1))
        window._on_file_selection_changed()
        assert called

    def test_refresh_file_info_no_window_noop(self, window):
        window._refresh_file_info()  # no crash

    def test_refresh_file_info_no_selection(self, window, tmp_path):
        (tmp_path / "f.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._on_file_info()
        window._ui.tblFiles.clearSelection()
        window._refresh_file_info()

    def test_refresh_file_info_single_selection(self, window, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._on_file_info()
        window._ui.tblFiles.setCurrentItem(window._ui.tblFiles.topLevelItem(0))
        window._refresh_file_info()

    def test_refresh_file_info_multi_selection(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / "b.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._on_file_info()
        from PySide6.QtWidgets import QAbstractItemView

        window._ui.tblFiles.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        for i in range(window._ui.tblFiles.topLevelItemCount()):
            window._ui.tblFiles.topLevelItem(i).setSelected(True)
        window._refresh_file_info()
        window._ui.tblFiles.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

    def test_on_file_double_clicked(self, window, tmp_path, monkeypatch):
        from PySide6.QtGui import QDesktopServices

        f = tmp_path / "file.txt"
        f.write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        item = window._ui.tblFiles.topLevelItem(0)
        called = []
        monkeypatch.setattr(
            QDesktopServices, "openUrl", staticmethod(lambda url: called.append(url))
        )
        window._on_file_double_clicked(item)
        assert called

    def test_refresh_file_info_item_without_path(self, window, tmp_path):
        # Line 1068: selected item exists but its UserRole data is None/empty
        # → show_empty() is called.
        window._on_file_info()
        window._current_dir = str(tmp_path)
        window._reload_files()
        # Manually add an item whose UserRole data is None
        from PySide6.QtWidgets import QTreeWidgetItem

        ghost_item = QTreeWidgetItem(["ghost", ""])
        ghost_item.setData(0, Qt.ItemDataRole.UserRole, None)
        window._ui.tblFiles.addTopLevelItem(ghost_item)
        window._ui.tblFiles.setCurrentItem(ghost_item)
        window._refresh_file_info()  # path is None → show_empty()

    def test_on_files_context_menu(self, window):
        window._on_files_context_menu(window._ui.tblFiles.pos())


# ---------------------------------------------------------------------------
# Helpers shared by TestOnPreview and TestRefreshConflicts
# ---------------------------------------------------------------------------


def _set_preview(item, text: str, is_error: bool = False) -> None:
    """Set the preview column text and error flag on a tblFiles item."""
    item.setText(1, text)
    item.setData(1, Qt.ItemDataRole.UserRole, is_error)


def _item_color(item) -> str:
    """Return the hex color of the preview column foreground brush."""
    return item.foreground(1).color().name()


# ---------------------------------------------------------------------------
# _on_preview  (lines 492-606)
# ---------------------------------------------------------------------------


class TestOnPreview:
    # ── Early-return guards ──────────────────────────────────────────────────

    def test_guard_no_current_dir(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        window._current_dir = None
        window._ui.cmbPatternSearch.setCurrentText("a")
        window._on_preview()  # returns before accessing tblFiles

    def test_guard_no_search(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._ui.cmbPatternSearch.setCurrentText("")
        window._on_preview()
        assert window._ui.tblFiles.topLevelItem(0).text(1) == ""

    def test_guard_invalid_regex(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._ui.radRegex.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("[invalid")
        window._ui.cmbPatternDest.setCurrentText("x")
        window._on_preview()  # _validate_search_input returns False → return
        assert window._ui.tblFiles.topLevelItem(0).text(1) == ""

    def test_guard_invalid_replace(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._ui.radPattern.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("{L}")
        window._ui.cmbPatternDest.setCurrentText("{bad{")
        window._on_preview()  # _validate_replace_input returns False → return
        assert window._ui.tblFiles.topLevelItem(0).text(1) == ""

    # ── Non-newnum branch ────────────────────────────────────────────────────

    def test_plain_rename_no_match_empty_preview(self, window, tmp_path):
        (tmp_path / "hello.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._ui.radPlainText.setChecked(True)
        window._ui.chkKeepExtension.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("nomatch")
        window._ui.cmbPatternDest.setCurrentText("world")
        window._on_preview()
        assert window._ui.tblFiles.topLevelItem(0).text(1) == ""

    def test_plain_rename_success_no_keep_ext(self, window, tmp_path):
        (tmp_path / "hello.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._ui.radPlainText.setChecked(True)
        window._ui.chkKeepExtension.setChecked(False)
        window._ui.cmbPatternSearch.setCurrentText("hello.txt")
        window._ui.cmbPatternDest.setCurrentText("world.txt")
        window._on_preview()
        assert window._ui.tblFiles.topLevelItem(0).text(1) == "world.txt"

    def test_plain_rename_success_keep_ext(self, window, tmp_path):
        (tmp_path / "hello.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._ui.radPlainText.setChecked(True)
        window._ui.chkKeepExtension.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("hello")
        window._ui.cmbPatternDest.setCurrentText("world")
        window._on_preview()
        assert window._ui.tblFiles.topLevelItem(0).text(1) == "world.txt"

    def test_field_error_non_newnum(self, window, tmp_path, monkeypatch):
        (tmp_path / "file.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._ui.radPattern.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("{L}")
        window._ui.cmbPatternDest.setCurrentText("{0}")

        def _raise(*a, **kw):
            raise _repl.FieldResolutionError("artist")

        monkeypatch.setattr(window, "_do_rename", _raise)
        window._on_preview()
        item = window._ui.tblFiles.topLevelItem(0)
        assert "artist" in item.text(1)
        # The error flag is set so _refresh_conflicts colours it
        assert item.data(1, Qt.ItemDataRole.UserRole) is True

    # ── newnum branch ────────────────────────────────────────────────────────

    def test_newnum_basic(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._ui.radPattern.setChecked(True)
        window._ui.chkKeepExtension.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("{L}")
        window._ui.cmbPatternDest.setCurrentText("{newnum}")
        window._on_preview()
        assert window._ui.tblFiles.topLevelItem(0).text(1) == "1.txt"

    def test_newnum_raw_is_none(self, window, tmp_path, monkeypatch):
        # _do_rename returns (None, None) inside the newnum loop → break → no preview
        (tmp_path / "file.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._ui.radPattern.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("{L}")
        window._ui.cmbPatternDest.setCurrentText("{newnum}")
        monkeypatch.setattr(window, "_do_rename", lambda *a, **kw: (None, None))
        window._on_preview()
        assert window._ui.tblFiles.topLevelItem(0).text(1) == ""

    def test_newnum_collision_loop(self, window, tmp_path):
        # "1.txt" already exists on disk → a.txt's first candidate ("1.txt") collides →
        # loop increments k → a.txt gets "2.txt"
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / "1.txt").write_text("existing")
        window._current_dir = str(tmp_path)
        window._reload_files()
        item_a = _find_item(window, str(tmp_path / "a.txt"))
        item_1 = _find_item(window, str(tmp_path / "1.txt"))
        # Select only a.txt so 1.txt is not in active_items
        window._ui.tblFiles.clearSelection()
        item_a.setSelected(True)
        window._ui.radPattern.setChecked(True)
        window._ui.chkKeepExtension.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("{L}")
        window._ui.cmbPatternDest.setCurrentText("{newnum}")
        window._on_preview()
        assert item_a.text(1) == "2.txt"
        _ = item_1  # referenced to avoid lint warning

    def test_newnum_field_error(self, window, tmp_path, monkeypatch):
        (tmp_path / "file.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._ui.radPattern.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("{L}")
        window._ui.cmbPatternDest.setCurrentText("{newnum}")

        def _raise(*a, **kw):
            raise _repl.FieldResolutionError("artist")

        monkeypatch.setattr(window, "_do_rename", _raise)
        window._on_preview()
        item = window._ui.tblFiles.topLevelItem(0)
        assert "artist" in item.text(1)
        assert item.data(1, Qt.ItemDataRole.UserRole) is True

    def test_multiple_files_sequential_newnum(self, window, tmp_path):
        # Two files → 1.txt and 2.txt
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / "b.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        window._ui.radPattern.setChecked(True)
        window._ui.chkKeepExtension.setChecked(True)
        window._ui.cmbPatternSearch.setCurrentText("{L}")
        window._ui.cmbPatternDest.setCurrentText("{newnum}")
        window._on_preview()
        previews = {
            window._ui.tblFiles.topLevelItem(i).text(1)
            for i in range(window._ui.tblFiles.topLevelItemCount())
        }
        assert {"1.txt", "2.txt"} == previews


# ---------------------------------------------------------------------------
# _refresh_conflicts  (lines 608-664)
# ---------------------------------------------------------------------------


class TestRefreshConflicts:
    def test_no_previews_disables_rename(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        # Leave column 1 empty → no previews
        window._ui.btnRename.setEnabled(True)
        window._refresh_conflicts()
        assert not window._ui.btnRename.isEnabled()

    def test_all_errors_disables_rename_and_sets_error_color(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        item = window._ui.tblFiles.topLevelItem(0)
        _set_preview(item, "⚠ artist unavailable", is_error=True)
        window._ui.btnRename.setEnabled(True)
        window._refresh_conflicts()
        assert not window._ui.btnRename.isEnabled()
        assert _item_color(item) == "#cc0000"

    def test_no_conflict_enables_rename_with_preview_color(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        item = _find_item(window, str(tmp_path / "a.txt"))
        _set_preview(item, "renamed.txt")  # doesn't exist on disk → no conflict
        window._refresh_conflicts()
        assert window._ui.btnRename.isEnabled()
        assert _item_color(item) == "#0066cc"

    def test_unchanged_name_gives_unchanged_color_and_disables_rename(
        self, window, tmp_path
    ):
        (tmp_path / "a.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        item = _find_item(window, str(tmp_path / "a.txt"))
        _set_preview(item, "a.txt")  # same as original → unchanged
        window._ui.btnRename.setEnabled(True)
        window._refresh_conflicts()
        assert not window._ui.btnRename.isEnabled()
        assert _item_color(item) == "#888888"

    def test_duplicate_target_gives_conflict_color(self, window, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / "b.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        item_a = _find_item(window, str(tmp_path / "a.txt"))
        item_b = _find_item(window, str(tmp_path / "b.txt"))
        _set_preview(item_a, "same.txt")
        _set_preview(item_b, "same.txt")
        window._refresh_conflicts()
        assert not window._ui.btnRename.isEnabled()
        assert _item_color(item_a) == "#cc0000"
        assert _item_color(item_b) == "#cc0000"

    def test_existing_file_target_gives_conflict_color(self, window, tmp_path):
        # a.txt preview is b.txt, which already exists on disk and is not a.txt
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / "b.txt").write_text("existing")
        window._current_dir = str(tmp_path)
        window._reload_files()
        item_a = _find_item(window, str(tmp_path / "a.txt"))
        item_b = _find_item(window, str(tmp_path / "b.txt"))
        _set_preview(item_a, "b.txt")  # target already exists
        # b.txt has no preview → not in active set
        window._refresh_conflicts()
        assert not window._ui.btnRename.isEnabled()
        assert _item_color(item_a) == "#cc0000"
        _ = item_b

    def test_field_error_mixed_with_valid_disables_rename(self, window, tmp_path):
        # has_field_error=True blocks rename even when other items have valid previews
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / "b.txt").write_text("x")
        window._current_dir = str(tmp_path)
        window._reload_files()
        item_a = _find_item(window, str(tmp_path / "a.txt"))
        item_b = _find_item(window, str(tmp_path / "b.txt"))
        _set_preview(item_a, "⚠ artist unavailable", is_error=True)
        _set_preview(item_b, "renamed.txt")
        window._refresh_conflicts()
        assert not window._ui.btnRename.isEnabled()
        assert _item_color(item_a) == "#cc0000"  # error color
        assert _item_color(item_b) == "#0066cc"  # preview color


# ---------------------------------------------------------------------------
# showEvent / _restore_window_state / _restore_splitters / _on_field_requested
# ---------------------------------------------------------------------------


class TestWindowStateRestore:
    def test_show_event_triggers_restore(self, qtbot, monkeypatch):
        called = []
        w = MainWindow()
        qtbot.addWidget(w)
        monkeypatch.setattr(w, "_restore_window_state", lambda: called.append(True))
        w.show()
        qtbot.waitExposed(w)
        qtbot.wait(50)  # allow QTimer.singleShot(0) to fire
        assert called

    def test_show_event_only_restores_once(self, qtbot, monkeypatch):
        called = []
        w = MainWindow()
        qtbot.addWidget(w)
        monkeypatch.setattr(w, "_restore_window_state", lambda: called.append(True))
        w.show()
        qtbot.waitExposed(w)
        qtbot.wait(50)
        w.hide()
        w.show()
        qtbot.waitExposed(w)
        qtbot.wait(50)
        assert len(called) == 1

    def test_restore_window_state_no_saved_data(self, qtbot):
        w = MainWindow()
        qtbot.addWidget(w)
        ws = MagicMock()
        ws.load.return_value = (None, None, None)
        w._window_state = ws
        w._restore_window_state()  # covers "no saved geometry" branch

    def test_restore_splitters_none(self, qtbot):
        w = MainWindow()
        qtbot.addWidget(w)
        w._restore_splitters(None, None)  # covers both "no saved splitter" branches

    def test_on_field_requested_inserts_into_dest(self, window):
        w = window
        w._ui.cmbPatternDest.lineEdit().clear()
        w._on_field_requested("{X}")
        assert "{X}" in w._ui.cmbPatternDest.lineEdit().text()
