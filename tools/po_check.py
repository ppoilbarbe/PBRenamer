#!/usr/bin/env python3
"""
PO file inspection tool for PBRenamer.

Uses the babel library (same as pybabel) to parse .po files correctly,
including multi-line msgid/msgstr.  Never calls msgfmt/xgettext/msgmerge.

Usage
-----
    python tools/po_check.py                   # statistics for all languages
    python tools/po_check.py --lang fr         # statistics for one language
    python tools/po_check.py --empty           # list untranslated entries (all langs)
    python tools/po_check.py --empty --lang fr # untranslated entries for fr only
    python tools/po_check.py --search PATTERN  # find msgids matching PATTERN (regex)
    python tools/po_check.py --search PATTERN --msgstr  # also search in msgstr
    python tools/po_check.py --diff fr de        # compare two languages
"""

import argparse
import re
import sys
from pathlib import Path

try:
    from babel.messages.pofile import read_po
except ImportError:
    sys.exit("babel is not installed.  Run: conda install -n pbrenamer babel")

LOCALE_DIR = Path(__file__).parent.parent / "src" / "pbrenamer" / "locale"
ALL_LANGS = sorted(
    p.name
    for p in LOCALE_DIR.iterdir()
    if p.is_dir() and (p / "LC_MESSAGES" / "pbrenamer.po").exists()
)


def load_catalog(lang: str):
    po_path = LOCALE_DIR / lang / "LC_MESSAGES" / "pbrenamer.po"
    with po_path.open(encoding="utf-8") as fh:
        return read_po(fh)


def is_empty(msg) -> bool:
    """True when the msgstr carries no translated content."""
    s = msg.string
    if not s:
        return True
    if isinstance(s, tuple):
        return all(not part for part in s)
    return False


def is_shortcut(msgid: str) -> bool:
    """Keyboard shortcuts and technical tokens that are intentionally left empty."""
    stripped = msgid.strip()
    # Ctrl/Alt/Shift combos, bare glob patterns, single-word tech tokens
    if re.fullmatch(r"(Ctrl|Alt|Shift)\+\S+", stripped):
        return True
    if re.fullmatch(r"\*\.\w+", stripped):
        return True
    return False


def stats_for(lang: str) -> dict:
    cat = load_catalog(lang)
    total = translated = fuzzy = shortcut_empty = 0
    untranslated = []
    for msg in cat:
        if not msg.id:
            continue  # header entry
        total += 1
        if msg.fuzzy:
            fuzzy += 1
        if is_empty(msg):
            if is_shortcut(str(msg.id)):
                shortcut_empty += 1
            else:
                untranslated.append(msg)
        else:
            translated += 1
    return {
        "lang": lang,
        "total": total,
        "translated": translated,
        "untranslated": untranslated,
        "shortcut_empty": shortcut_empty,
        "fuzzy": fuzzy,
    }


def print_stats(langs):
    header = (
        f"{'lang':<8} {'total':>6} {'transl':>8}"
        f" {'missing':>8} {'shortcuts':>10} {'fuzzy':>6}"
    )
    print(header)
    print("-" * len(header))
    for lang in langs:
        s = stats_for(lang)
        miss = len(s["untranslated"])
        print(
            f"{s['lang']:<8} {s['total']:>6} {s['translated']:>8} {miss:>8}"
            f" {s['shortcut_empty']:>10} {s['fuzzy']:>6}"
        )


def print_empty(langs):
    for lang in langs:
        s = stats_for(lang)
        if not s["untranslated"]:
            print(f"[{lang}] ✓ no missing translations")
            continue
        print(f"\n[{lang}] {len(s['untranslated'])} missing:")
        for msg in s["untranslated"]:
            msgid = msg.id if isinstance(msg.id, str) else msg.id[0]
            print(f"  {msgid!r}")


def print_search(langs, pattern: str, in_msgstr: bool):
    rx = re.compile(pattern, re.IGNORECASE)
    for lang in langs:
        cat = load_catalog(lang)
        hits = []
        for msg in cat:
            if not msg.id:
                continue
            msgid = msg.id if isinstance(msg.id, str) else msg.id[0]
            msgstr = (
                msg.string if isinstance(msg.string, str) else (msg.string or ("",))[0]
            )
            if rx.search(msgid) or (in_msgstr and rx.search(msgstr or "")):
                hits.append((msgid, msgstr or ""))
        if not hits:
            continue
        print(f"\n[{lang}] {len(hits)} match(es) for {pattern!r}:")
        for msgid, msgstr in hits:
            print(f"  msgid  : {msgid!r}")
            print(f"  msgstr : {msgstr!r}")
            print()


def print_diff(lang_a: str, lang_b: str):
    sa = stats_for(lang_a)
    sb = stats_for(lang_b)
    ids_a = {str(m.id) for m in sa["untranslated"]}
    ids_b = {str(m.id) for m in sb["untranslated"]}
    only_a = ids_a - ids_b
    only_b = ids_b - ids_a
    both = ids_a & ids_b
    print(f"Missing in both {lang_a} and {lang_b} ({len(both)}):")
    for i in sorted(both):
        print(f"  {i!r}")
    print(f"\nMissing only in {lang_a} ({len(only_a)}):")
    for i in sorted(only_a):
        print(f"  {i!r}")
    print(f"\nMissing only in {lang_b} ({len(only_b)}):")
    for i in sorted(only_b):
        print(f"  {i!r}")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--lang", metavar="LANG", help="restrict to one language (e.g. fr)"
    )
    parser.add_argument("--empty", action="store_true", help="list untranslated msgids")
    parser.add_argument("--search", metavar="PATTERN", help="regex to search in msgids")
    parser.add_argument(
        "--msgstr", action="store_true", help="also search in msgstr (with --search)"
    )
    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("LANG_A", "LANG_B"),
        help="compare untranslated between two languages",
    )
    args = parser.parse_args()

    langs = [args.lang] if args.lang else ALL_LANGS

    for lang in langs:
        po = LOCALE_DIR / lang / "LC_MESSAGES" / "pbrenamer.po"
        if not po.exists():
            sys.exit(f"No PO file found for language {lang!r} at {po}")

    if args.diff:
        print_diff(args.diff[0], args.diff[1])
    elif args.search:
        print_search(langs, args.search, args.msgstr)
    elif args.empty:
        print_empty(langs)
    else:
        print_stats(langs)


if __name__ == "__main__":
    main()
