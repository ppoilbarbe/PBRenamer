"""Tests for pbrenamer.platform.auto_update — self-update via GitHub releases."""

from __future__ import annotations

import io
import json
import os
import sys
import zipfile

import pytest

from pbrenamer import __version__
from pbrenamer.platform import auto_update


class _FakeResponse:
    """Minimal stand-in for the object returned by urllib.request.urlopen."""

    def __init__(self, data: bytes):
        self._io = io.BytesIO(data)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self, *args, **kwargs):
        return self._io.read(*args, **kwargs)


def _release(tag: str, assets: list[dict]) -> bytes:
    return json.dumps({"tag_name": tag, "assets": assets}).encode()


# ---------------------------------------------------------------------------
# _arch_tag / _updater_for_platform / asset_suffix
# ---------------------------------------------------------------------------


class TestArchTag:
    def test_normalizes_known_machine(self, monkeypatch):
        monkeypatch.setattr(auto_update.platform, "machine", lambda: "AMD64")
        assert auto_update._arch_tag() == "x86_64"

    def test_unknown_machine_passthrough(self, monkeypatch):
        monkeypatch.setattr(auto_update.platform, "machine", lambda: "riscv64")
        assert auto_update._arch_tag() == "riscv64"


class TestUpdaterForPlatform:
    def test_linux_returns_linux_updater(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        updater = auto_update._updater_for_platform()
        assert isinstance(updater, auto_update._LinuxUpdater)
        assert updater.os_tag == "linux"

    def test_windows_returns_windows_updater(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        updater = auto_update._updater_for_platform()
        assert isinstance(updater, auto_update._WindowsUpdater)
        assert updater.os_tag == "windows"

    def test_macos_returns_mac_updater(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        updater = auto_update._updater_for_platform()
        assert isinstance(updater, auto_update._MacUpdater)
        assert updater.os_tag == "macos"

    def test_unrecognized_platform_falls_back_to_linux(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "freebsd13")
        updater = auto_update._updater_for_platform()
        assert isinstance(updater, auto_update._LinuxUpdater)


class TestAssetSuffix:
    def test_linux_has_no_extension(self):
        assert auto_update._LinuxUpdater().asset_suffix("x86_64") == "-linux-x86_64"

    def test_windows_has_exe_extension(self):
        suffix = auto_update._WindowsUpdater().asset_suffix("x86_64")
        assert suffix == "-windows-x86_64.exe"

    def test_macos_has_zip_extension(self):
        assert auto_update._MacUpdater().asset_suffix("arm64") == "-macos-arm64.zip"


class TestFindAsset:
    def test_matches_prefix_and_suffix(self):
        release = {
            "assets": [
                {"name": "pbrenamer-1.8.0-windows-x86_64.exe"},
                {"name": "pbrenamer-1.8.0-linux-x86_64"},
            ]
        }
        asset = auto_update._find_asset(release, "-linux-x86_64")
        assert asset["name"] == "pbrenamer-1.8.0-linux-x86_64"

    def test_returns_none_when_no_match(self):
        release = {"assets": [{"name": "pbrenamer-1.8.0-macos-arm64.zip"}]}
        assert auto_update._find_asset(release, "-linux-x86_64") is None

    def test_ignores_non_pbrenamer_assets(self):
        release = {"assets": [{"name": "checksums-linux-x86_64.txt"}]}
        assert auto_update._find_asset(release, "-linux-x86_64") is None


class TestFetchLatestRelease:
    def test_parses_json_response(self, monkeypatch):
        data = _release("v1.8.0", [{"name": "pbrenamer-1.8.0-linux-x86_64"}])
        monkeypatch.setattr(
            auto_update.urllib.request,
            "urlopen",
            lambda req, timeout=None: _FakeResponse(data),
        )
        release = auto_update._fetch_latest_release()
        assert release["tag_name"] == "v1.8.0"
        assert release["assets"][0]["name"] == "pbrenamer-1.8.0-linux-x86_64"


class TestDownload:
    def test_writes_response_body_to_dest(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            auto_update.urllib.request,
            "urlopen",
            lambda req, timeout=None: _FakeResponse(b"binary payload"),
        )
        dest = tmp_path / "out.bin"
        auto_update._download("https://example.invalid/asset", dest)
        assert dest.read_bytes() == b"binary payload"


# ---------------------------------------------------------------------------
# perform_auto_update
# ---------------------------------------------------------------------------


class TestPerformAutoUpdateGuards:
    def test_not_frozen_is_rejected(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        ok, message = auto_update.perform_auto_update()
        assert ok is False
        assert "only available in PyInstaller" in message

    def test_network_error_is_reported(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)

        def raise_error(*args, **kwargs):
            raise auto_update.urllib.error.URLError("no route to host")

        monkeypatch.setattr(auto_update, "_fetch_latest_release", raise_error)
        ok, message = auto_update.perform_auto_update()
        assert ok is False
        assert "could not reach GitHub" in message

    def test_no_matching_asset_is_reported(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(auto_update.platform, "machine", lambda: "x86_64")
        monkeypatch.setattr(
            auto_update,
            "_fetch_latest_release",
            lambda: {"tag_name": "v1.8.0", "assets": []},
        )
        ok, message = auto_update.perform_auto_update()
        assert ok is False
        assert "no release asset found" in message

    def test_already_up_to_date_skips_download(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(auto_update.platform, "machine", lambda: "x86_64")
        monkeypatch.setattr(
            sys, "executable", str(tmp_path / f"pbrenamer-{__version__}-linux-x86_64")
        )
        monkeypatch.setattr(
            auto_update,
            "_fetch_latest_release",
            lambda: {
                "tag_name": f"v{__version__}",
                "assets": [
                    {
                        "name": f"pbrenamer-{__version__}-linux-x86_64",
                        "browser_download_url": "https://example.invalid/asset",
                    }
                ],
            },
        )

        def fail_if_called(*args, **kwargs):
            raise AssertionError("should not download when already up to date")

        monkeypatch.setattr(auto_update, "_download", fail_if_called)

        ok, message = auto_update.perform_auto_update()
        assert ok is True
        assert __version__ in message
        assert "Already running the latest version" in message


class TestPerformAutoUpdateLinux:
    def test_success_replaces_executable_preserving_mode(self, monkeypatch, tmp_path):
        current = tmp_path / f"pbrenamer-{__version__}-linux-x86_64"
        current.write_bytes(b"OLD BINARY")
        os.chmod(current, 0o755)

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(sys, "executable", str(current))
        monkeypatch.setattr(auto_update.platform, "machine", lambda: "x86_64")
        monkeypatch.setattr(
            auto_update,
            "_fetch_latest_release",
            lambda: {
                "tag_name": "v9.9.9",
                "assets": [
                    {
                        "name": "pbrenamer-9.9.9-linux-x86_64",
                        "browser_download_url": "https://example.invalid/asset",
                    }
                ],
            },
        )
        monkeypatch.setattr(
            auto_update, "_download", lambda url, dest: dest.write_bytes(b"NEW BINARY")
        )

        ok, message = auto_update.perform_auto_update()

        assert ok is True
        assert "Updated to version 9.9.9" in message
        assert current.read_bytes() == b"NEW BINARY"
        assert (os.stat(current).st_mode & 0o777) == 0o755

    def test_download_failure_leaves_original_and_cleans_tmp(
        self, monkeypatch, tmp_path
    ):
        current = tmp_path / f"pbrenamer-{__version__}-linux-x86_64"
        current.write_bytes(b"OLD BINARY")

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(sys, "executable", str(current))
        monkeypatch.setattr(auto_update.platform, "machine", lambda: "x86_64")
        monkeypatch.setattr(
            auto_update,
            "_fetch_latest_release",
            lambda: {
                "tag_name": "v9.9.9",
                "assets": [
                    {
                        "name": "pbrenamer-9.9.9-linux-x86_64",
                        "browser_download_url": "https://example.invalid/asset",
                    }
                ],
            },
        )

        def raise_download(url, dest):
            raise OSError("connection reset")

        monkeypatch.setattr(auto_update, "_download", raise_download)

        ok, message = auto_update.perform_auto_update()

        assert ok is False
        assert "update failed" in message
        assert current.read_bytes() == b"OLD BINARY"
        assert list(tmp_path.iterdir()) == [current]


class TestWindowsUpdaterReplace:
    def test_success_moves_new_build_into_place(self, tmp_path):
        current = tmp_path / "app.exe"
        current.write_bytes(b"OLD")
        new_file = tmp_path / "new.exe"
        new_file.write_bytes(b"NEW")

        auto_update._WindowsUpdater().replace(current, new_file)

        assert current.read_bytes() == b"NEW"
        assert not (tmp_path / "app.exe.old").exists()

    def test_restores_original_on_failure(self, monkeypatch, tmp_path):
        current = tmp_path / "app.exe"
        current.write_bytes(b"OLD")
        new_file = tmp_path / "new.exe"
        new_file.write_bytes(b"NEW")

        real_replace = os.replace

        def flaky_replace(src, dst):
            if str(src) == str(new_file):
                raise OSError("file in use")
            real_replace(src, dst)

        monkeypatch.setattr(auto_update.os, "replace", flaky_replace)

        with pytest.raises(OSError):
            auto_update._WindowsUpdater().replace(current, new_file)

        assert current.read_bytes() == b"OLD"


class TestMacUpdaterAppRoot:
    def test_finds_enclosing_app_bundle(self, tmp_path):
        executable = (
            tmp_path / "PBRenamer.app" / "Contents" / "MacOS" / "pbrenamer-1.7.0"
        )
        executable.parent.mkdir(parents=True)
        executable.touch()
        app_root = auto_update._MacUpdater()._app_root(executable)
        assert app_root == tmp_path / "PBRenamer.app"

    def test_returns_none_when_no_bundle_in_path(self, tmp_path):
        executable = tmp_path / "bin" / "pbrenamer-1.7.0"
        executable.parent.mkdir(parents=True)
        executable.touch()
        assert auto_update._MacUpdater()._app_root(executable) is None

    def test_resolve_target_raises_when_no_bundle(self, tmp_path):
        executable = tmp_path / "bin" / "pbrenamer-1.7.0"
        executable.parent.mkdir(parents=True)
        executable.touch()
        with pytest.raises(LookupError, match="enclosing .app bundle"):
            auto_update._MacUpdater().resolve_target(executable)


class TestMacUpdaterReplace:
    def _make_app_zip(self, tmp_path, app_name="PBRenamer.app", content=b"NEW"):
        zip_path = tmp_path / "download.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(f"{app_name}/Contents/MacOS/pbrenamer", content)
        return zip_path

    def test_success_swaps_bundle_contents(self, tmp_path):
        app_root = tmp_path / "PBRenamer.app"
        (app_root / "Contents" / "MacOS").mkdir(parents=True)
        (app_root / "Contents" / "MacOS" / "pbrenamer").write_bytes(b"OLD")

        zip_path = self._make_app_zip(tmp_path)

        auto_update._MacUpdater().replace(app_root, zip_path)

        binary = app_root / "Contents" / "MacOS" / "pbrenamer"
        assert binary.read_bytes() == b"NEW"
        assert not (tmp_path / "PBRenamer.app.old").exists()
        assert not zip_path.exists()

    def test_rejects_archive_without_exactly_one_app_bundle(self, tmp_path):
        app_root = tmp_path / "PBRenamer.app"
        (app_root / "Contents" / "MacOS").mkdir(parents=True)
        (app_root / "Contents" / "MacOS" / "pbrenamer").write_bytes(b"OLD")

        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", "no app bundle here")

        with pytest.raises(RuntimeError, match="exactly one .app bundle"):
            auto_update._MacUpdater().replace(app_root, zip_path)

        # Original bundle must be left untouched on failure.
        assert (app_root / "Contents" / "MacOS" / "pbrenamer").read_bytes() == b"OLD"


class TestPerformAutoUpdateMacos:
    def test_missing_app_bundle_is_reported(self, monkeypatch, tmp_path):
        current = tmp_path / "bin" / f"pbrenamer-{__version__}-macos-arm64"
        current.parent.mkdir(parents=True)
        current.touch()

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(sys, "executable", str(current))
        monkeypatch.setattr(auto_update.platform, "machine", lambda: "arm64")
        monkeypatch.setattr(
            auto_update,
            "_fetch_latest_release",
            lambda: {
                "tag_name": "v9.9.9",
                "assets": [
                    {
                        "name": "pbrenamer-9.9.9-macos-arm64.zip",
                        "browser_download_url": "https://example.invalid/asset",
                    }
                ],
            },
        )

        ok, message = auto_update.perform_auto_update()

        assert ok is False
        assert "could not locate the enclosing .app bundle" in message

    def test_success_replaces_app_bundle(self, monkeypatch, tmp_path):
        current = (
            tmp_path
            / "PBRenamer.app"
            / "Contents"
            / "MacOS"
            / f"pbrenamer-{__version__}"
        )
        current.parent.mkdir(parents=True)
        current.write_bytes(b"OLD")

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(sys, "executable", str(current))
        monkeypatch.setattr(auto_update.platform, "machine", lambda: "arm64")
        monkeypatch.setattr(
            auto_update,
            "_fetch_latest_release",
            lambda: {
                "tag_name": "v9.9.9",
                "assets": [
                    {
                        "name": "pbrenamer-9.9.9-macos-arm64.zip",
                        "browser_download_url": "https://example.invalid/asset",
                    }
                ],
            },
        )

        def fake_download(url, dest):
            with zipfile.ZipFile(dest, "w") as zf:
                zf.writestr("PBRenamer.app/Contents/MacOS/pbrenamer-9.9.9", b"NEW")

        monkeypatch.setattr(auto_update, "_download", fake_download)

        ok, message = auto_update.perform_auto_update()

        assert ok is True
        assert "Updated to version 9.9.9" in message
        new_binary = (
            tmp_path / "PBRenamer.app" / "Contents" / "MacOS" / "pbrenamer-9.9.9"
        )
        assert new_binary.read_bytes() == b"NEW"
