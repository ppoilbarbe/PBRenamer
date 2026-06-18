# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `settings.configure(config_dir)` — new public function that overrides the
  configuration directory used by all settings and i18n functions; a single call
  redirects `settings`, `i18n`, and `PatternPresets` config I/O simultaneously;
  pass `None` to restore the platform default; intended for testing
- `--config-dir DIR` CLI option (both GUI and headless modes): overrides the
  configuration directory at startup before any settings access; intended for
  testing (noted in `--help`)
- Window geometry persistence for all windows and dialogs (except About):
  `MainWindow`, `FileInfoWindow`, `HistoryDialog`, `SettingsDialog`,
  `ShortcutsDialog`, and `PatternHelpDialog` save/restore size and position
  across sessions via `WindowState.save_geometry` / `load_geometry`
- LRU management for search, replace, and named-saves dropdowns: the most
  recently used entry is promoted to position 0 on each use; history is
  capped at 20 entries
- Mixed file-type replacement templates: when `{im:…}`, `{vi:…}`, or
  `{au:…}` tokens from more than one namespace appear in the same template,
  `substitute()` probes each namespace with `can_read()` at runtime — the
  applicable namespace follows strict behaviour (absent field without default
  → `FieldResolutionError`), non-applicable namespaces silently contribute
  `""` without requiring a default
- `{vi:…}` field resolution now rejects files that have no video track even
  when MediaInfo returns a General track (e.g. JPEG files parsed by
  pymediainfo)
- UI layouts converted from Qt Designer `.ui` files to hand-written Python
  source (`*_ui.py`): `main_window_ui.py`, `history_dialog_ui.py`,
  `settings_dialog_ui.py`, `about_dialog_ui.py` — eliminates the Qt Designer
  file-parsing step at build time

### Changed

- Test configuration isolation: `conftest.py` provides a `config_dir` autouse
  fixture that redirects all settings I/O to a per-test temporary directory via
  `settings.configure()`; the real `~/.config/pbrenamer` is never touched
  during test runs; tests that need direct file access can request the
  `config_dir` fixture to obtain the path
- Named saves storage format migrated from a flat JSON dict (no ordering
  guarantee) to an ordered JSON list `[{"name": …, …config…}, …]`; legacy
  dict files are read transparently and upgraded on next write
- `patternHelp.PatternHelpDialog`: geometry now restored in `showEvent`
  (first paint) rather than in the constructor, matching the behaviour of all
  other secondary windows

### Fixed

- `audio_meta.can_read` now returns `False` for video container files (MP4,
  MKV, MOV, …) that carry no audio-only track; previously a `General` track
  from pymediainfo could satisfy the read check, causing `{au:…}` fields to
  attempt — and silently fail — audio tag extraction on video files
- Main window geometry was not restored at startup: `restoreGeometry()` was
  called in `__init__` before `show()`, so the window manager ignored it;
  moved to `showEvent` (fires once via `_geometry_restored` flag)
- Named saves combo list order reverted to sorted order on a subsequent save:
  Qt's `QCompleter` (auto-attached to the editable `QComboBox`) received
  `textChanged` events from the embedded `QLineEdit` even while
  `combo.blockSignals(True)` was active, and could queue a deferred
  `activated` callback that called `use_save` with a wrong index; fixed by
  blocking the `QLineEdit` signals separately and using `setCurrentIndex`
  instead of `setCurrentText` during `_populate_named_saves`
- Preview pane appeared and immediately disappeared on the first click in the
  directory tree: `_on_directory_selected` was called twice for the initial
  path, the second call with the same path clearing the just-populated
  preview; fixed with an early-return guard when the path has not changed

### Removed

- Qt Designer `.ui` files (`about_dialog.ui`, `history_dialog.ui`,
  `main_window.ui`, `settings_dialog.ui`) — replaced by `*_ui.py` Python
  sources
- `tools/extract_ui_strings.py` — no longer needed; translatable strings are
  extracted directly from Python source via pybabel

## [1.3.0] - 2026-06-15

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
- `src/pbrenamer/argparse_qt.py`: `add_qt_arguments()` declares Qt CLI flags
  (`--style`, `--platform`, …) as a proper argparse argument group; collected in
  `args.qt_args` as single-dash tokens ready for `QApplication`; Qt options are
  hidden from the `usage:` line to reduce noise while remaining fully visible in
  the `--help` output
- `tools/fix_po_files.py`: utility to normalise PO file formatting in bulk
- Comprehensive test suite covering all source modules at 100%; includes the
  full main window (`_on_preview`, `_refresh_conflicts`, context menus, undo,
  conflict detection, drag-and-drop, keyboard shortcuts, settings dialog,
  file-info window, pattern-help dialog, presets, bookmarks, i18n bootstrap,
  and all core modules)
- Headless Qt test execution via `QT_QPA_PLATFORM=offscreen` in `conftest.py`;
  `QMenu.exec` patched at module level so no blocking dialog appears during CI
  or local `make test` runs

### Changed

- `main()` now uses `parse_args()` instead of `parse_known_args()`; unknown
  flags are rejected natively by argparse — `_validate_qt_argv` removed

### Fixed

- `{L}` search-pattern token now matches Unicode letters; accented Latin
  (`é`, `ê`, `ü`, …), Cyrillic, Greek and all other Unicode letter categories
  are captured correctly — was limited to ASCII `[a-zA-Z]`, now uses
  `[^\W\d_]` which covers all `\w` characters that are neither digits nor
  underscores
- Qt built-in translations are now loaded alongside the application catalogue
  so dialog buttons (`OK`, `Cancel`, `Yes`, `No`, …) are correctly translated
  when a non-English language is selected
- Pattern help dialog: HTML-escaped `{1:&lt;12}` so the browser no longer
  interprets `<12>` as an HTML tag
- Fifteen `# pragma: no cover` guards on reachable logic replaced by targeted
  tests: case-insensitive no-match in `rename_using_plain_text`, zero-width
  regex guard, `{newnum}` CLI branch (start value, invalid start, no-match,
  field error, collision k+=1), rename failure exit path, `main()` headless
  dispatch, `_parse_exif_datetime` on malformed input, `_read_iptc` unknown
  key, `_apply_case` unknown modifier

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
