"""Tests for pbrenamer.core.replacement — parser, validator, formatter, substitutor."""

import datetime

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
        segs = parse("{ex:Make}")
        assert any(isinstance(s, FieldSegment) and s.name == "ex:Make" for s in segs)

    def test_re_field_valid(self):
        segs = parse("{re:year}")
        assert any(isinstance(s, FieldSegment) and s.name == "re:year" for s in segs)

    def test_ex_field_with_options(self):
        # {ex:Make::default} — empty fmt, then default after second colon
        segs = parse("{ex:Make::unknown}")
        field = next(s for s in segs if isinstance(s, FieldSegment))
        assert field.name == "ex:Make"
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
        result = _sub("{ex:Make::n/a}", path=str(f))
        assert result == "n/a"

    def test_ex_field_missing_no_default_raises(self, tmp_path):
        f = tmp_path / "plain.txt"
        f.touch()
        with pytest.raises(FieldResolutionError):
            _sub("{ex:Make}", path=str(f))

    def test_literal_brace_in_result(self):
        # {{ → literal '{'; lone '}' is not special → "{{num}" produces "{num}"
        assert _sub("{{num}") == "{num}"

    def test_mixed_literal_and_field(self):
        result = _sub("photo_{num:03}_copy", counter=5)
        assert result == "photo_005_copy"
