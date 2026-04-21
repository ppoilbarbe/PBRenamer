# PBRenamer

A cross-platform graphical batch file renaming utility built with Qt 6 (PySide6).

PBRenamer lets you rename hundreds of files at once using patterns, regular
expressions, counters, date stamps, and metadata — all previewed live before
any change is applied.

## Features

- **Live preview** — see the result before committing
- **Flexible rules** — text substitution, regex, numbering, case conversion, date/metadata insertion
- **Undo** — revert a rename operation in one click
- **Presets** — save and reuse rule sets
- **Cross-platform** — Linux, macOS, Windows

## Requirements

- Python 3.12 or later
- PySide6 6.6 or later (Qt 6)
- Linux / macOS / Windows

## Installation

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

## Running

```bash
pbrenamer           # installed entry-point
python -m pbrenamer # directly from source
```

## Documentation

Full documentation is available at
[pbrenamer.readthedocs.io](https://pbrenamer.readthedocs.io) _(coming soon)_.

## Contributing

See [CODING.md](CODING.md) for developer setup instructions, coding conventions,
and contribution guidelines.

## License

PBRenamer is free software: you can redistribute it and/or modify it under the
terms of the **GNU General Public License v3** as published by the Free Software
Foundation. See the [LICENSE](LICENSE) file for details.

Copyright © 2026 PBMou — Marcel Spock
<mrspock@cardolan.net>
