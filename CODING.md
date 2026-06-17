# Developer Guide

This document covers everything you need to contribute to PBRenamer.
For user-facing information see [README.md](README.md).

## Tech stack

| Layer          | Technology                                  |
|----------------|---------------------------------------------|
| Language       | Python 3.12+                                |
| GUI            | PySide6 (Qt 6 official Python binding)      |
| UI design      | Hand-written `*_ui.py` (no Qt Designer)     |
| Tests          | pytest + pytest-qt                          |
| Linter         | ruff (line-length 88, target py312)         |
| Docs           | Sphinx + sphinx-rtd-theme (ReadTheDocs)     |
| Package mgr    | conda — **conda-forge only** (`nodefaults`) |
| Build          | Hatchling (`pyproject.toml`)                |
| Packaging      | PyInstaller (`pbrenamer.spec`)              |
| CI/CD          | GitHub Actions                              |

## Project layout

```
PBRenamer/
├── src/pbrenamer/
│   ├── __init__.py              version / author metadata
│   ├── __main__.py              CLI entry point — GUI mode or headless rename (--search/--saved)
│   ├── argparse_qt.py           argparse integration for Qt CLI options (add_qt_arguments)
│   ├── i18n.py                  gettext bootstrap; language from platform.dirs
│   ├── settings.py              application preferences — log level (QSettings)
│   ├── xdg.py                   compat re-export → platform.dirs (do not use directly)
│   ├── core/
│   │   ├── filetools.py         file listing, text transforms, rename engine
│   │   ├── audio_meta.py        audio metadata reading via mutagen ({au:} fields)
│   │   ├── image_meta.py        EXIF/IPTC metadata reading via Pillow ({im:} fields)
│   │   ├── replacement.py       replacement-string parser, validator, substitutor
│   │   ├── undo.py              batch undo stack
│   │   └── video_meta.py        video metadata reading via pymediainfo ({vi:} fields)
│   ├── platform/                all OS-specific abstractions
│   │   ├── dirs.py              AppDirs(): XDG / macOS Library / Windows AppData
│   │   ├── fs.py                filesystem case-sensitivity probe + helpers
│   │   └── locale.py            cross-platform system language detection
│   ├── resources/               bundled resource files (SVG icon, …)
│   └── ui/
│       ├── about_dialog.py      About dialog
│       ├── about_dialog_ui.py   UI layout (hand-written) — edit directly
│       ├── history_dialog.py    history / pattern-preset management dialog
│       ├── history_dialog_ui.py UI layout (hand-written) — edit directly
│       ├── main_window.py       main window (logic)
│       ├── main_window_ui.py    UI layout (hand-written) — edit directly
│       ├── pattern_help.py      non-modal help dialogs for search / replace fields
│       ├── presets.py           pattern preset persistence
│       ├── settings_dialog.py   language settings dialog
│       ├── settings_dialog_ui.py UI layout (hand-written) — edit directly
│       ├── widgets.py           custom reusable widgets (WhitespaceLineEdit, …)
│       └── window_state.py      persistent window geometry and splitter positions
├── tests/
│   ├── test_argparse_qt.py      add_qt_arguments — flag accumulation, value/nargs=0 flags, unknown rejection
│   ├── test_filetools.py        listing, transforms, rename engine, disk I/O, newnum workflow
│   ├── test_headless.py         CLI argument parser (defaults, flags, unknown-flag rejection), --saved preset loading + CLI overrides, _apply_postproc, _plan (all three modes, keep-ext, postproc, syntax errors), _detect_conflicts, _headless_run integration
│   ├── test_i18n.py             i18n bootstrap — setup(), language selection, fallback chain
│   ├── test_main_window.py      full main window: _on_preview, _refresh_conflicts, context menus, undo, conflict detection, drag-and-drop, keyboard shortcuts, settings dialog, file-info window, pattern-help dialog, presets, bookmarks
│   ├── test_meta_audio.py       audio metadata — field registry, mutagen parsing, real file
│   ├── test_meta_image.py       EXIF/IPTC metadata (image_meta) — main IFD, sub-IFD, encoding, real file
│   ├── test_meta_video.py       video metadata — field registry, pymediainfo parsing, real file
│   ├── test_platform_bookmarks.py  platform.bookmarks — system dirs, GTK bookmarks, user-defined shortcuts
│   ├── test_platform_dirs.py    cross-platform directory resolution (XDG / macOS / Windows)
│   ├── test_platform_fs.py      case-sensitivity probe, path comparison, conflict keys
│   ├── test_platform_locale.py  system language detection — env vars, locale.getlocale fallback
│   ├── test_presets.py          PatternPresets — CRUD, persistence, migration
│   ├── test_replacement.py      replacement parser, validator, formatter, substitutor
│   ├── test_resources.py        bundled resources and xdg re-export shim
│   ├── test_settings.py         Settings — log level, shortcuts, toolbar-state, preview-delay persistence
│   ├── test_ui_dialogs.py       AboutDialog, SettingsDialog, HistoryDialog, ShortcutsDialog, FileInfoWindow, PatternHelpDialog, WhitespaceLineEdit
│   ├── test_undo.py             UndoManager — add_batch, undo (single/multi-file, LIFO), can_undo, clear, __len__
│   └── test_window_state.py     WindowState — geometry/splitter persistence
├── docs/                        Sphinx documentation source
├── tools/
│   ├── extract_changelog.py     reads CHANGELOG.md entry for a tag (CI release)
│   ├── bump_version.py          increments or force-sets the version in both source files
│   └── po_check.py              inspect .po files (stats, untranslated, search) — use instead of grep/msgfmt
├── .github/
│   └── workflows/
│       └── ci.yml               CI pipeline
├── pbrenamer.spec               PyInstaller build spec
├── environment.yml              conda environment declaration
├── pyproject.toml               project metadata + tool configuration
├── Makefile                     development task runner
└── .readthedocs.yaml            ReadTheDocs build configuration
```

