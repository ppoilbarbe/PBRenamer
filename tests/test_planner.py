"""Tests for pbrenamer.core.planner — batch name computation and {newnum}.

Includes the cases of PBPicat's renamer tests (schema examples, numbering,
fill gaps, separate image/video counters, video marker, renumbering),
expressed as pattern-mode rules: a schema ``A, B, ###`` with destination
ROOT compiles to search ``{X}`` / replace ``{dest}/A/B/A_B_{newnum:03}``.
"""

import os

import pytest

from pbrenamer.core import filetools, planner
from pbrenamer.core.replacement import NEWNUM_MARKER, FieldResolutionError
from pbrenamer.core.sidecar import SidecarConfig


def _touch(directory, *names):
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).touch()
    return [str(directory / name) for name in names]


def _schema_rule(dest, replace, **kw):
    """Rule equivalent to a compiled PBPicat schema."""
    kw.setdefault("per_category", True)
    return planner.Rule(
        search="{X}",
        replace=replace,
        ext_mode="lower",
        dest_root=str(dest),
        **kw,
    )


def _names(rule, paths, **kw):
    return [
        os.path.relpath(e.target, rule.dest_root) if e.target else None
        for e in planner.compute_names(rule, paths, **kw)
    ]


# ---------------------------------------------------------------------------
# PBPicat SPEC — § Rename Schema / Examples
# ---------------------------------------------------------------------------


class TestSpecExamples:
    def test_without_counter(self, tmp_path):
        src = _touch(tmp_path / "src", "IMG.JPG")
        rule = _schema_rule(tmp_path / "root", "{dest}/abc/def/ghi/abc_def_ghi")
        assert _names(rule, src) == ["abc/def/ghi/abc_def_ghi.jpg"]

    def test_three_digit_counter(self, tmp_path):
        src = _touch(tmp_path / "src", "IMG.jpg")
        rule = _schema_rule(
            tmp_path / "root", "{dest}/abc/def/ghi/abc_def_ghi_{newnum:03}"
        )
        assert _names(rule, src) == ["abc/def/ghi/abc_def_ghi_001.jpg"]

    def test_four_digit_counter_max_plus_one(self, tmp_path):
        src = _touch(tmp_path / "src", "IMG.jpg")
        _touch(tmp_path / "root/A/B/C/D", "A_B_C_D_0041.jpg")
        rule = _schema_rule(tmp_path / "root", "{dest}/A/B/C/D/A_B_C_D_{newnum:04}")
        assert _names(rule, src) == ["A/B/C/D/A_B_C_D_0042.jpg"]


# ---------------------------------------------------------------------------
# PBPicat SPEC — § Numbering (max + 1, numeric comparison)
# ---------------------------------------------------------------------------


class TestNumbering:
    def test_numeric_not_lexicographic_order(self, tmp_path):
        dest = tmp_path / "root"
        _touch(dest / "A", *(f"A_{n}.jpg" for n in (1, 2, 13, 101, 121)))
        src = _touch(tmp_path / "src", "x.jpg")
        assert _names(_schema_rule(dest, "{dest}/A/A_{newnum}"), src) == ["A/A_122.jpg"]

    def test_missing_target_dir_starts_at_one(self, tmp_path):
        src = _touch(tmp_path / "src", "x.jpg", "y.jpg")
        rule = _schema_rule(tmp_path / "root", "{dest}/A/A_{newnum:02}")
        assert _names(rule, src) == ["A/A_01.jpg", "A/A_02.jpg"]

    def test_other_series_ignored(self, tmp_path):
        dest = tmp_path / "root"
        _touch(dest / "A", "B_9.jpg", "AA_9.jpg", "A_x.jpg")
        src = _touch(tmp_path / "src", "x.jpg")
        assert _names(_schema_rule(dest, "{dest}/A/A_{newnum}"), src) == ["A/A_1.jpg"]

    def test_series_shared_across_extensions(self, tmp_path):
        dest = tmp_path / "root"
        _touch(dest, "A_4.png", "A_5.jpg.xmp")
        src = _touch(tmp_path / "src", "x.jpg")
        rule = _schema_rule(dest, "{dest}/A_{newnum}", per_category=False)
        assert _names(rule, src) == ["A_6.jpg"]

    def test_start_value_is_a_floor(self, tmp_path):
        dest = tmp_path / "root"
        _touch(dest, "A_3.jpg")
        src = _touch(tmp_path / "src", "x.jpg")
        assert _names(_schema_rule(dest, "{dest}/A_{newnum::10}"), src) == ["A_10.jpg"]

    def test_extension_lowercased(self, tmp_path):
        src = _touch(tmp_path / "src", "x.JPG", "y.Mp4")
        rule = _schema_rule(tmp_path / "root", "{dest}/A_{newnum}")
        assert _names(rule, src) == ["A_1.jpg", "A_1.mp4"]

    def test_batch_files_keep_their_numbers(self, tmp_path):
        paths = _touch(tmp_path, "A_1.jpg", "A_2.jpg", "A_3.jpg")
        rule = planner.Rule(search="{X}", replace="A_{newnum}")
        entries = planner.compute_names(rule, paths)
        assert [e.new_name for e in entries] == ["A_1.jpg", "A_2.jpg", "A_3.jpg"]

    def test_existing_name_of_another_file_skipped(self, tmp_path):
        # Space padding is not recognised as part of the series: the counter
        # falls back on checking the disk name by name.
        _touch(tmp_path, "A_ 1.txt")
        paths = _touch(tmp_path, "x.txt")
        rule = planner.Rule(search="{X}", replace="A_{newnum:2}")
        assert planner.compute_names(rule, paths)[0].new_name == "A_ 2.txt"


