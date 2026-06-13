"""Tests for pbrenamer.core.filetools — transforms, rename engine, and disk I/O."""

import os

import pytest

from pbrenamer.core import filetools
from pbrenamer.core.replacement import FieldResolutionError, NewNumState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _p(name: str) -> str:
    """Return a fake absolute path for pure-function tests."""
    return f"/fake/dir/{name}"


def make_tree(root, spec: dict) -> None:
    """Recursively create files/dirs from a dict spec.

    spec: {name: None (empty file) | dict (subdirectory)}
    """
    for name, content in spec.items():
        path = root / name
        if content is None:
            path.touch()
        else:
            path.mkdir(exist_ok=True)
            make_tree(path, content)


# ---------------------------------------------------------------------------
# Text transforms (pure — no disk I/O)
# ---------------------------------------------------------------------------


class TestReplaceSpaces:
    @pytest.mark.parametrize(
        "mode, src, expected",
        [
            (0, "hello world", "hello_world"),
            (1, "hello_world", "hello world"),
            (2, "hello world", "hello.world"),
            (3, "hello.world", "hello world"),
            (4, "hello world", "hello-world"),
            (5, "hello-world", "hello world"),
        ],
    )
    def test_all_modes(self, mode, src, expected):
        name, _ = filetools.replace_spaces(src, _p(src), mode)
        assert name == expected


class TestReplaceCapitalization:
    @pytest.mark.parametrize(
        "mode, src, expected",
        [
            (0, "hello world", "HELLO WORLD"),
            (1, "HELLO WORLD", "hello world"),
            (2, "hello world", "Hello world"),
            (3, "hello world", "Hello World"),
        ],
    )
    def test_all_modes(self, mode, src, expected):
        name, _ = filetools.replace_capitalization(src, _p(src), mode)
        assert name == expected


class TestReplaceAccents:
    def test_strips_diacritics(self):
        name, _ = filetools.replace_accents("café résumé", _p("café résumé"))
        assert name == "cafe resume"

    def test_no_change_without_accents(self):
        name, _ = filetools.replace_accents("hello", _p("hello"))
        assert name == "hello"


class TestReplaceDuplicated:
    @pytest.mark.parametrize(
        "src, expected",
        [
            ("hello  world", "hello world"),
            ("a__b", "a_b"),
            ("a..b", "a.b"),
            ("a--b", "a-b"),
            ("hello", "hello"),
        ],
    )
    def test_collapses_separators(self, src, expected):
        name, _ = filetools.replace_duplicated(src, _p(src))
        assert name == expected


class TestInsertAt:
    def test_insert_at_start(self):
        name, _ = filetools.insert_at("world", _p("world"), "hello_", 0)
        assert name == "hello_world"

    def test_insert_in_middle(self):
        name, _ = filetools.insert_at("helloworld", _p("helloworld"), "_", 5)
        assert name == "hello_world"

    def test_append_with_negative_pos(self):
        name, _ = filetools.insert_at("hello", _p("hello"), "_world", -1)
        assert name == "hello_world"


class TestDeleteFrom:
    def test_delete_prefix(self):
        # "img_photo" → delete indices 0..3 inclusive → "photo"
        name, _ = filetools.delete_from("img_photo", _p("img_photo"), 0, 3)
        assert name == "photo"

    def test_delete_single_char(self):
        name, _ = filetools.delete_from("hello_world", _p("hello_world"), 5, 5)
        assert name == "helloworld"


class TestCutExtension:
    def test_with_extension(self):
        stem, _, ext = filetools.cut_extension("photo.jpg", _p("photo.jpg"))
        assert stem == "photo"
        assert ext == "jpg"

    def test_without_extension(self):
        stem, _, ext = filetools.cut_extension("README", _p("README"))
        assert stem == "README"
        assert ext == ""

    def test_multiple_dots_takes_last(self):
        stem, _, ext = filetools.cut_extension("archive.tar.gz", _p("archive.tar.gz"))
        assert stem == "archive.tar"
        assert ext == "gz"


class TestAddExtension:
    def test_adds_dot_extension(self):
        name, _ = filetools.add_extension("photo", _p("photo"), "jpg")
        assert name == "photo.jpg"

    def test_empty_extension_unchanged(self):
        name, _ = filetools.add_extension("photo", _p("photo"), "")
        assert name == "photo"

    def test_empty_name_unchanged(self):
        name, _ = filetools.add_extension("", _p(""), "jpg")
        assert name == ""


# ---------------------------------------------------------------------------
# Pattern-based rename engine (pure — no disk I/O)
# ---------------------------------------------------------------------------


