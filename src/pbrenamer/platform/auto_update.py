"""Self-update: replace the running executable with the latest GitHub release.

Only meaningful for a PyInstaller-built executable — a source checkout or a
pip/PyPI install has no single running binary to overwrite and is updated
through its own channel (git pull / pip install -U) instead.

Dispatches to the right implementation based on ``sys.platform``, mirroring
``platform/dirs.py``:
- Windows  : rename the running .exe aside, move the new build into place
- macOS    : swap the .app bundle directory for the extracted release zip
- Linux    : atomic ``os.replace`` of the single-file executable
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from pbrenamer import __version__

_REPO = "ppoilbarbe/PBRenamer"
_API_URL = f"https://api.github.com/repos/{_REPO}/releases/latest"
_TIMEOUT = 30

# Mirrors the arch mapping in pbrenamer.spec.
_ARCH_MAP = {
    "x86_64": "x86_64",
    "amd64": "x86_64",  # Windows reports AMD64
    "arm64": "arm64",  # macOS Apple Silicon
    "aarch64": "arm64",  # Linux ARM 64-bit
}


def _arch_tag() -> str:
    machine = platform.machine().lower()
    return _ARCH_MAP.get(machine, machine)


# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------


class _BaseUpdater:
    os_tag: str

    def asset_suffix(self, arch: str) -> str:
        """Return the release-asset filename suffix for this platform."""
        return f"-{self.os_tag}-{arch}"

    def resolve_target(self, executable: Path) -> tuple[Path, Path]:
        """Return (target, dest_dir): the entry to replace, and the
        directory to download the update into (must be on *target*'s
        filesystem, so the final swap can be an atomic rename)."""
        return executable, executable.parent

    def replace(self, target: Path, downloaded_file: Path) -> None:
        """Replace *target* with *downloaded_file* (consuming it)."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Linux — single-file executable
# ---------------------------------------------------------------------------


class _LinuxUpdater(_BaseUpdater):
    os_tag = "linux"

    def replace(self, target: Path, downloaded_file: Path) -> None:
        """Atomic same-filesystem rename — safe even while *target* is the
        running process's own image (POSIX keeps it mapped by inode)."""
        os.chmod(downloaded_file, target.stat().st_mode)
        os.replace(downloaded_file, target)


# ---------------------------------------------------------------------------
# Windows — single-file executable
# ---------------------------------------------------------------------------


class _WindowsUpdater(_BaseUpdater):
    os_tag = "windows"

    def asset_suffix(self, arch: str) -> str:
        return f"-{self.os_tag}-{arch}.exe"

    def replace(self, target: Path, downloaded_file: Path) -> None:
        """Windows refuses to overwrite the bytes of a running .exe, but
        renaming it aside is permitted (the loader keeps its handle to the
        renamed file). Move the new build into place, then best-effort
        delete the old one."""
        old = Path(str(target) + ".old")
        old.unlink(missing_ok=True)
        os.replace(target, old)
        try:
            os.replace(downloaded_file, target)
        except OSError:
            os.replace(old, target)  # restore on failure
            raise
        try:
            old.unlink()
        except OSError:
            pass  # leftover .old file — harmless, cleaned up on a later update


# ---------------------------------------------------------------------------
# macOS — .app bundle
# ---------------------------------------------------------------------------


class _MacUpdater(_BaseUpdater):
    os_tag = "macos"

    def asset_suffix(self, arch: str) -> str:
        # The .app bundle is a directory; the release job zips it for upload.
        return f"-{self.os_tag}-{arch}.zip"

    def resolve_target(self, executable: Path) -> tuple[Path, Path]:
        app_root = self._app_root(executable)
        if app_root is None:
            raise LookupError("could not locate the enclosing .app bundle")
        return app_root, app_root.parent

    def _app_root(self, executable: Path) -> Path | None:
        """Walk up from the running executable to find the enclosing .app
        bundle."""
        for parent in executable.parents:
            if parent.suffix == ".app":
                return parent
        return None

    def replace(self, target: Path, downloaded_file: Path) -> None:
        """Extract the downloaded .zip (a zipped .app bundle) and swap it in
        for *target*."""
        with tempfile.TemporaryDirectory(dir=target.parent) as tmp_dir:
            with zipfile.ZipFile(downloaded_file) as zf:
                zf.extractall(tmp_dir)
            candidates = list(Path(tmp_dir).glob("*.app"))
            if len(candidates) != 1:
                raise RuntimeError(
                    "expected exactly one .app bundle in the release archive, "
                    f"found {len(candidates)}"
                )
            new_app = candidates[0]
            old = Path(str(target) + ".old")
            if old.exists():
                shutil.rmtree(old)
            os.replace(target, old)
            try:
                shutil.move(str(new_app), str(target))
            except OSError:
                os.replace(old, target)  # restore on failure
                raise
            shutil.rmtree(old, ignore_errors=True)
        downloaded_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _updater_for_platform() -> _BaseUpdater:
    if sys.platform == "win32":
        return _WindowsUpdater()
    if sys.platform == "darwin":
        return _MacUpdater()
    return _LinuxUpdater()


# ---------------------------------------------------------------------------
# GitHub release fetching
# ---------------------------------------------------------------------------


def _fetch_latest_release() -> dict:
    req = urllib.request.Request(
        _API_URL, headers={"Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
        return json.load(resp)


def _find_asset(release: dict, suffix: str) -> dict | None:
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if name.startswith("pbrenamer-") and name.endswith(suffix):
            return asset
    return None


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
    with (
        urllib.request.urlopen(req, timeout=_TIMEOUT) as resp,  # noqa: S310
        open(dest, "wb") as f,
    ):
        shutil.copyfileobj(resp, f)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def perform_auto_update() -> tuple[bool, str]:
    """Replace the running executable with the latest GitHub release build.

    Returns (ok, message).
    """
    if not getattr(sys, "frozen", False):
        return False, (
            "error: --auto-update is only available in PyInstaller-built "
            "executables (not source or pip/PyPI installs)"
        )

    updater = _updater_for_platform()
    arch = _arch_tag()
    suffix = updater.asset_suffix(arch)

    try:
        release = _fetch_latest_release()
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return False, f"error: could not reach GitHub: {exc}"

    asset = _find_asset(release, suffix)
    if asset is None:
        return False, (
            f"error: no release asset found for this platform ({updater.os_tag}-{arch})"
        )

    tag = str(release.get("tag_name", "")).lstrip("v")
    if tag and tag == __version__:
        return True, f"Already running the latest version ({__version__})."

    executable = Path(sys.executable).resolve()
    try:
        target, dest_dir = updater.resolve_target(executable)
    except LookupError as exc:
        return False, f"error: {exc}"

    tmp_path: Path | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(dir=dest_dir, prefix=".pbrenamer-update-")
        os.close(fd)
        tmp_path = Path(tmp_name)
        _download(asset["browser_download_url"], tmp_path)
        updater.replace(target, tmp_path)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        return False, f"error: update failed: {exc}"

    new_version = tag or "latest"
    return True, f"Updated to version {new_version}. Restart PBRenamer to use it."