# ---------------------------------------------------------------------------
# Separate image / video counters and the video marker
# ---------------------------------------------------------------------------


class TestCategories:
    def test_separate_counters(self, tmp_path):
        src = _touch(tmp_path / "src", "a.jpg", "b.mp4", "c.jpg", "d.mp4")
        rule = _schema_rule(tmp_path / "root", "{dest}/A_{newnum:03}")
        assert _names(rule, src) == ["A_001.jpg", "A_001.mp4", "A_002.jpg", "A_002.mp4"]

    def test_separate_counters_continue_from_existing(self, tmp_path):
        dest = tmp_path / "root"
        _touch(dest, "A_005.jpg", "A_002.mp4")
        src = _touch(tmp_path / "src", "a.jpg", "b.mp4")
        rule = _schema_rule(dest, "{dest}/A_{newnum:03}")
        assert _names(rule, src) == ["A_006.jpg", "A_003.mp4"]

    def test_shared_counter_without_per_category(self, tmp_path):
        src = _touch(tmp_path / "src", "a.jpg", "b.mp4")
        rule = _schema_rule(tmp_path / "root", "{dest}/A_{newnum}", per_category=False)
        assert _names(rule, src) == ["A_1.jpg", "A_2.mp4"]

    @pytest.mark.parametrize(
        ("replace", "expected"),
        [
            ("{dest}/A/B/{if:video:vid_}A_B_{newnum:03}", "A/B/vid_A_B_001.mp4"),
            ("{dest}/A/B/A{if:video:_vid}_B_{newnum:03}", "A/B/A_vid_B_001.mp4"),
            ("{dest}/A/B/A_B{if:video:_vid}_{newnum:03}", "A/B/A_B_vid_001.mp4"),
        ],
        ids=["first", "middle", "last"],
    )
    def test_video_marker_position(self, tmp_path, replace, expected):
        src = _touch(tmp_path / "src", "a.jpg", "b.mp4")
        assert _names(_schema_rule(tmp_path / "root", replace), src) == [
            "A/B/A_B_001.jpg",
            expected,
        ]

    def test_video_marker_series_continues(self, tmp_path):
        dest = tmp_path / "root"
        _touch(dest, "A_vid_007.mp4", "A_009.jpg")
        src = _touch(tmp_path / "src", "a.mp4")
        assert _names(
            _schema_rule(dest, "{dest}/A{if:video:_vid}_{newnum:03}"), src
        ) == ["A_vid_008.mp4"]

    def test_custom_category_table(self, tmp_path):
        config = SidecarConfig.defaults()
        config.base_extensions["video"] = frozenset({"raw"})
        src = _touch(tmp_path / "src", "a.raw")
        rule = _schema_rule(
            tmp_path / "root", "{dest}/A{if:video:_v}", sidecar_config=config
        )
        assert _names(rule, src) == ["A_v.raw"]


# ---------------------------------------------------------------------------
# Fill gaps
# ---------------------------------------------------------------------------


