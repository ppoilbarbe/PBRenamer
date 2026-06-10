# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Undo button displays the number of available undo levels — text changes to
  "Undo (N)" and the tooltip explains how many rename batches can be reverted
- Case-transform modifier in replacement field tokens: `=` (unchanged), `-`
  (lower), `+` (upper), `!` (capitalise first char), `*` (Title Case)
- Centre-align (`^`) in replacement field tokens
- Toolbar-state and preview-delay persistence in Settings
- `tools/po_check.py`: PO file inspection tool using the babel library
  (statistics, untranslated entries, regex search, language diff) — replaces
  ad-hoc `grep`/`msgfmt` usage that breaks on multi-line entries

### Fixed

- Pattern help dialog: HTML-escaped `{1:&lt;12}` so the browser no longer
  interprets `<12>` as an HTML tag

## [1.2.0] - 2026-06-09

### Added

- **Shortcuts menu** (`Go → Shortcuts`): navigate instantly to system directories
  (Home, Desktop, Documents, Downloads, Pictures, Music, Videos on all platforms;
  GTK bookmarks on Linux) and user-defined shortcuts
- Right-click on any directory in the tree to **Add as shortcut**; shortcuts are
  persisted to `shortcuts.json` in the user config directory
- **Edit Shortcuts** dialog (`Go → Edit Shortcuts`): reorder (Move up / Move down)
  and remove user-defined shortcuts
- **File information window** (`View → File information`): non-modal window that
  shows the actual values of all replacement fields (`{date}`, `{mdatetime}`,
  `{dir}`, `{im:…}`, `{au:…}`, `{vi:…}`, …) for the currently selected file;
  updates live as the selection changes
- **Restore last opened directory** setting in the new *Behaviour* group of the
  Settings dialog; when enabled, the app reopens the last accessed directory at
  startup (CLI-provided directory always takes priority; default: disabled)
- `make run` now accepts an `ARGS` variable to forward arguments and options to
  the program (e.g. `make run ARGS="--debug /some/dir"`)

### Fixed

- `email.utils` was incorrectly listed in PyInstaller `excludes`, causing
  `importlib.metadata` calls in the About dialog to fail in packaged builds
- CI `test` job now compiles `.mo` catalogues before running the test suite,
  fixing four `test_i18n.py` failures (`available_languages()` globs `.mo` files
  which are gitignored and were absent on the runner)

### Changed

- Executable names are now lowercase in the PyInstaller spec and CI artifact globs
  (e.g. `pbrenamer-1.2.0-linux-x86_64` instead of `PBRenamer-…`)
- `pybabel extract` now uses `--no-location` to omit source-file/line-number
  comments from `.po` files; `make translate` is idempotent on an unchanged
  source tree, fixing `make dist` always producing a `dev` build instead of
  using the git tag version

## [1.1.0] - 2026-06-01

### Added

- `srcdist` Makefile target: produces a source archive
  `dist/pbrenamer-<ver>-src.tar.gz` via `git archive`
- `tools/git_version.sh`: derives the version string from the exact Git tag
  when HEAD is tagged and the working tree is clean, falls back to `dev`;
  used by both `dist` and `srcdist` targets

### Changed

- i18n toolchain replaced: `xgettext`/`msgmerge`/`msgfmt`/`msginit` removed in
  favour of `pybabel extract`/`update`/`compile`/`init`; `babel.cfg` mapping
  file added; `gettext` dependency replaced by `babel` in `environment.yml`

### Removed

- `.mo` compiled catalogues removed from the repository (now gitignored); the
  CI regenerates them via `pybabel compile` before each PyInstaller build

## [1.0.0] - 2026-05-03

### Added

- Translations for six new languages: German (`de`), Spanish (`es`), Italian
  (`it`), Russian (`ru`), Vietnamese (`vi`), and Simplified Chinese (`zh_CN`)
- All 272 translatable strings covered in each new locale; `.mo` files compiled
  and committed alongside the `.po` sources

## [0.3.2] - 2026-04-25

### Fixed

- `docs/conf.py`: read `release` and `version` dynamically from
  `pbrenamer.__version__` instead of a hard-coded string, so the Sphinx build
  always reflects the current version without a manual update

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

[1.2.0]: https://github.com/ppoilbarbe/PBRenamer/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/ppoilbarbe/PBRenamer/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/ppoilbarbe/PBRenamer/releases/tag/v1.0.0
[0.3.2]: https://github.com/ppoilbarbe/PBRenamer/releases/tag/v0.3.2
[0.3.1]: https://github.com/ppoilbarbe/PBRenamer/releases/tag/v0.3.1
[0.3.0]: https://github.com/ppoilbarbe/PBRenamer/releases/tag/v0.3.0
[0.2.0]: https://github.com/ppoilbarbe/PBRenamer/releases/tag/v0.2.0
[0.1.0]: https://github.com/ppoilbarbe/PBRenamer/releases/tag/v0.1.0
