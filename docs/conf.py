"""Sphinx configuration for PBRenamer."""

import re
import sys
from pathlib import Path

# Make the src layout importable by autodoc without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pbrenamer import __version__

project = "PBRenamer"
author = "Marcel Spock"
copyright = "2026, PBMou"
release = __version__
version = ".".join(__version__.split(".")[:2])

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosummary",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pillow": ("https://pillow.readthedocs.io/en/stable/", None),
}

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_logo = "_static/pbrenamer.svg"
html_favicon = "_static/pbrenamer.svg"
html_theme_options = {
    "navigation_depth": 4,
    "titles_only": False,
}

autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_typehints_format = "short"

# Mock PySide6 and generated *_ui.py artefacts so autodoc never triggers
# PySide6's shibokensupport import hooks, which cause inspect.unwrap() to
# loop on MagicMock wrappers and raise ValueError.
autodoc_mock_imports = [
    "PySide6",
    "pbrenamer.ui.main_window_ui",
    "pbrenamer.ui.about_dialog_ui",
    "pbrenamer.ui.history_dialog_ui",
    "pbrenamer.ui.settings_dialog_ui",
]

napoleon_google_docstring = False
napoleon_numpy_docstring = False

autosummary_generate = True


# ---------------------------------------------------------------------------
# Changelog — generated from CHANGELOG.md at build time
# ---------------------------------------------------------------------------

_H2 = re.compile(r"^## \[([^\]]+)\] - (\d{4}-\d{2}-\d{2})\s*$")
_H3 = re.compile(r"^### (.+)$")
_LINK = re.compile(r"^\[[^\]]+\]:\s*https?://")

_UNDERLINES = {1: "=", 2: "-", 3: "^"}


def _section(title: str, level: int) -> str:
    char = _UNDERLINES[level]
    return f"{title}\n{char * len(title)}\n"


def _md_inline(text: str) -> str:
    """Convert inline Markdown to RST (bold, inline code, backticks)."""
    text = re.sub(r"`([^`]+)`", r"``\1``", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"**\1**", text)
    return text


def _heading(out: list[str], title: str, level: int) -> None:
    """Append a RST heading with exactly one blank line before it."""
    char = _UNDERLINES[level]
    while out and out[-1] == "":
        out.pop()
    out.append("")
    out.append(title)
    out.append(char * len(title))


def _convert_changelog(md_path: Path) -> str:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    in_intro = True

    for line in lines:
        # Skip reference link lines at the bottom
        if _LINK.match(line):
            continue

        m2 = _H2.match(line)
        if m2:
            in_intro = False
            _heading(out, f"{m2.group(1)} ({m2.group(2)})", 2)
            continue

        m3 = _H3.match(line)
        if m3:
            _heading(out, m3.group(1), 3)
            continue

        if in_intro:
            continue

        # Keep single blank lines; drop consecutive duplicates
        converted = _md_inline(line)
        if converted == "" and out and out[-1] == "":
            continue
        out.append(converted)

    header = ["Changelog", "=" * len("Changelog")]
    preamble = [
        "",
        "All notable changes to this project are documented here.",
        "The format is based on `Keep a Changelog"
        " <https://keepachangelog.com/en/1.1.0/>`_.",
    ]
    return "\n".join(header + preamble + out).rstrip() + "\n"


_DOCS_DIR = Path(__file__).parent
_CHANGELOG_MD = _DOCS_DIR.parent / "CHANGELOG.md"
_CHANGELOG_RST = _DOCS_DIR / "changelog.rst"

_CHANGELOG_RST.write_text(_convert_changelog(_CHANGELOG_MD), encoding="utf-8")


# ---------------------------------------------------------------------------
# Logo / favicon — copied from the app's own icon at build time, so the
# artwork has a single source of truth (src/pbrenamer/resources/pbrenamer.svg).
# ---------------------------------------------------------------------------

_SVG_ROOT_TAG = re.compile(r"<svg\b[^>]*>", re.DOTALL)
_VIEWBOX = re.compile(r'viewBox="0 0 (\d+) (\d+)"')


def _svg_with_explicit_size(svg_text: str) -> str:
    """Add width/height attributes derived from the viewBox, if missing.

    Guards against SVGs that rely on percentage sizing (fine for Qt's
    fixed-size widget rendering) but leave the intrinsic size undefined for
    a browser <img>, which some browsers (e.g. Firefox) then render as 0x0.
    A no-op when the root already has explicit width/height attributes.
    """
    root_match = _SVG_ROOT_TAG.search(svg_text)
    if not root_match or "width=" in root_match.group():
        return svg_text
    m = _VIEWBOX.search(root_match.group())
    if not m:
        return svg_text
    width, height = m.groups()
    start = root_match.start() + len("<svg")
    return f'{svg_text[:start]} width="{width}" height="{height}"{svg_text[start:]}'


_APP_ICON = _DOCS_DIR.parent / "src" / "pbrenamer" / "resources" / "pbrenamer.svg"
_STATIC_ICON = _DOCS_DIR / "_static" / "pbrenamer.svg"

_STATIC_ICON.write_text(
    _svg_with_explicit_size(_APP_ICON.read_text(encoding="utf-8")), encoding="utf-8"
)
