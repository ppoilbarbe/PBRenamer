"""Tests for the headless CLI mode (--search / --saved activates no-GUI renaming)."""

import argparse
import sys

import pytest

from pbrenamer.__main__ import (
    _apply_postproc,
    _build_parser,
    _detect_conflicts,
    _headless_run,
    _plan,
    _resolve_ns,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ns(**kwargs) -> argparse.Namespace:
    """Build a Namespace with resolved headless defaults, overridable via kwargs."""
    defaults = dict(
        search="",
        replace="",
        mode="pattern",
        list="files",
        recurse=False,
        keep_ext=True,
        filter_glob=None,
        sep="none",
        accent=False,
        dup=False,
        case="none",
        confirm=False,
        directory=None,
        log_level=None,
        saved=None,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _make_files(root, *names: str) -> list[str]:
    """Touch *names* under *root* and return their full paths."""
    paths = []
    for name in names:
        p = root / name
        p.touch()
        paths.append(str(p))
    return paths


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


class TestParser:
    def test_search_default_is_none(self):
        ns, _ = _build_parser().parse_known_args([])
        assert ns.search is None

    def test_search_short_flag(self):
        ns, _ = _build_parser().parse_known_args(["-s", "foo"])
        assert ns.search == "foo"

    def test_saved_default_is_none(self):
        ns, _ = _build_parser().parse_known_args([])
        assert ns.saved is None

    def test_saved_flag(self):
        ns, _ = _build_parser().parse_known_args(["--saved", "mypreset"])
        assert ns.saved == "mypreset"

    def test_replace_short_flag(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "-r", "y"])
        assert ns.replace == "y"

    def test_replace_raw_default_is_none(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x"])
        assert ns.replace is None

    def test_mode_raw_default_is_none(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x"])
        assert ns.mode is None

    def test_mode_regex(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "--mode", "regex"])
        assert ns.mode == "regex"

    def test_mode_plain(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "--mode", "plain"])
        assert ns.mode == "plain"

    def test_list_default_files(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x"])
        assert ns.list == "files"

    def test_list_dirs(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "--list", "dirs"])
        assert ns.list == "dirs"

    def test_recurse_default_false(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x"])
        assert ns.recurse is False

    def test_recurse_flag(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "--recurse"])
        assert ns.recurse is True

    def test_no_recurse_flag(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "--no-recurse"])
        assert ns.recurse is False

    def test_keep_ext_raw_default_is_none(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x"])
        assert ns.keep_ext is None

    def test_keep_ext_flag(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "--keep-ext"])
        assert ns.keep_ext is True

    def test_no_keep_ext_flag(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "--no-keep-ext"])
        assert ns.keep_ext is False

    def test_filter_default_none(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x"])
        assert ns.filter_glob is None

    def test_filter_value(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "--filter", "*.jpg"])
        assert ns.filter_glob == "*.jpg"

    def test_accent_raw_default_is_none(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x"])
        assert ns.accent is None

    def test_accent_flag(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "--accent"])
        assert ns.accent is True

    def test_dup_raw_default_is_none(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x"])
        assert ns.dup is None

    def test_dup_flag(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "--dup"])
        assert ns.dup is True

    def test_sep_raw_default_is_none(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x"])
        assert ns.sep is None

    @pytest.mark.parametrize(
        "value",
        [
            "none",
            "space-underscore",
            "underscore-space",
            "space-dot",
            "dot-space",
            "space-dash",
            "dash-space",
        ],
    )
    def test_sep_values(self, value):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "--sep", value])
        assert ns.sep == value

    def test_sep_invalid_rejected(self):
        with pytest.raises(SystemExit):
            _build_parser().parse_args(["-s", "x", "--sep", "camel"])

    def test_case_raw_default_is_none(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x"])
        assert ns.case is None

    @pytest.mark.parametrize("value", ["none", "upper", "lower", "capitalize", "title"])
    def test_case_values(self, value):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "--case", value])
        assert ns.case == value

    def test_confirm_default_false(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x"])
        assert ns.confirm is False

    def test_confirm_flag(self):
        ns, _ = _build_parser().parse_known_args(["-s", "x", "--confirm"])
        assert ns.confirm is True

    def test_mode_invalid_rejected(self):
        with pytest.raises(SystemExit):
            _build_parser().parse_args(["-s", "x", "--mode", "wildcard"])

    def test_case_invalid_rejected(self):
        with pytest.raises(SystemExit):
            _build_parser().parse_args(["-s", "x", "--case", "camelcase"])


# ---------------------------------------------------------------------------
# _apply_postproc
# ---------------------------------------------------------------------------


class TestApplyPostproc:
    def _path(self, name: str) -> str:
        return f"/fake/{name}"

    def test_no_ops_returns_unchanged(self):
        result = _apply_postproc(
            "hello", self._path("hello"), accent=False, dup=False, case="none"
        )
        assert result == "hello"

    def test_accent_strips_diacritics(self):
        result = _apply_postproc(
            "café", self._path("café"), accent=True, dup=False, case="none"
        )
        assert result == "cafe"

    def test_dup_collapses_separators(self):
        result = _apply_postproc(
            "foo--bar", self._path("foo--bar"), accent=False, dup=True, case="none"
        )
        assert result == "foo-bar"

    def test_case_upper(self):
        result = _apply_postproc(
            "hello", self._path("hello"), accent=False, dup=False, case="upper"
        )
        assert result == "HELLO"

    def test_case_lower(self):
        result = _apply_postproc(
            "HELLO", self._path("HELLO"), accent=False, dup=False, case="lower"
        )
        assert result == "hello"

    def test_case_capitalize(self):
        result = _apply_postproc(
            "hello world", self._path("x"), accent=False, dup=False, case="capitalize"
        )
        assert result == "Hello world"

    def test_case_title(self):
        result = _apply_postproc(
            "hello world", self._path("x"), accent=False, dup=False, case="title"
        )
        assert result == "Hello World"

    def test_all_ops_combined(self):
        # accent → dup → case; "café--lait" → "cafe-lait" → "Cafe-lait"
        result = _apply_postproc(
            "café--lait", self._path("x"), accent=True, dup=True, case="capitalize"
        )
        assert result == "Cafe-lait"

    def test_sep_space_to_underscore(self):
        result = _apply_postproc(
            "hello world",
            self._path("x"),
            sep="space-underscore",
            accent=False,
            dup=False,
            case="none",
        )
        assert result == "hello_world"

    def test_sep_space_to_dash(self):
        result = _apply_postproc(
            "hello world",
            self._path("x"),
            sep="space-dash",
            accent=False,
            dup=False,
            case="none",
        )
        assert result == "hello-world"

    def test_sep_none_unchanged(self):
        result = _apply_postproc(
            "hello world",
            self._path("x"),
            sep="none",
            accent=False,
            dup=False,
            case="none",
        )
        assert result == "hello world"


# ---------------------------------------------------------------------------
# _resolve_ns
# ---------------------------------------------------------------------------


class TestResolveNs:
    def _raw_ns(self, **kwargs) -> argparse.Namespace:
        """Namespace with None for unset save-overridable fields."""
        defaults = dict(
            search=None,
            saved=None,
            replace=None,
            mode=None,
            list="files",
            recurse=False,
            keep_ext=None,
            filter_glob=None,
            sep=None,
            accent=None,
            dup=None,
            case=None,
            confirm=False,
            directory=None,
            log_level=None,
        )
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_search_sets_hardcoded_defaults(self):
        ns = self._raw_ns(search="foo")
        _resolve_ns(ns)
        assert ns.replace == ""
        assert ns.mode == "pattern"
        assert ns.sep == "none"
        assert ns.accent is False
        assert ns.dup is False
        assert ns.case == "none"
        assert ns.keep_ext is True

    def test_explicit_cli_flags_preserved(self):
        ns = self._raw_ns(
            search="foo", replace="bar", mode="regex", keep_ext=False, accent=True
        )
        _resolve_ns(ns)
        assert ns.replace == "bar"
        assert ns.mode == "regex"
        assert ns.keep_ext is False
        assert ns.accent is True

    def test_no_search_no_saved_exits(self):
        ns = self._raw_ns()
        with pytest.raises(SystemExit):
            _resolve_ns(ns)

    def _make_presets(self, tmp_path, saves: dict):
        from pbrenamer.ui.presets import PatternPresets

        p = PatternPresets(tmp_path / "patterns")
        for name, cfg in saves.items():
            p.set_save(name, cfg)
        return p

    def test_saved_not_found_exits(self, tmp_path, monkeypatch):
        from pbrenamer.ui import presets as _presets

        empty = self._make_presets(tmp_path, {})
        monkeypatch.setattr(_presets, "PatternPresets", lambda: empty)
        ns = self._raw_ns(saved="ghost")
        with pytest.raises(SystemExit):
            _resolve_ns(ns)

    def test_saved_loads_config(self, tmp_path, monkeypatch):
        from pbrenamer.ui import presets as _presets

        p = self._make_presets(
            tmp_path,
            {
                "mypreset": {
                    "search_pattern": "{X}",
                    "search_mode": "pattern",
                    "replace_pattern": "{1}",
                    "separator": 1,  # space-underscore
                    "remove_accents": True,
                    "remove_duplicates": False,
                    "case": 2,  # lowercase
                    "keep_extension": False,
                }
            },
        )
        monkeypatch.setattr(_presets, "PatternPresets", lambda: p)
        ns = self._raw_ns(saved="mypreset")
        _resolve_ns(ns)
        assert ns.search == "{X}"
        assert ns.mode == "pattern"
        assert ns.replace == "{1}"
        assert ns.sep == "space-underscore"
        assert ns.accent is True
        assert ns.dup is False
        assert ns.case == "lower"
        assert ns.keep_ext is False

    def test_cli_overrides_saved_field(self, tmp_path, monkeypatch):
        from pbrenamer.ui import presets as _presets

        p = self._make_presets(
            tmp_path,
            {
                "p": {
                    "search_pattern": "original",
                    "replace_pattern": "from_save",
                    "case": 1,
                }
            },
        )
        monkeypatch.setattr(_presets, "PatternPresets", lambda: p)
        # --replace overrides the save's replace_pattern; --case overrides case
        ns = self._raw_ns(saved="p", replace="from_cli", case="upper")
        _resolve_ns(ns)
        assert ns.search == "original"
        assert ns.replace == "from_cli"
        assert ns.case == "upper"

    def test_saved_search_can_be_overridden_by_search_flag(self, tmp_path, monkeypatch):
        from pbrenamer.ui import presets as _presets

        p = self._make_presets(tmp_path, {"p": {"search_pattern": "from_save"}})
        monkeypatch.setattr(_presets, "PatternPresets", lambda: p)
        ns = self._raw_ns(saved="p", search="from_cli")
        _resolve_ns(ns)
        assert ns.search == "from_cli"


# ---------------------------------------------------------------------------
# _plan
# ---------------------------------------------------------------------------


class TestPlan:
    def test_plain_rename(self, tmp_path):
        _make_files(tmp_path, "foo_bar.txt", "baz_qux.txt")
        entries = [(f, str(tmp_path / f)) for f in ["foo_bar.txt", "baz_qux.txt"]]
        ns = _ns(search="_", replace="-", mode="plain")
        result = _plan(entries, ns)
        names = {orig: new for _, orig, new in result}
        assert names["foo_bar.txt"] == "foo-bar.txt"
        assert names["baz_qux.txt"] == "baz-qux.txt"

    def test_regex_rename(self, tmp_path):
        # Capture groups are referenced as {1}, {2}… in the replacement syntax
        _make_files(tmp_path, "img001.jpg", "img002.jpg")
        entries = [(f, str(tmp_path / f)) for f in ["img001.jpg", "img002.jpg"]]
        ns = _ns(search=r"img(\d+)", replace="photo_{1}", mode="regex")
        result = _plan(entries, ns)
        names = {orig: new for _, orig, new in result}
        assert names["img001.jpg"] == "photo_001.jpg"
        assert names["img002.jpg"] == "photo_002.jpg"

    def test_pattern_counter(self, tmp_path):
        # {L} captures letters in the search; {1} back-references the capture,
        # {num} inserts the per-batch file counter (1-based)
        _make_files(tmp_path, "alpha.txt", "beta.txt")
        entries = [(f, str(tmp_path / f)) for f in ["alpha.txt", "beta.txt"]]
        ns = _ns(search="{L}", replace="{1}_{num}", mode="pattern")
        result = _plan(entries, ns)
        names = {orig: new for _, orig, new in result}
        assert names["alpha.txt"] == "alpha_1.txt"
        assert names["beta.txt"] == "beta_2.txt"

    def test_no_match_returns_none(self, tmp_path):
        _make_files(tmp_path, "hello.txt")
        entries = [("hello.txt", str(tmp_path / "hello.txt"))]
        ns = _ns(search="xyz", replace="abc", mode="plain")
        result = _plan(entries, ns)
        assert result[0][2] is None

    def test_keep_ext_preserves_extension(self, tmp_path):
        _make_files(tmp_path, "my_file.txt")
        entries = [("my_file.txt", str(tmp_path / "my_file.txt"))]
        ns = _ns(search="_", replace="-", mode="plain", keep_ext=True)
        result = _plan(entries, ns)
        assert result[0][2] == "my-file.txt"

    def test_no_keep_ext_includes_extension_in_search(self, tmp_path):
        # With keep_ext=False the full filename (incl. extension) is the stem,
        # so a search that touches the extension part works too.
        _make_files(tmp_path, "report.docx")
        entries = [("report.docx", str(tmp_path / "report.docx"))]
        ns = _ns(search=".docx", replace=".txt", mode="plain", keep_ext=False)
        result = _plan(entries, ns)
        assert result[0][2] == "report.txt"

    def test_postproc_applied(self, tmp_path):
        _make_files(tmp_path, "café.txt")
        entries = [("café.txt", str(tmp_path / "café.txt"))]
        ns = _ns(search="café", replace="cafe", mode="plain", accent=True, case="upper")
        result = _plan(entries, ns)
        assert result[0][2] == "CAFE.txt"

    def test_invalid_replacement_syntax_exits(self, tmp_path):
        _make_files(tmp_path, "a.txt")
        entries = [("a.txt", str(tmp_path / "a.txt"))]
        ns = _ns(search="a", replace="{unclosed", mode="pattern")
        with pytest.raises(SystemExit):
            _plan(entries, ns)


# ---------------------------------------------------------------------------
# _detect_conflicts
# ---------------------------------------------------------------------------


class TestDetectConflicts:
    def test_no_conflict(self, tmp_path):
        a = str(tmp_path / "a.txt")
        b = str(tmp_path / "b.txt")
        plan = [(a, "a.txt", "x.txt"), (b, "b.txt", "y.txt")]
        assert _detect_conflicts(plan) == set()

    def test_duplicate_targets_are_conflicts(self, tmp_path):
        a = str(tmp_path / "a.txt")
        b = str(tmp_path / "b.txt")
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.txt").touch()
        plan = [(a, "a.txt", "same.txt"), (b, "b.txt", "same.txt")]
        conflicts = _detect_conflicts(plan)
        assert conflicts == {0, 1}

    def test_existing_target_is_conflict(self, tmp_path):
        a = str(tmp_path / "a.txt")
        existing = tmp_path / "taken.txt"
        (tmp_path / "a.txt").touch()
        existing.touch()
        plan = [(a, "a.txt", "taken.txt")]
        conflicts = _detect_conflicts(plan)
        assert 0 in conflicts

    def test_rename_to_same_name_not_a_conflict(self, tmp_path):
        a = str(tmp_path / "a.txt")
        (tmp_path / "a.txt").touch()
        plan = [(a, "a.txt", "a.txt")]
        assert _detect_conflicts(plan) == set()

    def test_no_new_name_ignored(self, tmp_path):
        a = str(tmp_path / "a.txt")
        (tmp_path / "a.txt").touch()
        plan = [(a, "a.txt", None)]
        assert _detect_conflicts(plan) == set()


# ---------------------------------------------------------------------------
# _headless_run (integration)
# ---------------------------------------------------------------------------


class TestHeadlessRun:
    def test_basic_rename_no_confirm(self, tmp_path, capsys):
        _make_files(tmp_path, "foo_bar.txt", "baz_qux.txt")
        ns = _ns(search="_", replace="-", mode="plain", directory=str(tmp_path))
        _headless_run(ns)
        out = capsys.readouterr().out
        assert "foo-bar.txt" in out
        assert "baz-qux.txt" in out
        assert (tmp_path / "foo-bar.txt").exists()
        assert (tmp_path / "baz-qux.txt").exists()

    def test_no_match_prints_nothing_renamed(self, tmp_path, capsys):
        _make_files(tmp_path, "hello.txt")
        ns = _ns(search="xyz", replace="abc", mode="plain", directory=str(tmp_path))
        _headless_run(ns)
        out = capsys.readouterr().out
        assert "No files" in out

    def test_empty_directory_prints_no_entries(self, tmp_path, capsys):
        ns = _ns(search="x", replace="y", mode="plain", directory=str(tmp_path))
        _headless_run(ns)
        assert "No entries" in capsys.readouterr().out

    def test_confirm_yes_renames(self, tmp_path, capsys, monkeypatch):
        _make_files(tmp_path, "old.txt")
        monkeypatch.setattr("builtins.input", lambda _: "y")
        ns = _ns(
            search="old",
            replace="new",
            mode="plain",
            confirm=True,
            directory=str(tmp_path),
        )
        _headless_run(ns)
        assert (tmp_path / "new.txt").exists()
        assert not (tmp_path / "old.txt").exists()

    def test_confirm_no_aborts(self, tmp_path, capsys, monkeypatch):
        _make_files(tmp_path, "old.txt")
        monkeypatch.setattr("builtins.input", lambda _: "n")
        ns = _ns(
            search="old",
            replace="new",
            mode="plain",
            confirm=True,
            directory=str(tmp_path),
        )
        _headless_run(ns)
        assert (tmp_path / "old.txt").exists()
        assert not (tmp_path / "new.txt").exists()
        assert "Aborted" in capsys.readouterr().out

    def test_confirm_shows_preview_table(self, tmp_path, capsys, monkeypatch):
        _make_files(tmp_path, "foo_bar.txt")
        monkeypatch.setattr("builtins.input", lambda _: "n")
        ns = _ns(
            search="_", replace="-", mode="plain", confirm=True, directory=str(tmp_path)
        )
        _headless_run(ns)
        out = capsys.readouterr().out
        assert "foo_bar.txt" in out
        assert "foo-bar.txt" in out

    def test_filter_glob_restricts_listing(self, tmp_path, capsys):
        _make_files(tmp_path, "photo.jpg", "doc.txt")
        ns = _ns(
            search="photo",
            replace="image",
            mode="plain",
            filter_glob="*.jpg",
            directory=str(tmp_path),
        )
        _headless_run(ns)
        assert (tmp_path / "image.jpg").exists()
        assert (tmp_path / "doc.txt").exists()

    def test_recurse_renames_in_subdirs(self, tmp_path, capsys):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "foo_bar.txt").touch()
        ns = _ns(
            search="_", replace="-", mode="plain", recurse=True, directory=str(tmp_path)
        )
        _headless_run(ns)
        assert (sub / "foo-bar.txt").exists()

    def test_accent_strips_diacritics(self, tmp_path, capsys):
        (tmp_path / "café.txt").touch()
        ns = _ns(
            search="café",
            replace="cafe_raw",
            mode="plain",
            accent=True,
            directory=str(tmp_path),
        )
        _headless_run(ns)
        assert (tmp_path / "cafe_raw.txt").exists()

    def test_case_upper(self, tmp_path, capsys):
        _make_files(tmp_path, "hello.txt")
        ns = _ns(
            search="hello",
            replace="world",
            mode="plain",
            case="upper",
            directory=str(tmp_path),
        )
        _headless_run(ns)
        assert (tmp_path / "WORLD.txt").exists()

    def test_dup_collapses_separators(self, tmp_path, capsys):
        _make_files(tmp_path, "foo--bar.txt")
        ns = _ns(
            search="foo", replace="baz", mode="plain", dup=True, directory=str(tmp_path)
        )
        _headless_run(ns)
        assert (tmp_path / "baz-bar.txt").exists()

    def test_list_dirs_only(self, tmp_path, capsys):
        _make_files(tmp_path, "file.txt")
        (tmp_path / "mydir").mkdir()
        ns = _ns(
            search="mydir",
            replace="renamed_dir",
            mode="plain",
            list="dirs",
            directory=str(tmp_path),
        )
        _headless_run(ns)
        assert (tmp_path / "renamed_dir").exists()
        assert (tmp_path / "file.txt").exists()

    def test_conflict_skipped_files_remain(self, tmp_path, capsys):
        _make_files(tmp_path, "a_x.txt", "b_x.txt")
        # Both would rename to "x.txt" — conflict
        ns = _ns(search=r"^[ab]_", replace="", mode="regex", directory=str(tmp_path))
        _headless_run(ns)
        # Both originals must still exist (skipped due to conflict)
        assert (tmp_path / "a_x.txt").exists()
        assert (tmp_path / "b_x.txt").exists()

    def test_conflict_shown_in_confirm_preview(self, tmp_path, capsys, monkeypatch):
        _make_files(tmp_path, "a_x.txt", "b_x.txt")
        monkeypatch.setattr("builtins.input", lambda _: "n")
        ns = _ns(
            search=r"^[ab]_",
            replace="",
            mode="regex",
            confirm=True,
            directory=str(tmp_path),
        )
        _headless_run(ns)
        out = capsys.readouterr().out
        assert "CONFLICT" in out

    def test_no_keep_ext_renames_full_filename(self, tmp_path, capsys):
        _make_files(tmp_path, "data_v1.csv")
        ns = _ns(
            search="_",
            replace="-",
            mode="plain",
            keep_ext=False,
            directory=str(tmp_path),
        )
        _headless_run(ns)
        assert (tmp_path / "data-v1.csv").exists()

    def test_regex_mode(self, tmp_path, capsys):
        _make_files(tmp_path, "img001.jpg", "img042.jpg")
        ns = _ns(
            search=r"img(\d+)",
            replace="photo_{1}",
            mode="regex",
            directory=str(tmp_path),
        )
        _headless_run(ns)
        assert (tmp_path / "photo_001.jpg").exists()
        assert (tmp_path / "photo_042.jpg").exists()

    def test_uses_cwd_when_no_directory(self, tmp_path, capsys, monkeypatch):
        _make_files(tmp_path, "old_name.txt")
        monkeypatch.chdir(tmp_path)
        ns = _ns(search="old", replace="new", mode="plain", directory=None)
        _headless_run(ns)
        assert (tmp_path / "new_name.txt").exists()


