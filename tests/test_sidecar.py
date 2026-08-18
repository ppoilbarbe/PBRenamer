"""Tests for pbrenamer.core.sidecar — sidecar file detection and grouping."""

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
