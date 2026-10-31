# PBRenamer

[![Release](https://img.shields.io/github/v/release/ppoilbarbe/PBRenamer)](https://github.com/ppoilbarbe/PBRenamer/releases/latest)
[![CI](https://github.com/ppoilbarbe/PBRenamer/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ppoilbarbe/PBRenamer/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/ppoilbarbe/PBRenamer/branch/main/graph/badge.svg)](https://codecov.io/gh/ppoilbarbe/PBRenamer)
[![PyPI](https://img.shields.io/pypi/v/pbrenamer)](https://pypi.org/project/pbrenamer/)
[![Documentation Status](https://readthedocs.org/projects/pbrenamer/badge/?version=latest)](https://pbrenamer.readthedocs.io/en/latest/?badge=latest)

A cross-platform graphical batch file renaming utility built with Qt 6 (PySide6).

PBRenamer lets you rename hundreds of files at once using patterns, substitutions,
counters, date stamps, and metadata — all previewed live before any change is applied.
Its Schema mode files photos and videos into a folder tree built from a few
fields, and its optional image tools (thumbnails, viewer, lossless rotation,
EXIF orientation) cover a whole photo-sorting workflow.

PBRenamer 2.0 replaces **PBPicat**: its catalogues are imported as profiles on
the first start (see
[Migrating from PBPicat](https://pbrenamer.readthedocs.io/en/latest/user_guide.html#pbpicat-migration)).

## Features

- **Live preview** with conflict detection — renamed entries that collide with
  existing files or with each other are highlighted in red; the Rename button
  is disabled until all conflicts are resolved
- **Atomic renames** — every target is checked first and a failure rolls back
  the whole batch; swaps and chains of names are handled
- **Two modes**
  - **Pattern** — search / replace on file names (see the rules below)
  - **Schema** — a list of fields such as `Trip,,Paris,###` builds both the
    folder tree under a destination root and the file name
    (`Trip/Paris/Trip_Paris_001.jpg`), with a counter that continues after
    the highest existing number, an optional video marker, *Fill gaps* and
    *Renumber*; *Template* infers the fields from an existing file name
- **Profiles** — named sets of settings (mode, schema, presets, histories,
  sidecars, display and image options) for each workflow; hidden profiles,
  `--profile NAME` on the command line
- **Multi-selection** — apply transformations to selected files only
- Flexible renaming rules
  - Pattern-based search / replace (`{#}`, `{L}`, `{X}`, `{@}`, capture groups…)
  - Text substitution (find & replace, spaces ↔ underscores / dots / dashes, case)
  - Counter (`{num}`, `{num:03}` zero-padded, `{num::10}` start offset), auto-number continuing
    after the highest number in the target folder (`{newnum}`)
  - Folders in the result (`2024/{1}`), destination root (`{dest}`), text for one file category only
    (`{if:video:_vid}`)
  - Dates (`{date}`, `{datetime}`, `{mdatetime}` file-modification time), parent-folder name
    (`{dir}`)
  - Image metadata (`{im:Make}`, `{im:Model}`, `{im:DateTimeOriginal}`… — EXIF/IPTC via Pillow)
  - Audio metadata (`{au:Title}`, `{au:Artist}`, `{au:Album}`, `{au:Year}`… — via mutagen)
  - Video metadata (`{vi:Title}`, `{vi:Duration}`, `{vi:Width}`, `{vi:Height}`, `{vi:VideoCodec}`… —
    via pymediainfo)
  - **Mixed-type templates**: combining `{im:…}`, `{vi:…}` and `{au:…}` in the same
    replacement field works across file types — the non-matching tokens silently
    produce nothing (e.g. `{im:DateTimeOriginal:%Y-%m-%d:}{vi:encodeddate:%Y-%m-%d:}`
    uses the EXIF date for images and the encoded date for videos)
- **Directory colouring** — directories are shown in a distinct colour in the file list
- **Thumbnails** — optional thumbnail column, loaded lazily (HEIC included)
- **Extension mode** — *Keep*, *Lowercase*, *Uppercase*, *Normalize* (via a
  user-editable extension mapping table), or *Modify* (extension included in
  the search/replace pattern)
- **Sidecar files** — a file associated with a base file by a name suffix
  (e.g. `img.jpg` + `img.xmp`) can be grouped, coloured, selected, and renamed
  together with its base file; an ambiguous sidecar (matching more than one
  candidate base file) is flagged as an explicit, unrenamable error; an
  optional sidecar column opens or creates sidecars, and a filter keeps the
  files whose sidecar content matches a regular expression
- **Image tools** — Images menu and context menu: viewer (zoom, selection
  strip, metadata panel), lossless rotation (jpegtran or Pillow), apply or
  reset the EXIF orientation, Open with, delete with sidecars (to the trash),
  orphan sidecars
- **Drag'n'drop** — copy or move files and directories between the directory
  tree, the file list, and external applications, with a batched
  Overwrite/Skip/Cancel confirmation on collisions; sidecars follow their file
- **Recursive** directory traversal
- **Undo** — revert the last batch (rename, move, copy, rotation, EXIF reset)
  in one click; the button shows the number of batches available for undo
- **Pattern presets** — save and reuse search/replace pairs
- **History** — LRU drop-down lists for the search, replacement, schema and
  sidecar filter fields; full history browsable and editable via the History
  dialog
- **Directory shortcuts** — Shortcuts menu combines system bookmarks (GTK /
  macOS / Windows) with user-defined favourite directories for fast navigation;
  last-used directory is restored on startup
- **File info** — dedicated window showing filesystem metadata and embedded
  EXIF/IPTC/XMP/ID3/media tags for any selected file
- **Help** — keyboard and mouse shortcuts (F1) and the online user guide in
  the interface language
- **Window state persistence** — window size, position, and splitter ratios are
  saved and restored between sessions
- **Case-aware conflict detection** — honours the case sensitivity of the
  underlying filesystem (case-insensitive on Windows/macOS by default)
- **Internationalised** — 8 languages included (English, German, Spanish,
  French, Italian, Russian, Vietnamese, Chinese); additional languages can be
  added via gettext `.po` files
- **Cross-platform** — Linux, macOS, Windows

## Download

Pre-built standalone executables are attached to every
[GitHub release](https://github.com/ppoilbarbe/PBRenamer/releases):

| Platform | File |
| --- | --- |
| Linux x86-64 | `pbrenamer-<ver>-linux-x86_64` |
| Windows x86-64 | `pbrenamer-<ver>-windows-x86_64.exe` |
| macOS (Apple Silicon) | `pbrenamer-<ver>-macos-arm64.zip` |

No installation required — just download and run.

## Installation from source

### Requirements

- Python 3.12 or later
- PySide6 6.6 or later (Qt 6)

### From PyPI

```bash
pip install pbrenamer                  # renaming only
pip install "pbrenamer[meta,images]"   # with the metadata fields and image tools
```

| Extra | Packages | Enables |
| --- | --- | --- |
| `meta` | Pillow, mutagen, pymediainfo | `{im:…}`, `{au:…}` and `{vi:…}` fields |
| `images` | Pillow, pillow-heif, pyexiv2 | thumbnails (HEIC included), rotation, EXIF orientation, metadata panel |

Lossless JPEG rotation also uses the external `jpegtran` tool when it is on
the `PATH`. Actions that need a missing package are disabled. The
pre-built executables include everything.

On Linux, `pip install` cannot register an application menu entry by itself
(pip has no post-install hook). Run this once after installing to add a
menu entry and icon for the current user:

```bash
pbrenamer --install-desktop-entry
```

Remove it again with `pbrenamer --uninstall-desktop-entry`.

### From source

```bash
git clone https://github.com/ppoilbarbe/PBRenamer.git
cd PBRenamer
pip install .
```

## Usage

### GUI mode

```bash
pbrenamer            # launch the GUI (last-used directory)
pbrenamer /path/dir  # launch the GUI starting in a given directory (use '.' for current)
pbrenamer --profile photos   # launch the GUI on the profile "photos"
python -m pbrenamer  # launch from source

pbrenamer --help     # show command-line help and exit
pbrenamer --version  # print version and exit
```

Qt platform options (`--style`, `--platform`, `--display`, …) are forwarded
to Qt and can be combined with the above flags.

### Headless (command-line) mode

Providing `--search`, `--saved` or `--schema` disables the GUI and renames
files directly from the terminal. All options that exist in the main window
are available:

```text
pbrenamer [DIR] --search TEXT [--replace TEXT] [OPTIONS]      # pattern mode
pbrenamer [DIR] --schema "F1,F2,…,FN" [--dest ROOT] [OPTIONS]  # schema mode
```

| Option | Default | Description |
| --- | --- | --- |
| `-s`, `--search TEXT` | *(required¹)* | Search pattern — activates headless mode |
| `--saved NAME` | *(required¹)* | Load a named preset — activates headless mode; CLI options override preset values |
| `--schema LIST` | *(required¹)* | Comma-separated schema fields — activates headless mode in schema mode (sidecar mode always on) |
| `--dest DIR` | *(profile's destination)* | Destination root: required by `--schema` when the profile has none (except with `--renumber`); value of `{dest}` |
| `--fill-gaps` / `--no-fill-gaps` | *(profile with `--schema`, else off)* | `{newnum}` takes the smallest free number |
| `--renumber` | *(off)* | `{newnum}` restarts from its start value; with `--schema`, renumber the files in place |
| `--video-marker TEXT` | *(profile's marker)* | With `--schema`: text added to the name of video files |
| `--video-marker-pos N` | *(profile's position)* | With `--schema`: position of the video marker between the fields |
| `-r`, `--replace TEXT` | `""` | Replacement string |
| `--mode {pattern,regex,plain}` | `pattern` | Search mode |
| `--list {files,dirs,all}` | `files` | Entry types to process |
| `--recurse` / `--no-recurse` | `--no-recurse` | Recurse into sub-directories |
| `--ext-mode {keep,lower,upper,normalize,modify}` | `keep` | How to handle the extension during rename |
| `--sidecar-mode` / `--no-sidecar-mode` | `--no-sidecar-mode` | Group sidecar files with their base file (requires `--ext-mode keep`, `lower`, or `upper`) |
| `--filter GLOB` | *(none)* | Restrict listing to matching entries |
| `--select GLOB` | *(none — all entries)* | Restrict the rename to matching entries, as if clicked in the GUI; repeatable (accumulates, like Ctrl+click); with `--sidecar-mode`, also selects the matched entry's sidecar group |
| `--accent` / `--no-accent` | `--no-accent` | Strip diacritics from result names |
| `--dup` / `--no-dup` | `--no-dup` | Collapse consecutive duplicate separators |
| `--sep {none,space-underscore,…}` | `none` | Separator conversion applied after rename |
| `--case {none,upper,lower,capitalize,title}` | `none` | Apply capitalisation after rename |
| `--confirm` / `--no-confirm` | `--no-confirm` | Preview and confirm before renaming |
| `--dry-run` / `--no-dry-run` | `--no-dry-run` | Print the equivalent `mv` commands instead of renaming |
| `--profile NAME` | *(last profile used in the GUI)* | Take the settings, presets and schema defaults from profile `NAME` |
| `--debug` / `--verbose` / `--quiet` | *(saved pref)* | Override the saved log-level preference |
| `--config-dir DIR` | *(platform default)* | Override the configuration directory (intended for testing) |

¹ Exactly one of `--search`, `--saved` or `--schema` is required.

### Examples

```bash
# Replace underscores with hyphens, preview first
pbrenamer ~/Photos --search "_" --replace "-" --mode plain --confirm

# Print the mv commands without renaming anything
pbrenamer ~/Photos --search "_" --replace "-" --mode plain --dry-run

# Number all JPEG files: photo_001.jpg, photo_002.jpg, …
pbrenamer ~/Photos --search "{L}" --replace "photo_{num:03}" --filter "*.jpg"

# Strip diacritics and upper-case everything, recursively
pbrenamer ~/docs --search "{X}" --replace "{1}" --recurse --accent --case upper

# Rename using a regex capture group
pbrenamer . --search "img(\d+)" --replace "photo_{1}" --mode regex

# Only rename img1.jpg and img2.jpg (plus their sidecars) out of the whole directory
pbrenamer ~/Photos --search "img" --replace "photo" --sidecar-mode \
    --select "img1.jpg" --select "img2.jpg"

# File the photos of a card as ~/Sorted/Trip/Paris/Trip_Paris_001.jpg, …
pbrenamer /media/card --schema "Trip,,Paris,###" --dest ~/Sorted --dry-run
```

Renames are atomic: if any target conflicts (two files mapping to the same
target, or target already exists), nothing is renamed and the command exits
with status 1 after listing the conflicts; `--dry-run` shows them as
`# CONFLICT:` comments.

## Documentation

Full documentation is available at
[pbrenamer.readthedocs.io](https://pbrenamer.readthedocs.io).

## Contributing

See [CODING.md](CODING.md) for developer setup, coding conventions, and the
release process.

The development environment is managed with pixi, but all `make` targets can
run against a plain Python environment by setting `NOCONDA=1` (see CODING.md).

## License

PBRenamer is free software: you can redistribute it and/or modify it under the
terms of the **GNU General Public License v3** as published by the Free Software
Foundation. See the [LICENSE](LICENSE) file for details.

Copyright © 2026 PBMou — Marcel Spock <mrspock@cardolan.net>

## Author

Marcel Spock <mrspock@cardolan.net>
PBMou

PBMou is a cross-language pun: "PB" stands for "Poilbarbe", and "Mou" is the
French translation of "Soft" — so PBMou reads like "PBSoft" half-translated
into French.

## Acknowledgements

PBRenamer is heavily inspired by
[pyRenamer](https://github.com/TheTimeTombs/pyRenamer), an earlier graphical
batch file renamer for Linux. Many thanks to its authors,
Adolfo González Blázquez <code@infinicode.org> and
Thomas Freeman <tfree87@users.noreply.github.com>, for their great work.
