"""Tests for pbrenamer.core.schema — PBPicat-style rename schemas.

Ports the schema cases of PBPicat's ``tests/test_renamer.py``
(``validate_schema``, ``build_rename_plan``, ``build_renumber_plan``) and the
examples of its SPEC, run through the planner.
"""

import os

import pytest

from pbrenamer.core import filetools, planner, schema
from pbrenamer.core.sidecar import SidecarConfig


def _touch(directory, *names):
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).touch()
    return [str(directory / name) for name in names]


def _targets(rule, paths, base, **kw):
    return [
        os.path.relpath(e.target, base) if e.target else None
        for e in planner.compute_names(rule, paths, **kw)
    ]


def _rename(fields, src_dir, names, dest, **kw):
    paths = _touch(src_dir, *names)
    rule = schema.compile_rule(fields, dest_root=str(dest), **kw)
    return _targets(rule, paths, dest)


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


class TestValidate:
    def test_parts_and_counter(self):
        assert schema.validate(["abc", "", "def", "###"]) == (["abc", "def"], "###")

    def test_no_counter(self):
        assert schema.validate(["abc", "def"]) == (["abc", "def"], None)

    def test_counter_only(self):
        assert schema.validate(["", "##"]) == ([], "##")

    def test_two_counters_rejected(self):
        with pytest.raises(schema.SchemaError, match="several numeric"):
            schema.validate(["abc", "##", "###"])

    @pytest.mark.parametrize("char", ["_", ".", "/", "\\"])
    def test_forbidden_character(self, char):
        with pytest.raises(schema.SchemaError, match="forbidden character"):
            schema.validate(["abc", f"d{char}f"])

    @pytest.mark.parametrize("fields", [[], ["", ""]])
    def test_empty_schema_rejected(self, fields):
        with pytest.raises(schema.SchemaError, match="empty"):
            schema.validate(fields)

    def test_hash_mixed_with_text_is_a_part(self):
        assert schema.validate(["a#"]) == (["a#"], None)


# ---------------------------------------------------------------------------
# compile_template
# ---------------------------------------------------------------------------


class TestCompileTemplate:
    @pytest.mark.parametrize(
        ("fields", "expected"),
        [
            (["abc", "def", "", "ghi", "", ""], "{dest}/abc/def/ghi/abc_def_ghi"),
            (
                ["abc", "def", "", "ghi", "", "###"],
                "{dest}/abc/def/ghi/abc_def_ghi_{newnum:03}",
            ),
            (["A", "", "B", "C", "D", "####"], "{dest}/A/B/C/D/A_B_C_D_{newnum:04}"),
            (["#"], "{dest}/{newnum:01}"),
            (["a{b}"], "{dest}/a{{b}/a{{b}"),
        ],
    )
    def test_rename(self, fields, expected):
        assert schema.compile_template(fields) == expected

    def test_in_place(self):
        assert (
            schema.compile_template(["A", "B", "###"], in_place=True)
            == "A_B_{newnum:03}"
        )

    @pytest.mark.parametrize(
        ("fields", "pos", "expected"),
        [
            (["abc", "def"], 0, "{if:video:VID_}abc_def"),
            (["abc", "def"], 1, "abc{if:video:_VID}_def"),
            (["abc", "def"], 2, "abc_def{if:video:_VID}"),
            (["abc", "def"], 99, "abc_def{if:video:_VID}"),
            (["abc", "def"], -1, "{if:video:VID_}abc_def"),
            # The number always comes last, whatever the marker position.
            (["abc", "###"], 2, "abc{if:video:_VID}_{newnum:03}"),
            (["###", "abc"], 0, "{if:video:VID_}abc_{newnum:03}"),
            (["###"], 1, "{if:video:VID_}{newnum:03}"),
            # Displayed position: empty fields before it hold no part.
            (["A", "", "B"], 2, "A{if:video:_VID}_B"),
            (["A", "", "B"], 1, "A{if:video:_VID}_B"),
        ],
    )
    def test_video_marker(self, fields, pos, expected):
        template = schema.compile_template(
            fields, video_marker="VID", video_marker_pos=pos, in_place=True
        )
        assert template == expected

    def test_marker_never_in_directories(self):
        template = schema.compile_template(
            ["abc", "def"], video_marker="VID", video_marker_pos=1
        )
        assert template == "{dest}/abc/def/abc{if:video:_VID}_def"

    @pytest.mark.parametrize("char", ["_", ".", "/", "\\", "{", "}"])
    def test_marker_forbidden_character(self, char):
        with pytest.raises(schema.SchemaError, match="video marker"):
            schema.compile_template(["abc"], video_marker=f"V{char}D")

    def test_invalid_fields_reported_before_marker(self):
        with pytest.raises(schema.SchemaError, match="several numeric"):
            schema.compile_template(["#", "#"], video_marker="V_D")


