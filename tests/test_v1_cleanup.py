"""Tests for v1_cleanup — offer to delete the PBRenamer 1.x files."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from pbrenamer import migration, profiles, settings
from pbrenamer.ui import v1_cleanup
from pbrenamer.ui.v1_cleanup import offer_v1_cleanup

DATA = Path(__file__).parent / "data"
_YES = QMessageBox.StandardButton.Yes
_NO = QMessageBox.StandardButton.No


@pytest.fixture
def v1_config(config_dir):
    shutil.copytree(DATA / "pbrenamer_v1_config", config_dir, dirs_exist_ok=True)
    settings.configure(config_dir)
    return config_dir


@pytest.fixture
def migrated(v1_config):
    """1.x configuration migrated at a previous start."""
    profiles.current()
    settings.configure(v1_config)
    return v1_config


@pytest.fixture
def answer(monkeypatch):
    """Replace the question box; set ``answer.reply`` before the call."""

    class Answer:
        reply = _NO
        asked: list[str] = []
        warned: list[str] = []

    def question(parent, title, text, *args):
        Answer.asked.append(text)
        return Answer.reply

    def warning(parent, title, text, *args):
        Answer.warned.append(text)

    Answer.asked, Answer.warned = [], []
    monkeypatch.setattr(QMessageBox, "question", question)
    monkeypatch.setattr(QMessageBox, "warning", warning)
    return Answer


def test_silent_when_migrating(v1_config, answer):
    offer_v1_cleanup(None)
    assert answer.asked == []
    assert (v1_config / "sidecar_config.json").is_file()


def test_silent_without_leftovers(config_dir, answer):
    offer_v1_cleanup(None)
    assert answer.asked == []


def test_yes_deletes(migrated, answer):
    answer.reply = _YES
    offer_v1_cleanup(None)
    assert len(answer.asked) == 1
    assert str(migrated / "sidecar_config.json") in answer.asked[0]
    assert migration.v1_leftovers(migrated) == []
    assert not (migrated / migration.V1_KEEP_MARKER).exists()
    assert answer.warned == []


def test_no_keeps_and_remembers(migrated, answer):
    offer_v1_cleanup(None)
    assert (migrated / "sidecar_config.json").is_file()
    assert (migrated / migration.V1_KEEP_MARKER).is_file()
    offer_v1_cleanup(None)
    assert len(answer.asked) == 1


def test_failure_warned(migrated, answer, monkeypatch):
    answer.reply = _YES
    target = migrated / "sidecar_config.json"
    monkeypatch.setattr(
        v1_cleanup.migration, "remove_v1_leftovers", lambda home, paths: [target]
    )
    offer_v1_cleanup(None)
    assert len(answer.warned) == 1
    assert str(target) in answer.warned[0]


def test_main_window_offers(migrated, answer, qtbot):
    from pbrenamer.ui.main_window import MainWindow

    w = MainWindow()
    qtbot.addWidget(w)
    qtbot.waitUntil(lambda: answer.asked != [])
