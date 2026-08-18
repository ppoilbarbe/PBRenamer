#!/usr/bin/env python3
"""Sync icons in src/pbrenamer/resources/ from the PBIcons project.

Three kinds of files live in that directory, all sourced from PBIcons:

- The app icon files used by PyInstaller packaging: `pbrenamer.ico` and
  `pbrenamer.icns` (`_APP_ICON_FILES` below). The app's own GUI icon
  (window icon) is `pbrenamer.svg`, already covered by the SVG sync below.
- Every `*.svg` already present in the resources directory (toolbar/menu
  action icons plus `pbrenamer.svg`).
- The drag'n'drop cursor pixmaps (`_CURSOR_FILES` below): one PNG per DnD
  state — copy, move, alias (link), not-allowed — each with `@2x`/`@3x`
  HiDPI variants (Qt's `QPixmap.setDevicePixelRatio()` convention), synced
  from PBIcons' `cursors/` subdirectory. Listed explicitly rather than
  glob-matched like the SVGs above, since they don't exist locally before
  the first sync.

Icons are looked up by filename (case-insensitive) within a fixed list of
PBIcons subdirectories, `_ICON_DIRS`, tried in order — not a recursive search
of the whole PBIcons tree, so an icon in a subdirectory outside that list is
treated as not found (see the error below).

Lookup order, per icon:
    1. A local PBIcons checkout: a directory named "pbicons" (any case),
       sibling of this project's root, searched in `_ICON_DIRS` order for a
       same-named file.
    2. If not found there (including if no such local checkout exists at
       all), the PBIcons GitHub repository (ppoilbarbe/PBIcons, "main"
       branch), fetched over the network and searched in the same order.

If an icon is found in neither place, this is an error: either `_ICON_DIRS`
below is missing the subdirectory the icon actually lives in and needs
updating, or the icon genuinely doesn't exist in PBIcons.

PBIcons is the source of truth: a file is copied byte-for-byte (its content
is never altered) whenever its SHA-256 differs from the local resources/
copy.

Note: `.png`/`.jpg` files in PBIcons are stored via Git LFS; fetching them
from GitHub raw returns the LFS pointer text, not the actual bytes, which is
treated as an error below. A local PBIcons checkout (with LFS objects
smudged in) is required to sync those. `.svg`/`.ico`/`.icns` are not
LFS-tracked in PBIcons and work either way.

Usage:
    python tools/update_icons.py               # sync every icon file (see above)
    python tools/update_icons.py pbrenamer.svg  # sync only the named file(s)
    python tools/update_icons.py --dry-run      # report changes, write nothing

An optional GITHUB_TOKEN environment variable is used (if set) to authenticate
the GitHub API call, to avoid the low unauthenticated rate limit.
"""

import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
RESOURCES_DIR = ROOT / "src" / "pbrenamer" / "resources"

# App icon files (PyInstaller packaging), always synced regardless of what's
# already on disk.
_APP_ICON_FILES = (
    "pbrenamer.ico",
    "pbrenamer.icns",
)

# Drag'n'drop cursor pixmaps: one PNG per DnD state, at 1x/2x/3x, always
# synced regardless of what's already on disk (same reasoning as
# _APP_ICON_FILES — they can't be glob-discovered before their first sync).
_CURSOR_STATES = ("copy", "move", "alias", "not-allowed")
_CURSOR_SCALES = ("", "@2x", "@3x")
_CURSOR_FILES = tuple(
    f"{state}{scale}.png" for state in _CURSOR_STATES for scale in _CURSOR_SCALES
)

# PBIcons subdirectories to search for an icon, in priority order.
_ICON_DIRS = ("programs", "actions", "media", "cursors")

_GITHUB_REPO = "ppoilbarbe/PBIcons"
_GITHUB_BRANCH = "main"
_GITHUB_TREE_API = f"https://api.github.com/repos/{_GITHUB_REPO}/git/trees/{_GITHUB_BRANCH}?recursive=1"
_GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{_GITHUB_REPO}/{_GITHUB_BRANCH}/"

_USER_AGENT = "pbrenamer-update-icons"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_local_pbicons_dir() -> Path | None:
    """Return the PBIcons checkout sibling of this project's root, if any."""
    for entry in ROOT.parent.iterdir():
        if entry.is_dir() and entry.name.lower() == "pbicons":
            return entry
    return None