# ---------------------------------------------------------------------------
# compile_rule — renaming (PBPicat build_rename_plan)
# ---------------------------------------------------------------------------


class TestRename:
    def test_spec_example_without_counter(self, tmp_path):
        assert _rename(
            ["abc", "def", "", "ghi", "", ""], tmp_path / "src", ["IMG.JPG"], tmp_path
        ) == ["abc/def/ghi/abc_def_ghi.jpg"]

    def test_spec_example_three_digits(self, tmp_path):
        assert _rename(
            ["abc", "def", "", "ghi", "", "###"],
            tmp_path / "src",
            ["a.jpg", "b.jpg"],
            tmp_path,
        ) == ["abc/def/ghi/abc_def_ghi_001.jpg", "abc/def/ghi/abc_def_ghi_002.jpg"]

    def test_spec_example_four_digits_max_plus_one(self, tmp_path):
        _touch(tmp_path / "A/B/C/D", "A_B_C_D_0007.jpg")
        assert _rename(
            ["A", "", "B", "C", "D", "####"], tmp_path / "src", ["x.jpg"], tmp_path
        ) == ["A/B/C/D/A_B_C_D_0008.jpg"]

    def test_numeric_comparison(self, tmp_path):
        _touch(tmp_path / "A", *(f"A_{n}.jpg" for n in (1, 2, 13, 101, 121)))
        assert _rename(["A", "#"], tmp_path / "src", ["x.jpg"], tmp_path) == [
            "A/A_122.jpg"
        ]

    def test_counter_only_schema(self, tmp_path):
        _touch(tmp_path, "05.jpg")
        assert _rename(["##"], tmp_path / "src", ["x.jpg"], tmp_path) == ["06.jpg"]

    def test_separate_image_and_video_counters(self, tmp_path):
        _touch(tmp_path / "A", "A_004.jpg", "A_010.mp4")
        assert _rename(
            ["A", "###"], tmp_path / "src", ["a.JPG", "b.MP4", "c.png"], tmp_path
        ) == ["A/A_005.jpg", "A/A_011.mp4", "A/A_006.png"]

    def test_video_marker(self, tmp_path):
        assert _rename(
            ["abc", "def", "###"],
            tmp_path / "src",
            ["a.jpg", "b.mp4"],
            tmp_path,
            video_marker="VID",
            video_marker_pos=1,
        ) == ["abc/def/abc_def_001.jpg", "abc/def/abc_VID_def_001.mp4"]

    def test_fill_gaps(self, tmp_path):
        _touch(tmp_path / "A", "A_001.jpg", "A_003.jpg")
        assert _rename(
            ["A", "###"],
            tmp_path / "src",
            ["a.jpg", "b.jpg", "c.jpg"],
            tmp_path,
            fill_gaps=True,
        ) == ["A/A_002.jpg", "A/A_004.jpg", "A/A_005.jpg"]

    def test_custom_category_table(self, tmp_path):
        config = SidecarConfig.defaults()
        config.base_extensions["video"] = frozenset({"raw"})
        assert _rename(
            ["A", "#"],
            tmp_path / "src",
            ["a.jpg", "b.raw"],
            tmp_path,
            video_marker="V",
            video_marker_pos=1,
            sidecar_config=config,
        ) == ["A/A_1.jpg", "A/A_V_1.raw"]

    def test_sidecars_follow_and_reserve(self, tmp_path):
        src = tmp_path / "src"
        paths = _touch(src, "a.jpg", "a.xmp", "b.jpg")
        _touch(tmp_path / "A", "A_1.xmp")
        rule = schema.compile_rule(["A", "#"], dest_root=str(tmp_path))
        followers = {paths[0]: [(paths[1], "xmp")]}
        assert _targets(rule, paths, tmp_path, followers=followers) == [
            "A/A_2.jpg",
            None,
            "A/A_3.jpg",
        ]

    def test_rule_settings(self, tmp_path):
        rule = schema.compile_rule(["A"], dest_root=str(tmp_path), fill_gaps=True)
        assert (rule.search, rule.ext_mode, rule.dest_root) == (
            "{X}",
            "lower",
            str(tmp_path),
        )
        assert rule.per_category and rule.fill_gaps and not rule.renumber