## Setup

### 1. Create the conda environment

```bash
make venv
conda activate pbrenamer
```

Installs Python 3.12, PySide6 (+ Qt Designer), pytest, Sphinx, ruff, PyInstaller,
and the GitHub CLI in a self-contained conda environment sourced exclusively from
**conda-forge** (`nodefaults`). Never add the `defaults` channel.

### 2. Install the package in editable mode

```bash
make install   # pip install -e ".[dev]"  +  pre-commit install
```

### Running without conda

Set `NOCONDA` to bypass conda wrapping entirely. Every tool (`python`, `pytest`,
`ruff`, `sphinx-build`, …) must then be available on your `PATH`:

```bash
make test NOCONDA=1          # one-off override on the command line
export NOCONDA=1 && make lint test   # for the whole shell session
```

`make venv` and `make venv-update` always invoke `conda` directly and are
unaffected by `NOCONDA`.

## Daily workflow

| Task                      | Command                                  |
|---------------------------|------------------------------------------|
| Run the application       | `make run`                               |
| Run tests                 | `make test`                              |
| HTML coverage report      | `make coverage`                          |
| Lint & style check        | `make lint`                              |
| Auto-format               | `make format`                            |
| Run all pre-commit hooks  | `make hooks`                             |
| Update translations       | `make translate`                         |
| Build standalone binary   | `make dist`                              |
| Build docs                | `make docs`                              |
| Live-reload docs          | `make docs-live`                         |
| Remove build artifacts    | `make clean`                             |
| Bump patch version        | `make bump-patch`                        |
| Bump minor version        | `make bump-minor`                        |
| Bump major version        | `make bump-major`                        |
| Force a specific version  | `make bump-set VERSION=x.y.z`            |

Run `make` (or `make help`) to see all targets with descriptions.

