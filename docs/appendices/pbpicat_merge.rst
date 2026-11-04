=============================
Merging PBRenamer and PBPicat
=============================

.. note::

   This document was written for the merge of PBPicat into PBRenamer, which
   led to version 2.0.0.  It is kept as a record of the design decisions and
   of how the work was carried out.

Feasibility study and execution plan for combining PBRenamer (v1.8.1) and
PBPicat (v1.21.0) into a single program, with no loss of functionality and an
interface as simple as today's.

Date: 2026-08-02 (decisions approved, see :ref:`§ 9 <pbpicat-merge-9>`)

.. _pbpicat-merge-1:

1. Summary
==========

Both programs rename files, but following two different approaches:

- **PBRenamer** renames files *in place* from a search and replace pattern,
  with a live preview.
- **PBPicat** *files* pictures and videos according to a **schema** of N fields,
  which produces both the destination tree and the file name.

Key finding: a PBPicat schema is just a special case of a PBRenamer replacement
template whose result contains directory separators. For example, the schema
``Paris``, ``2024``, *(empty)*, ``Street``, *(empty)*, ``###`` is equivalent
to::

   {dest}/Paris/2024/Street/Paris_2024_Street_{newnum:03}

The merge therefore relies on **a single renaming engine** fed by **two input
modes** (Pattern and Schema), in **a single window** where only the rule panel
changes.

Chosen directions:

1. **PBRenamer is the base** and keeps its name: more mature code, PyPI
   release, Read the Docs, CI on 3 OSes, cross-platform ``platform/`` layer,
   headless CLI mode.
2. PBPicat's features are ported into PBRenamer, as a **Schema mode** and
   **optional image tools**.
3. The result is released directly as **PBRenamer 2.0.0**, then PBPicat is
   deprecated.

2. Current state
================

2.1 Feature comparison
----------------------

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Topic
     - PBRenamer
     - PBPicat
   * - Code size (``src/``)
     - ~8,900 lines
     - ~6,700 lines
   * - Principle
     - In-place renaming by pattern
     - Filing by a schema of N fields
   * - Destination
     - Current directory
     - ``ROOT/field1/field2/…/field1_field2_…[_NNN].ext``
   * - Search modes
     - ``pattern``, ``regex``, ``plain``
     - none
   * - Replacement fields
     - ``{num}``, ``{newnum}``, ``{date}``, ``{datetime}``, ``{mdatetime}``,
       ``{dir}``, ``{im:…}``, ``{au:…}``, ``{vi:…}``, captured groups
     - text fields, ``###``
   * - Numbering
     - ``{num:03}``, start offset, conflict-free ``{newnum}``
     - existing max + 1 (numeric comparison), separate counters for pictures
       and videos, "fill gaps", "renumber from 1"
   * - Post-processing
     - separators, case, accents, duplicate separators
     - none
   * - Extension
     - Keep, Lower, Upper, Normalize, Modify
     - kept
   * - Sidecars
     - any suffix, configuration per category (image, video, audio, other)
       plus common suffixes, ambiguity detection
     - ``stem + ext`` (multi-dot extensions accepted), extension for a new
       sidecar, deletion of empty sidecars
   * - Conflicts
     - live preview, conflicts in red, Rename button disabled
     - whole operation aborted if a destination already exists
   * - Undo
     - per batch, multi-level
     - multi-level and typed (rename, renumber, move, copy, rotation,
       reset_exif)
   * - Drag and drop
     - copy and move between tree, list and external applications, grouped
       Overwrite/Skip/Cancel confirmation
     - copy (Ctrl) and move to the tree, sidecars included, internally undoable
   * - File list
     - original name and new name, coloring of directories and sidecars
     - thumbnail (lazy, multithreaded loading), name, sidecar indicator
   * - Image features
     - information window (metadata)
     - viewer (zoom, navigation, selection strip, metadata panel), lossless
       rotation (jpegtran, Pillow), applying and resetting the EXIF
       orientation, deletion, Open and Open with (MRU per MIME type on Linux)
   * - Filters
     - glob on names
     - regular expression on the *content* of sidecars
   * - Inference
     - none
     - "Template": infers the schema fields from an existing file name
   * - Profiles
     - named pattern presets, LRU histories
     - catalogs (configuration, histories and window state per catalog,
       hidden catalogs)
   * - CLI
     - full headless mode (``--search``, ``--saved``, ``--dry-run``,
       ``--confirm``, ``--select``…)
     - catalog name as argument, ``--dev-config-dir``
   * - Configuration
     - ``platform/dirs.py`` (XDG, macOS, Windows), ``--config-dir``
     - ``$XDG_CONFIG_HOME/pbpicat/<catalog>/``
   * - Required pip dependencies
     - PySide6 only (Pillow, mutagen and pymediainfo provided by the pixi
       environment)
     - PySide6, Pillow, pillow-heif, pyexiv2 (+ external jpegtran)
   * - Miscellaneous
     - automatic update, desktop menu entry, system bookmarks
     - video marker placeable in the name

2.2 Common foundation already shared
------------------------------------

- Python 3.12, PySide6, pixi (conda-forge), Makefile, ruff, pytest and
  pytest-qt, Sphinx and Read the Docs, PyInstaller.
- ``argparse_qt.py`` identical in both projects.
- gettext i18n in the same 8 languages (en, de, es, fr, it, ru, vi, zh_CN).
- Same author, same license (GPLv3), same executable naming convention.

3. Target architecture
======================

3.1 Principle
-------------

.. code-block:: text

    Pattern mode ────────────┐
    (search/replace)         │
                             ├──► Compiled rule ──► Plan [(src, dst, sidecars)] ──► Preview + conflicts
    Schema mode  ────────────┘    (single template)                               ──► Atomic execution
    (fields + destination)                                                        ──► Undo stack
                                                                                  ──► Headless CLI

Schema mode is a ``schema → template`` **compiler**. Everything built on the
engine (preview, conflicts, undo, CLI) then serves both modes without
duplicated code.

.. _pbpicat-merge-3-2:

3.2 Engine extensions (``core/``)
---------------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 60 20

   * - Extension
     - Detail
     - Origin
   * - Destination path
     - the result may contain ``/``; a ``{dest}`` field (destination root) is
       added; intermediate directories are created at execution time
     - PBPicat
   * - Cleanup
     - removal of source directories left empty after a rename, a move or a
       deletion
     - PBPicat
   * - Contextual counter
     - ``{newnum}`` computes max + 1 **in the target directory** rather than
       in the current directory, using a numeric comparison
     - PBPicat ``find_max_number``
   * - Fill gaps
     - ``{newnum}`` option: smallest free integer, then continue after the
       max
     - PBPicat ``fill_gaps``
   * - Per-category counters
     - option: separate counter per file category (image, video…)
     - PBPicat
   * - Conditional field
     - inserts a text depending on the file category (video marker)
     - PBPicat ``video_marker``
   * - Renumbering
     - two-phase plan through temporary names to avoid circular permutations
     - PBPicat ``build_renumber_plan``
   * - Atomic execution
     - all destinations checked beforehand, rollback on an intermediate
       error; default behavior in both modes, in the GUI as in the CLI
     - PBPicat ``execute_rename``
   * - Typed undo
     - ``rename``, ``move``, ``copy``, ``rotation``, ``reset_exif`` entries
       in ``core/undo.py``
     - PBPicat

3.3 Compiling a schema
----------------------

Input: fields ``f1…fN``, root ``ROOT``, video marker position ``p``, marker
``M``.

