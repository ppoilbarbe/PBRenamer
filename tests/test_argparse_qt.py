"""Tests for src/pbrenamer/argparse_qt.py."""

import argparse

import pytest

from pbrenamer.argparse_qt import add_qt_arguments


def _make_parser():
    parser = argparse.ArgumentParser(prog="pbrenamer")
    add_qt_arguments(parser)
    return parser


def test_qt_args_default_is_empty_list():
    args = _make_parser().parse_args([])
    assert args.qt_args == []


def test_qt_args_flag_with_value():
    args = _make_parser().parse_args(["--style", "fusion"])
    assert args.qt_args == ["-style", "fusion"]


def test_qt_args_flag_without_value():
    args = _make_parser().parse_args(["--reverse"])
    assert args.qt_args == ["-reverse"]


def test_qt_args_multiple_flags_accumulate():
    args = _make_parser().parse_args(
        ["--style", "fusion", "--reverse", "--platform", "xcb"]
    )
    assert args.qt_args == ["-style", "fusion", "-reverse", "-platform", "xcb"]


def test_qt_args_unknown_flag_raises():
    with pytest.raises(SystemExit) as exc:
        _make_parser().parse_args(["--unknown-flag"])
    assert exc.value.code == 2


def test_qt_args_unknown_positional_raises():
    with pytest.raises(SystemExit) as exc:
        _make_parser().parse_args(["positional"])
    assert exc.value.code == 2
