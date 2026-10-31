"""Tests for pbrenamer.core.sidecar — sidecar file detection and grouping."""

import pytest

from pbrenamer.core import sidecar


def _p(name: str, directory: str = "/fake/dir") -> str:
    return f"{directory}/{name}"


def _config(
    *,
    image_ext=("jpg", "png"),
    video_ext=("avi",),
    audio_ext=("mp3",),
    image_suf=("xml", "xmp"),
    video_suf=(),
    audio_suf=(),
    other_suf=(),
    common_suf=(),
) -> sidecar.SidecarConfig:
    return sidecar.SidecarConfig(
        base_extensions={
            "image": frozenset(image_ext),
            "video": frozenset(video_ext),
            "audio": frozenset(audio_ext),
        },
        own_suffixes={
            "image": frozenset(image_suf),
            "video": frozenset(video_suf),
            "audio": frozenset(audio_suf),
            "other": frozenset(other_suf),
        },
        common_suffixes=frozenset(common_suf),
    )


def _sensitive(_directory: str) -> bool:
    return True


def _insensitive(_directory: str) -> bool:
    return False


class TestSidecarConfig:
    def test_effective_suffixes_unions_common(self) -> None:
        config = _config(image_suf=("xmp",), common_suf=("meta",))
        assert config.effective_suffixes("image") == {"xmp", "meta"}

    def test_effective_suffixes_unknown_category_is_just_common(self) -> None:
        config = _config(common_suf=("meta",))
        assert config.effective_suffixes("bogus") == {"meta"}

    def test_category_of_extension_matches_configured_list(self) -> None:
        config = _config(image_ext=("jpg",), video_ext=("avi",))
        assert config.category_of_extension("jpg") == "image"
        assert config.category_of_extension("avi") == "video"

    def test_category_of_extension_uppercase_normalizes(self) -> None:
        config = _config(image_ext=("jpg",))
        assert config.category_of_extension("JPG") == "image"

    def test_category_of_extension_unmatched_is_other(self) -> None:
        config = _config()
        assert config.category_of_extension("xyz") == "other"

    def test_defaults_cover_all_categories(self) -> None:
        config = sidecar.SidecarConfig.defaults()
        assert config.category_of_extension("jpg") == "image"
        assert config.category_of_extension("mp4") == "video"
        assert config.category_of_extension("mp3") == "audio"
        assert "xmp" in config.effective_suffixes("image")


class TestBuildSidecarGroupsBasics:
    def test_empty_file_list(self) -> None:
        result = sidecar.build_sidecar_groups([], _config())
        assert result.sidecar_of == {}
        assert result.groups == {}
        assert result.errors == {}

    def test_no_dot_file_is_other_category_no_crash(self) -> None:
        files = [("README", _p("README"))]
        result = sidecar.build_sidecar_groups(files, _config())
        assert result.sidecar_of == {}
        assert result.errors == {}

    def test_unrelated_files_are_not_grouped(self) -> None:
        files = [("a.jpg", _p("a.jpg")), ("b.avi", _p("b.avi"))]
        result = sidecar.build_sidecar_groups(files, _config())
        assert result.sidecar_of == {}
        assert result.groups == {}
        assert result.errors == {}

    def test_sidecar_candidate_with_no_owner_is_ungrouped(self) -> None:
        # ".xml" is an image sidecar suffix but no image base exists here.
        files = [("xxx.xml", _p("xxx.xml")), ("xxx.avi", _p("xxx.avi"))]
        result = sidecar.build_sidecar_groups(files, _config())
        assert result.sidecar_of == {}
        assert result.errors == {}