.. code-block:: text

   parts    = non-empty, non-numeric fields
   numeric  = field made only of '#' (at most one)
   dir      = ROOT / parts[0] / … / parts[k]
   prefix   = "_".join(parts)  with M inserted at position p for the video category
   name     = prefix [ "_" + {newnum:0<len(numeric)>} ] + original extension

PBPicat's validation rules are kept: ``_`` and ``.`` are forbidden in a field,
at most one numeric field, an empty field is skipped.

3.4 Sidecars
------------

PBRenamer's model (``core/sidecar.py``) is kept; it already covers PBPicat's
``stem + ext``. The following is added:

- the extension used to create a new sidecar (double-click on the indicator);
- optional deletion of empty sidecars when a directory is loaded;
- reading the content for the regular expression filter.

In Schema mode, sidecar mode is **forced on**, as in PBPicat today.

3.5 Profiles (merging catalogs and presets)
-------------------------------------------

A **profile** replaces both PBPicat's catalog and PBRenamer's set of settings.
It contains:

- the default mode (Pattern or Schema);
- the Schema mode settings (number and titles of the fields, destination root,
  video marker and its position, fill gaps);
- the extensions per category and the sidecar suffixes;
- the display options (thumbnails, size, sidecar filter shown);
- the histories (schema fields, search, replace, sidecar filter);
- the profile's own window state.

The existing **pattern presets** remain quick entries of Pattern mode, stored
in the current profile. The catalog rules are carried over: at least one
visible profile (``default``, created by the migration, is a profile like any
other, recreated only when no visible profile is left), hidden profiles (name
starting with ``.`` or ``-``), names limited to letters, digits, ``-`` and
``_``.

.. _pbpicat-merge-3-6:

3.6 Dependencies
----------------

.. list-table::
   :header-rows: 1
   :widths: 15 35 50

   * - Group
     - Content
     - Status
   * - Base
     - PySide6
     - required
   * - ``[meta]``
     - Pillow, mutagen, pymediainfo
     - optional (reading ``{au:}`` and ``{vi:}`` metadata, and ``{im:}`` as a
       fallback)
   * - ``[images]``
     - pyexiv2, pillow-heif, Pillow
     - optional (preferred reading of ``{im:}``, HEIC thumbnails, rotation,
       EXIF writing, metadata panel)
   * - External
     - jpegtran
     - optional (lossless JPEG rotation)

Actions depending on a missing group are disabled, with an explanatory
tooltip. PyInstaller executables bundle everything.

Image metadata (decision 2): reading goes through **pyexiv2** (already needed
to write the orientation); **Pillow is the fallback** when pyexiv2 is missing or
fails on a file.

4. Target interface
===================

4.1 Main window
---------------