def find_local_file(pbicons_dir: Path, filename: str) -> Path | None:
    target = filename.lower()
    subdirs = {p.name.lower(): p for p in pbicons_dir.iterdir() if p.is_dir()}
    for dirname in _ICON_DIRS:
        subdir = subdirs.get(dirname)
        if subdir is None:
            continue
        for path in sorted(subdir.iterdir()):
            if path.is_file() and path.name.lower() == target:
                return path
    return None


def _github_request(url: str) -> bytes:
    headers = {"User-Agent": _USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read()


def fetch_github_index() -> dict[str, str]:
    """Return {lowercased filename: path in repo} for every file directly
    under an `_ICON_DIRS` subdirectory, favoring earlier directories on a
    name clash."""
    data = json.loads(_github_request(_GITHUB_TREE_API))
    by_dir: dict[str, dict[str, str]] = {dirname: {} for dirname in _ICON_DIRS}
    for entry in data.get("tree", []):
        path = entry.get("path", "")
        if entry.get("type") != "blob":
            continue
        top_dir, _, rest = path.partition("/")
        if not rest or "/" in rest or top_dir not in by_dir:
            continue
        by_dir[top_dir][rest.lower()] = path

    index: dict[str, str] = {}
    for dirname in _ICON_DIRS:
        for filename, path in by_dir[dirname].items():
            index.setdefault(filename, path)
    return index


def fetch_github_file(repo_path: str) -> bytes:
    url = _GITHUB_RAW_BASE + urllib.parse.quote(repo_path)
    content = _github_request(url)
    if content.startswith(b"version https://git-lfs.github.com/spec"):
        raise RuntimeError(
            f"{repo_path} is stored via git-lfs and can't be fetched as raw content"
        )
    return content


def resolve_icon(
    name: str, local_dir: Path | None, github_index: dict[str, str] | None
) -> tuple[bytes, str] | None:
    """Return (content, source description) for `name`, or None if not found."""
    if local_dir is not None:
        src = find_local_file(local_dir, name)
        if src is not None:
            return src.read_bytes(), f"local:{src.relative_to(local_dir)}"
    if github_index is not None:
        repo_path = github_index.get(name.lower())
        if repo_path is not None:
            return fetch_github_file(repo_path), f"github:{repo_path}"
    return None


def default_names() -> list[str]:
    svgs = sorted(p.name for p in RESOURCES_DIR.glob("*.svg"))
    return svgs + list(_APP_ICON_FILES) + list(_CURSOR_FILES)


def main() -> None:
    args = sys.argv[1:]
    if "-h" in args or "--help" in args:
        sys.exit(__doc__)
    dry_run = "--dry-run" in args
    names = [a for a in args if not a.startswith("-")]
    if not names:
        names = default_names()

    local_dir = find_local_pbicons_dir()
    if local_dir is not None:
        print(f"Local PBIcons checkout: {local_dir}")
    else:
        print(
            "No local PBIcons checkout found next to the project root; will use GitHub."
        )

    github_index: dict[str, str] | None = None
    updated: list[tuple[str, str]] = []
    unchanged: list[str] = []
    missing: list[str] = []

    for name in names:
        content_source = resolve_icon(name, local_dir, github_index)
        if content_source is None and github_index is None:
            print("Fetching PBIcons file index from GitHub…")
            try:
                github_index = fetch_github_index()
            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                json.JSONDecodeError,
            ) as exc:
                sys.exit(f"error: could not reach GitHub ({exc})")
            content_source = resolve_icon(name, local_dir, github_index)

        if content_source is None:
            missing.append(name)
            continue

        content, source = content_source
        dest = RESOURCES_DIR / name
        if dest.exists() and sha256(dest.read_bytes()) == sha256(content):
            unchanged.append(name)
            continue
        updated.append((name, source))
        if not dry_run:
            dest.write_bytes(content)

    verb = "would update" if dry_run else "updated"
    for name, source in updated:
        print(f"  {verb} {name}  ({source})")
    for name in unchanged:
        print(f"  unchanged {name}")
    if missing:
        dirs = ", ".join(_ICON_DIRS)
        for name in missing:
            print(
                f"  ERROR: {name} not found in [{dirs}] (local checkout or GitHub)",
                file=sys.stderr,
            )
        print(
            f"error: {len(missing)} icon(s) not found under {dirs} — either "
            "_ICON_DIRS in this script needs a new subdirectory, or the icon "
            "doesn't exist in PBIcons",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