class TestUnambiguousGrouping:
    def test_single_sidecar_joins_base(self) -> None:
        base = _p("img.jpg")
        side = _p("img.xmp")
        files = [("img.jpg", base), ("img.xmp", side)]
        result = sidecar.build_sidecar_groups(files, _config())
        assert result.sidecar_of == {side: base}
        assert result.groups == {base: [side]}
        assert result.sidecar_suffix == {side: "xmp"}
        assert result.errors == {}

    def test_multiple_sidecars_share_one_base(self) -> None:
        base = _p("img.jpg")
        xmp = _p("img.xmp")
        xml = _p("img.xml")
        files = [("img.jpg", base), ("img.xmp", xmp), ("img.xml", xml)]
        result = sidecar.build_sidecar_groups(files, _config())
        assert result.sidecar_of == {xmp: base, xml: base}
        assert sorted(result.groups[base]) == sorted([xmp, xml])
        assert result.errors == {}

    def test_suffix_only_declared_for_image_ignores_video_owner(self) -> None:
        # ".xml" is only an image sidecar suffix: xxx.avi is never a
        # candidate owner, so xxx.xml unambiguously joins xxx.png (image).
        png = _p("xxx.png")
        avi = _p("xxx.avi")
        xml = _p("xxx.xml")
        files = [("xxx.png", png), ("xxx.avi", avi), ("xxx.xml", xml)]
        result = sidecar.build_sidecar_groups(files, _config())
        assert result.sidecar_of == {xml: png}
        assert avi not in result.groups
        assert result.errors == {}

    def test_longest_suffix_wins_within_category(self) -> None:
        base = _p("xxx.jpg")
        side = _p("xxx.info.xml")
        files = [("xxx.jpg", base), ("xxx.info.xml", side)]
        config = _config(image_suf=("xml", "info.xml"))
        result = sidecar.build_sidecar_groups(files, config)
        assert result.sidecar_of == {side: base}
        assert result.sidecar_suffix[side] == "info.xml"

    def test_common_suffix_applies_to_every_category(self) -> None:
        base = _p("clip.avi")
        side = _p("clip.meta")
        files = [("clip.avi", base), ("clip.meta", side)]
        config = _config(video_suf=(), common_suf=("meta",))
        result = sidecar.build_sidecar_groups(files, config)
        assert result.sidecar_of == {side: base}

    def test_sidecar_never_matches_itself_as_owner(self) -> None:
        # "clip.meta" is itself registered as an "other"-category base
        # (stem "clip") since its own extension ("meta") isn't a
        # recognized image/video/audio extension. The common suffix
        # "meta" also makes it a sidecar candidate for every category,
        # including "other" — it must not resolve to itself as owner.
        base = _p("clip.avi")
        side = _p("clip.meta")
        files = [("clip.avi", base), ("clip.meta", side)]
        config = _config(common_suf=("meta",))
        result = sidecar.build_sidecar_groups(files, config)
        assert result.sidecar_of == {side: base}
        assert result.errors == {}


class TestAmbiguousGrouping:
    def test_two_bases_same_category_is_ambiguous(self) -> None:
        # xxx.xml + xxx.jpg + xxx.png: ".xml" is an image sidecar suffix,
        # and both xxx.jpg and xxx.png are image bases with the same stem.
        xml = _p("xxx.xml")
        jpg = _p("xxx.jpg")
        png = _p("xxx.png")
        files = [("xxx.xml", xml), ("xxx.jpg", jpg), ("xxx.png", png)]
        result = sidecar.build_sidecar_groups(files, _config())
        assert set(result.errors) == {xml, jpg, png}
        assert result.sidecar_of == {}
        for path in (xml, jpg, png):
            assert "xxx.xml" in result.errors[path]

    def test_two_bases_different_categories_is_ambiguous(self) -> None:
        # ".xml" declared as a sidecar suffix for both image and video.
        xml = _p("xxx.xml")
        png = _p("xxx.png")
        avi = _p("xxx.avi")
        files = [("xxx.xml", xml), ("xxx.png", png), ("xxx.avi", avi)]
        config = _config(image_suf=("xml",), video_suf=("xml",))
        result = sidecar.build_sidecar_groups(files, config)
        assert set(result.errors) == {xml, png, avi}
        assert result.sidecar_of == {}

    def test_error_message_names_the_conflicting_files(self) -> None:
        xml = _p("xxx.xml")
        jpg = _p("xxx.jpg")
        png = _p("xxx.png")
        files = [("xxx.xml", xml), ("xxx.jpg", jpg), ("xxx.png", png)]
        result = sidecar.build_sidecar_groups(files, _config())
        msg = result.errors[xml]
        assert "xxx.jpg" in msg
        assert "xxx.png" in msg


class TestDirectoryScoping:
    def test_grouping_never_crosses_directories(self) -> None:
        base_a = _p("img.jpg", "/dir/a")
        side_a = _p("img.xmp", "/dir/a")
        base_b = _p("img.jpg", "/dir/b")
        files = [
            ("img.jpg", base_a),
            ("img.xmp", side_a),
            ("img.jpg", base_b),
        ]
        result = sidecar.build_sidecar_groups(files, _config())
        assert result.sidecar_of == {side_a: base_a}
        assert base_b not in result.groups


class TestCaseSensitivity:
    def test_case_insensitive_directory_matches_suffix_regardless_of_case(
        self,
    ) -> None:
        base = _p("img.jpg")
        side = _p("IMG.XMP")
        files = [("img.jpg", base), ("IMG.XMP", side)]
        result = sidecar.build_sidecar_groups(
            files, _config(), is_case_sensitive=_insensitive
        )
        assert result.sidecar_of == {side: base}
        # verbatim suffix is preserved as found on disk, not folded
        assert result.sidecar_suffix[side] == "XMP"

    def test_case_sensitive_directory_requires_exact_suffix_case(self) -> None:
        base = _p("img.jpg")
        side = _p("IMG.XMP")
        files = [("img.jpg", base), ("IMG.XMP", side)]
        result = sidecar.build_sidecar_groups(
            files, _config(), is_case_sensitive=_sensitive
        )
        assert result.sidecar_of == {}
        assert result.errors == {}


