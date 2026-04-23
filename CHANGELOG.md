# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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

[0.1.0]: https://github.com/ppoilbarbe/PBRenamer/releases/tag/v0.1.0
