#!/usr/bin/env bash
# Emit the release version (stripped from the exact git tag) or "dev".
# A release version is only produced when HEAD is tagged exactly AND the
# working tree is clean (no staged or unstaged changes).
tag=$(git describe --exact-match --tags HEAD 2>/dev/null)
if [ -n "$tag" ] && git diff --quiet && git diff --cached --quiet; then
    echo "${tag#v}"
else
    echo "dev"
fi