# ---------------------------------------------------------------------------
# Helpers for the file list: empty sidecars, sidecars on disk, content filter
# ---------------------------------------------------------------------------


def _listing(directory):
    return sorted((p.name, str(p)) for p in directory.iterdir() if p.is_file())


class TestAllSuffixes:
    def test_union(self):
        config = sidecar.SidecarConfig(
            base_extensions={},
            own_suffixes={"image": frozenset({"xmp"}), "video": frozenset({"srt"})},
            common_suffixes=frozenset({"txt"}),
        )
        assert sidecar.all_suffixes(config) == {"xmp", "srt", "txt"}


class TestEmptySidecars:
    def test_only_empty_sidecar_names(self, tmp_path):
        config = sidecar.SidecarConfig.defaults()
        (tmp_path / "a.jpg").write_bytes(b"")
        (tmp_path / "a.xmp").write_bytes(b"")
        (tmp_path / "b.XMP").write_bytes(b"")
        (tmp_path / "c.xmp").write_text("x")
        (tmp_path / ".xmp").write_bytes(b"")
        (tmp_path / "d.xmp").mkdir()
        paths = [str(p) for p in tmp_path.iterdir()] + [str(tmp_path / "gone.xmp")]
        assert sorted(sidecar.empty_sidecars(paths, config)) == [
            str(tmp_path / "a.xmp"),
            str(tmp_path / "b.XMP"),
        ]

    def test_stat_error_skipped(self, tmp_path, monkeypatch):
        f = tmp_path / "a.xmp"
        f.write_bytes(b"")

        def boom(_path):
            raise OSError("denied")

        monkeypatch.setattr(sidecar.os.path, "getsize", boom)
        config = sidecar.SidecarConfig.defaults()
        assert sidecar.empty_sidecars([str(f)], config) == []


class TestOrphanSidecars:
    def test_orphans(self):
        config = _config()
        files = [
            (n, _p(n))
            for n in ["a.jpg", "a.xmp", "b.XMP", "c.xml", "x.png.xmp", "notes.txt"]
        ]
        files += [("d.png", _p("d.png")), ("d.jpg", _p("d.jpg"))]
        files += [("d.xmp", _p("d.xmp")), (".xmp", _p(".xmp")), ("e", _p("e"))]
        result = sidecar.build_sidecar_groups(
            files, config, is_case_sensitive=_sensitive
        )
        assert sidecar.orphan_sidecars(files, result, config) == [
            _p("b.XMP"),
            _p("c.xml"),
            _p("x.png.xmp"),
        ]

    def test_media_file_is_never_orphan(self):
        config = _config(image_suf=("jpg",))
        files = [("a.jpg", _p("a.jpg"))]
        result = sidecar.build_sidecar_groups(files, config)
        assert sidecar.orphan_sidecars(files, result, config) == []


class TestSidecarsOnDisk:
    def test_found_per_directory(self, tmp_path):
        config = sidecar.SidecarConfig.defaults()
        d1, d2 = tmp_path / "d1", tmp_path / "d2"
        d1.mkdir()
        d2.mkdir()
        for f in ("a.jpg", "a.xmp", "a.info", "b.jpg"):
            (d1 / f).write_text("x")
        (d2 / "c.jpg").write_text("x")
        (d2 / "c.xmp").write_text("x")
        (d1 / "sub.xmp").mkdir()
        result = sidecar.sidecars_on_disk(
            [str(d1 / "a.jpg"), str(d1 / "b.jpg"), str(d2 / "c.jpg"), str(d1)],
            config,
        )
        assert result == {
            str(d1 / "a.jpg"): [str(d1 / "a.info"), str(d1 / "a.xmp")],
            str(d2 / "c.jpg"): [str(d2 / "c.xmp")],
        }

    def test_unreadable_directory(self, tmp_path, monkeypatch):
        f = tmp_path / "a.jpg"
        f.write_text("x")

        def boom(_path):
            raise OSError("denied")

        monkeypatch.setattr(sidecar.os, "listdir", boom)
        config = sidecar.SidecarConfig.defaults()
        assert sidecar.sidecars_on_disk([str(f)], config) == {}


