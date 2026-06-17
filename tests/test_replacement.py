"""Tests for pbrenamer.core.replacement — parser, validator, formatter, substitutor."""

import datetime
from unittest.mock import patch

import pytest

from pbrenamer.core.replacement import (
    SEARCH_PATTERN,
    SEARCH_PLAIN,
    SEARCH_REGEX,
    FieldResolutionError,
    FieldSegment,
    LiteralSegment,
    ReplacementSyntaxError,
    parse,
    substitute,
    validate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.datetime(2024, 6, 15, 10, 30, 45)


def _sub(template: str, *, path: str = "/dir/file.txt", counter: int = 1, **kw) -> str:
    defaults = dict(full_match=None, groups=[], named_groups={}, now=_NOW, newnum=None)
    defaults.update(kw)
    return substitute(parse(template), path=path, counter=counter, **defaults)


# ---------------------------------------------------------------------------
# ReplacementSyntaxError
# ---------------------------------------------------------------------------


class TestReplacementSyntaxError:
    def test_raw_attribute_stored(self):
        err = ReplacementSyntaxError("bad syntax", raw="{bad}")
        assert err.raw == "{bad}"

    def test_raw_defaults_to_empty(self):
        err = ReplacementSyntaxError("bad syntax")
        assert err.raw == ""


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class TestParse:
    def test_literal_only(self):
        segs = parse("hello")
        assert len(segs) == 1
        assert isinstance(segs[0], LiteralSegment)
        assert segs[0].text == "hello"

    def test_double_brace_becomes_literal(self):
        segs = parse("a{{b")
        texts = [s.text for s in segs if isinstance(s, LiteralSegment)]
        assert "{" in texts

    def test_field_segment_parsed(self):
        segs = parse("{num}")
        assert any(isinstance(s, FieldSegment) and s.name == "num" for s in segs)

    def test_empty_field_raises(self):
        with pytest.raises(ReplacementSyntaxError) as exc_info:
            parse("{}")
        assert exc_info.value.raw == "{}"

    def test_unknown_field_raises(self):
        with pytest.raises(ReplacementSyntaxError) as exc_info:
            parse("{totally_unknown}")
        assert "totally_unknown" in str(exc_info.value)

    def test_unmatched_brace_raises(self):
        with pytest.raises(ReplacementSyntaxError):
            parse("prefix { no close")

    def test_ex_field_valid(self):
        segs = parse("{im:Make}")
        assert any(isinstance(s, FieldSegment) and s.name == "im:Make" for s in segs)

    def test_mu_field_valid(self):
        segs = parse("{au:title}")
        assert any(isinstance(s, FieldSegment) and s.name == "au:title" for s in segs)

    def test_mu_field_with_options(self):
        segs = parse("{au:title::untitled}")
        field = next(s for s in segs if isinstance(s, FieldSegment))
        assert field.name == "au:title"
        assert field.default == "untitled"

    def test_mu_field_with_fmt(self):
        # "02:00" → align="0", fmt="2", default="00"
        segs = parse("{au:tracknumber:02:00}")
        field = next(s for s in segs if isinstance(s, FieldSegment))
        assert field.name == "au:tracknumber"
        assert field.align == "0"
        assert field.fmt == "2"
        assert field.default == "00"

    def test_vi_field_valid(self):
        segs = parse("{vi:width}")
        assert any(isinstance(s, FieldSegment) and s.name == "vi:width" for s in segs)

    def test_vi_field_with_options(self):
        segs = parse("{vi:videocodec::unknown}")
        field = next(s for s in segs if isinstance(s, FieldSegment))
        assert field.name == "vi:videocodec"
        assert field.default == "unknown"

    def test_re_field_valid(self):
        segs = parse("{re:year}")
        assert any(isinstance(s, FieldSegment) and s.name == "re:year" for s in segs)

    def test_ex_field_with_options(self):
        # {im:Make::default} — empty fmt, then default after second colon
        segs = parse("{im:Make::unknown}")
        field = next(s for s in segs if isinstance(s, FieldSegment))
        assert field.name == "im:Make"
        assert field.default == "unknown"

    def test_field_with_default(self):
        segs = parse("{1::fallback}")
        field = next(s for s in segs if isinstance(s, FieldSegment))
        assert field.default == "fallback"

    def test_field_with_align_left(self):
        segs = parse("{num:<8}")
        field = next(s for s in segs if isinstance(s, FieldSegment))
        assert field.align == "<"
        assert field.fmt == "8"

    def test_field_with_align_right(self):
        segs = parse("{num:>8}")
        field = next(s for s in segs if isinstance(s, FieldSegment))
        assert field.align == ">"
        assert field.fmt == "8"

    def test_field_with_case_lower(self):
        segs = parse("{0:-}")
        field = next(s for s in segs if isinstance(s, FieldSegment))
        assert field.case == "-"
        assert field.align == ""
        assert field.fmt == ""

    def test_field_with_case_and_align(self):
        segs = parse("{0:*^10}")
        field = next(s for s in segs if isinstance(s, FieldSegment))
        assert field.case == "*"
        assert field.align == "^"
        assert field.fmt == "10"

    def test_field_with_case_align_default(self):
        segs = parse("{0:*^10:fallback}")
        field = next(s for s in segs if isinstance(s, FieldSegment))
        assert field.case == "*"
        assert field.align == "^"
        assert field.fmt == "10"
        assert field.default == "fallback"


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class TestValidate:
    def test_group_in_plain_mode_reports_error(self):
        segs = parse("{1}")
        errors = validate(segs, SEARCH_PLAIN)
        assert len(errors) == 1
        assert "plain-text" in errors[0]

    def test_re_field_in_non_regex_mode_reports_error(self):
        segs = parse("{re:year}")
        errors = validate(segs, SEARCH_PLAIN)
        assert len(errors) == 1
        assert "regex" in errors[0]

    def test_re_field_in_regex_mode_no_error(self):
        segs = parse("{re:year}")
        assert validate(segs, SEARCH_REGEX) == []

    def test_plain_field_in_any_mode_no_error(self):
        segs = parse("{num}")
        assert validate(segs, SEARCH_PLAIN) == []
        assert validate(segs, SEARCH_REGEX) == []
        assert validate(segs, SEARCH_PATTERN) == []

    def test_literal_segment_ignored(self):
        segs = parse("just text")
        assert validate(segs, SEARCH_PLAIN) == []


# ---------------------------------------------------------------------------
# Align formatting
# ---------------------------------------------------------------------------


class TestApplyAlign:
    def test_zero_pad(self):
        assert _sub("{num:03}") == "001"

    def test_left_justify(self):
        result = _sub("{num:<5}")
        assert result == "1    "

    def test_right_justify(self):
        result = _sub("{num:>5}")
        assert result == "    1"

    def test_no_align_no_pad(self):
        assert _sub("{num}") == "1"

    def test_center_align_even_padding(self):
        # "ab" in width 6: pad=4, left=2, right=2
        result = _sub("{0:^6}", full_match="ab")
        assert result == "  ab  "

    def test_center_align_odd_padding(self):
        # "ab" in width 7: pad=5, left_pad=(5+1)//2=3, right_pad=2
        result = _sub("{0:^7}", full_match="ab")
        assert result == "   ab  "

    def test_center_align_string_longer_than_width(self):
        result = _sub("{0:^3}", full_match="abcde")
        assert result == "abcde"


class TestApplyCase:
    def test_lowercase(self):
        assert _sub("{0:-}", full_match="HELLO World") == "hello world"

    def test_uppercase(self):
        assert _sub("{0:+}", full_match="hello world") == "HELLO WORLD"

    def test_capitalize(self):
        assert _sub("{0:!}", full_match="hello world") == "Hello world"

    def test_capitalize_rest_lowercased(self):
        assert _sub("{0:!}", full_match="hELLO WORLD") == "Hello world"

    def test_title(self):
        assert _sub("{0:*}", full_match="hello world") == "Hello World"

    def test_unchanged_explicit(self):
        assert _sub("{0:=}", full_match="Hello World") == "Hello World"

    def test_no_case_modifier(self):
        assert _sub("{0}", full_match="Hello World") == "Hello World"

    def test_case_with_align(self):
        # "*^10" on "hi": title="Hi" (len 2), pad=8, left=4, right=4
        result = _sub("{0:*^10}", full_match="hi")
        assert result == "    Hi    "

    def test_case_applied_to_default(self):
        # Field absent, default "hello" with uppercase modifier
        result = _sub("{2:+:hello}", groups=[])
        assert result == "HELLO"

    def test_unknown_case_value_returns_string_unchanged(self):
        from pbrenamer.core.replacement import _apply_case

        assert _apply_case("Hello", "?") == "Hello"


# ---------------------------------------------------------------------------
# Substitutor — simple fields
# ---------------------------------------------------------------------------


class TestSubstituteFields:
    def test_full_match(self):
        assert _sub("{0}", full_match="IMG_001") == "IMG_001"

    def test_capture_group(self):
        assert _sub("{1}", groups=["hello"]) == "hello"

    def test_capture_group_out_of_range_uses_default(self):
        assert _sub("{2::missing}", groups=["only_one"]) == "missing"

    def test_capture_group_out_of_range_no_default_raises(self):
        with pytest.raises(FieldResolutionError):
            _sub("{2}", groups=["only_one"])

    def test_named_group(self):
        assert _sub("{re:year}", named_groups={"year": "2024"}) == "2024"

    def test_named_group_missing_uses_default(self):
        assert _sub("{re:year::????}", named_groups={}) == "????"

    def test_named_group_missing_no_default_raises(self):
        with pytest.raises(FieldResolutionError):
            _sub("{re:year}", named_groups={})

    def test_num_counter(self):
        assert _sub("{num}", counter=7) == "7"

    def test_num_with_start_offset(self):
        # {num::10} — default encodes start offset: 1 + 10 - 1 = 10
        assert _sub("{num::10}", counter=1) == "10"
        assert _sub("{num::10}", counter=2) == "11"

    def test_date_field(self):
        result = _sub("{date}")
        assert result == "2024-06-15"

    def test_date_field_custom_fmt(self):
        result = _sub("{date:%d/%m/%Y}")
        assert result == "15/06/2024"

    def test_datetime_field(self):
        result = _sub("{datetime}")
        assert result == "2024-06-15_103045"

    def test_datetime_field_custom_fmt(self):
        result = _sub("{datetime:%Y%m%d}")
        assert result == "20240615"

    def test_dir_field(self):
        result = _sub("{dir}", path="/home/user/photos/image.jpg")
        assert result == "photos"

    def test_mdatetime_field_real_file(self, tmp_path):
        f = tmp_path / "sample.txt"
        f.touch()
        result = _sub("{mdatetime}", path=str(f))
        assert len(result) > 0  # formatted datetime string

    def test_mdatetime_missing_file_uses_default(self):
        result = _sub("{mdatetime::unknown}", path="/no/such/file.txt")
        assert result == "unknown"

    def test_mdatetime_missing_file_no_default_raises(self):
        with pytest.raises(FieldResolutionError):
            _sub("{mdatetime}", path="/no/such/file.txt")

    def test_cdatetime_field_real_file(self, tmp_path):
        f = tmp_path / "sample.txt"
        f.touch()
        result = _sub("{cdatetime}", path=str(f))
        assert len(result) > 0

    def test_cdatetime_missing_file_uses_default(self):
        result = _sub("{cdatetime::unknown}", path="/no/such/file.txt")
        assert result == "unknown"

    def test_cdatetime_missing_file_no_default_raises(self):
        with pytest.raises(FieldResolutionError):
            _sub("{cdatetime}", path="/no/such/file.txt")

    def test_ex_field_missing_uses_default(self, tmp_path):
        f = tmp_path / "plain.txt"
        f.touch()
        result = _sub("{im:Make::n/a}", path=str(f))
        assert result == "n/a"

    def test_ex_field_missing_no_default_raises(self, tmp_path):
        f = tmp_path / "plain.txt"
        f.touch()
        with pytest.raises(FieldResolutionError):
            _sub("{im:Make}", path=str(f))

    def test_mu_field_missing_uses_default(self, tmp_path):
        f = tmp_path / "plain.txt"
        f.touch()
        result = _sub("{au:title::untitled}", path=str(f))
        assert result == "untitled"

    def test_mu_field_missing_no_default_raises(self, tmp_path):
        f = tmp_path / "plain.txt"
        f.touch()
        with pytest.raises(FieldResolutionError):
            _sub("{au:title}", path=str(f))

    def test_vi_field_missing_uses_default(self, tmp_path):
        f = tmp_path / "plain.txt"
        f.touch()
        result = _sub("{vi:width::0}", path=str(f))
        assert result == "0"

    def test_vi_field_missing_no_default_raises(self, tmp_path):
        f = tmp_path / "plain.txt"
        f.touch()
        with pytest.raises(FieldResolutionError):
            _sub("{vi:width}", path=str(f))

    def test_literal_brace_in_result(self):
        # {{ → literal '{'; lone '}' is not special → "{{num}" produces "{num}"
        assert _sub("{{num}") == "{num}"

    def test_mixed_literal_and_field(self):
        result = _sub("photo_{num:03}_copy", counter=5)
        assert result == "photo_005_copy"


# ---------------------------------------------------------------------------
# {num} non-numeric offset (lines 308-309 in substitute)
# ---------------------------------------------------------------------------


class TestNumNonNumericOffset:
    def test_non_numeric_default_is_ignored(self):
        # {num::badval} — seg.default = "badval", int("badval") raises ValueError
        # expect: offset silently ignored, counter value used as-is
        result = _sub("{num::badval}", counter=3)
        assert result == "3"


# ---------------------------------------------------------------------------
# _resolve fallthrough to return None (line 375)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Regression: {vi:encodeddate} must not fire on JPEG files
# Bug: MediaInfo can surface General-track metadata (e.g. encoded_date) for
# any file including JPEG, causing {vi:encodeddate:…:} to duplicate the EXIF
# date already resolved by {im:DateTimeDigitized:…:}.
# ---------------------------------------------------------------------------

_JPEG_DATE = datetime.datetime(2024, 5, 29, 17, 30, 1)
_JPEG_DATE_STR = "2024-05-29 17-30-01"


# ---------------------------------------------------------------------------
# Multi-meta mode
# When a template mixes fields from several file-type namespaces (im:, vi:,
# au:…), a field whose namespace doesn't match the file is silently "".
# With a single namespace the strict behaviour is kept (error if no default).
# ---------------------------------------------------------------------------


def _patch_meta(mapping: dict):
    """Patch _META_READERS in replacement.py with the given prefix→callable dict."""
    import pbrenamer.core.replacement as _repl

    return patch.dict(_repl._META_READERS, mapping)


def _patch_can_read(mapping: dict):
    """Patch _META_CAN_READ in replacement.py with the given prefix→callable dict."""
    import pbrenamer.core.replacement as _repl

    return patch.dict(_repl._META_CAN_READ, mapping)


class TestMultiMetaMode:
    def test_non_matching_ns_produces_empty_in_mixed_template(self):
        # im: matches the file and returns a value; vi: does not match → silently "".
        with _patch_meta({"im:": lambda p, f: "Canon", "vi:": lambda p, f: None}):
            with _patch_can_read({"im:": lambda p: True, "vi:": lambda p: False}):
                result = _sub("{im:Make}{vi:encodeddate}", path="/x.jpg")
        assert result == "Canon"

    def test_no_matching_ns_raises(self):
        # Neither im: nor vi: match the file → error (not silent "").
        with _patch_meta({"im:": lambda p, f: None, "vi:": lambda p, f: None}):
            with _patch_can_read({"im:": lambda p: False, "vi:": lambda p: False}):
                with pytest.raises(FieldResolutionError):
                    _sub("{im:Make}{vi:encodeddate}", path="/x.txt")

    def test_all_three_ns_mixed(self):
        # Three namespaces; only au: matches → im: and vi: silently "".
        with _patch_meta(
            {
                "im:": lambda p, f: None,
                "au:": lambda p, f: "Miles Davis",
                "vi:": lambda p, f: None,
            }
        ):
            with _patch_can_read(
                {
                    "im:": lambda p: False,
                    "au:": lambda p: True,
                    "vi:": lambda p: False,
                }
            ):
                result = _sub("{im:Make}{au:artist}{vi:encodeddate}", path="/x.mp3")
        assert result == "Miles Davis"

    def test_single_ns_no_default_raises(self):
        # Single namespace + absent field + no default → error (strict mode).
        with _patch_meta({"im:": lambda p, f: None}):
            with pytest.raises(FieldResolutionError):
                _sub("{im:Make}", path="/x.jpg")

    def test_single_ns_with_default_uses_default(self):
        # Single namespace + absent field + default → uses default (strict mode).
        with _patch_meta({"im:": lambda p, f: None}):
            result = _sub("{im:Make::unknown}", path="/x.jpg")
        assert result == "unknown"

    def test_matching_ns_absent_field_no_default_raises(self):
        # im: matches the file but the field is absent and has no default → error.
        with _patch_meta({"im:": lambda p, f: None, "vi:": lambda p, f: "Avatar"}):
            with _patch_can_read({"im:": lambda p: True, "vi:": lambda p: False}):
                with pytest.raises(FieldResolutionError):
                    _sub("{im:Make}{vi:title}", path="/x.jpg")

    def test_mixed_ns_non_applicable_has_default_uses_default(self):
        # Non-applicable namespace with an
        # explicit default → uses default (not silenced).
        with _patch_meta({"im:": lambda p, f: None, "vi:": lambda p, f: "2024"}):
            with _patch_can_read({"im:": lambda p: False, "vi:": lambda p: True}):
                result = _sub("{im:Make::fallback}{vi:title}", path="/x.mp4")
        assert result == "fallback2024"

    def test_literal_between_mixed_fields_preserved(self):
        # Literals between fields are untouched even when one namespace is empty.
        with _patch_meta({"im:": lambda p, f: "Canon", "vi:": lambda p, f: None}):
            with _patch_can_read({"im:": lambda p: True, "vi:": lambda p: False}):
                result = _sub("{im:Make}-{vi:encodeddate}", path="/x.jpg")
        assert result == "Canon-"


class TestViFieldIgnoredOnJpeg:
    """End-to-end regression: mixed {im:…}{vi:…} template on a JPEG file.

    Multi-meta mode silences the non-matching namespace; video_meta.read_field
    independently returns None for files without a Video track.
    """

    def test_im_resolves_vi_returns_empty_on_jpeg(self):
        # Mixed template: im: matches the file, resolves; vi: does not match → "".
        template = (
            "{im:DateTimeDigitized:%Y-%m-%d %H-%M-%S:}"
            "{vi:encodeddate:%Y-%m-%d %H-%M-%S:}"
        )
        with _patch_meta({"im:": lambda p, f: _JPEG_DATE, "vi:": lambda p, f: None}):
            with _patch_can_read({"im:": lambda p: True, "vi:": lambda p: False}):
                result = _sub(template, path="/photos/img.jpg")
        assert result == _JPEG_DATE_STR

    def test_result_is_not_duplicated(self):
        # Date must appear exactly once; vi: must not echo the EXIF date.
        template = (
            "{im:DateTimeDigitized:%Y-%m-%d %H-%M-%S:}"
            "{vi:encodeddate:%Y-%m-%d %H-%M-%S:}"
        )
        with _patch_meta({"im:": lambda p, f: _JPEG_DATE, "vi:": lambda p, f: None}):
            with _patch_can_read({"im:": lambda p: True, "vi:": lambda p: False}):
                result = _sub(template, path="/photos/img.jpg")
        assert result.count(_JPEG_DATE_STR) == 1

    def test_vi_encodeddate_none_for_general_track_only(self):
        # At the video_meta level: a file with only a General track (JPEG)
        # must not expose encodeddate via {vi:…}.
        from unittest.mock import MagicMock

        from pbrenamer.core import video_meta

        general = MagicMock()
        general.track_type = "General"
        general.encoded_date = "UTC 2024-05-29 17:30:01"
        general.tagged_date = None

        mock_info = MagicMock()
        mock_info.tracks = [general]  # no Video track

        with patch("pbrenamer.core.video_meta.MediaInfo") as mock_cls:
            mock_cls.parse.return_value = mock_info
            with patch.object(video_meta, "_MEDIAINFO", True):
                result = video_meta.read_field("/photos/img.jpg", "encodeddate")
        assert result is None


class TestResolveUnknownField:
    def test_unknown_field_with_default_uses_default(self):
        # A FieldSegment whose name passes _is_valid_name() but is unknown
        # at resolve-time can be injected directly to hit the final return None.
        from pbrenamer.core.replacement import FieldSegment, _resolve

        seg = FieldSegment(
            name="totally_unknown_x",
            case="",
            align="",
            fmt="",
            default=None,
            raw="{totally_unknown_x}",
        )
        result = _resolve(
            seg,
            full_match=None,
            groups=[],
            named_groups={},
            path="/",
            counter=1,
            now=_NOW,
        )
        assert result is None