class TestFillGaps:
    def test_smallest_missing_number(self, tmp_path):
        dest = tmp_path / "root"
        _touch(dest, "A_001.jpg", "A_003.jpg")
        src = _touch(tmp_path / "src", "x.jpg")
        rule = _schema_rule(dest, "{dest}/A_{newnum:03}", fill_gaps=True)
        assert _names(rule, src) == ["A_002.jpg"]

    def test_no_gap_continues_after_max(self, tmp_path):
        dest = tmp_path / "root"
        _touch(dest, "A_1.jpg", "A_2.jpg")
        src = _touch(tmp_path / "src", "x.jpg")
        rule = _schema_rule(dest, "{dest}/A_{newnum}", fill_gaps=True)
        assert _names(rule, src) == ["A_3.jpg"]

    def test_several_gaps_then_continue(self, tmp_path):
        dest = tmp_path / "root"
        _touch(dest, "A_2.jpg", "A_4.jpg")
        src = _touch(tmp_path / "src", "a.jpg", "b.jpg", "c.jpg", "d.jpg")
        rule = _schema_rule(dest, "{dest}/A_{newnum}", fill_gaps=True)
        assert _names(rule, src) == ["A_1.jpg", "A_3.jpg", "A_5.jpg", "A_6.jpg"]

    def test_separate_counters(self, tmp_path):
        dest = tmp_path / "root"
        _touch(dest, "A_2.jpg", "A_1.mp4")
        src = _touch(tmp_path / "src", "a.jpg", "b.mp4")
        rule = _schema_rule(dest, "{dest}/A_{newnum}", fill_gaps=True)
        assert _names(rule, src) == ["A_1.jpg", "A_2.mp4"]

    def test_batch_files_already_in_dest_excluded(self, tmp_path):
        dest = tmp_path / "root"
        paths = _touch(dest, "A_1.jpg", "A_3.jpg")
        rule = _schema_rule(dest, "{dest}/A_{newnum}", fill_gaps=True)
        assert _names(rule, paths) == ["A_1.jpg", "A_2.jpg"]


# ---------------------------------------------------------------------------
# Renumbering (two-phase execution)
# ---------------------------------------------------------------------------


class TestReserved:
    def test_series_sharing_a_target_take_distinct_numbers(self, tmp_path):
        # Extension kept in the stem: the image and the video have distinct
        # per-category series, yet the same candidate name.
        paths = _touch(tmp_path, "a.jpg", "b.mp4")
        rule = planner.Rule(
            search="{X}", replace="P_{newnum}", ext_mode="modify", per_category=True
        )
        entries = planner.compute_names(rule, paths)
        assert [e.new_name for e in entries] == ["P_1", "P_2"]


class TestRenumber:
    def test_sequence_from_one_ignoring_disk_numbers(self, tmp_path):
        paths = _touch(tmp_path, "A_5.jpg", "A_9.jpg")
        rule = planner.Rule(search="{X}", replace="A_{newnum}", renumber=True)
        entries = planner.compute_names(rule, paths)
        assert [e.new_name for e in entries] == ["A_1.jpg", "A_2.jpg"]

    def test_chain_executed_atomically(self, tmp_path):
        paths = _touch(tmp_path, "A_2.jpg", "A_3.jpg")
        (tmp_path / "A_2.jpg").write_text("two")
        rule = planner.Rule(search="{X}", replace="A_{newnum}", renumber=True)
        entries = planner.compute_names(rule, paths)
        assert [e.new_name for e in entries] == ["A_1.jpg", "A_2.jpg"]
        filetools.execute_renames(
            [(p, e.target) for p, e in zip(paths, entries, strict=True)]
        )
        assert sorted(os.listdir(tmp_path)) == ["A_1.jpg", "A_2.jpg"]
        assert (tmp_path / "A_1.jpg").read_text() == "two"

    def test_circular_swap(self, tmp_path):
        paths = _touch(tmp_path, "A_2.jpg", "A_1.jpg")
        (tmp_path / "A_2.jpg").write_text("first")
        rule = planner.Rule(search="{X}", replace="A_{newnum}", renumber=True)
        entries = planner.compute_names(rule, paths)
        filetools.execute_renames(
            [(p, e.target) for p, e in zip(paths, entries, strict=True)]
        )
        assert (tmp_path / "A_1.jpg").read_text() == "first"

    def test_separate_counters_with_marker(self, tmp_path):
        paths = _touch(tmp_path, "x.jpg", "y.mp4", "z.jpg")
        rule = _schema_rule(
            tmp_path, "{dest}/A{if:video:_vid}_{newnum:02}", renumber=True
        )
        assert _names(rule, paths) == ["A_01.jpg", "A_vid_01.mp4", "A_02.jpg"]

    def test_file_outside_batch_is_skipped(self, tmp_path):
        _touch(tmp_path, "A_1.jpg")
        paths = _touch(tmp_path, "x.jpg")
        rule = planner.Rule(search="{X}", replace="A_{newnum}", renumber=True)
        assert planner.compute_names(rule, paths)[0].new_name == "A_2.jpg"


