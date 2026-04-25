# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.1] - 2026-04-25

### Fixed

- README: remove insert/delete at position and manual rename from feature
  list (functions exist in `filetools.py` but are not wired to the GUI)

## [0.3.0] - 2026-04-25

### Added

- Complete Sphinx documentation: user guide (GUI usage, all search modes,
  replacement fields reference, headless CLI reference) and API reference
  (autodoc for all modules)
- `docs/conf.py` generates `changelog.rst` from `CHANGELOG.md` at build time;
  the generated file is gitignored

## [0.2.0] - 2026-04-24

### Added

- Non-modal help dialogs for search and replace patterns, with geometry
  persistence (position and size saved across sessions)
- Help dialog content fully translated (English and French); field-name tokens
  left in code syntax, all descriptions and headers localised
- Log-level preference in the Settings dialog (DEBUG / INFO / WARNING / ERROR /
  CRITICAL, default INFO); applied at startup and immediately on change
- CLI flags `--debug` / `-d`, `--verbose` / `-v`, `--quiet` / `-q` to override
  the saved log-level preference at launch
- Debug traces throughout the codebase via Python `logging` (file listing,
  per-file preview, rename operations, metadata reads, template parsing)
- `.ui` files for the About, Settings and History dialogs; all dialogs now
  follow the Designer → `pyside6-uic` workflow
- `WindowState.save_geometry` / `load_geometry` for named secondary-window
  geometry slots

### Fixed

- CI "Compile Qt UI files" step now compiles all `*.ui` files instead of only
  `main_window.ui`, fixing `ModuleNotFoundError` for the new dialog modules

## [0.1.0] - 2026-04-23

### Added

- Live-preview rename table with per-row conflict highlighting; Rename button
  disabled until all conflicts are resolved
- Flexible renaming rules: pattern search/replace, text substitution, case
  transforms, insert/delete at position, counter, date stamps, parent-folder
  name, and manual rename
- Keep-extension option so transforms apply to the stem only
- Multi-selection — apply rules to selected files only
- Recursive directory traversal
- Directory entries shown in a distinct colour
- One-click undo of the last rename batch
- Pattern preset save/restore (persisted per user)
- Case-aware conflict detection honouring the filesystem's actual
  case-sensitivity (probed at runtime)
- Language settings dialog; language preference persisted across sessions
- Internationalisation via gettext — English and French bundled
- Platform abstraction layer (`platform/`) covering Linux (XDG), macOS, and
  Windows for config/data directories, filesystem probing, and locale detection
- Standalone executable builds via PyInstaller for Linux, macOS, and Windows
- CI/CD pipeline: test → pre-commit hooks → 3-platform build → GitHub release
  on semver tag
- `make bump-patch / bump-minor / bump-major / bump-set` targets backed by
  `tools/bump_version.py` for atomic version increments
- `NOCONDA=1` Makefile flag to bypass conda wrapping when tools are on `PATH`

[0.3.1]: https://github.com/ppoilbarbe/PBRenamer/releases/tag/v0.3.1
[0.3.0]: https://github.com/ppoilbarbe/PBRenamer/releases/tag/v0.3.0
[0.2.0]: https://github.com/ppoilbarbe/PBRenamer/releases/tag/v0.2.0
[0.1.0]: https://github.com/ppoilbarbe/PBRenamer/releases/tag/v0.1.0
