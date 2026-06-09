"""Tests for pbrenamer.platform.bookmarks — system directory bookmarks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from pbrenamer.platform.bookmarks import (
    _gtk_bookmarks,
    _parse_gtk,
    system_bookmarks,
)


class TestParseGtk:
    def test_empty_file_returns_empty_list(self, tmp_path):
        bm = tmp_path / "bookmarks"
        bm.write_text("")
        assert _parse_gtk(bm) == []

    def test_blank_lines_skipped(self, tmp_path):
        bm = tmp_path / "bookmarks"
        bm.write_text(f"\n\nfile://{tmp_path}\n\n")
        assert len(_parse_gtk(bm)) == 1

    def test_entry_without_label_uses_basename(self, tmp_path):
        bm = tmp_path / "bookmarks"
        bm.write_text(f"file://{tmp_path}\n")
        result = _parse_gtk(bm)
        assert len(result) == 1
        assert result[0] == (tmp_path.name, str(tmp_path))

    def test_entry_with_label(self, tmp_path):
        bm = tmp_path / "bookmarks"
        bm.write_text(f"file://{tmp_path} My Projects\n")
        result = _parse_gtk(bm)
        assert result[0] == ("My Projects", str(tmp_path))

    def test_non_file_scheme_skipped(self, tmp_path):
        bm = tmp_path / "bookmarks"
        bm.write_text("smb://server/share\nftp://host/dir\n")
        assert _parse_gtk(bm) == []

    def test_nonexistent_directory_skipped(self, tmp_path):
        bm = tmp_path / "bookmarks"
        bm.write_text("file:///nonexistent/path/that/does/not/exist\n")
        assert _parse_gtk(bm) == []

    def test_url_encoded_space_in_path(self, tmp_path):
        spaced = tmp_path / "my dir"
        spaced.mkdir()
        encoded = str(spaced).replace(" ", "%20")
        bm = tmp_path / "bookmarks"
        bm.write_text(f"file://{encoded}\n")
        result = _parse_gtk(bm)
        assert len(result) == 1
        assert result[0][1] == str(spaced)

    def test_multiple_valid_entries(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        bm = tmp_path / "bookmarks"
        bm.write_text(f"file://{dir_a} Alpha\nfile://{dir_b} Beta\n")
        result = _parse_gtk(bm)
        assert result == [("Alpha", str(dir_a)), ("Beta", str(dir_b))]


class TestGtkBookmarks:
    def test_returns_empty_when_no_bookmark_files(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            assert _gtk_bookmarks() == []

    def test_reads_gtk3_bookmarks(self, tmp_path):
        gtk3_dir = tmp_path / ".config" / "gtk-3.0"
        gtk3_dir.mkdir(parents=True)
        bm_file = gtk3_dir / "bookmarks"
        bm_file.write_text(f"file://{tmp_path} Root\n")
        with patch.object(Path, "home", return_value=tmp_path):
            result = _gtk_bookmarks()
        assert len(result) == 1
        assert result[0] == ("Root", str(tmp_path))

    def test_fallback_to_legacy_gtk_bookmarks(self, tmp_path):
        bm_file = tmp_path / ".gtk-bookmarks"
        bm_file.write_text(f"file://{tmp_path} Home\n")
        with patch.object(Path, "home", return_value=tmp_path):
            result = _gtk_bookmarks()
        assert len(result) == 1


class TestSystemBookmarks:
    def test_linux_with_gtk_returns_gtk_bookmarks(self, tmp_path):
        gtk3_dir = tmp_path / ".config" / "gtk-3.0"
        gtk3_dir.mkdir(parents=True)
        (gtk3_dir / "bookmarks").write_text(f"file://{tmp_path} Root\n")
        with patch("sys.platform", "linux"):
            with patch.object(Path, "home", return_value=tmp_path):
                result = system_bookmarks()
        assert result == [("Root", str(tmp_path))]

    def test_linux_without_gtk_falls_back_to_standard(self, tmp_path):
        fake = [("Home", str(tmp_path))]
        with patch("sys.platform", "linux"):
            with patch.object(Path, "home", return_value=tmp_path):
                with patch(
                    "pbrenamer.platform.bookmarks._standard_locations",
                    return_value=fake,
                ):
                    result = system_bookmarks()
        assert result == fake

    def test_non_linux_uses_standard_locations(self):
        fake = [("Home", "/home/user")]
        with patch("sys.platform", "darwin"):
            with patch(
                "pbrenamer.platform.bookmarks._standard_locations", return_value=fake
            ):
                result = system_bookmarks()
        assert result == fake