# ---------------------------------------------------------------------------
# compute_names — general behaviour
# ---------------------------------------------------------------------------


class TestComputeNames:
    def test_no_match(self, tmp_path):
        paths = _touch(tmp_path, "abc.txt")
        rule = planner.Rule(search="zzz", replace="y", mode="plain")
        assert planner.compute_names(rule, paths) == [planner.PlanEntry()]

    def test_no_match_with_newnum(self, tmp_path):
        paths = _touch(tmp_path, "abc.txt")
        rule = planner.Rule(search="zzz", replace="{newnum}", mode="plain")
        assert planner.compute_names(rule, paths) == [planner.PlanEntry()]

    def test_empty_result(self, tmp_path):
        paths = _touch(tmp_path, "abc")
        rule = planner.Rule(search="{X}", replace="")
        assert planner.compute_names(rule, paths) == [planner.PlanEntry()]

    def test_relative_sub_directory(self, tmp_path):
        paths = _touch(tmp_path, "a.txt")
        rule = planner.Rule(search="{X}", replace="sub/{0}", mode="pattern")
        (entry,) = planner.compute_names(rule, paths)
        assert entry.new_name == "sub/a.txt"
        assert entry.target == str(tmp_path / "sub" / "a.txt")

    def test_field_error(self, tmp_path):
        paths = _touch(tmp_path, "a.txt")
        rule = planner.Rule(search="{X}", replace="{im:Model}")
        (entry,) = planner.compute_names(rule, paths)
        assert isinstance(entry.error, FieldResolutionError)
        assert entry.new_name is None

    def test_field_error_with_newnum(self, tmp_path):
        paths = _touch(tmp_path, "a.txt")
        rule = planner.Rule(search="{X}", replace="{im:Model}_{newnum}")
        (entry,) = planner.compute_names(rule, paths)
        assert isinstance(entry.error, FieldResolutionError)

    @pytest.mark.parametrize("replace", ["{dest}/{0}", "{dest}/{0}_{newnum}"])
    def test_dest_without_root(self, tmp_path, replace):
        paths = _touch(tmp_path, "a.txt")
        rule = planner.Rule(search="{X}", replace=replace)
        (entry,) = planner.compute_names(rule, paths)
        assert entry.error.reason == filetools.TargetPathError.NO_DEST

    def test_skipped_paths_take_no_number(self, tmp_path):
        paths = _touch(tmp_path, "a.jpg", "a.xmp", "b.jpg")
        rule = planner.Rule(search="{X}", replace="P_{newnum}")
        entries = planner.compute_names(
            rule, paths, followers={paths[0]: [(paths[1], "xmp")]}
        )
        assert [e.new_name for e in entries] == ["P_1.jpg", None, "P_2.jpg"]

    def test_newnum_outside_every_match(self, tmp_path):
        # x* only matches empty strings: the template is never applied.
        paths = _touch(tmp_path, "abc")
        rule = planner.Rule(search="x*", replace="{newnum}", mode="regex")
        (entry,) = planner.compute_names(rule, paths)
        assert entry.new_name == "abc"

    def test_newnum_in_directory_component(self, tmp_path):
        # The series is the whole target path: same names share a counter.
        paths = _touch(tmp_path / "x", "a") + _touch(tmp_path / "y", "a")
        paths += _touch(tmp_path / "x", "b")
        rule = planner.Rule(search="{X}", replace="../{newnum}/{0}")
        entries = planner.compute_names(rule, paths)
        assert all(e.error for e in entries)
        rule.replace = "{newnum}/{0}"
        entries = planner.compute_names(rule, paths)
        assert [e.new_name for e in entries] == ["1/a", "1/a", "1/b"]

    def test_modify_mode_keeps_extension_in_match(self, tmp_path):
        paths = _touch(tmp_path, "a.txt")
        rule = planner.Rule(
            search=".txt", replace=".md", mode="plain", ext_mode="modify"
        )
        assert planner.compute_names(rule, paths)[0].new_name == "a.md"

    @pytest.mark.parametrize(
        ("mode", "search"), [("regex", "a"), ("plain", "a"), ("pattern", "a")]
    )
    def test_case_insensitive(self, tmp_path, mode, search):
        paths = _touch(tmp_path, "A.txt")
        rule = planner.Rule(
            search=search, replace="b", mode=mode, case_insensitive=True
        )
        assert planner.compute_names(rule, paths)[0].new_name == "b.txt"