class TestRenameUsingPatterns:
    def test_basic_letter_digit_pattern(self):
        # {L} = group 1, {#} = group 2
        name, path = filetools.rename_using_patterns(
            "IMG_001", _p("IMG_001"), "{L}_{#}", "photo_{2}", 1
        )
        assert name == "photo_001"
        assert path == _p("photo_001")

    def test_no_match_returns_none_pair(self):
        # Literal prefix forces a true non-match (no "IMG_" in "document")
        assert filetools.rename_using_patterns(
            "document", _p("document"), "IMG_{#}", "num_{1}", 1
        ) == (None, None)

    def test_counter_num_field(self):
        name, _ = filetools.rename_using_patterns(
            "file", _p("file"), "{X}", "{0}_{num}", 3
        )
        assert name == "file_3"

    def test_newnum_parameter_substituted(self):
        name, _ = filetools.rename_using_patterns(
            "file", _p("file"), "{X}", "item_{newnum}", 1, newnum=5
        )
        assert name == "item_5"

    def test_newnum_none_raises_field_error(self):
        with pytest.raises(FieldResolutionError):
            filetools.rename_using_patterns(
                "file", _p("file"), "{X}", "item_{newnum}", 1, newnum=None
            )

    def test_wildcard_x_matches_anything(self):
        name, _ = filetools.rename_using_patterns(
            "My Photo 2024", _p("My Photo 2024"), "{X}", "renamed", 1
        )
        assert name == "renamed"

    def test_non_capturing_at_token(self):
        # {@} should match but not consume a group number
        name, _ = filetools.rename_using_patterns(
            "prefix_content", _p("prefix_content"), "{@}_{C}", "{1}", 1
        )
        assert name == "content"

    def test_invalid_replacement_syntax_returns_none_pair(self):
        # {} is invalid syntax → _apply_replacement returns None → (None, None)
        assert filetools.rename_using_patterns("file", _p("file"), "{X}", "{}", 1) == (
            None,
            None,
        )

    def test_case_sensitive_no_match_on_wrong_case(self):
        assert filetools.rename_using_patterns(
            "img_001",
            _p("img_001"),
            "IMG_{#}",
            "photo_{1}",
            1,
            case_insensitive=False,
        ) == (None, None)

    def test_case_insensitive_matches_wrong_case(self):
        name, path = filetools.rename_using_patterns(
            "img_001",
            _p("img_001"),
            "IMG_{#}",
            "photo_{1}",
            1,
            case_insensitive=True,
        )
        assert name == "photo_001"
        assert path == _p("photo_001")

    def test_case_insensitive_letter_token(self):
        # {L} matches uppercase letters even when name is lowercase
        name, _ = filetools.rename_using_patterns(
            "abc_007",
            _p("abc_007"),
            "{L}_{#}",
            "{1}_photo_{2}",
            1,
            case_insensitive=True,
        )
        assert name == "abc_photo_007"


class TestRenameUsingPlainText:
    def test_basic_replace(self):
        name, _ = filetools.rename_using_plain_text(
            "IMG_001.jpg", _p("IMG_001.jpg"), "IMG", "photo"
        )
        assert name == "photo_001.jpg"

    def test_no_match_returns_none_pair(self):
        assert filetools.rename_using_plain_text(
            "photo.jpg", _p("photo.jpg"), "IMG", "photo"
        ) == (None, None)

    def test_replaces_all_occurrences(self):
        name, _ = filetools.rename_using_plain_text(
            "aa_bb_aa", _p("aa_bb_aa"), "aa", "cc"
        )
        assert name == "cc_bb_cc"

    def test_newnum_substitution(self):
        name, _ = filetools.rename_using_plain_text(
            "file_old", _p("file_old"), "old", "{newnum}", newnum=7
        )
        assert name == "file_7"

    def test_newnum_none_raises_field_error(self):
        with pytest.raises(FieldResolutionError):
            filetools.rename_using_plain_text(
                "file_old", _p("file_old"), "old", "{newnum}", newnum=None
            )

    def test_invalid_replacement_syntax_returns_none_pair(self):
        assert filetools.rename_using_plain_text("file_x", _p("file_x"), "x", "{}") == (
            None,
            None,
        )

    def test_case_sensitive_no_match_on_wrong_case(self):
        assert filetools.rename_using_plain_text(
            "img_001.jpg",
            _p("img_001.jpg"),
            "IMG",
            "photo",
            case_insensitive=False,
        ) == (None, None)

    def test_case_insensitive_matches_wrong_case(self):
        name, _ = filetools.rename_using_plain_text(
            "IMG_001.jpg",
            _p("IMG_001.jpg"),
            "img",
            "photo",
            case_insensitive=True,
        )
        assert name == "photo_001.jpg"

    def test_case_insensitive_replaces_all_occurrences(self):
        name, _ = filetools.rename_using_plain_text(
            "AA_bb_Aa",
            _p("AA_bb_Aa"),
            "aa",
            "cc",
            case_insensitive=True,
        )
        assert name == "cc_bb_cc"

    def test_case_insensitive_full_match_token(self):
        # {0} should expand to the actual matched text (preserving original case)
        name, _ = filetools.rename_using_plain_text(
            "Hello_World",
            _p("Hello_World"),
            "hello",
            "prefix_{0}",
            case_insensitive=True,
        )
        assert name == "prefix_Hello_World"

    def test_case_insensitive_no_match_returns_none_pair(self):
        assert filetools.rename_using_plain_text(
            "hello.txt", _p("hello.txt"), "xyz", "new", case_insensitive=True
        ) == (None, None)


