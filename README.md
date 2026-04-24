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
  - Counter (`{num}`, `{num3}`, `{num2+10}`), date (`{date}`, `{year}`…), parent-folder name (`{dir}`)
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

```bash
pbrenamer            # launch the GUI (installed entry-point)
python -m pbrenamer  # launch from source

pbrenamer --help     # show command-line help and exit
pbrenamer --version  # print version and exit
```

Qt platform options (`--style`, `--platform`, `--display`, …) are forwarded
to Qt and can be combined with the above flags.

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