class TestApplyPostproc:
    def test_all_options(self):
        rule = planner.Rule(
            search="",
            replace="",
            spaces=0,
            remove_accents=True,
            remove_duplicates=True,
            capitalization=0,
        )
        assert planner.apply_postproc("éa  b", "/d/x", rule) == "EA_B"

    def test_no_option(self):
        rule = planner.Rule(search="", replace="")
        assert planner.apply_postproc("é a", "/d/x", rule) == "é a"


class TestNewNumStart:
    @pytest.mark.parametrize(
        ("template", "expected"),
        [
            ("{0}", None),
            ("{bad{", None),
            ("{newnum}", 1),
            ("{newnum::5}", 5),
            ("{newnum::abc}", 1),
        ],
    )
    def test_start(self, template, expected):
        assert planner.newnum_start(template) == expected


class TestNewNumState:
    def test_used_numbers_of_missing_directory(self, tmp_path):
        import re

        state = planner.NewNumState()
        pattern = re.compile(r"^A_(\d+)$")
        assert state.used_numbers(str(tmp_path / "missing"), pattern, None) == set()

    def test_marker_is_private_use_character(self):
        assert NEWNUM_MARKER == ""


# ---------------------------------------------------------------------------
# End to end: plan, sidecars, atomic execution, undo
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_classify_with_sidecars_then_undo(self, media_dir, tmp_path):
        from pbrenamer.core import sidecar
        from pbrenamer.core.undo import RenameEntry

        entries = filetools.get_file_listing(str(media_dir), 0)
        groups = sidecar.build_sidecar_groups(entries, SidecarConfig.defaults())
        paths = [path for _name, path in entries]
        dest = tmp_path / "root"
        rule = _schema_rule(dest, "{dest}/Paris/Paris_{newnum:03}")
        followers = sidecar.followers(groups)
        plan = dict(zip(paths, planner.compute_names(rule, paths, followers=followers)))
        pairs = [(p, e.target) for p, e in plan.items() if e.target]
        for base, scs in followers.items():
            for sc, suffix in scs:
                pairs.append((sc, planner.sidecar_target(plan[base].target, suffix)))

        result = filetools.execute_renames(pairs, prune_root=str(tmp_path))

        assert sorted(os.listdir(dest / "Paris")) == [
            "Paris_001.png",
            "Paris_001.xmp",
            "Paris_002.png",
            "Paris_002.xmp",
        ]
        assert not media_dir.exists()
        RenameEntry.from_result(result).undo()
        assert sorted(os.listdir(media_dir)) == [
            "img_001.png",
            "img_001.xmp",
            "img_002.png",
            "orphan.xmp",
        ]
        assert not dest.exists()


# ---------------------------------------------------------------------------
# Search spanning the extension separator (7.2 #5.1)
# ---------------------------------------------------------------------------


class TestExtensionSeparator:
    def _plan(self, tmp_path, name, search, replace, **kw):
        (path,) = _touch(tmp_path, name)
        rule = planner.Rule(search=search, replace=replace, **kw)
        return planner.compute_names(rule, [path])[0]

    def test_double_dot_collapsed(self, tmp_path):
        entry = self._plan(tmp_path, "c_0002..xmp", "..", ".")
        assert entry.new_name == "c_0002.xmp"

    def test_extension_mode_applied(self, tmp_path):
        entry = self._plan(tmp_path, "c..XMP", "..", ".", ext_mode="lower")
        assert entry.new_name == "c.xmp"

    def test_plain_text_mode(self, tmp_path):
        entry = self._plan(tmp_path, "c..xmp", "..", ".", mode="plain")
        assert entry.new_name == "c.xmp"

    def test_separator_removed_is_an_error(self, tmp_path):
        entry = self._plan(tmp_path, "photo.jpg", "o.", "o_")
        assert entry.new_name is None
        assert isinstance(entry.error, filetools.TargetPathError)
        assert entry.error.reason == filetools.TargetPathError.EXT_SEPARATOR

    def test_stem_match_unchanged(self, tmp_path):
        entry = self._plan(tmp_path, "a.b.jpg", ".", "_")
        assert entry.new_name == "a_b.jpg"

    def test_no_match_anywhere(self, tmp_path):
        entry = self._plan(tmp_path, "photo.jpg", "zz", "y")
        assert entry.new_name is None and entry.error is None

    def test_without_extension_no_retry(self, tmp_path):
        entry = self._plan(tmp_path, "README", ".", "_")
        assert entry.new_name is None and entry.error is None

    def test_modify_mode_works_on_full_name(self, tmp_path):
        entry = self._plan(tmp_path, "c..xmp", "..", ".", ext_mode="modify")
        assert entry.new_name == "c.xmp"