class TestRenameUsingRegex:
    def test_basic_capture_group(self):
        name, _ = filetools.rename_using_regex(
            "IMG_001", _p("IMG_001"), r"IMG_(\d+)", "photo_{1}"
        )
        assert name == "photo_001"

    def test_no_match_returns_none_pair(self):
        assert filetools.rename_using_regex(
            "document", _p("document"), r"\d+", "num"
        ) == (None, None)

    def test_invalid_pattern_returns_none_pair(self):
        assert filetools.rename_using_regex("file", _p("file"), r"[invalid", "x") == (
            None,
            None,
        )

    def test_named_group(self):
        name, _ = filetools.rename_using_regex(
            "2024_photo",
            _p("2024_photo"),
            r"(?P<year>\d{4})_(?P<title>.+)",
            "{re:title}_{re:year}",
        )
        assert name == "photo_2024"

    def test_full_match_field(self):
        name, _ = filetools.rename_using_regex(
            "hello", _p("hello"), r"hello", "prefix_{0}"
        )
        assert name == "prefix_hello"

    def test_field_resolution_error_propagates(self):
        # {newnum} with no value raises FieldResolutionError (not silently (None, None))
        with pytest.raises(FieldResolutionError):
            filetools.rename_using_regex(
                "hello world", _p("hello world"), r"\w+", "{newnum}", newnum=None
            )

    def test_invalid_replacement_syntax_returns_none_pair(self):
        assert filetools.rename_using_regex("file", _p("file"), r"file", "{}") == (
            None,
            None,
        )

    def test_zero_width_match_is_skipped(self):
        # (?:) matches at every position (zero-width); the guard returns "" for each
        # empty match, leaving the original name unchanged.
        name, _ = filetools.rename_using_regex("hello", _p("hello"), r"(?:)", "X")
        assert name == "hello"

    def test_all_matches_replaced(self):
        # ([^.]+) matches "IMG_5100" and "jpeg"; both are substituted.
        name, _ = filetools.rename_using_regex(
            "IMG_5100.jpeg", _p("IMG_5100.jpeg"), r"([^.]+)", "{1}.jpg"
        )
        assert name == "IMG_5100.jpg.jpeg.jpg"

    def test_case_sensitive_no_match_on_wrong_case(self):
        assert filetools.rename_using_regex(
            "img_001",
            _p("img_001"),
            r"IMG_(\d+)",
            "photo_{1}",
            case_insensitive=False,
        ) == (None, None)

    def test_case_insensitive_matches_wrong_case(self):
        name, _ = filetools.rename_using_regex(
            "img_001",
            _p("img_001"),
            r"IMG_(\d+)",
            "photo_{1}",
            case_insensitive=True,
        )
        assert name == "photo_001"

    def test_case_insensitive_named_group(self):
        name, _ = filetools.rename_using_regex(
            "PHOTO_2024",
            _p("PHOTO_2024"),
            r"(?P<title>[a-z]+)_(?P<year>\d{4})",
            "{re:year}_{re:title}",
            case_insensitive=True,
        )
        assert name == "2024_PHOTO"


# ---------------------------------------------------------------------------
# File listing
# ---------------------------------------------------------------------------


class TestGetFileListing:
    def test_files_only(self, tmp_path):
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.txt").touch()
        (tmp_path / "subdir").mkdir()

        entries = filetools.get_file_listing(str(tmp_path), 0)
        names = [e[0] for e in entries]
        assert "a.txt" in names
        assert "b.txt" in names
        assert "subdir" not in names

    def test_dirs_only(self, tmp_path):
        (tmp_path / "a.txt").touch()
        (tmp_path / "subdir").mkdir()

        entries = filetools.get_file_listing(str(tmp_path), 1)
        names = [e[0] for e in entries]
        assert "subdir" in names
        assert "a.txt" not in names

    def test_both_files_and_dirs(self, tmp_path):
        (tmp_path / "a.txt").touch()
        (tmp_path / "subdir").mkdir()

        entries = filetools.get_file_listing(str(tmp_path), 2)
        names = [e[0] for e in entries]
        assert "a.txt" in names
        assert "subdir" in names

    def test_glob_pattern_filters(self, tmp_path):
        (tmp_path / "photo.jpg").touch()
        (tmp_path / "photo.png").touch()
        (tmp_path / "doc.txt").touch()

        entries = filetools.get_file_listing(str(tmp_path), 0, pattern="*.jpg")
        names = [e[0] for e in entries]
        assert names == ["photo.jpg"]

    def test_results_are_sorted_case_insensitive(self, tmp_path):
        for n in ["Zebra.txt", "apple.txt", "Mango.txt"]:
            (tmp_path / n).touch()

        entries = filetools.get_file_listing(str(tmp_path), 0)
        names = [e[0] for e in entries]
        assert names == sorted(names, key=str.lower)

    def test_full_paths_are_absolute(self, tmp_path):
        (tmp_path / "a.txt").touch()

        entries = filetools.get_file_listing(str(tmp_path), 0)
        for _, path in entries:
            assert os.path.isabs(path)