## Coding conventions

- **Language**: English — all identifiers, comments, docstrings, and commit
  messages must be in English.
- **Style**: enforced by `ruff` (line length 88, target Python 3.12).
- **Type hints**: required on all public functions and methods.
- **Comments**: only when the *why* is non-obvious. No narration of what the
  code obviously does; no multi-line comment blocks.
- **No gold-plating**: implement only what the task requires; no speculative
  abstractions or backward-compatibility shims.

### Replacement engine — multi-meta mode

`replacement.substitute()` detects whether a template mixes fields from
more than one file-type namespace (`im:`, `vi:`, `au:`, and any future
additions declared in `_META_READERS`).

| Condition | Behaviour |
|---|---|
| Single namespace only | Strict: absent field + no default → `FieldResolutionError` (file flagged red) |
| Multiple namespaces | Lenient: a field whose namespace doesn't match the current file silently contributes `""` |

An explicit `default` always takes priority over the lenient behaviour.

To add a new file-type namespace, register its reader in `_META_READERS`
(in `replacement.py`). `_FILE_META_PREFIXES` is derived from that dict
automatically, so the multi-meta logic applies to the new namespace for free.

## UI layout files (`*_ui.py`)

UI layouts are hand-written Python files (`*_ui.py`) committed alongside the
business-logic files. There is no Qt Designer step.

- Edit `*_ui.py` directly — they are ordinary source files.
- Use `_()` for all user-visible strings; pybabel extracts them automatically.
- Each file exposes a single `Ui_*` class with a `setupUi(widget)` method.
- Import via composition: `self._ui = Ui_MainWindow(); self._ui.setupUi(self)`.
  Never use multiple inheritance.

## Platform abstraction (`pbrenamer/platform/`)

All OS-specific code must live in this package. The three modules are:

| Module       | Responsibility                                             |
|--------------|------------------------------------------------------------|
| `dirs.py`    | `AppDirs(name)` factory → `config_home`, `data_home`, `cache_home` |
| `fs.py`      | `is_case_sensitive(dir)` — probes the filesystem at runtime; `conflict_key()`, `same_file_path()` |
| `locale.py`  | `system_language()` — env vars (Unix) + `locale.getlocale()` (Windows/macOS) |

`AppDirs` dispatches to `XdgDirs` (Linux), `_MacDirs` (macOS), or `_WindowsDirs`
(Windows) based on `sys.platform`. `is_case_sensitive` creates a temporary
mixed-case file and checks whether its swapped-case counterpart resolves on
disk; the result is cached via `@lru_cache`.

`xdg.py` at the package root is a thin re-export shim kept for backwards
compatibility. All new code must import from `pbrenamer.platform`.

## Internationalisation (i18n)

Translatable strings are wrapped with `_()` (installed into builtins by
`i18n.setup()`). On startup, `setup()` also loads Qt's own translation
catalogue (`qtbase_<lang>.qm`) so that built-in dialog buttons (`OK`,
`Cancel`, `Yes`, `No`, …) are translated automatically.  The full toolchain:

```
Python source + *_ui.py
       │
       ▼ pybabel extract
  locale/pbrenamer.pot          ← template (not committed)
       │
       ▼ pybabel update / pybabel init
  locale/<lang>/LC_MESSAGES/pbrenamer.po   ← human-edited, committed
       │
       ▼ pybabel compile
  locale/<lang>/LC_MESSAGES/pbrenamer.mo   ← binary catalogue, committed
```

To inspect `.po` files (statistics, untranslated entries, pattern search) use
`tools/po_check.py` — never `grep` or `msgfmt`, both break on multi-line entries.

Run `make translate` to regenerate everything for all languages listed in
`PO_LOCALES` (Makefile). The application discovers available languages at
runtime by scanning `locale/*/LC_MESSAGES/pbrenamer.mo`; no code change is
required when a new language is added.

### Adding a new language

