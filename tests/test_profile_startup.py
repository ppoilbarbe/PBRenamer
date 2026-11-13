"""Tests for pbrenamer.ui.profile_startup — choice of a missing start-up profile."""

import pytest
from PySide6.QtWidgets import QInputDialog

import pbrenamer.settings as _cfg
from pbrenamer import profiles
from pbrenamer.ui.profile_startup import resolve_startup_profile


@pytest.fixture
def asked(monkeypatch):
    """Record the getItem calls; answer with ``asked.answer``."""

    class Asked(list):
        answer = ("p", True)

    calls = Asked()

    def get_item(_parent, title, label, names, index, editable):
        calls.append({"label": label, "names": names, "index": index})
        return calls.answer

    monkeypatch.setattr(QInputDialog, "getItem", get_item)
    return calls


def _restart():
    _cfg.configure(_cfg._dirs.config_home)


def test_nothing_missing(asked):
    assert resolve_startup_profile() is True
    assert asked == []


def test_missing_default_chosen(asked):
    profiles.create("p")
    profiles.create(".h")
    profiles.set_default("gone")
    _restart()
    assert resolve_startup_profile() is True
    assert asked[0]["names"] == ["default", "p"]
    assert asked[0]["index"] == 0
    assert "default profile “gone”" in asked[0]["label"]
    assert profiles.current() == "p"
    assert profiles.missing_startup() is None
    assert profiles.startup_name() == "gone"  # the setting is left alone


def test_missing_last_profile(asked):
    profiles.create("p")
    profiles.create("x")
    profiles.use("x")
    profiles.delete("default")
    root = _cfg._dirs.config_home / "profiles"
    (root / "x").rename(root / "y")
    _restart()
    assert resolve_startup_profile() is True
    assert "last profile used, “x”" in asked[0]["label"]
    assert asked[0]["names"] == ["p", "y"]
    assert profiles.current() == "p"


@pytest.mark.parametrize("answer", [("", False), ("p", False), ("", True)])
def test_cancelled(asked, answer):
    profiles.create("p")
    profiles.set_default("gone")
    _restart()
    asked.answer = answer
    assert resolve_startup_profile() is False
    assert profiles.missing_startup() == "gone"