class TestGetFileListingRecursive:
    def test_finds_nested_files(self, tmp_path):
        (tmp_path / "a.txt").touch()
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.txt").touch()

        entries = filetools.get_file_listing_recursive(str(tmp_path), 0)
        names = [e[0] for e in entries]
        assert "a.txt" in names
        assert "b.txt" in names

    def test_subdirs_listed_before_root(self, tmp_path):
        """topdown=False guarantees nested files appear before root files."""
        (tmp_path / "root.txt").touch()
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").touch()

        entries = filetools.get_file_listing_recursive(str(tmp_path), 0)
        names = [e[0] for e in entries]
        assert names.index("nested.txt") < names.index("root.txt")

    def test_deeply_nested(self, tmp_path):
        make_tree(
            tmp_path,
            {"a": {"b": {"deep.txt": None}}, "root.txt": None},
        )
        entries = filetools.get_file_listing_recursive(str(tmp_path), 0)
        names = [e[0] for e in entries]
        assert "deep.txt" in names
        assert "root.txt" in names


# ---------------------------------------------------------------------------
# rename_file — disk I/O
# ---------------------------------------------------------------------------


class TestRenameFile:
    def test_simple_rename(self, tmp_path):
        src = tmp_path / "original.txt"
        dst = tmp_path / "renamed.txt"
        src.touch()

        ok, err = filetools.rename_file(str(src), str(dst))
        assert ok is True
        assert err is None
        assert dst.exists()
        assert not src.exists()

    def test_same_path_is_noop(self, tmp_path):
        f = tmp_path / "file.txt"
        f.touch()

        ok, err = filetools.rename_file(str(f), str(f))
        assert ok is True
        assert err is None
        assert f.exists()

    def test_target_exists_returns_error_and_preserves_source(self, tmp_path):
        src = tmp_path / "a.txt"
        dst = tmp_path / "b.txt"
        src.touch()
        dst.touch()

        ok, err = filetools.rename_file(str(src), str(dst))
        assert ok is False
        assert err is not None
        assert src.exists()
        assert dst.exists()

    def test_nonexistent_source_returns_error(self, tmp_path):
        src = tmp_path / "ghost.txt"
        dst = tmp_path / "target.txt"

        ok, err = filetools.rename_file(str(src), str(dst))
        assert ok is False
        assert err is not None

    def test_rename_into_subdir_creates_parent(self, tmp_path):
        src = tmp_path / "file.txt"
        src.touch()
        dst = tmp_path / "new_subdir" / "file.txt"

        # os.renames creates intermediate directories
        ok, _ = filetools.rename_file(str(src), str(dst))
        assert ok is True
        assert dst.exists()


# ---------------------------------------------------------------------------
# Full workflow — no extension
# ---------------------------------------------------------------------------


class TestRenameWorkflowNoExtension:
    def test_plain_text_rename_without_extension(self, tmp_path):
        (tmp_path / "README").touch()
        (tmp_path / "LICENSE").touch()

        for name, path in filetools.get_file_listing(str(tmp_path), 0):
            new_name, new_path = filetools.rename_using_plain_text(
                name, path, "README", "LISEZMOI"
            )
            if new_name is not None:
                filetools.rename_file(path, new_path)

        names = os.listdir(str(tmp_path))
        assert "LISEZMOI" in names
        assert "README" not in names
        assert "LICENSE" in names

    def test_pattern_rename_without_extension(self, tmp_path):
        for i in range(1, 4):
            (tmp_path / f"track{i:02d}").touch()

        for counter, (name, path) in enumerate(
            filetools.get_file_listing(str(tmp_path), 0), start=1
        ):
            new_name, new_path = filetools.rename_using_patterns(
                name, path, "track{#}", "song_{1}", counter
            )
            if new_name is not None:
                filetools.rename_file(path, new_path)

        assert sorted(os.listdir(str(tmp_path))) == ["song_01", "song_02", "song_03"]


# ---------------------------------------------------------------------------
# Full workflow — with extension (stem-only rename)
# ---------------------------------------------------------------------------


