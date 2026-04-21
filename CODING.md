# Developer Guide

This document covers everything you need to contribute to PBRenamer.
For user-facing information see [README.md](README.md).

## Tech stack

| Layer        | Technology                          |
|--------------|-------------------------------------|
| Language     | Python 3.12+                        |
| GUI          | PySide6 (Qt 6 official Python binding) |
| UI design    | Qt Designer (`pyside6-designer`)    |
| Tests        | pytest + pytest-qt                  |
| Linter       | ruff                                |
| Docs         | Sphinx + sphinx-rtd-theme           |
| Package mgr  | conda (env: `pbrenamer`)            |
| Build        | Hatchling (`pyproject.toml`)        |
| CI/CD        | GitHub Actions                      |

## Project layout

```
PBRenamer/
├── src/pbrenamer/       # application source (src layout)
│   ├── __init__.py      # version / metadata
│   ├── __main__.py      # entry point
│   └── ui/
│       └── main_window.py
├── tests/               # pytest test suite
├── docs/                # Sphinx documentation
├── pyproject.toml       # project metadata + tool config
├── Makefile             # development task runner
├── .readthedocs.yaml    # ReadTheDocs build config
└── .gitignore
```

## Setup

### 1. Create the conda environment

```bash
make venv
conda activate pbrenamer
```

This installs Python 3.12, PySide6 (including Qt Designer), pytest, Sphinx,
ruff, and the GitHub CLI in a self-contained conda environment.

### 2. Install the package in editable mode

```bash
make install   # equivalent to: pip install -e ".[dev]"
```

## Daily workflow

| Task                    | Command           |
|-------------------------|-------------------|
| Run the application     | `make run`        |
| Run tests               | `make test`       |
| Lint & style check      | `make lint`       |
| Auto-format             | `make format`     |
| Build docs              | `make docs`       |
| Live-reload docs        | `make docs-live`  |
| Open Qt Designer        | `make designer`   |
| Remove build artifacts  | `make clean`      |

Run `make` (or `make help`) to see all available targets with descriptions.

## Coding conventions

- **Language**: English — all identifiers, comments, docstrings, and commit
  messages must be in English.
- **Style**: enforced by `ruff` (line length 100, target Python 3.12).
- **Docstrings**: one-line summary for simple items; NumPy style for public API.
- **Type hints**: required on all public functions and methods.
- **No comments** unless the *why* is non-obvious (avoid narrating what the
  code obviously does).

## Qt Designer workflow

UI files are stored in `src/pbrenamer/ui/` with a `.ui` extension and compiled
to Python with:

```bash
pyside6-uic src/pbrenamer/ui/main_window.ui -o src/pbrenamer/ui/main_window_ui.py
```

Generated `*_ui.py` files are **not** committed — add them to `.gitignore`.
Import the generated class via composition, not multiple inheritance.

## Testing

```bash
make test               # full suite with coverage
pytest -k test_foo      # single test
pytest --no-cov         # skip coverage
```

Tests live in `tests/` and mirror the source structure.
Use `qtbot` from `pytest-qt` for all widget interactions.
Do **not** instantiate `QApplication` manually in tests — `pytest-qt` manages it.

## Documentation

Source is in `docs/` (reStructuredText).
Build locally with `make docs`; the output lands in `docs/_build/html/`.
ReadTheDocs builds are configured in `.readthedocs.yaml`.

## Releasing

1. Bump `version` in `pyproject.toml` and `src/pbrenamer/__init__.py`.
2. Update `docs/changelog.rst`.
3. Tag: `git tag v0.x.y && git push --tags`
4. Build: `python -m build`
5. Publish: `twine upload dist/*`

## License

GPLv3 — all contributions must be compatible with this license.
Copyright © 2026 PBMou — Marcel Spock <mrspock@cardolan.net>
