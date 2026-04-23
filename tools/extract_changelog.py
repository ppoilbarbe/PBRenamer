#!/usr/bin/env python3
"""Extract the release body for the current git tag from CHANGELOG.md.

Expected format (Keep a Changelog — https://keepachangelog.com/):

    ## [1.2.3] - 2025-04-23
    ### Added
    - …

The extracted section is written to GITHUB_OUTPUT so it can be consumed
by a subsequent ``softprops/action-gh-release`` step.  When run locally
(no GITHUB_OUTPUT) the body is printed to stdout instead.

Usage:
    python3 tools/extract_changelog.py        # in CI (GITHUB_REF_NAME set)
    python3 tools/extract_changelog.py v1.2.3 # local test
"""

import os
import re
import sys


def extract(content: str, version: str) -> str:
    """Return the body of the changelog section for *version*, or ''."""
    pattern = rf"(?m)^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)"
    m = re.search(pattern, content, re.DOTALL)
    return m.group(1).strip() if m else ""


def main() -> None:
    tag = os.environ.get("GITHUB_REF_NAME") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not tag:
        print("error: provide a tag via GITHUB_REF_NAME or argv[1]", file=sys.stderr)
        sys.exit(1)

    version = tag.lstrip("v")

    try:
        with open("CHANGELOG.md", encoding="utf-8") as f:
            content = f.read()
        body = extract(content, version)
    except FileNotFoundError:
        body = ""

    if not body:
        print(f"warning: no CHANGELOG.md entry found for [{version}]", file=sys.stderr)
        body = f"Release {tag}."

    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        # Multiline value using the heredoc delimiter syntax required by GitHub
        # Actions when the content may itself contain newlines.
        with open(github_output, "a", encoding="utf-8") as f:
            f.write("body<<CHANGELOG_EOF\n")
            f.write(body)
            f.write("\nCHANGELOG_EOF\n")
    else:
        print(body)


if __name__ == "__main__":
    main()