class TestRenameWorkflowWithExtension:
    def test_rename_stem_keep_extension(self, tmp_path):
        for i in range(1, 4):
            (tmp_path / f"IMG_{i:04d}.jpg").touch()

        for counter, (name, path) in enumerate(
            filetools.get_file_listing(str(tmp_path), 0), start=1
        ):
            stem, stem_path, ext = filetools.cut_extension(name, path)
            new_stem, new_stem_path = filetools.rename_using_patterns(
                stem, stem_path, "IMG_{#}", "photo_{1}", counter
            )
            if new_stem is not None:
                _, new_path = filetools.add_extension(new_stem, new_stem_path, ext)
                filetools.rename_file(path, new_path)

        assert sorted(os.listdir(str(tmp_path))) == [
            "photo_0001.jpg",
            "photo_0002.jpg",
            "photo_0003.jpg",
        ]

    def test_num_counter_with_extension(self, tmp_path):
        for i in range(1, 4):
            (tmp_path / f"scan{i}.pdf").touch()

        for counter, (name, path) in enumerate(
            filetools.get_file_listing(str(tmp_path), 0), start=1
        ):
            stem, stem_path, ext = filetools.cut_extension(name, path)
            new_stem, new_stem_path = filetools.rename_using_patterns(
                stem, stem_path, "{X}", "document_{num}", counter
            )
            if new_stem is not None:
                _, new_path = filetools.add_extension(new_stem, new_stem_path, ext)
                filetools.rename_file(path, new_path)

        assert sorted(os.listdir(str(tmp_path))) == [
            "document_1.pdf",
            "document_2.pdf",
            "document_3.pdf",
        ]

    def test_regex_rename_with_extension(self, tmp_path):
        for i in range(1, 4):
            (tmp_path / f"episode_{i:02d}.mkv").touch()

        for counter, (name, path) in enumerate(
            filetools.get_file_listing(str(tmp_path), 0), start=1
        ):
            stem, stem_path, ext = filetools.cut_extension(name, path)
            new_stem, new_stem_path = filetools.rename_using_regex(
                stem, stem_path, r"episode_(\d+)", "ep{1}"
            )
            if new_stem is not None:
                _, new_path = filetools.add_extension(new_stem, new_stem_path, ext)
                filetools.rename_file(path, new_path)

        assert sorted(os.listdir(str(tmp_path))) == [
            "ep01.mkv",
            "ep02.mkv",
            "ep03.mkv",
        ]

    def test_mixed_extensions_only_matching_renamed(self, tmp_path):
        (tmp_path / "photo_001.jpg").touch()
        (tmp_path / "photo_002.jpg").touch()
        (tmp_path / "notes.txt").touch()

        for counter, (name, path) in enumerate(
            filetools.get_file_listing(str(tmp_path), 0), start=1
        ):
            stem, stem_path, ext = filetools.cut_extension(name, path)
            new_stem, new_stem_path = filetools.rename_using_patterns(
                stem, stem_path, "photo_{#}", "img_{1}", counter
            )
            if new_stem is not None:
                _, new_path = filetools.add_extension(new_stem, new_stem_path, ext)
                filetools.rename_file(path, new_path)

        names = sorted(os.listdir(str(tmp_path)))
        assert "notes.txt" in names
        assert "img_001.jpg" in names
        assert "img_002.jpg" in names
        assert "photo_001.jpg" not in names


# ---------------------------------------------------------------------------
# Full workflow — recursive
# ---------------------------------------------------------------------------


class TestRenameWorkflowRecursive:
    def test_recursive_renames_files_in_all_subdirs(self, tmp_path):
        make_tree(
            tmp_path,
            {
                "IMG_001.jpg": None,
                "vacation": {
                    "IMG_002.jpg": None,
                    "IMG_003.jpg": None,
                },
            },
        )

        for counter, (name, path) in enumerate(
            filetools.get_file_listing_recursive(str(tmp_path), 0), start=1
        ):
            stem, stem_path, ext = filetools.cut_extension(name, path)
            new_stem, new_stem_path = filetools.rename_using_patterns(
                stem, stem_path, "IMG_{#}", "photo_{1}", counter
            )
            if new_stem is not None:
                _, new_path = filetools.add_extension(new_stem, new_stem_path, ext)
                filetools.rename_file(path, new_path)

        root_files = [
            n for n in os.listdir(str(tmp_path)) if os.path.isfile(str(tmp_path / n))
        ]
        sub_files = os.listdir(str(tmp_path / "vacation"))
        all_files = root_files + sub_files

        assert len(all_files) == 3
        assert not any(n.startswith("IMG_") for n in all_files)
        assert all(n.startswith("photo_") and n.endswith(".jpg") for n in all_files)

    def test_non_recursive_does_not_touch_subdirs(self, tmp_path):
        (tmp_path / "root.txt").touch()
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").touch()

        for name, path in filetools.get_file_listing(str(tmp_path), 0):
            new_name, new_path = filetools.rename_using_plain_text(
                name, path, ".txt", "_renamed.txt"
            )
            if new_name is not None:
                filetools.rename_file(path, new_path)

        assert (tmp_path / "root_renamed.txt").exists()
        assert not (tmp_path / "root.txt").exists()
        assert (sub / "nested.txt").exists()  # untouched

    def test_recursive_two_levels_deep(self, tmp_path):
        make_tree(
            tmp_path,
            {
                "a": {"b": {"deep.txt": None}, "mid.txt": None},
                "root.txt": None,
            },
        )

        entries = filetools.get_file_listing_recursive(str(tmp_path), 0)
        renamed = 0
        for name, path in entries:
            new_name, new_path = filetools.rename_using_plain_text(
                name, path, ".txt", ".bak"
            )
            if new_name is not None:
                ok, _ = filetools.rename_file(path, new_path)
                if ok:
                    renamed += 1

        assert renamed == 3
        assert (tmp_path / "root.bak").exists()
        assert (tmp_path / "a" / "mid.bak").exists()
        assert (tmp_path / "a" / "b" / "deep.bak").exists()


