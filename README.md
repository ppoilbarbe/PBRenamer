# PBRenamer

A cross-platform graphical batch file renaming utility built with Qt 6 (PySide6).

PBRenamer lets you rename hundreds of files at once using patterns, substitutions,
counters, date stamps, and metadata — all previewed live before any change is applied.

## Features

- **Live preview** with conflict detection — renamed entries that collide with
  existing files or with each other are highlighted in red; the Rename button
  is disabled until all conflicts are resolved
- **Multi-selection** — apply transformations to selected files only
- **Flexible renaming rules**
  - Pattern-based search / replace (`{#}`, `{L}`, `{X}`, `{@}`, capture groups…)
  - Text substitution (find & replace, spaces ↔ underscores / dots / dashes, case)
  - Insert or delete characters at a given position
  - Manual rename for individual files
  - Counter (`{num}`, `{num:03}` zero-padded, `{num::10}` start offset), conflict-free auto-number (`{newnum}`)
  - Dates (`{date}`, `{datetime}`, `{mdatetime}` file-modification time), parent-folder name (`{dir}`)
  - Image metadata (`{im:Make}`, `{im:Model}`, `{im:DateTimeOriginal}`… — EXIF/IPTC via Pillow)
  - Audio metadata (`{au:Title}`, `{au:Artist}`, `{au:Album}`, `{au:Year}`… — via mutagen)
  - Video metadata (`{vi:Title}`, `{vi:Duration}`, `{vi:Width}`, `{vi:Height}`, `{vi:VideoCodec}`… — via pymediainfo)
- **Directory colouring** — directories are shown in a distinct colour in the file list
- **Keep extension** option — transformations apply to the stem only
- **Recursive** directory traversal
- **Undo** — revert the last rename batch in one click
- **Pattern presets** — save and reuse search/replace pairs
- **Case-aware conflict detection** — honours the case sensitivity of the
  underlying filesystem (case-insensitive on Windows/macOS by default)
- **Internationalised** — English and French included; additional languages can
  be added via gettext `.po` files
- **Cross-platform** — Linux, macOS, Windows

## Download

Pre-built standalone executables are attached to every
[GitHub release](https://github.com/ppoilbarbe/PBRenamer/releases):

| Platform | File |
|---|---|
| Linux x86-64  | `PBRenamer-<ver>-linux-x86_64` |
| Windows x86-64 | `PBRenamer-<ver>-windows-x86_64.exe` |
| macOS (Apple Silicon) | `PBRenamer-<ver>-macos-arm64.zip` |

No installation required — just download and run.

## Installation from source

### Requirements

- Python 3.12 or later
- PySide6 6.6 or later (Qt 6)

### From PyPI _(once published)_

```bash
pip install pbrenamer
```

### From source

```bash
git clone https://github.com/ppoilbarbe/PBRenamer.git
cd PBRenamer
pip install .
```

## Usage

### GUI mode

```bash
pbrenamer            # launch the GUI (current directory)
pbrenamer /path/dir  # launch the GUI starting in a given directory
python -m pbrenamer  # launch from source

pbrenamer --help     # show command-line help and exit
pbrenamer --version  # print version and exit
```

Qt platform options (`--style`, `--platform`, `--display`, …) are forwarded
to Qt and can be combined with the above flags.

### Headless (command-line) mode

Providing `--search` disables the GUI and renames files directly from the
terminal. All options that exist in the main window are available:

```
pbrenamer [DIR] --search TEXT [--replace TEXT] [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `-s`, `--search TEXT` | _(required¹)_ | Search pattern — activates headless mode |
| `--saved NAME` | _(required¹)_ | Load a named preset — activates headless mode; CLI options override preset values |
| `-r`, `--replace TEXT` | `""` | Replacement string |
| `--mode {pattern,regex,plain}` | `pattern` | Search mode |
| `--list {files,dirs,all}` | `files` | Entry types to process |
| `--recurse` / `--no-recurse` | `--no-recurse` | Recurse into sub-directories |
| `--keep-ext` / `--no-keep-ext` | `--keep-ext` | Preserve the file extension |
| `--filter GLOB` | _(none)_ | Restrict listing to matching entries |
| `--accent` / `--no-accent` | `--no-accent` | Strip diacritics from result names |
| `--dup` / `--no-dup` | `--no-dup` | Collapse consecutive duplicate separators |
| `--sep {none,space-underscore,…}` | `none` | Separator conversion applied after rename |
| `--case {none,upper,lower,capitalize,title}` | `none` | Apply capitalisation after rename |
| `--confirm` / `--no-confirm` | `--no-confirm` | Preview and confirm before renaming |
| `--debug` / `--verbose` / `--quiet` | _(saved pref)_ | Override the saved log-level preference |

¹ Exactly one of `--search` or `--saved` is required.

**Examples**

```bash
# Replace underscores with hyphens, preview first
pbrenamer ~/Photos --search "_" --replace "-" --mode plain --confirm

# Number all JPEG files: photo_001.jpg, photo_002.jpg, …
pbrenamer ~/Photos --search "{L}" --replace "photo_{num:03}" --filter "*.jpg"

# Strip diacritics and upper-case everything, recursively
pbrenamer ~/docs --search "{X}" --replace "{1}" --recurse --accent --case upper

# Rename using a regex capture group
pbrenamer . --search "img(\d+)" --replace "photo_{1}" --mode regex
```

Conflicting renames (two files mapping to the same target, or target already
exists) are detected and skipped automatically; `--confirm` shows them flagged
as `[CONFLICT]` before you confirm.

## Documentation

Full documentation is available at
[pbrenamer.readthedocs.io](https://pbrenamer.readthedocs.io) _(coming soon)_.

## Contributing

See [CODING.md](CODING.md) for developer setup, coding conventions, and the
release process.

The development environment is managed with conda, but all `make` targets can
run against a plain Python environment by setting `NOCONDA=1` (see CODING.md).

## License

PBRenamer is free software: you can redistribute it and/or modify it under the
terms of the **GNU General Public License v3** as published by the Free Software
Foundation. See the [LICENSE](LICENSE) file for details.

Copyright © 2026 PBMou — Marcel Spock <mrspock@cardolan.net>

## Acknowledgements

PBRenamer is heavily inspired by
[pyRenamer](https://github.com/TheTimeTombs/pyRenamer), an earlier graphical
batch file renamer for Linux. Many thanks to its authors,
Adolfo González Blázquez <code@infinicode.org> and
Thomas Freeman <tfree87@users.noreply.github.com>, for their great work.