.. code-block:: text

   File  Edit  Profile ▾  Images  Shortcuts  Settings  Help                  [profile]
   ┌───────────────┬───────────────────────────────────────────────────────────────┐
   │ Directory     │ Show [Files ▾]  Filter [*.jpg ]  ☐Recursive  ☑Thumbnails      │
   │ tree          │ ┌─────┬───────────────┬─────────┬───────────────────────────┐ │
   │               │ │ 🖼  │ IMG_0012.jpg  │ ● xmp   │ Paris/2024/…_013.jpg      │ │
   │ (drop target  │ │ 🖼  │ IMG_0013.jpg  │ ○       │ Paris/2024/…_014.jpg      │ │
   │  for files)   │ │ 🎞  │ VID_0001.mp4  │ ● xmp   │ Paris/2024/…_vid_001.mp4  │ │
   │               │ └─────┴───────────────┴─────────┴───────────────────────────┘ │
   ├───────────────┴───────────────────────────────────────────────────────────────┤
   │ ┌ Pattern ┐┌ Schema ┐                                                          │
   │  Destination [~/Photos/Sorted                ][…]   ☐ Fill gaps                │
   │  ◦ [Place  ▾] ◦ [Year  ▾] ◦ [      ▾] ◦ [Topic ▾] ◦ [      ▾] ◦ [###  ▾] ◦     │
   │                                     ◦ = video marker position                  │
   ├────────────────────────────────────────────────────────────────────────────────┤
   │ [Undo (3)]          Sidecar filter [regex      ▾]   [Renumber] [Rename (12)]   │
   └────────────────────────────────────────────────────────────────────────────────┘

Pattern tab (current PBRenamer content):

.. code-block:: text

   │  Search  [{X}            ▾] ☐Case insensitive   Mode [pattern▾]  [?]          │
   │  Replace [{1}_{num:03}   ▾]   Extension [Keep▾]   Preset [      ▾][+][−]       │
   │  ▸ Post-processing (separators, case, accents, duplicates)                     │

4.2 Simplicity rules
--------------------

1. **A single frame**: tree, list, action bar and undo are identical in both
   modes. Only the rule panel changes (tabs).
2. **A single Rename button**: it applies to the selection, or to all the
   displayed files when nothing is selected. The label shows the count
   (``Rename (12)``). Shortcut F2. PBPicat's "Rename All" and "Rename
   selection" buttons are dropped.
3. **"New name" column always visible**: it replaces PBPicat's preview
   tooltip. Conflicts are shown in red and block the button, as in PBRenamer.
4. **Progressive disclosure**:

   - post-processing collapsed by default;
   - thumbnail column and sidecar filter enabled per profile;
   - "Renumber" visible only in Schema mode with a ``###`` field;
   - image actions (rotation, EXIF, viewer) only in the **Images** menu, the
     context menu and the viewer.

5. **The profile carries the context**: a "photos" profile opens in Schema
   mode with thumbnails, the default profile in Pattern mode without
   thumbnails. The user sets nothing at each launch.
6. **"Template"** (context menu) fills the schema fields from the selected file
   and switches to the Schema tab.

.. _pbpicat-merge-4-3:

4.3 Menus
---------

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Menu
     - Content
   * - File
     - Quit
   * - Edit
     - Undo, Histories…, Presets…
   * - Profile
     - New…, Duplicate…, Delete…, list of visible profiles
   * - Images
     - Open, Open with…, Template, Delete, Rotate 90° left/right, 180°, Apply
       EXIF orientation, Reset EXIF orientation to 0°, Information, Refresh
   * - Shortcuts
     - system bookmarks and favorites (PBRenamer)
   * - Settings
     - Profile configuration…, Program settings…, Extension normalization
       table…
   * - Help
     - Pattern help, Keyboard shortcuts, About, Update

4.4 Secondary windows
---------------------

- **Viewer** (PBPicat): taken over as is, merged with PBRenamer's information
  window for the metadata panel (a single metadata display component).
- **Profile configuration**: Schema, Sidecars, Categories and extensions,
  Images (zoom, automatic EXIF rotation, deletion confirmation, side of the
  metadata panel) and Thumbnails tabs.
- **Program settings**: language, logging level, update, defaults for new
  profiles.
- **Histories**: one tab per history (schema fields, search, replace, sidecar
  filter), with PBPicat's accent- and case-insensitive sorting.

.. _pbpicat-merge-5:

5. CLI
======

PBRenamer's headless mode is extended to Schema mode:

.. code-block:: text

   pbrenamer [DIR] --search TEXT [--replace TEXT] [OPTIONS]      # Pattern mode (unchanged)
   pbrenamer [DIR] --schema "F1,F2,…,FN" --dest ROOT [OPTIONS]   # Schema mode
   pbrenamer [DIR] --profile NAME                                 # GUI on a profile

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - New option
     - Description
   * - ``--schema LIST``
     - comma-separated schema fields; enables headless mode
   * - ``--dest DIR``
     - destination root (required with ``--schema``)
   * - ``--fill-gaps`` / ``--no-fill-gaps``
     - fill numbering gaps
   * - ``--video-marker TEXT``, ``--video-marker-pos N``
     - video marker and its position
   * - ``--renumber``
     - renumber from 1 in place
   * - ``--profile NAME``
     - load a profile (replaces PBPicat's positional catalog argument)

The existing options (``--dry-run``, ``--confirm``, ``--select``,
``--filter``, ``--recurse``, ``--config-dir``…) apply to both modes.

Behavior changes:

- **Conflicts** (decision 3): execution is now atomic in the CLI too. If a
  destination conflicts, nothing is renamed and the command exits with an
  error listing the conflicts. Previously, conflicting files were skipped and
  the others renamed.

.. _pbpicat-merge-6:

6. PBPicat feature mapping
==========================

Every PBPicat feature must have a place in the merged program.

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - PBPicat feature
     - Target location
   * - Schema of N fields with history
     - Schema tab
   * - Destination + Browse
     - Schema tab
   * - Rename All / Rename selection
     - single Rename button
   * - Renumber from 1
     - Renumber button (Schema mode) + ``--renumber``
   * - Fill gaps
     - Schema tab checkbox + ``{newnum}`` option
   * - Separate picture/video counters
     - ``{newnum}`` option enabled by the schema
   * - Video marker and radio buttons
     - Schema tab + engine conditional field
   * - Lazy multithreaded thumbnails
     - optional list column
   * - Sidecar indicator, opening, creation
     - optional list column
   * - Filter on sidecar content
     - action bar (shown per profile)
   * - Viewer, zoom, linear/circular navigation, selection strip
     - Viewer window
   * - EXIF/IPTC/XMP metadata panel + XMP sidecar
     - merged Viewer and Information window
   * - Lossless rotation, apply/reset EXIF
     - Images menu, context menu, Viewer
   * - JPEG SOS header repair
     - ``core/image_ops.py``
   * - Delete (file + sidecars + empty directories)
     - Images menu
   * - Open, Open with (Linux MRU)
     - Images menu, ``platform/``
   * - Template (field inference)
     - Images menu and context menu
   * - Drag and drop to the tree, Ctrl = copy, undoable
     - merged with PBRenamer's drag and drop
   * - Catalogs (hidden, duplication)
     - Profiles
   * - Automatic selection after an action
     - file list
   * - Tab keyboard navigation between tree and list
     - file list
   * - Orphan sidecars (dialog)
     - Images menu
   * - Deletion to the trash (``use_trash``)
     - Images tab of the profile configuration
   * - Sort by date and reverse sort
     - option bar checkboxes, saved in the profile
   * - Refresh on disk changes (``QFileSystemWatcher``)
     - file list

7. Execution plan
=================

Each phase ends with a green test suite (``make test``), a clean lint
(``make lint``) and a state that can be integrated into the branch. The work is
done in PBRenamer, on a ``merge-pbpicat`` branch. The final 2.0.0 release comes
out at the end of phase 7.

All tasks are done.

Phase 0: preparation (≈ 2 days)
-------------------------------

.. list-table::
   :header-rows: 1
   :widths: 8 92

   * - Task
     - Detail
   * - 0.1
     - Create the ``merge-pbpicat`` branch in PBRenamer.
   * - 0.2
     - Split ``ui/main_window.py`` (1,525 lines) into components:
       ``ui/rule_panel_pattern.py``, ``ui/file_list.py``,
       ``ui/action_bar.py``. No behavior change. Done: ``QObject`` components
       connected by signals (``PatternRulePanel``, ``FileListController``,
       ``ActionBar``); ``main_window.py`` reduced to 380 lines of
       orchestration. The panel produces ``PreviewEntry`` objects, the list
       displays them; named saves stay in the Pattern panel.
   * - 0.3
     - Add the ``[meta]`` and ``[images]`` extras in ``pyproject.toml`` and
       the pixi environment (pyexiv2, pillow-heif). Done: pyexiv2 (PyPI)
       targeted at linux-64, win-64 and osx-arm64 (``__osx = 14.0``); osx-64
       kept without pyexiv2, with the Pillow fallback (environment marker in
       the ``[images]`` extra).
   * - 0.4
     - List the PBPicat tests to port (``test_renamer.py``,
       ``test_image_ops.py``, ``test_image_io.py``, ``test_metadata.py``,
       ``test_config.py``, ``test_platform_*.py``, ``test_ui_*.py``). Done:
       see :ref:`§ 10 <pbpicat-merge-10>`.

Exit criterion: behavior identical to v1.8.1, existing tests green.

Phase 1: engine (≈ 1 week)
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 8 92

   * - Task
     - Detail
   * - 1.1
     - Result with a path: support for ``/`` and the ``{dest}`` field in
       ``core/replacement.py``; validation (no ``..``, no absolute path
       outside ``{dest}``). Done: ``{dest}`` field (internal marker replaced
       after post-processing, which therefore never touches the root);
       ``filetools.resolve_target`` rejects ``..``, ``.``, empty components,
       absolute paths and ``{dest}`` anywhere but at the start;
       ``cut_extension`` reads the extension from the last component only.
   * - 1.2
     - Execution: creation of intermediate directories, removal of empty
       source directories, prior check of all destinations, rollback
       (``core/filetools.py``, inspired by ``renamer.execute_rename``). Done:
       ``filetools.execute_renames`` (prior check through
       ``find_rename_conflicts``, rollback, created directories recorded,
       pruning of emptied source directories strictly below the displayed
       directory); wired into the GUI and the CLI. In the CLI, a conflict
       makes the command fail (exit code 1) without renaming anything,
       ``--dry-run`` included. Permutations and chains are allowed (through
       temporary names).
   * - 1.3
     - Contextual ``{newnum}``: computed per target directory, numeric
       comparison, ``fill_gaps`` and ``per_category`` options
       (``NewNumState``). Done: new ``core/planner.py`` module (``Rule``,
       ``compute_names``), which factors out the loop formerly duplicated
       between the preview and the CLI. ``{newnum}`` = max + 1 of the series
       (target directory + name around the number, all extensions), batch
       sources excluded; ``fill_gaps`` and ``per_category`` options. Sidecars
       do not consume a number, and the number of their base file is chosen
       so that their names are free.
   * - 1.4
     - Conditional field per category for the video marker. Done:
       ``{if:CATEGORY:TEXT}`` (image, video, audio, other, according to the
       table of ``core/sidecar.py``).
   * - 1.5
     - Two-phase renumbering plan (``build_renumber_plan``,
       ``execute_renumber``, ``undo_renumber``). Done: ``Rule.renumber``
       (sequence 1..N per series, without reading the disk); two-step
       execution handled by ``execute_renames``.
   * - 1.6
     - Typed undo stack in ``core/undo.py``. Done: ``RenameEntry``,
       ``MoveEntry``, ``CopyEntry``; ``UndoError`` shown by the GUI (failures
       used to be silent). ``rotation`` and ``reset_exif`` will come in 6.2,
       undoable copy through drag and drop in 5.5.
   * - 1.7
     - Port the cases of ``PBPicat/tests/test_renamer.py`` to
       ``tests/test_replacement.py`` and ``tests/test_filetools.py``. Done:
       ``tests/test_planner.py`` (cases from ``test_renamer.py``, SPEC
       examples, end to end with sidecars and undo), additions in
       ``test_replacement.py``, ``test_filetools.py``, ``test_undo.py``,
       ``test_headless.py``, ``test_main_window.py``; ``media_dir`` fixture in
       ``conftest.py``.

Exit criterion: all the examples of PBPicat's SPEC (§ Rename Schema, Examples,
Numbering) pass through the PBRenamer engine.

Phase 2: headless Schema mode (≈ 3 days)
----------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 8 92

   * - Task
     - Detail
   * - 2.1
     - ``core/schema.py``: schema validation (PBPicat rules) and compilation
       into a template. Done: ``validate``, ``compile_template``,
       ``compile_rule`` (search ``{X}``, lowercase extension, per-category
       counters, marker through ``{if:video:…}``); ``/`` and ``\`` forbidden
       in addition to ``_`` and ``.``, ``{`` escaped; renumbering produces the
       name only, in place. Marker position = position shown between the
       fields (empty fields before it do not count), which fixes PBPicat's
       discrepancy.
   * - 2.2
     - CLI options ``--schema``, ``--dest``, ``--fill-gaps``,
       ``--video-marker``, ``--video-marker-pos``, ``--renumber`` in
       ``__main__.py``. Done: ``--schema`` exclusive with ``--search`` and
       ``--saved``; ``--dest``, ``--fill-gaps`` and ``--renumber`` also apply
       in Pattern mode (``{dest}`` usable in the CLI); in Schema mode, sidecar
       mode forced, Pattern mode options rejected, ``--dest`` required except
       with ``--renumber`` (ignored with a warning); invalid schema reported
       before the directory is read. ``_()`` installed (NullTranslations) in
       headless mode.
   * - 2.3
     - Tests in ``tests/test_headless.py``: ``--dry-run`` and real execution
       on temporary directories, sidecars included. Done:
       ``tests/test_schema.py`` (cases from ``validate_schema``,
       ``build_rename_plan``, ``build_renumber_plan``, SPEC examples) and the
       ``TestSchemaParser``, ``TestSchemaResolveNs``, ``TestSchemaRun``
       classes (dry-run, sidecars, pruning, successive batches, fill gaps,
       conflict, ``--select``, renumbering, ``{dest}`` in Pattern mode).

Exit criterion: feature parity with PBPicat renaming on the command line.

Phase 3: profiles and configuration (≈ 4 days)
----------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 8 92

   * - Task
     - Detail
   * - 3.1
     - Profile model in ``settings.py``: creation, duplication, deletion,
       hidden profiles, ``default`` profile, remembering the last non-hidden
       profile. Done: ``profiles.py`` module (separate from ``settings.py``);
       one directory per profile under ``profiles/`` (``profile.json`` with
       typed values, ``history.json`` in PBPicat format,
       ``sidecar_config.json``, ``patterns/``); names ``^\.?[\w-]+$``,
       ``default`` profile recreated when no visible profile is left, last
       profile in ``pbrenamer.conf`` (``profiles/last``). Lazy creation in
       ``profiles.tmp/``, renamed at the end (an interrupted migration is
       replayed). ``window_state.json`` now follows ``--config-dir`` (the tests
       used to write into the real configuration).
   * - 3.2
     - Attach the existing presets and histories to the ``default`` profile
       (migration of the current PBRenamer configuration). Done:
       ``migration.migrate_v1`` **copies** ``patterns/``,
       ``sidecar_config.json``, ``last_dir`` and ``toolbar_state`` into
       ``default``; the 1.x files stay in place. Shortcuts, extension
       normalization, geometries, language and preferences remain global.
   * - 3.3
     - One-time import of the catalogs from ``$XDG_CONFIG_HOME/pbpicat/``:
       ``settings.json``, ``history.json``, ``ui.conf``, ``open_with.json``.
       The source directory is never modified. Done:
       ``migration.import_pbpicat``, automatic on first launch; a collision is
       renamed ``pbpicat-NAME`` (``.pbpicat-NAME`` if hidden), invalid names
       sanitized. Extensions and sidecars go to ``sidecar_config.json`` (dot
       removed, sidecars for pictures and videos), schema settings, display
       and image options to ``profile.json``, ``open_with.json`` copied,
       viewer options from ``app.conf`` to ``pbrenamer.conf``. Not imported:
       geometries, language, ``global_settings.json``, ``catalog.conf``,
       obsolete keys (``text_sidecar_extensions``, ``thumbnail_size``…). No
       import with ``--config-dir``.
   * - 3.4
     - ``--profile`` CLI option. Done: unknown profile → exit code 2;
       remembered in the GUI, never in headless mode; ``--saved``, sidecars
       and schema defaults (``--dest``, marker, position, fill gaps) taken
       from the profile; the CLI never writes to the profile.
   * - 3.5
     - Migration tests from real, anonymized PBPicat and PBRenamer
       configuration sets in ``tests/data/``. Always through
       ``--config-dir``. Done: ``tests/data/pbpicat_config/`` and
       ``tests/data/pbrenamer_v1_config/`` (anonymized),
       ``tests/test_profiles.py``, ``tests/test_migration.py`` (unchanged
       source checked by fingerprint), ``TestProfileOption`` class of
       ``test_headless.py``.

Exit criterion: an existing PBPicat configuration is found in full in a
profile.

Phase 4: Schema mode interface (≈ 1 week)
-----------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 8 92

   * - Task
     - Detail
   * - 4.1
     - Pattern / Schema tabs in the rule panel (``QTabWidget``). Done: active
       tab remembered per profile (``profile.json`` ``mode``, last tab used);
       in Schema mode, extension mode and Sidecar checkbox disabled, sidecars
       always grouped (``sidecars_forced`` callback of
       ``FileListController``).
   * - 4.2
     - ``ui/rule_panel_schema.py``: port of ``SchemaFrame`` (fields with
       history, marker radio buttons, destination, fill gaps). Done:
       ``SchemaRulePanel`` (destination and Browse, Fill gaps, N fields with
       an LRU history ``field_N`` limited to ``history_max``, validator
       rejecting ``_ . / \``, marker position); marker and Fill gaps saved on
       change; destination saved when chosen, after a rename, on profile
       change and on close; errors (missing or relative destination, invalid
       schema) shown in the panel.
   * - 4.3
     - Single Rename button (selection or all, count in the label, F2),
       conditional Renumber button. Done: "Rename (n)"
       (``rename_count_changed`` signal), F2; Renumber visible in Schema mode
       with a ``###`` field, plan computed on the selection (or everything),
       confirmation, atomic execution and undo like a rename.
   * - 4.4
     - "New name" column showing the path relative to the destination in
       Schema mode. Done: ``PreviewEntry.target`` (absolute path, dedicated
       role in the column) used for conflicts and execution; text relative to
       the destination, sidecars included.
   * - 4.5
     - Profile menu, profile configuration dialog (Schema tab). Done: Profile
       menu (New Ctrl+N, Duplicate Ctrl+Shift+D, Rename (current profile,
       without ".", never onto an existing profile), Delete (visible profiles
       only, ``default`` included, never the last visible one), Profile
       configuration Ctrl+,, checkable list of the visible profiles and of the
       current profile if hidden); "PBRenamer [profile]" title; profile
       switch: presets, Schema panel, tab, toolbar state and last directory of
       the profile, undo stack kept. ``ProfileDialog`` (Schema tab: number of
       fields, titles, video marker, history size). Menus of :ref:`§ 4.3 <pbpicat-merge-4-3>`
       restructured in phase 6.
   * - 4.6
     - Histories: schema fields added to the dialog, accent-insensitive sort
       (PBPicat's ``_sort_fold``). Done: "Patterns" tab (search and replace
       unchanged) and one tab per field (``FieldHistoryWidget``: move up, move
       down, drag, sort, delete, clear all, saved immediately); ``sort_fold``
       and ``QCollator`` on the current language
       (``i18n.current_language``), empty strings last. Sidecar filter tab
       with task 5.3.

Exit criterion: a photo directory can be filed as with PBPicat, without
thumbnails.

Phase 5: enriched file list (≈ 1 week)
--------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 8 92

   * - Task
     - Detail
   * - 5.1
     - Optional thumbnail column: port of the lazy loading (visible window +
       margin, 400 ms debounce, up to 4 workers, shared ``QImageReader``
       lock, stale signals rejected by path). Done: ``core/image_io.py``
       (shared lock, allocation limit, Pillow fallback, HEIC through
       pillow-heif) and ``core/image_ops.py`` (``is_jpeg``,
       ``repair_jpeg_sos``, completed in 6.1); ``ui/thumbnails.py``
       (``ThumbnailLoader``: visible rows plus one screen of margin, 400 ms
       debounce, nothing while the scrollbar handle is held, up to 4 workers,
       rejection by path), thumbnail in ``DecorationRole`` (no widget per
       cell), video icon, second line "W×H · size". Column enabled per
       profile (``display.thumbnails``, "Thumbnails" checkbox of the option
       bar, Display tab of the profile configuration).
   * - 5.2
     - Sidecar column: indicator, opening, choice menu, creation with the
       default extension. Done: column enabled per profile
       (``display.sidecar_column``); sidecars remain separate rows, the
       "● suffixes" or "○" indicator is on the base file row; double-click:
       opening, choice menu, or empty creation with
       ``images.sidecar_new_extension``. Deletion of empty sidecars on
       loading, ``images.delete_empty_sidecars`` option off by default (true
       for imported PBPicat catalogs), a just-created sidecar spared.
   * - 5.3
     - Filter on sidecar content, with history. Done:
       ``sidecar.filter_by_content`` (DOTALL, case-insensitive, cache by
       mtime), editable combo box in the option bar shown according to the
       profile (``display.sidecar_filter``), 400 ms debounce, invalid
       expression framed in red, ``sidecar_filter`` history on Enter and
       "Sidecar filter" tab of the histories dialog, cleared on directory
       change.
   * - 5.4
     - Automatic selection after renaming or deletion, Tab navigation, refresh
       on disk changes, restoring the current index. Done: new directory:
       first row current without selection (Rename always applies to
       everything); reloading the same directory (disk, options, drag and
       drop): selection and current row restored; after Rename or Renumber:
       targets still listed are selected, otherwise the next row becomes
       current (``select_paths``, ``next_path_after``, reusable in 6.5); Tab
       and Shift+Tab between the tree and the list.
   * - 5.5
     - Merging drag and drop: PBRenamer's behavior (grouped confirmation) +
       PBPicat's sidecars and internal undo. Done: grouped
       Overwrite/Skip/Cancel confirmation kept; sidecars follow their file
       (list: groups; external drop: ``sidecar.sidecars_on_disk``) and are
       skipped with it; undoable copies (``CopyEntry``), except those that
       overwrote a file.
   * - 5.6
     - Performance test: directory of 5,000 pictures, loading and scrolling
       time. Done: ``tests/perf/test_perf_file_list.py`` (``perf`` marker,
       ``make perf``, outside ``make test``), 5,000 1600×1200 JPEGs, 1,000 of
       them with a ``.xmp``. PBRenamer: reload 0.31 s, first thumbnails
       0.71 s, scrolling 7 to 10 ms per page, Pattern ``{newnum}`` preview
       0.78 s, Schema preview 1.04 s, filter 0.10 s. PBPicat v1.21.0, same
       scenario: 0.35 s, 0.51 s, 9 ms per page, filter 0.07 s. Test budgets:
       about three times PBPicat.

Exit criterion: no smoothness regression compared to PBPicat v1.21.0.

Phase 6: image tools (≈ 1 week)
-------------------------------

.. list-table::
   :header-rows: 1
   :widths: 8 92

   * - Task
     - Detail
   * - 6.1
     - ``core/image_ops.py``, ``core/image_io.py``: port of rotation, EXIF
       and SOS repair. Done: ``core/image_ops.py`` (lossless rotation with
       jpegtran or Pillow, ``get_exif_orientation``, ``set_exif_orientation``
       through pyexiv2, availability of Pillow, pyexiv2 and jpegtran,
       jpegtran looked up first in the PyInstaller bundle); typed undo
       ``RotationEntry`` and ``ExifResetEntry`` in ``core/undo.py``.
   * - 6.2
     - Images menu and context menu, enabled according to the selection and
       to the presence of the ``[images]`` extra and of jpegtran. Done: Images
       menu (Open Ctrl+Enter, Open with Ctrl+Shift+O, Viewer Enter, Template,
       Delete Del, Orphan sidecars, rotations F6 to F10, Information, Refresh
       F5), which also serves as the context menu; Ctrl+O stays "Open folder";
       ``ui/image_actions.py``; actions on the selection, otherwise on the
       current row; enabled according to pictures, Pillow, jpegtran and EXIF
       orientation (read for at most 50 files). Sort by date and reverse sort
       (gap from :ref:`§ 10.3 <pbpicat-merge-10-3>`): option bar checkboxes, saved in the profile.
   * - 6.3
     - Viewer: port of ``image_viewer.py`` and ``metadata_panel.py``, merged
       with ``file_info_window.py``. Done: ``ui/image_viewer.py`` (zoom,
       selection strip, linear or circular navigation, video, shortcuts); a
       single metadata component, ``ui/metadata_view.py``, shared by the
       viewer and the Information window, with the raw EXIF, IPTC and XMP
       sections and the sidecar XMP (``image_meta.read_raw_sections``,
       pyexiv2 with Pillow fallback); double-click on a picture or a video:
       viewer; Images tab of the profile configuration; state in
       ``window_state.json`` and ``pbrenamer.conf``.
   * - 6.4
     - Open with: port of ``platform/_linux.py``, ``_macos.py``,
       ``_windows.py`` into ``platform/``, MRU per MIME type. Done:
       ``platform/open_with.py`` and ``_open_linux.py``, ``_open_macos.py``,
       ``_open_windows.py``; MRU per MIME type in ``open_with.json``
       (``settings.get_open_with_lru``). "Open" keeps ``QDesktopServices``.
   * - 6.5
     - Delete (files, sidecars, empty directories, configurable confirmation).
       Done: files and sidecars, trash (``use_trash``, gap from :ref:`§ 10.3 <pbpicat-merge-10-3>`) or
       permanent deletion with cleanup of empty directories below the
       displayed directory, configurable confirmation, next row current;
       orphan sidecars dialog (gap from :ref:`§ 10.3 <pbpicat-merge-10-3>`,
       ``sidecar.orphan_sidecars``).
   * - 6.6
     - Template: inference of the schema fields from a file name. Done:
       ``schema.infer_fields``, proposal dialog, fields filled in and switch to
       the Schema tab.
   * - 6.7
     - PyInstaller bundles: pyexiv2 native libraries in ``pbrenamer.spec``.
       Done: jpegtran and pyexiv2 native libraries in ``pbrenamer.spec``
       (conditional); checked in the Linux executable.

Exit criterion: every row of the table in :ref:`§ 6 <pbpicat-merge-6>` is covered.

Phase 7: documentation, translations, release (≈ 4 days)
--------------------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 8 92

   * - Task
     - Detail
   * - 7.1
     - Merge the ``.po`` catalogs with pybabel (``make translate``), translate
       the new strings into the 8 languages, check with ``tools/po_check.py``.
       Done: 225 new strings per language (79 taken from the PBPicat catalogs,
       146 translated), 607/607 entries in the 8 languages; French non-breaking
       spaces applied to the whole ``fr`` catalog and 25 strings reworded
       without em dashes or straight quotes, ASCII umlauts inherited from
       PBPicat fixed in ``de``.
   * - 7.2
     - Intensive testing by the user. Every bug found is recorded here with
       its fix, to keep a record of the tests. Finished, unless new bugs turn
       up: 15 bugs fixed and approved (batches 1 to 3), test coverage raised to
       100 % (``platform/auto_update.py``, ``ui/main_window.py``). Any bug
       found later is added to the log below.
   * - 7.3
     - Sphinx documentation: new "Schema mode", "Profiles" and "Image tools"
       chapters; migration guide from PBPicat. Addition (requested on
       2026-10-31): translation of the User Guide (narrative pages
       ``index.rst`` and ``user_guide.rst``, neither the API nor the
       changelog) into the 7 interface languages (fr, de, es, it, ru, vi,
       zh_CN): sphinx-intl, one ``.po`` per page
       under ``docs/locale/``, ``language`` read from
       ``READTHEDOCS_LANGUAGE``, ``make docs LANG=xx``,
       ``make docs-translate`` and ``make docs-stats`` targets. On the Read the
       Docs side, one project per language to declare by hand as a
       translation of the main project. Done, committed (``0b8e97e``):
       ``user_guide.rst`` completed (Profiles, Schema Mode, Image Tools,
       Migrating from PBPicat chapters, F1 help and online manual, optional
       dependencies), outdated passages fixed (menus, preferences,
       per-profile configuration files, ``{newnum}``, ``{dest}``,
       ``{if:…}``, schema CLI options and ``--profile``, examples checked with
       ``--dry-run``); i18n infrastructure (``sphinx-intl`` added to the
       dependencies, ``conf.py``, Makefile, ``tools/fix_po_files.py --docs``);
       624 entries translated per language (141 copied as purely technical),
       French proofread for typography, other languages marked ``==AUTO==``,
       interface labels taken from the application catalogs, escaped spaces
       for Chinese. Read the Docs translation projects created on 2026-10-31
       (the 8 ``/<language>/latest/`` addresses respond); the translated
       content will be published with the merge into the main branch (7.5).
       API reference fixed (PySide6 mocked during the whole build, 26 modules
       added).
   * - 7.4
     - README and CHANGELOG (Keep a Changelog, every ``git log`` entry since
       v1.8.1), with the behavior changes of :ref:`§ 5 <pbpicat-merge-5>` (atomic conflicts in the
       CLI). Done (2026-10-31): at the top of the entry, a "Merge PBPicat"
       section (intended deviation from Keep a Changelog) describes the
       changes brought by the merge, without the intermediate fixes; the rest
       goes into Added, Changed and Fixed. README: Schema mode, profiles,
       image tools, ``[meta]`` and ``[images]`` extras, schema CLI options and
       ``--profile``, atomic conflicts. The 12 commits of ``merge-pbpicat``
       are squashed into one.
   * - 7.5
     - Merge ``merge-pbpicat`` and release **PBRenamer 2.0.0** (major change:
       profiles, migrated configuration, atomic conflicts). Done on
       2026-11-04: ``merge-pbpicat`` fast-forwarded into ``main``
       (``7db4154``), version 2.0.0 (``make bump-set``),
       ``[2.0.0] - 2026-11-04`` section of the CHANGELOG, commit ``73717ae``
       and local tag ``v2.0.0``.
   * - 7.6
     - Last PBPicat release (v1.22.0) showing a deprecation message pointing
       to PBRenamer; repository archived after a transition period. Done on
       2026-11-04.

Exit criterion: PBRenamer 2.0.0 released on GitHub, PyPI and Read the Docs;
complete translations in the 8 languages.

Test log for 7.2
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 5 30 30 35

   * - No.
     - Bug
     - Cause
     - Fix
   * - 1
     - When switching to sidecar mode, the selection is not extended to the
       groups (1.1: base selected without its sidecars; 1.2: sidecar selected
       without its base or the other sidecars).
     - ``reload`` then ``_restore_state`` restore the selection as is; only a
       click triggers ``_link_group_selection``.
     - ``_restore_state`` extends the restored selection to whole groups
       (``_expand_to_groups`` helper, shared with
       ``_link_group_selection``).
   * - 2
     - Sidecar mode, a single file with sidecars selected: "Information"
       reports a multiple selection. Same defect for Template (grayed out),
       Open and Open with (which also open the sidecars).
     - ``_refresh_file_info`` and ``ImageActions.targets()`` count the
       selected rows, sidecars included.
     - ``FileListController.selected_bases()`` reduces the selection to the
       base files; used by the Information window and by ``targets()``
       (Delete still takes the sidecars along).
   * - 3
     - Context menu: no "Open sidecar" entry.
     - Missing feature.
     - "Open sidecar" submenu in the Images menu (hence also in the context
       menu), one entry per suffix present, grayed out without a sidecar; new
       strings translated into the 8 languages.
   * - 4
     - Double-click: on the name, the viewer opens instead of the application
       (4.2); on the thumbnail, the viewer is expected (4.3). 4.1 (Sidecar
       column) is correct.
     - ``_on_item_double_clicked`` only tells the Sidecar column apart.
     - Original and Preview columns: default application; Thumbnail column:
       viewer for a media file, otherwise default application.
   * - 5.1
     - The pattern ".." to "." does not rename ``xxxxx_0002..xmp``.
     - Outside "Modify" mode, the pattern applies only to the stem
       (``xxxxx_0002.``), which does not contain "..".
     - Option A: the extension separator dot is included in the searched
       text; the result must always end with a dot, otherwise the preview
       shows an error.
   * - 5.2
     - ``xxxxx_0001.xmp`` seen as a base file although ``xmp`` is a sidecar
       suffix.
     - ``TESTS`` profile: ``info.json`` and ``prompt.txt`` are common
       suffixes, hence also valid for the "other" category; the ``.xmp``
       becomes an "other" base competing with the ``.jpg`` (ambiguity error).
     - ``build_sidecar_groups``: an "other" file whose name looks like a
       sidecar is never a base.
   * - 6
     - Sidecar mode: sidecars do not follow their base file (``a.info``
       before ``a.jpg``), and the date or reverse sort scatters them.
     - The list is sorted by name, then by the sort options; groups were only
       used for coloring and selection.
     - In sidecar mode, each base file is followed by its sidecars sorted by
       name (hence by suffix); only base files follow the date or reverse sort
       (``_grouped_order``).
   * - 7
     - Viewer with several files: Left and Right step through the selection,
       but Up and Down change the main window's selection.
     - Up and Down always navigated the list, Left and Right always the
       selection.
     - Up and Left = previous, Down and Right = next. Multiple selection:
       move within the selection; single file: go to the previous or next
       media file of the list.
   * - 8
     - A selection change in the main window is not reflected in the open
       viewer (other file, selection extended or reduced).
     - The viewer was only updated when opened and by navigation, unlike in
       PBPicat.
     - The open viewer follows the selection (a sidecar group counts as its
       base file). Displayed file: the current row if selected, otherwise the
       file already displayed, otherwise the first one. An empty selection or
       one without media changes nothing.
   * - 9
     - Viewer: with many files selected, the window takes a very long time to
       show up.
     - The selection strip loaded all its thumbnails at once, on every
       selection change.
     - Deferred loading: only the visible thumbnails (plus one width on each
       side) are loaded, four per event loop pass, the displayed file's first;
       scrolling loads the rest.
   * - 10
     - Schema mode, TESTS profile: with "renomme,,,####", the file is renamed
       in place instead of being moved into ``arbre/renomme/``.
     - Without a preview (automatic preview off), Rename was grayed out but
       Renumber enabled; yet Renumber renames in place by design.
     - Renumber stays grayed out as long as no preview is shown, like Rename.
   * - 11
     - Schema mode: the field history is not saved.
     - It was only saved after Rename (as in PBPicat), not after Renumber.
     - Renumber also saves the field history after a successful renumbering.
   * - 12
     - Schema mode: after Renumber, the previews are not cleared (to be
       checked after Rename too).
     - With the automatic preview, the reload and the new selection that
       follow the operation recompute the preview; in Schema mode it always
       yields a target. After Rename, the files have left the directory, hence
       an empty list.
     - After a successful rename or renumbering, the automatic preview is
       suspended during the reload: the preview stays empty, in both modes,
       until the next change.
   * - 13
     - Schema mode: an orphan sidecar (``dummy.xmp``) gets a preview that
       attaches it to a base file that does not have this kind of sidecar yet
       (``xxxxx_0003.xmp``, next to ``xxxxx_0003.jpg``).
     - Without a base file, the orphan was handled as an ordinary file and
       numbered.
     - In Schema mode, orphan sidecars are neither renamed nor renumbered:
       their preview shows "⚠ orphan sidecar, not renamed" (in gray), without
       blocking the renaming of the other files. Pattern mode is unchanged.
   * - 14
     - PBPicat's shortcut help (F1) was not carried over.
     - PBPicat's ``_ShortcutsDialog`` window had not been ported; the Help
       menu only offered "About".
     - New Help > "Keyboard and mouse shortcuts…" menu entry (F1, PBPicat's
       icon), a non-modal window that keeps its geometry
       (``ui/keyboard_help.py``, reuses ``PatternHelpDialog``). It takes over
       PBPicat's content and adds PBRenamer's specifics: Ctrl+O, Ctrl+I,
       profile configuration, F2 depending on the Preview column, Enter
       (viewer) and Ctrl+Enter, empty selection = all files, double-click on
       thumbnail / name / sidecar, right-click on list and tree, drag (move)
       and Ctrl+drag (copy) with sidecars, viewer: ←↑ / →↓ within the
       selection or the list, I, Ctrl+Enter, Ctrl+Shift+O, F6 to F10, click
       on the strip. Keys in native format (⌘ on macOS). 57 strings
       translated into the 8 languages, 3 tests.
   * - 15
     - The Help menu does not point to the online user manual.
     - Missing entry.
     - New Help > "User manual" entry that opens
       ``https://pbrenamer.readthedocs.io/<language>/latest/user_guide.html``
       in the browser. The language is that of the catalog actually loaded
       (``i18n.ui_language``: ``fr_FR`` gives ``fr``, a language without a
       catalog gives ``en``), spelled as Read the Docs does (``zh_CN`` gives
       ``zh-cn``). 3 strings translated into the 8 languages, 5 tests. To
       date, only the ``en`` version of the manual exists online (404 for
       ``fr``, ``de``, ``zh-cn``).

Batch 1 fixes (bugs 1 to 5.2) approved and committed: 32 tests added,
``make test`` (2,267 tests, 99 % coverage), ``make perf`` and ``make hooks``
passed. Two new strings translated into the 8 languages ("Open sidecar",
"⚠ extension separator removed"). For 5.1, the search on "stem + ." is only
attempted when the pattern finds nothing in the stem alone, so as not to change
the result of existing patterns (``*`` would capture the dot).

Batch 2 fixes (bugs 6 to 8) approved and committed: 15 tests added or adapted,
``make test`` (2,282 tests, 99 % coverage), ``make perf``, ``make lint`` and
``make hooks`` passed. No new string to translate.

Batch 3 fixes (bugs 9 to 15) approved and committed: 19 tests added,
``make test`` (2,301 tests, 99 % coverage), ``make perf``, ``make lint`` and
``make hooks`` passed. 61 new strings translated into the 8 languages (orphan
sidecar, F1 help, user manual).

Coverage completed after batch 3: ``pragma: no cover`` on the abstract method
of ``auto_update._BaseUpdater``, tests of the Windows and macOS error paths of
the automatic update and of the main window state restoration. ``make test``
(2,306 tests, 100 % coverage), ``make lint`` and ``make hooks`` passed.

Summary
-------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Phase
     - Estimated duration
     - Deliverable
   * - 0\. Preparation
     - 2 d
     - code split, dependencies
   * - 1\. Engine
     - 5 d
     - extended and tested engine
   * - 2\. Schema CLI
     - 3 d
     - working ``--schema``
   * - 3\. Profiles
     - 4 d
     - profiles and migration
   * - 4\. Schema interface
     - 5 d
     - usable Schema tab
   * - 5\. Enriched list
     - 5 d
     - thumbnails, sidecars, filter
   * - 6\. Image tools
     - 5 d
     - viewer, rotation, EXIF
   * - 7\. Release
     - 4 d
     - PBRenamer 2.0.0
   * - **Total**
     - **≈ 33 days**
     -

.. _pbpicat-merge-8:

8. Risks and mitigations
========================

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Risk
     - Impact
     - Mitigation
   * - Different conflict semantics ("skip" in PBRenamer, "all or nothing" in
       PBPicat)
     - Unexpected partial rename; existing CLI scripts relying on the old
       behavior
     - Atomic execution everywhere (decision 3); change flagged in the
       CHANGELOG and the 2.0.0 documentation
   * - Performance: live preview + thumbnails + metadata reading
     - Slow interface on large directories
     - Preview computed in the background, per-file metadata cache,
       performance test in phase 5
   * - ``main_window.py`` already large
     - Code hard to maintain
     - Prior split (phase 0)
   * - Executable size (pyexiv2 native libraries)
     - Heavier download
     - Accepted for binaries; optional extras for pip
   * - Configuration migration
     - Loss of histories or catalogs
     - Read-only import, tests on real configurations, never on the user's
       configuration (``--config-dir``)
   * - Two category definitions (picture/video extensions in both projects)
     - Inconsistent filing
     - A single table per profile, the one of ``core/sidecar.py``

.. _pbpicat-merge-9:

9. Decisions
============

.. list-table::
   :header-rows: 1
   :widths: 5 30 45 20

   * - \#
     - Question
     - Decision
     - Applied in
   * - 1
     - Name of the merged program
     - keep **PBRenamer** (name already published on PyPI and Read the Docs)
     - :ref:`§ 1 <pbpicat-merge-1>`
   * - 2
     - Reading image metadata
     - **pyexiv2 with Pillow fallback**
     - :ref:`§ 3.6 <pbpicat-merge-3-6>`
   * - 3
     - Conflict behavior in the CLI
     - **atomic**: nothing is renamed in case of conflict
     - :ref:`§ 3.2 <pbpicat-merge-3-2>`, :ref:`§ 5 <pbpicat-merge-5>`, :ref:`§ 8 <pbpicat-merge-8>`

.. _pbpicat-merge-10:

10. Appendix: inventory of the PBPicat tests (task 0.4)
=======================================================

PBPicat v1.21.0 has 22 test files (≈ 9,800 lines, ≈ 870 tests) plus
``conftest.py``. Each file is mapped to its target file in PBRenamer and to the
phase in which it is ported. Tests are ported together with the code they
cover, never before.

10.1 Fixtures
-------------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - PBPicat fixture
     - Outcome in PBRenamer
   * - ``install_gettext_builtin``
     - not needed: already handled by PBRenamer's ``conftest.py``
   * - ``catalog_env`` (redirection of ``config._BASE_DIR``)
     - replaced by ``config_dir`` / ``_isolated_config`` (through
       ``settings.configure``); the profile tests (phase 3) rely on it
   * - ``sample_png``
     - to be taken over in ``tests/conftest.py`` in phase 5 (thumbnails)
   * - ``media_dir`` (PNG + ``.xmp`` sidecars, one of them orphan)
     - to be taken over in ``tests/conftest.py`` in phase 1 (execution with
       sidecars)

10.2 File mapping
-----------------

.. list-table::
   :header-rows: 1
   :widths: 20 7 23 8 42

   * - PBPicat file
     - Tests
     - PBRenamer target file
     - Phase
     - Notes
   * - ``test_renamer.py``
     - 79
     - ``test_replacement.py``, ``test_filetools.py``, ``test_schema.py``
       (new)
     - 1, 2
     - ``find_max_number``, ``_fill_gap_numbers`` → contextual ``{newnum}``
       (1.3); ``build_rename_plan``, ``execute_rename``, ``undo_rename`` →
       engine (1.2); ``build_renumber_plan``, ``execute_renumber``,
       ``undo_renumber`` → 1.5; ``execute_copy``, ``undo_copy`` → typed undo
       (1.6); ``validate_schema`` → ``core/schema.py`` (2.1). Basis of the
       phase 1 exit criterion.
   * - ``test_config.py``
     - 63
     - ``test_settings.py``, ``test_profiles.py`` (new)
     - 3
     - Catalog management (creation, duplication, hidden), histories, last
       destination, video marker position, fill gaps → profiles.
       ``_FakeQSettings`` and ``qsettings()``: obsolete (PBRenamer does not use
       ``QSettings``). ``load/save_open_with_lru`` → phase 6 (6.4). Also serves
       as a reference for the catalog import (3.3).
   * - ``test_main.py``
     - 9
     - ``test_headless.py``
     - 2, 3
     - Positional catalog argument → ``--profile``; ``--dev-config-dir``
       obsolete (``--config-dir`` already exists).
   * - ``test_argparse_qt.py``
     - 6
     - ``test_argparse_qt.py``
     - —
     - Obsolete: identical module, already covered.
   * - ``test_i18n.py``
     - 28
     - ``test_i18n.py``
     - —
     - Obsolete: equivalent gettext bootstrap, already covered.
   * - ``test_ui_schema_frame.py``
     - 19
     - ``test_rule_panel_schema.py`` (new)
     - 4
     - ``SchemaFrame``, ``_SchemaField``, ``_ForbiddenCharValidator`` (``_``
       and ``.`` forbidden).
   * - ``test_ui_history_dialog.py``
     - 31
     - ``test_ui_dialogs.py``
     - 4
     - Schema fields tab; ``_sort_fold`` (accent- and case-insensitive sort)
       to be taken over as is (4.6).
   * - ``test_ui_settings_dialog.py``
     - 48
     - ``test_ui_dialogs.py``, ``test_profile_dialog.py`` (new)
     - 4, 6
     - ``SettingsDialog`` → profile configuration; ``GlobalSettingsDialog``
       → program settings. The Images and Thumbnails tabs come in phases 5
       and 6.
   * - ``test_ui_main_window.py``
     - 129
     - ``test_main_window.py``
     - 3 to 6
     - Catalogs → Profile menu (4.5); drag and drop and undo → 5.5; rotations
       and ``reset_exif`` undo → 6.2; ``_ShortcutsDialog`` → "Keyboard
       shortcuts" window; ``_OrphanSidecarsDialog``: see :ref:`§ 10.3 <pbpicat-merge-10-3>`.
   * - ``test_ui_file_list_widget.py``
     - 172
     - ``test_file_list.py``, ``test_main_window.py``
     - 5, 6
     - The largest batch. Loading and ``QFileSystemWatcher``, sidecar filter
       (5.3), automatic selection and keyboard navigation (5.4), internal or
       external move and copy (5.5), thumbnails and preview tooltip (5.1; the
       tooltip becomes obsolete, replaced by the "New name" column); open,
       delete, Template, viewer (phase 6); ``use_trash`` trash mode: see
       :ref:`§ 10.3 <pbpicat-merge-10-3>`.
   * - ``test_ui_file_panel.py``
     - 3
     - ``test_main_window.py``
     - 4
     - ``FilePanel`` disappears in the merge (tree + list already assembled by
       ``MainWindow``); keep only the behaviors still relevant.
   * - ``test_ui_dir_tree.py``
     - 33
     - ``test_dnd_widgets.py``
     - 5
     - Context menu and drop on the tree; to be merged with
       ``DirectoryTreeView`` (5.5).
   * - ``test_image_ops.py``
     - 52
     - ``test_image_ops.py`` (new)
     - 6
     - Lossless rotation (jpegtran, Pillow), EXIF orientation, SOS repair
       (6.1). jpegtran tests conditional on its presence.
   * - ``test_image_io.py``
     - 16
     - ``test_image_io.py`` (new)
     - 5, 6
     - ``QImage`` / ``QPixmap`` loading, HEIC (pillow-heif); useful from the
       thumbnails on (5.1).
   * - ``test_metadata.py``
     - 7
     - ``test_meta_image.py``
     - 6
     - ``read_metadata`` (pyexiv2) and ``find_xmp_sidecar``; to be aligned
       with decision 2 (pyexiv2 with Pillow fallback) and with
       ``core/sidecar.py``.
   * - ``test_ui_image_viewer.py``
     - 86
     - ``test_ui_image_viewer.py`` (new)
     - 6
     - Viewer: zoom, navigation, signals, metadata panel (6.3).
   * - ``test_ui_metadata_panel.py``
     - 7
     - ``test_file_info_window.py`` (new)
     - 6
     - Panel merged with ``file_info_window.py`` (6.3).
   * - ``test_platform_linux.py``
     - 68
     - ``test_platform_open_with.py`` (new)
     - 6
     - Open with and MRU per MIME type (6.4).
   * - ``test_platform_macos.py``
     - 5
     - ``test_platform_open_with.py``
     - 6
     - Same, macOS.
   * - ``test_platform_windows.py``
     - 5
     - ``test_platform_open_with.py``
     - 6
     - Same, Windows.

Outcome: 2 obsolete files (``test_argparse_qt.py``, ``test_i18n.py``); ≈ 80
tests for the engine and the schema (phases 1 and 2), ≈ 65 for the profiles
(phase 3), the rest for the interface and the image tools (phases 4 to 6).

.. _pbpicat-merge-10-3:

10.3 Gaps found with § 6
------------------------

The inventory reveals PBPicat features missing from the mapping table of
:ref:`§ 6 <pbpicat-merge-6>`:

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - PBPicat feature
     - Proposal
   * - Orphan sidecars dialog (``_OrphanSidecarsDialog``: list, refresh,
       selective or full deletion)
     - Images or Edit menu, phase 6 (with 6.5 Delete)
   * - Deletion to the trash (``use_trash``, on by default)
     - option in the Images tab of the profile configuration, phase 6 (6.5)
   * - Sort by date and reverse sort of the list (``sort_by_date``,
       ``sort_reverse``)
     - not ported in phase 5: list sorted by name as in PBRenamer; to be
       decided (option bar option, phase 6)

These three rows were added to :ref:`§ 6 <pbpicat-merge-6>` and handled in phase 6.