# ---------------------------------------------------------------------------
# Conflict handling
# ---------------------------------------------------------------------------


class TestConflictHandling:
    def test_rename_blocked_when_target_already_exists(self, tmp_path):
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.txt").touch()

        ok, err = filetools.rename_file(
            str(tmp_path / "a.txt"), str(tmp_path / "b.txt")
        )
        assert ok is False
        assert err is not None
        assert (tmp_path / "a.txt").exists()
        assert (tmp_path / "b.txt").exists()

    def test_two_files_mapping_to_same_target_second_blocked(self, tmp_path):
        """When two files produce the same target name, the second rename fails."""
        (tmp_path / "photo_a.jpg").touch()
        (tmp_path / "photo_b.jpg").touch()

        plan: list[tuple[str, str]] = []
        for name, path in filetools.get_file_listing(str(tmp_path), 0):
            stem, stem_path, ext = filetools.cut_extension(name, path)
            new_stem, new_stem_path = filetools.rename_using_patterns(
                stem, stem_path, "{X}", "fixed_name", 1
            )
            if new_stem is not None:
                _, new_path = filetools.add_extension(new_stem, new_stem_path, ext)
                plan.append((path, new_path))

        assert len(plan) == 2

        results = [filetools.rename_file(orig, new) for orig, new in plan]
        successes = sum(1 for ok, _ in results if ok)
        failures = sum(1 for ok, _ in results if not ok)
        assert successes == 1
        assert failures == 1

    def test_idempotent_same_name_is_noop(self, tmp_path):
        """Renaming a file to its own path must succeed without touching the file."""
        f = tmp_path / "photo.jpg"
        f.write_text("data")

        ok, err = filetools.rename_file(str(f), str(f))
        assert ok is True
        assert err is None
        assert f.read_text() == "data"


# ---------------------------------------------------------------------------
# {newnum} — conflict-free auto-numbering
# ---------------------------------------------------------------------------


class TestNewNum:
    def test_newnum_assigns_unique_numbers(self, tmp_path):
        for i in range(1, 4):
            (tmp_path / f"scan_{i}.pdf").touch()

        newnum_state = NewNumState(start=1)
        plan: list[tuple[str, str]] = []

        for name, path in filetools.get_file_listing(str(tmp_path), 0):
            stem, stem_path, ext = filetools.cut_extension(name, path)
            k = newnum_state.current
            while True:
                new_stem, new_stem_path = filetools.rename_using_patterns(
                    stem, stem_path, "{X}", "document_{newnum}", 1, newnum=k
                )
                if new_stem is None:
                    break
                _, new_path = filetools.add_extension(new_stem, new_stem_path, ext)
                new_name = os.path.basename(new_path)
                if new_name not in newnum_state.reserved:
                    newnum_state.reserved.add(new_name)
                    newnum_state.current = k + 1
                    plan.append((path, new_path))
                    break
                k += 1

        for orig, new in plan:
            ok, err = filetools.rename_file(orig, new)
            assert ok is True, f"Rename failed: {err}"

        assert sorted(os.listdir(str(tmp_path))) == [
            "document_1.pdf",
            "document_2.pdf",
            "document_3.pdf",
        ]

    def test_newnum_skips_pre_existing_file(self, tmp_path):
        """If document_1.pdf exists, the renamed file should become document_2.pdf."""
        (tmp_path / "document_1.pdf").touch()
        (tmp_path / "scan_a.pdf").touch()

        newnum_state = NewNumState(start=1)
        # Pre-reserve the already-existing name
        newnum_state.reserved.add("document_1.pdf")

        for name, path in filetools.get_file_listing(str(tmp_path), 0):
            if name == "document_1.pdf":
                continue
            stem, stem_path, ext = filetools.cut_extension(name, path)
            k = newnum_state.current
            while True:
                new_stem, new_stem_path = filetools.rename_using_patterns(
                    stem, stem_path, "{X}", "document_{newnum}", 1, newnum=k
                )
                if new_stem is None:
                    break
                _, new_path = filetools.add_extension(new_stem, new_stem_path, ext)
                new_name = os.path.basename(new_path)
                cand_path = os.path.join(str(tmp_path), new_name)
                if new_name not in newnum_state.reserved and not os.path.exists(
                    cand_path
                ):
                    newnum_state.reserved.add(new_name)
                    newnum_state.current = k + 1
                    filetools.rename_file(path, cand_path)
                    break
                k += 1

        names = sorted(os.listdir(str(tmp_path)))
        assert "document_1.pdf" in names
        assert "document_2.pdf" in names
        assert "scan_a.pdf" not in names

    def test_newnum_custom_start(self, tmp_path):
        """NewNumState(start=10) should produce document_10, document_11, …"""
        for i in range(1, 3):
            (tmp_path / f"file_{i}.txt").touch()

        newnum_state = NewNumState(start=10)
        plan: list[tuple[str, str]] = []

        for name, path in filetools.get_file_listing(str(tmp_path), 0):
            stem, stem_path, ext = filetools.cut_extension(name, path)
            k = newnum_state.current
            while True:
                new_stem, new_stem_path = filetools.rename_using_patterns(
                    stem, stem_path, "{X}", "item_{newnum}", 1, newnum=k
                )
                if new_stem is None:
                    break
                _, new_path = filetools.add_extension(new_stem, new_stem_path, ext)
                new_name = os.path.basename(new_path)
                if new_name not in newnum_state.reserved:
                    newnum_state.reserved.add(new_name)
                    newnum_state.current = k + 1
                    plan.append((path, new_path))
                    break
                k += 1

        for orig, new in plan:
            filetools.rename_file(orig, new)

        names = sorted(os.listdir(str(tmp_path)))
        assert names == ["item_10.txt", "item_11.txt"]

    def test_newnum_zero_padded(self, tmp_path):
        """Zero-padding format {newnum:03} should produce document_001, …"""
        for i in range(1, 4):
            (tmp_path / f"raw_{i}.jpg").touch()

        newnum_state = NewNumState(start=1)
        plan: list[tuple[str, str]] = []

        for name, path in filetools.get_file_listing(str(tmp_path), 0):
            stem, stem_path, ext = filetools.cut_extension(name, path)
            k = newnum_state.current
            while True:
                new_stem, new_stem_path = filetools.rename_using_patterns(
                    stem, stem_path, "{X}", "photo_{newnum:03}", 1, newnum=k
                )
                if new_stem is None:
                    break
                _, new_path = filetools.add_extension(new_stem, new_stem_path, ext)
                new_name = os.path.basename(new_path)
                if new_name not in newnum_state.reserved:
                    newnum_state.reserved.add(new_name)
                    newnum_state.current = k + 1
                    plan.append((path, new_path))
                    break
                k += 1

        for orig, new in plan:
            filetools.rename_file(orig, new)

        names = sorted(os.listdir(str(tmp_path)))
        assert names == ["photo_001.jpg", "photo_002.jpg", "photo_003.jpg"]