# ---------------------------------------------------------------------------
# compile_rule — renumbering (PBPicat build_renumber_plan)
# ---------------------------------------------------------------------------


class TestRenumber:
    def _renumber(self, fields, directory, names, **kw):
        paths = _touch(directory, *names)
        rule = schema.compile_rule(fields, dest_root=None, renumber=True, **kw)
        return paths, _targets(rule, paths, directory)

    def test_in_place_from_one(self, tmp_path):
        _paths, targets = self._renumber(
            ["A", "B", "###"], tmp_path, ["A_B_007.jpg", "A_B_012.jpg", "x.JPG"]
        )
        assert targets == ["A_B_001.jpg", "A_B_002.jpg", "A_B_003.jpg"]

    def test_dest_root_ignored(self, tmp_path):
        rule = schema.compile_rule(["A", "#"], dest_root="/elsewhere", renumber=True)
        assert rule.dest_root is None and rule.replace == "A_{newnum:01}"

    def test_separate_counters_with_marker(self, tmp_path):
        _paths, targets = self._renumber(
            ["A", "##"],
            tmp_path,
            ["a.jpg", "b.mp4", "c.jpg"],
            video_marker="V",
            video_marker_pos=1,
        )
        assert targets == ["A_01.jpg", "A_V_01.mp4", "A_02.jpg"]

    def test_already_numbered_unchanged(self, tmp_path):
        paths, targets = self._renumber(["A", "#"], tmp_path, ["A_1.jpg", "A_2.jpg"])
        assert targets == [os.path.basename(p) for p in paths]

    def test_swap_executes(self, tmp_path):
        paths = _touch(tmp_path, "A_2.jpg", "A_1.jpg")
        rule = schema.compile_rule(["A", "#"], dest_root=None, renumber=True)
        entries = planner.compute_names(rule, paths)
        filetools.execute_renames(
            [(p, e.target) for p, e in zip(paths, entries, strict=True)]
        )
        assert sorted(os.listdir(tmp_path)) == ["A_1.jpg", "A_2.jpg"]

    def test_requires_counter(self):
        with pytest.raises(schema.SchemaError, match="no numeric field"):
            schema.compile_rule(["A", "B"], dest_root=None, renumber=True)

    def test_invalid_schema_reported_first(self):
        with pytest.raises(schema.SchemaError, match="forbidden"):
            schema.compile_rule(["A_B"], dest_root=None, renumber=True)


class TestInferFields:
    history = {
        "field_0": ["Nature", "City"],
        "field_1": ["Birds", "Paris"],
        "field_3": ["", "Spring"],
        "field_5": ["##", "####", "x"],
    }

    def test_no_history(self):
        assert schema.infer_fields("/p/abc_def_001.jpg", 6, {}) is None

    def test_stem_parts(self):
        assert schema.infer_fields("/p/Nature_Birds_Spring.jpg", 6, self.history) == [
            "Nature",
            "Birds",
            "",
            "Spring",
            "",
            "",
        ]

    def test_counter_width_from_history(self):
        assert schema.infer_fields("/p/Nature_001.jpg", 6, self.history) == [
            "Nature",
            "",
            "",
            "",
            "",
            "####",
        ]

    def test_counter_only(self):
        assert schema.infer_fields("/p/IMG_001.jpg", 6, self.history)[5] == "####"

    def test_no_counter_field(self):
        assert schema.infer_fields("/p/IMG_001.jpg", 6, {"field_0": ["A"]}) is None

    def test_monotone_order(self):
        # "Birds" before "Nature": Nature cannot go back to field 0.
        assert schema.infer_fields("/p/Birds_Nature.jpg", 6, self.history) == [
            "",
            "Birds",
            "",
            "",
            "",
            "",
        ]

    def test_parent_directories(self, tmp_path):
        path = tmp_path / "City" / "Paris" / "IMG_001.jpg"
        assert schema.infer_fields(str(path), 6, self.history)[:2] == [
            "City",
            "Paris",
        ]

    def test_root_directory(self):
        assert schema.infer_fields("/Nature.jpg", 6, self.history)[0] == "Nature"
