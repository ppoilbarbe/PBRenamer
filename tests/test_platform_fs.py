"""Tests for pbrenamer.platform.fs — case sensitivity, path comparison."""

from unittest.mock import patch

from pbrenamer.platform.fs import conflict_key, is_case_sensitive, same_file_path


class TestIsCaseSensitive:
    def test_returns_bool(self, tmp_path):
        result = is_case_sensitive(str(tmp_path))
        assert isinstance(result, bool)

    def test_linux_is_case_sensitive(self, tmp_path):
        # Standard Linux ext4/xfs/btrfs filesystems are case-sensitive
        import sys

        if sys.platform == "linux":
            assert is_case_sensitive(str(tmp_path)) is True

    def test_result_cached(self, tmp_path):
        is_case_sensitive.cache_clear()
        d = str(tmp_path)
        r1 = is_case_sensitive(d)
        r2 = is_case_sensitive(d)
        assert r1 == r2
        is_case_sensitive.cache_clear()


class TestSameFilePath:
    def test_identical_paths_always_same(self):
        with patch("pbrenamer.platform.fs.is_case_sensitive", return_value=True):
            assert same_file_path("File.txt", "File.txt", "/dir")

    def test_different_case_on_case_sensitive_not_same(self):
        with patch("pbrenamer.platform.fs.is_case_sensitive", return_value=True):
            assert not same_file_path("File.txt", "file.txt", "/dir")

    def test_different_case_on_case_insensitive_same(self):
        with patch("pbrenamer.platform.fs.is_case_sensitive", return_value=False):
            assert same_file_path("File.txt", "file.txt", "/dir")

    def test_all_caps_on_case_insensitive_same(self):
        with patch("pbrenamer.platform.fs.is_case_sensitive", return_value=False):
            assert same_file_path("FILE.TXT", "file.txt", "/dir")

    def test_truly_different_names_not_same(self):
        with patch("pbrenamer.platform.fs.is_case_sensitive", return_value=False):
            assert not same_file_path("a.txt", "b.txt", "/dir")


class TestConflictKey:
    def test_case_sensitive_preserves_case(self):
        with patch("pbrenamer.platform.fs.is_case_sensitive", return_value=True):
            assert conflict_key("/dir/File.txt", "/dir") == "/dir/File.txt"

    def test_case_insensitive_lowercases(self):
        with patch("pbrenamer.platform.fs.is_case_sensitive", return_value=False):
            assert conflict_key("/dir/File.TXT", "/dir") == "/dir/file.txt"

    def test_case_insensitive_collision(self):
        with patch("pbrenamer.platform.fs.is_case_sensitive", return_value=False):
            assert conflict_key("/dir/Photo.JPG", "/dir") == conflict_key(
                "/dir/photo.jpg", "/dir"
            )

    def test_case_sensitive_no_collision(self):
        with patch("pbrenamer.platform.fs.is_case_sensitive", return_value=True):
            assert conflict_key("/dir/Photo.JPG", "/dir") != conflict_key(
                "/dir/photo.jpg", "/dir"
            )