# ---------------------------------------------------------------------------
# Workflow helpers shared by the three mode test classes below
# ---------------------------------------------------------------------------


def _pat(stem, stem_path, search, replace, *, case_insensitive=False):
    """Thin wrapper for rename_using_patterns with a fixed counter."""
    return filetools.rename_using_patterns(
        stem, stem_path, search, replace, 1, case_insensitive=case_insensitive
    )


def _workflow(fn, src, search, replace, *, keep_ext: bool, case_insensitive: bool):
    """Simulate the main-window preview for one filename (no disk I/O).

    Returns the predicted new filename, or *src* unchanged when no match.
    """
    path = _p(src)
    if keep_ext:
        stem, stem_path, ext = filetools.cut_extension(src, path)
    else:
        stem, stem_path, ext = src, path, ""
    result, result_path = fn(
        stem, stem_path, search, replace, case_insensitive=case_insensitive
    )
    if result is None:
        return src
    return filetools.add_extension(result, result_path, ext)[0]


# ---------------------------------------------------------------------------
# Rename workflow — pattern mode
# ---------------------------------------------------------------------------


class TestPatternModeWorkflow:
    @pytest.mark.parametrize(
        "src, search, replace, expected, keep_ext, case_insensitive",
        [
            # keep_ext=True  case_sensitive  — replaces all "i" in stem only
            (
                "checking multi.img",
                "i",
                "-found-",
                "check-found-ng mult-found-.img",
                True,
                False,
            ),
            # keep_ext=False case_sensitive  — replaces all "i" in full name
            (
                "checking multi.img",
                "i",
                "-found-",
                "check-found-ng mult-found-.-found-mg",
                False,
                False,
            ),
            # keep_ext=False case_insensitive — "I" matches every "i"/"I"
            (
                "checking multi.img",
                "I",
                "-found-",
                "check-found-ng mult-found-.-found-mg",
                False,
                True,
            ),
            # keep_ext=True  case_sensitive  — "I" not in stem → no change
            ("checking multi.img", "I", "-found-", "checking multi.img", True, False),
        ],
    )
    def test_rename(self, src, search, replace, expected, keep_ext, case_insensitive):
        assert (
            _workflow(
                _pat,
                src,
                search,
                replace,
                keep_ext=keep_ext,
                case_insensitive=case_insensitive,
            )
            == expected
        )


# ---------------------------------------------------------------------------
# Rename workflow — regex mode
# ---------------------------------------------------------------------------