# ---------------------------------------------------------------------------
# --help-search / --help-replace
# ---------------------------------------------------------------------------


class TestHelpExport:
    def test_help_search_default_is_false(self):
        ns, _ = _build_parser().parse_known_args([])
        assert ns.help_search is False

    def test_help_replace_default_is_false(self):
        ns, _ = _build_parser().parse_known_args([])
        assert ns.help_replace is False

    def test_help_search_flag(self):
        ns, _ = _build_parser().parse_known_args(["--help-search"])
        assert ns.help_search is True

    def test_help_replace_flag(self):
        ns, _ = _build_parser().parse_known_args(["--help-replace"])
        assert ns.help_replace is True

    def test_help_search_outputs_html(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["pbrenamer", "--help-search"])
        from pbrenamer.__main__ import main

        main()
        out = capsys.readouterr().out
        assert "<html>" in out
        assert "Search patterns" in out

    def test_help_replace_outputs_html(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["pbrenamer", "--help-replace"])
        from pbrenamer.__main__ import main

        main()
        out = capsys.readouterr().out
        assert "<html>" in out
        assert "Replacement fields" in out

    def test_both_flags_output_both(self, capsys, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["pbrenamer", "--help-search", "--help-replace"]
        )
        from pbrenamer.__main__ import main

        main()
        out = capsys.readouterr().out
        assert "Search patterns" in out
        assert "Replacement fields" in out