**1. Generate the template** (only needed once, or when new strings were added):

```bash
make translate
```

**2. Scaffold the new locale** with the dedicated target:

```bash
make new-lang LOCALE=de      # replace 'de' with the BCP-47 language code
```

This runs `pybabel init` to create
`src/pbrenamer/locale/de/LC_MESSAGES/pbrenamer.po` pre-filled with all
message IDs.

**3. Translate the `.po` file**

Open the generated file in a PO editor (e.g. Poedit, Lokalize, or any text
editor). Translate every `msgstr`. Pay special attention to two entries:

| msgid | What to put in msgstr |
|---|---|
| `language_name` | The language's own name, e.g. `Deutsch` — used in the Settings dialog |
| All UI strings | Faithful translations |

**4. Register the new locale**

Add the language code to `PO_LOCALES` in `Makefile`:

```makefile
PO_LOCALES := en fr de
```

**5. Compile and verify**

```bash
make translate          # updates the .po and compiles the .mo
make run                # open Settings → Language to check the new entry
```

**6. Commit**

```bash
git add src/pbrenamer/locale/de/
git commit -m "i18n: add German (de) translation"
```

Only `.po` and `.mo` files go into version control — the `.pot` template is
regenerated on demand and is excluded by `.gitignore`.

## Testing

```bash
make test               # full suite — terminal coverage report
make coverage           # full suite + HTML report in htmlcov/index.html
pytest -k test_foo      # run a single test by name
pytest --no-cov         # skip coverage instrumentation
```

Tests live in `tests/`, organised by module:

| Test file                    | What it covers |
|------------------------------|----------------|
| `test_argparse_qt.py`        | `add_qt_arguments`: flag accumulation into `args.qt_args`, value flags, `nargs=0` flags, rejection of unknown flags |
| `test_filetools.py`          | Text transforms, rename engine (patterns / plain / regex), file listing (recursive and non-recursive), disk rename, conflict handling, `{newnum}` workflow, Unicode coverage for pattern tokens (`{L}`, `{C}`, `{X}`, `{#}`) |
| `test_headless.py`           | CLI argument parser (defaults, flags, unknown-flag rejection), `--saved` preset loading + CLI overrides, `_apply_postproc`, `_plan` (all three modes, keep-ext, postproc, syntax errors), `_detect_conflicts`, `_headless_run` integration (confirm/abort, filter, recursion, case, dirs, conflicts, cwd fallback) |
| `test_i18n.py`               | `i18n.setup()` — language selection, env-var override, fallback to `en`, builtins injection |
| `test_main_window.py`        | Full main window: `_on_preview`, `_refresh_conflicts`, context menus, undo, conflict detection, drag-and-drop, keyboard shortcuts, settings dialog, file-info window, pattern-help dialog, presets, bookmarks |
| `test_meta_audio.py`         | Audio metadata: field registry, integer/date parsing, `read_field` with and without mutagen, easy-tag and info-tag fields, real MP3 fixture |
| `test_meta_image.py`         | EXIF/IPTC metadata (`image_meta`): main IFD, sub-IFD, encoding, case-insensitive lookup, Pillow-unavailable path, real JPEG fixture |
| `test_meta_video.py`         | Video metadata: field registry, encoded-date parsing, track selection, duration/bitrate/resolution/codec fields, library-unavailable path, real video fixture |
| `test_platform_bookmarks.py` | `platform.bookmarks`: system directories, GTK bookmark parsing (Linux), user-defined shortcuts CRUD |
| `test_platform_dirs.py`      | `AppDirs` factory — `XdgDirs` (Linux), `_MacDirs`, `_WindowsDirs`; `config_home`, `data_home`, `cache_home` |
| `test_platform_fs.py`        | `is_case_sensitive` probe, `same_file_path` and `conflict_key` on both case-sensitive and case-insensitive filesystems |
| `test_platform_locale.py`    | `system_language()` — env-var chain (LANGUAGE, LC_ALL, LANG), `locale.getlocale()` fallback, normalisation |
| `test_presets.py`            | `PatternPresets` — CRUD (add, rename, delete, reorder), persistence to JSON, migration from legacy format |
| `test_replacement.py`        | Replacement-string parser (fields, defaults, align, case-transform), validator, all built-in fields (`{num}`, `{date}`, `{datetime}`, `{dir}`, `{mdatetime}`, `{im:…}`, `{au:…}`, `{vi:…}`, `{re:…}`), formatting and error paths |
| `test_resources.py`          | Bundled resource loading (`get_resource`), `xdg.py` re-export shim |
| `test_settings.py`           | `Settings` — log level, shortcuts, toolbar-state and preview-delay persistence (QSettings) |
| `test_ui_dialogs.py`         | `AboutDialog`, `SettingsDialog`, `HistoryDialog`, `ShortcutsDialog`, `FileInfoWindow`, `PatternHelpDialog`, `WhitespaceLineEdit` |
| `test_undo.py`               | `UndoManager` — `add_batch`, `undo` (single and multi-file batches, LIFO order), `can_undo`, `clear`, `__len__` |
| `test_window_state.py`       | `WindowState` — geometry and splitter-position persistence (save / restore cycle) |