class TestRegexModeWorkflow:
    @pytest.mark.parametrize(
        "src, search, replace, expected, keep_ext, case_insensitive",
        [
            # ── basic character substitution ─────────────────────────────
            (
                "checking multi.img",
                "i",
                "-found-",
                "check-found-ng mult-found-.img",
                True,
                False,
            ),
            (
                "checking multi.img",
                "i",
                "-found-",
                "check-found-ng mult-found-.-found-mg",
                False,
                False,
            ),
            (
                "checking multi.img",
                "I",
                "-found-",
                "check-found-ng mult-found-.-found-mg",
                False,
                True,
            ),
            ("checking multi.img", "I", "-found-", "checking multi.img", True, False),
            # ── multi-occurrence of same character ───────────────────────
            (
                "checking multi.img",
                "c",
                "-found-",
                "-found-he-found-king multi.img",
                True,
                False,
            ),
            # ── start anchor ─────────────────────────────────────────────
            (
                "checking multi.img",
                "^c",
                "-found-",
                "-found-hecking multi.img",
                True,
                False,
            ),
            # ── end anchor, matches ───────────────────────────────────────
            (
                "checking multi.img",
                "i$",
                "-found-",
                "checking mult-found-.img",
                True,
                False,
            ),
            # ── end anchor, no match (stem ends with "i", not "g") ───────
            ("checking multi.img", "g$", "-found-", "checking multi.img", True, False),
            # ── end anchor on full name (ends with "g") ──────────────────
            (
                "checking multi.img",
                "g$",
                "-found-",
                "checking multi.im-found-",
                False,
                False,
            ),
            # ── anchored greedy pattern ──────────────────────────────────
            (
                "checking multi.img",
                "^c.+c",
                "-found-",
                "-found-king multi.img",
                True,
                False,
            ),
            # ── non-whitespace token, stem only ─────────────────────────
            (
                "checking multi.img",
                r"[^\s]+",
                "-found-",
                "-found- -found-.img",
                True,
                False,
            ),
            # ── non-whitespace token, full name ─────────────────────────
            (
                "checking multi.img",
                r"[^\s]+",
                "-found-",
                "-found- -found-",
                False,
                False,
            ),
            # ── literal-dot pattern on double extension, full name ───────
            (
                "IMG-20260509.JPG.JPG",
                r"\.JPG",
                ".jpg",
                "IMG-20260509.jpg.jpg",
                False,
                False,
            ),
            (
                "IMG-20260509ajpg.JPG.JPG",
                r"\.JPG",
                ".jpg",
                "IMG-20260509ajpg.jpg.jpg",
                False,
                False,
            ),
            # ── regex dot matches letter + case-insensitive ──────────────
            (
                "IMG-20260509ajpg.JPG.JPG",
                ".JPG",
                ".jpg",
                "IMG-20260509.jpg.jpg.jpg",
                False,
                True,
            ),
            # ── regex dot matches letter + case-sensitive ────────────────
            (
                "IMG-20260509ajpg.JPG.JPG",
                ".jpg",
                ".jpg",
                "IMG-20260509.jpg.JPG.JPG",
                False,
                False,
            ),
        ],
    )
    def test_rename(self, src, search, replace, expected, keep_ext, case_insensitive):
        assert (
            _workflow(
                filetools.rename_using_regex,
                src,
                search,
                replace,
                keep_ext=keep_ext,
                case_insensitive=case_insensitive,
            )
            == expected
        )


# ---------------------------------------------------------------------------
# Rename workflow — plain text mode
# ---------------------------------------------------------------------------


class TestPlainTextModeWorkflow:
    @pytest.mark.parametrize(
        "src, search, replace, expected, keep_ext, case_insensitive",
        [
            # ── basic character substitution ─────────────────────────────
            (
                "checking multi.img",
                "i",
                "-found-",
                "check-found-ng mult-found-.img",
                True,
                False,
            ),
            (
                "checking multi.img",
                "i",
                "-found-",
                "check-found-ng mult-found-.-found-mg",
                False,
                False,
            ),
            (
                "checking multi.img",
                "I",
                "-found-",
                "check-found-ng mult-found-.-found-mg",
                False,
                True,
            ),
            ("checking multi.img", "I", "-found-", "checking multi.img", True, False),
            # ── extension substring, stem only ───────────────────────────
            # uppercase search, case_sensitive → matches the .JPG in stem
            (
                "IMG-20260509.JPG.JPG",
                ".JPG",
                ".jpg",
                "IMG-20260509.jpg.JPG",
                True,
                False,
            ),
            # lowercase search, case_insensitive → same visual result
            (
                "IMG-20260509.JPG.JPG",
                ".jpg",
                ".jpg",
                "IMG-20260509.jpg.JPG",
                True,
                True,
            ),
            # ── extension substring, full name ───────────────────────────
            # uppercase search, case_sensitive → replaces both .JPG
            (
                "IMG-20260509.JPG.JPG",
                ".JPG",
                ".jpg",
                "IMG-20260509.jpg.jpg",
                False,
                False,
            ),
            # lowercase search, case_sensitive → .JPG not found → no change
            (
                "IMG-20260509.JPG.JPG",
                ".jpg",
                ".jpg",
                "IMG-20260509.JPG.JPG",
                False,
                False,
            ),
            # lowercase search, case_insensitive → replaces both .JPG
            (
                "IMG-20260509.JPG.JPG",
                ".jpg",
                ".jpg",
                "IMG-20260509.jpg.jpg",
                False,
                True,
            ),
        ],
    )
    def test_rename(self, src, search, replace, expected, keep_ext, case_insensitive):
        assert (
            _workflow(
                filetools.rename_using_plain_text,
                src,
                search,
                replace,
                keep_ext=keep_ext,
                case_insensitive=case_insensitive,
            )
            == expected
        )
