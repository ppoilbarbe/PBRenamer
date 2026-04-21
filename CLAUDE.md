# Mode
`full-en` — code and all communication in English.

# Project: PBRenamer
GUI batch file renamer. Python 3.12+, PySide6 (Qt6), src layout.
Publisher: PBMou | Author: Marcel Spock <mrspock@cardolan.net> | License: GPLv3

## Stack
- GUI: PySide6; Qt Designer via `pyside6-designer` / `make designer`
- Tests: pytest + pytest-qt (use `qtbot`, never instantiate `QApplication` manually)
- Docs: Sphinx + sphinx-rtd-theme, hosted on ReadTheDocs
- Lint: ruff (line-length 100, target py312)
- Env: conda, env name `pbrenamer` — `make venv` to create

## Layout
`src/pbrenamer/` sources | `tests/` pytest suite | `docs/` Sphinx
`Makefile` task runner — `make help` for all targets