Use `qtbot` from `pytest-qt` for all widget interactions.
Never instantiate `QApplication` manually — `pytest-qt` manages it.

## Packaging (`make dist`)

`make dist` runs `translate` (to ensure `.mo` files are current) then calls
PyInstaller with `pbrenamer.spec`.

The artifact name embeds version and platform so builds for different OSes can
coexist in the same directory:

| Platform | Output |
|---|---|
| Linux   | `dist/PBRenamer-<ver>-linux-x86_64` |
| Windows | `dist/PBRenamer-<ver>-windows-x86_64.exe` |
| macOS   | `dist/PBRenamer-<ver>-macos-arm64.app` |

The version is read from `pyproject.toml` at spec-evaluation time.
PyInstaller cannot cross-compile; each platform must build natively.

## CI/CD (`.github/workflows/ci.yml`)

The pipeline runs on every push and pull request:

```
push / PR
  ├── test   (ubuntu) ──┐
  └── hooks  (ubuntu) ──┴── build ──── release  ← semver tags only
                              ├── linux
                              ├── windows
                              └── macos
```

The `build` jobs call PyInstaller directly (not `make dist`) — `.mo` files
are committed and this avoids GNU Make / gettext portability issues on
Windows runners. `*_ui.py` files are committed source and require no
compilation step.

The `release` job runs only on tags matching `v[0-9]*.[0-9]*.[0-9]*`. It
downloads all three build artifacts, extracts the corresponding entry from
`CHANGELOG.md` (via `tools/extract_changelog.py`), and creates a GitHub
release with the three binaries attached.

## Releasing

1. Bump the version with the appropriate target — both `pyproject.toml` and
   `src/pbrenamer/__init__.py` are updated atomically:

   ```bash
   make bump-patch                  # 1.2.3 → 1.2.4
   make bump-minor                  # 1.2.3 → 1.3.0
   make bump-major                  # 1.2.3 → 2.0.0
   make bump-set VERSION=1.5.0      # jump to an arbitrary version (must be > current)
   ```

2. Add an entry to `CHANGELOG.md` (Keep a Changelog format: `## [x.y.z] - YYYY-MM-DD`).
3. Commit and push: `git add -p && git commit -m "Release vX.Y.Z"`.
4. Tag and push: `git tag vX.Y.Z && git push --tags`.

The CI pipeline takes over: it runs tests, builds the three platform binaries,
and creates the GitHub release automatically with the changelog text as body.

## License

GPLv3 — all contributions must be compatible with this license.
Copyright © 2026 PBMou — Marcel Spock <mrspock@cardolan.net>