class TestContentCache:
    def test_reads_and_caches(self, tmp_path, monkeypatch):
        f = tmp_path / "a.xmp"
        f.write_text("Hello")
        cache = sidecar.ContentCache()
        assert cache.text(str(f)) == "Hello"
        opened = []
        real_open = open
        monkeypatch.setattr(
            "builtins.open", lambda *a, **k: opened.append(a) or real_open(*a, **k)
        )
        assert cache.text(str(f)) == "Hello"
        assert opened == []

    def test_reread_when_modified(self, tmp_path):
        import os

        f = tmp_path / "a.xmp"
        f.write_text("old")
        cache = sidecar.ContentCache()
        cache.text(str(f))
        f.write_text("new")
        os.utime(f, (1, 1))
        assert cache.text(str(f)) == "new"

    def test_invalid_utf8_replaced(self, tmp_path):
        f = tmp_path / "a.xmp"
        f.write_bytes(b"caf\xe9")
        assert sidecar.ContentCache().text(str(f)) == "caf�"

    def test_missing(self, tmp_path):
        cache = sidecar.ContentCache()
        assert cache.text(str(tmp_path / "gone.xmp")) is None

    def test_unreadable(self, tmp_path):
        d = tmp_path / "dir.xmp"
        d.mkdir()
        assert sidecar.ContentCache().text(str(d)) is None


class TestFilterByContent:
    @pytest.fixture
    def listing(self, tmp_path):
        (tmp_path / "a.jpg").write_text("x")
        (tmp_path / "a.xmp").write_text("<dc:subject>\n  Été à Paris\n</dc:subject>")
        (tmp_path / "b.jpg").write_text("x")
        (tmp_path / "b.xmp").write_text("Lyon")
        (tmp_path / "b.info").write_text("rating=5")
        (tmp_path / "c.jpg").write_text("x")
        (tmp_path / "notes.txt").write_text("Paris")
        entries = _listing(tmp_path)
        groups = sidecar.build_sidecar_groups(entries, sidecar.SidecarConfig.defaults())
        return entries, groups

    def _names(self, entries):
        return [name for name, _ in entries]

    def test_matching_groups_kept(self, listing):
        entries, groups = listing
        regex = sidecar.compile_content_filter("paris")
        kept = sidecar.filter_by_content(entries, groups, regex)
        assert self._names(kept) == ["a.jpg", "a.xmp"]

    def test_any_sidecar_of_group(self, listing):
        entries, groups = listing
        regex = sidecar.compile_content_filter("rating=5")
        kept = sidecar.filter_by_content(entries, groups, regex)
        assert self._names(kept) == ["b.info", "b.jpg", "b.xmp"]

    def test_dotall_and_accents(self, listing):
        entries, groups = listing
        regex = sidecar.compile_content_filter("subject>.*ÉTÉ")
        kept = sidecar.filter_by_content(entries, groups, regex)
        assert self._names(kept) == ["a.jpg", "a.xmp"]

    def test_no_match(self, listing):
        entries, groups = listing
        regex = sidecar.compile_content_filter("Marseille")
        assert sidecar.filter_by_content(entries, groups, regex) == []

    def test_unreadable_sidecar_skipped(self, listing, tmp_path):
        entries, groups = listing
        (tmp_path / "a.xmp").unlink()
        regex = sidecar.compile_content_filter(".")
        kept = sidecar.filter_by_content(entries, groups, regex)
        assert self._names(kept) == ["b.info", "b.jpg", "b.xmp"]

    def test_invalid_pattern(self):
        import re

        with pytest.raises(re.error):
            sidecar.compile_content_filter("(")


class TestSidecarNamedOtherFiles:
    """An "other" file named like a sidecar is never a base (anomaly 5.2)."""

    def test_common_suffixes_do_not_make_xmp_a_competing_base(self) -> None:
        names = ["c_0001.jpg", "c_0001.xmp", "c_0001.info.json", "c_0001.prompt.txt"]
        files = [(n, _p(n)) for n in names]
        config = _config(image_suf=("xmp",), common_suf=("info.json", "prompt.txt"))
        result = sidecar.build_sidecar_groups(files, config)
        assert result.errors == {}
        assert sorted(result.groups[_p("c_0001.jpg")]) == sorted(
            _p(n) for n in names[1:]
        )

    def test_case_insensitive_directory(self) -> None:
        names = ["c.jpg", "C.XMP", "c.info.json"]
        files = [(n, _p(n)) for n in names]
        config = _config(image_suf=("xmp",), common_suf=("info.json",))
        result = sidecar.build_sidecar_groups(
            files, config, is_case_sensitive=_insensitive
        )
        assert result.errors == {}
        assert len(result.groups[_p("c.jpg")]) == 2

    def test_other_file_not_named_like_sidecar_stays_a_base(self) -> None:
        files = [("doc.pdf", _p("doc.pdf")), ("doc.note", _p("doc.note"))]
        config = _config(other_suf=("note",))
        result = sidecar.build_sidecar_groups(files, config)
        assert result.sidecar_of == {_p("doc.note"): _p("doc.pdf")}
