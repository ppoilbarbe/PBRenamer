User Guide
==========

.. contents:: On this page
   :local:
   :depth: 2

Installation
------------

PBRenamer is distributed as a standalone executable.  Download the archive for
your platform from the `GitHub Releases
<https://github.com/ppoilbarbe/PBRenamer/releases>`_ page, extract it, and run
the binary directly — no Python installation required.

Launching
---------

GUI mode
~~~~~~~~

Run the binary (or ``python -m pbrenamer`` from a development environment)::

    pbrenamer [DIR]

If *DIR* is omitted the current working directory is used as the starting
folder.  Qt platform options such as ``--style`` and ``--platform`` are
forwarded to Qt and can be appended after the positional argument.

Headless (no-GUI) mode
~~~~~~~~~~~~~~~~~~~~~~

Pass ``--search`` or ``--saved`` to activate headless mode.  PBRenamer will
list, rename, and exit without opening any window::

    pbrenamer --search PATTERN --replace REPLACEMENT [options] [DIR]
    pbrenamer --saved  NAME    [overrides…]            [DIR]

See :ref:`cli-reference` for the full flag list and :ref:`cli-examples` for
worked examples.

The GUI
-------

Opening a folder
~~~~~~~~~~~~~~~~

Click **Open folder…** (toolbar) or drag a directory onto the window to load
its contents.  Use the **Recurse** checkbox to include sub-directories.  A
**Filter** field accepts a glob pattern (e.g. ``*.jpg``) to restrict the
listing.

Use the **Show** combo to display *Files only*, *Directories only*, or *Both*.

The file list
~~~~~~~~~~~~~

The main table shows:

* **Original name** — the current file name on disk.
* **New name** — the preview of the name after renaming.  The cell is empty
  when the current pattern does not match the file.  Rows shown in a distinct
  colour are directories.

Rows with a naming conflict are highlighted in red.  The **Rename** button is
disabled until all conflicts are resolved.

You can select a subset of rows with the usual keyboard/mouse modifiers
(Shift+click, Ctrl+click).  Renaming then applies only to the selected files.

Drag and drop
~~~~~~~~~~~~~~

Files and directories can be dragged:

* between the directory tree and the file list,
* between PBRenamer and external applications (a file manager, another
  window),

to copy or move them.  The action taken (copy or move) follows the standard
OS/Qt drag modifier keys — the default action is a move; hold the platform's
copy modifier (e.g. **Ctrl** on Linux/Windows) to force a copy instead.
Custom cursors indicate the resulting action while dragging.

If any dropped item would overwrite an existing file or directory, a single
confirmation dialog lists how many collide and offers **Overwrite**, **Skip**
(collisions only — everything else still proceeds), or **Cancel** (nothing is
copied/moved). Dropping a folder into itself or one of its own
sub-directories is rejected with an error.

Only **moves** are recorded on the undo stack; copies are not undoable, since
the original file is left in place.

Configuring the rename rules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The right-hand panel contains all renaming controls.

Search field
^^^^^^^^^^^^

Enter the search expression in the **Search** combo.  Three modes are
available via the adjacent selector:

``Pattern``
    Wildcard-based matching.  See :ref:`pattern-mode`.

``Regex``
    Full Python ``re``-module syntax.  See :ref:`regex-mode`.

``Plain``
    Literal string matching.  See :ref:`plain-mode`.

Click the **?** button next to the search field to open the non-modal Search
Patterns help dialog.

Replace field
^^^^^^^^^^^^^

Enter the replacement expression.  The syntax is the same for all three search
modes.  See :ref:`replacement-fields` for the complete field reference.

Click the **?** button next to the replace field to open the non-modal
Replacement Fields help dialog.

Extension mode
^^^^^^^^^^^^^^

Controls how the file extension is handled during rename.  Choices:

* *Keep extension* (default) — the search/replace pattern is applied to the
  file *stem* only; the extension is preserved unchanged.
* *Extension in lowercase* — the extension is preserved but forced to
  lowercase (e.g. ``.JPG`` → ``.jpg``).
* *Extension in uppercase* — the extension is preserved but forced to
  uppercase (e.g. ``.jpg`` → ``.JPG``).
* *Normalize extension* — the extension is looked up (case-insensitively) in
  the extension normalization table (**Edit → Settings… → Extension
  Normalization** tab) and replaced accordingly (e.g. ``.jpeg`` → ``.jpg``);
  left unchanged if not found in the table.
* *Modify extension* — the search/replace pattern is applied to the full file
  name, including the extension.

The normalization table is managed from the **Extension Normalization** tab
of the Settings dialog (**Edit → Settings…**): add, remove, or clear
``from → to`` extension mappings (both sides without the leading dot).
Changes to the table apply immediately and are kept even if the dialog is
later cancelled.

.. _sidecar-files:

Sidecar files
^^^^^^^^^^^^^

A **sidecar file** is a file associated with a *base file* by a name suffix —
for example ``photo.jpg`` (base file) and ``photo.xmp`` or
``photo.info.json`` (sidecars). PBRenamer can detect these relationships,
group the files together in the list, and rename an entire group in one
operation.

Enabling sidecar mode
""""""""""""""""""""""

The **Sidecar mode** checkbox, next to the Extension mode combo, turns the
feature on.  It is only selectable when Extension mode is *Keep extension*,
*Extension in lowercase*, or *Extension in uppercase* — sidecar suffixes are
never re-derived, so a mode that rewrites the extension (*Normalize
extension*, *Modify extension*) would make the relationship ambiguous.  The
checkbox is greyed out (and treated as unchecked) for those two modes; its
checked/unchecked state is otherwise remembered like the Extension mode
itself, both in the toolbar state and in named presets.

How grouping works
"""""""""""""""""""

Each file is classified into one of four categories based on its own
extension: **Images**, **Video**, **Audio**, or **Other** (anything not
recognised as an image/video/audio base extension — this also includes
sidecar-only files such as a bare ``.xmp``). Each category has its own
configurable list of:

* **base extensions** — which extensions make a file a candidate *base* for
  that category (not applicable to *Other*, which is the catch-all);
* **sidecar suffixes** — which name suffixes, when found at the end of a
  file name, mark it as that category's sidecar.

A fifth, **Common** list of sidecar suffixes applies to every category in
addition to its own list.

For a candidate sidecar file, PBRenamer looks — within the same directory
only — for base files whose stem (the part before the matched suffix) and
category match. A sidecar suffix is only searched among *its own potential
base file's category* (plus the common list); it is never matched against
unrelated categories.

* **Exactly one** matching base file → the sidecar joins that base's group.
* **No** matching base file → the file is left ungrouped, exactly as if
  sidecar mode were off.
* **More than one** matching base file — whether all candidates are in the
  same category (e.g. ``clip.xml`` matching both ``clip.jpg`` and
  ``clip.png``, both images) or in different categories (e.g. ``clip.xml``
  matching an image ``clip.jpg`` *and* a video ``clip.avi``, because
  ``.xml`` is a sidecar suffix for both) — this is an explicit,
  **unrenamable ambiguity**. The sidecar and *every* candidate base file
  involved are flagged with an error explaining the conflict; none of them
  can be renamed until the ambiguity is resolved (e.g. by removing or
  renaming one of the conflicting files, or by adjusting the category
  configuration).

If a suffix is only configured as a sidecar suffix for one category, a file
of another category with the same stem never causes ambiguity: with
``.xml`` configured as an image-only sidecar suffix, ``clip.xml`` +
``clip.jpg`` (image) + ``clip.avi`` (video) has a single candidate
(``clip.jpg``) — ``clip.xml`` joins its group, and ``clip.avi`` stays an
independent, ungrouped file.

Selection, preview, and renaming
"""""""""""""""""""""""""""""""""

While sidecar mode is active:

* Sidecar rows are shown in a distinct colour in the file list; ambiguous
  rows are shown as errors (like any other conflict), disabling the
  **Rename** button until resolved.
* Selecting any file in a group — the base or any of its sidecars —
  automatically selects the whole group.
* The rename pattern is applied to the base file's *stem* only, exactly as
  under *Keep/Lowercase/Uppercase extension*; each sidecar reuses that same
  transformed stem, followed verbatim by its own sidecar suffix (case
  preserved as found on disk) — the suffix itself is never altered.
* Renaming a group is a single operation: the base file and all its
  sidecars are renamed together, recorded as one batch on the undo stack, so
  **Undo** restores the whole group at once.

Configuring categories
"""""""""""""""""""""""

Open **Edit → Sidecar Files…** to configure the base extensions and sidecar
suffixes for each category. The dialog has one tab per base category
(*Images*, *Video*, *Audio*, *Other*) plus a *Common* tab:

* Each *base extensions* list (Images/Video/Audio only — *Other* has no such
  list, it is the catch-all) and each *sidecar suffixes* list can be edited
  with add/remove controls; an extension already assigned to a different
  category is rejected with a warning naming the conflicting category.
* Each list has its own **Restore defaults** button.
* Changes apply immediately and persist across sessions
  (``sidecar_config.json`` in the configuration directory), independently of
  whether the dialog is later closed or cancelled.

Sidecar grouping is also available in :ref:`headless mode <cli-reference>`
via ``--sidecar-mode`` / ``--no-sidecar-mode``.

Post-processing options
^^^^^^^^^^^^^^^^^^^^^^^

These transforms are applied *after* the search/replace step, in the order
listed:

**Separator**
    Convert between space-like delimiters.  Choices:

    * *None* — no conversion (default)
    * *Space → underscore*
    * *Underscore → space*
    * *Space → dot*
    * *Dot → space*
    * *Space → dash*
    * *Dash → space*

**Case**
    Apply a case transform to the result:

    * *None* — no change (default)
    * *UPPER CASE*
    * *lower case*
    * *Capitalize* (first character upper, rest lower)
    * *Title Case* (each word capitalised)

**Strip accents**
    Remove diacritics via Unicode NFD normalisation (``á → a``, ``ü → u``).

**Collapse duplicates**
    Collapse consecutive identical separator characters (``.``, ``-``, ``_``,
    space) into one.

Presets
^^^^^^^

The search and replace combos store your history automatically (LRU order).
Use the **Save** button to give the current pattern pair a name; named saves
can be loaded later from the **Presets** menu or via ``--saved`` in headless
mode.

Applying renames
~~~~~~~~~~~~~~~~

Click **Rename** to apply all non-conflicting renames.  The status bar reports
how many files were renamed.

Undo
~~~~

Click **Undo** (or press **Ctrl+Z**) to revert the most recent rename batch.
Each rename batch is recorded on an undo stack; the button label shows the
number of available batches (e.g. **Undo (3)**) when more than one is queued.

Shortcuts
~~~~~~~~~

The **Go → Shortcuts** menu provides one-click navigation to common directories.

**System directories**
    The top of the menu lists platform directories (Home, Desktop, Documents,
    Downloads, Pictures, Music, Videos).  On Linux, GTK bookmarks are shown
    instead when the file ``~/.config/gtk-3.0/bookmarks`` (or
    ``~/.gtk-bookmarks``) exists.

**User-defined shortcuts**
    Right-click any directory in the left-hand tree and choose
    **Add as shortcut**.  The entry is appended to the shortcuts list and
    persisted between sessions.

**Editing shortcuts**
    Choose **Go → Edit Shortcuts** to open the *Edit Shortcuts* dialog, where
    shortcuts can be reordered with *Move up* / *Move down* or removed.

File information
~~~~~~~~~~~~~~~~

Open **View → File information** to display a non-modal window listing the
actual values of every replacement field for the selected file.

The window has three groups:

* **Universal fields** — ``{date}``, ``{datetime}``, ``{mdatetime}``,
  ``{cdatetime}``, ``{dir}``; values are read from the file system.
* **Batch fields** — ``{0}``, ``{1}``/``{2}``…, ``{num}``, ``{newnum}``,
  ``{re:name}``; labelled *Computed* (they depend on the active pattern).
* **Metadata fields** — ``{im:…}``, ``{au:…}``, or ``{vi:…}`` depending on
  the file type; values are read from the file's embedded metadata.

The window updates live whenever the selection changes.

Settings
--------

Open **Edit → Settings** to configure:

**Language**
    Select the UI language.  Several languages are bundled; the selection
    takes effect immediately and is persisted.

**Log level**
    Controls diagnostic output written to the console.  Choices: ``DEBUG``,
    ``INFO`` (default), ``WARNING``, ``ERROR``, ``CRITICAL``.  Can be
    overridden at launch with ``--debug``, ``--verbose``, or ``--quiet``.

**Restore last opened directory** *(Behaviour group)*
    When enabled, the app reopens the directory that was active in the
    previous session.  A directory passed on the command line always takes
    priority.  Default: disabled (current working directory is used).

.. _config-files:

Configuration Files
--------------------

Everything the Settings dialog and other panels persist — preferences,
presets, and per-feature configuration — is stored as plain-text files (Qt
INI and JSON) under a single per-user configuration directory.  No system
directories or registry keys are touched.

Default location
~~~~~~~~~~~~~~~~~

============ =================================================
Platform     Default directory
============ =================================================
Linux        ``$XDG_CONFIG_HOME/pbrenamer`` (usually ``~/.config/pbrenamer``)
macOS        ``~/Library/Preferences/pbrenamer``
Windows      ``%APPDATA%\pbrenamer``
============ =================================================

Override with ``--config-dir DIR`` (see :ref:`cli-reference`) to point at
a different directory — useful for testing or for running several isolated
profiles side by side.

Files
~~~~~

``pbrenamer.conf``
    Qt INI settings: log level, language override, "restore last
    directory" preference and last directory, toolbar state, preview
    delay.

``shortcuts.json``
    User-defined directory shortcuts (**Go → Shortcuts** menu).

``extension_normalization.json``
    Per-extension normalization table used by extension mode ``normalize``.

``sidecar_config.json``
    :ref:`Sidecar file <sidecar-files>` category configuration (base
    extensions / sidecar suffixes per category), managed from
    **Edit → Sidecar Files…**.

``window_state.json``
    Main window geometry, position, and splitter ratios.

``patterns/search.json`` / ``patterns/replace.json``
    Most-recently-used search and replacement patterns (field dropdown
    history).

``patterns/saves.json``
    Named presets saved from the Presets panel, also loadable headlessly
    with ``--saved NAME``.

None of these files are required to exist — deleting any one of them (or
the whole directory) simply resets that piece of state to its default the
next time PBRenamer starts.

.. _search-patterns:

Search Patterns
---------------

.. _pattern-mode:

Pattern mode
~~~~~~~~~~~~

Tokens act as typed wildcards.  Segments matched by numbered tokens are
*captured* and available in the replacement as ``{1}``, ``{2}``, etc.

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Token
     - Matches
   * - ``{#}``
     - One or more digits (0–9)
   * - ``{L}``
     - One or more letters (a–z, A–Z)
   * - ``{C}``
     - One or more non-whitespace characters
   * - ``{X}``
     - Any sequence of characters, including empty
   * - ``{@}``
     - Trash — matches and discards a segment (not captured)
   * - ``{1}``, ``{2}``…
     - Capture group — the matched text is bound to ``{1}``, ``{2}``… in the replacement

**Example** — swap two parts separated by an ignored middle segment:

+---------------------+--------------------+---------------------------+
| Search              | Replace            | Result                    |
+=====================+====================+===========================+
| ``{1}_{@}_{2}``     | ``{2}_{1}``        | photo_trash_holiday       |
|                     |                    | → holiday_photo           |
+---------------------+--------------------+---------------------------+

.. _regex-mode:

Regular expression mode
~~~~~~~~~~~~~~~~~~~~~~~

Full Python ``re``-module syntax.  The match is applied to the file stem (or
full name if the extension mode is *Modify extension*).

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Syntax
     - Description
   * - ``.``
     - Any single character
   * - ``.*`` / ``.+``
     - Any sequence (greedy); non-empty variant
   * - ``\\d+``
     - One or more digits
   * - ``\\w+``
     - Word characters (letters, digits, ``_``)
   * - ``(…)``
     - Numbered capture group → ``{1}``, ``{2}``… in replacement
   * - ``(?P<name>…)``
     - Named capture group → ``{re:name}`` in replacement
   * - ``(?i)``
     - Case-insensitive flag
   * - ``^`` / ``$``
     - Start / end of the name

**Example** — reformat an ISO date:

+------------------------------------+------------------+------------------+
| Search                             | Replace          | Result           |
+====================================+==================+==================+
| ``(\\d{4})-(\\d{2})-(\\d{2})``     | ``{3}/{2}/{1}``  | 2024-06-15       |
|                                    |                  | → 15/06/2024     |
+------------------------------------+------------------+------------------+

.. _plain-mode:

Plain text mode
~~~~~~~~~~~~~~~

The search field is matched as a literal string — no wildcards, no special
characters.  Every occurrence of the exact text in the file name is replaced.

**Example:**

+------------+-----------+-------------------+
| Search     | Replace   | Result            |
+============+===========+===================+
| ``IMG_``   | ``photo_``| IMG_0042          |
|            |           | → photo_0042      |
+------------+-----------+-------------------+

.. _replacement-fields:

Replacement Fields
------------------

The replacement string syntax is the same regardless of the search mode.
Fields are written ``{name}`` and accept optional formatting options::

    {name}                   plain value
    {name:fmt}               with format
    {name:fmt:default}       with format and fallback value
    {name:<fmt}              left-align  (digit fmt = minimum width)
    {name:>fmt}              right-align
    {name:0fmt}              zero-pad right (numbers)
    {{                       literal '{' character

* **fmt** is a minimum width (digit) for text/numbers, or a ``strftime``
  format string for dates and datetimes.
* **default** is used when the field is absent.  Omitting it makes the field's
  absence an error (the row is shown in red in the preview).

Available fields
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 18 60

   * - Field
     - Available in
     - Description
   * - ``{0}``
     - all modes
     - Full matched text (or the search literal in plain-text mode)
   * - ``{1}``, ``{2}``…
     - pattern, regex
     - Numbered capture groups (1-based)
   * - ``{re:name}``
     - regex only
     - Named group ``(?P<name>…)`` from the search regex
   * - ``{num}``
     - all modes
     - Auto-incrementing counter.  *fmt* is a minimum width; *default* sets
       the starting value (e.g. ``{num:02:10}`` starts at 10, zero-padded to
       2 digits)
   * - ``{newnum}``
     - all modes
     - Like ``{num}`` but skips values whose target name already exists on
       disk or has been assigned to another file in the same batch —
       guarantees conflict-free numbering
   * - ``{date}``
     - all modes
     - Today's date — default ``strftime`` format ``%Y-%m-%d``
   * - ``{datetime}``
     - all modes
     - Current date and time — default format ``%Y-%m-%d_%H%M%S``
   * - ``{mdatetime}``
     - all modes
     - File modification date/time — default format ``%Y-%m-%d_%H%M%S``
   * - ``{cdatetime}``
     - all modes
     - File creation date/time — default format ``%Y-%m-%d_%H%M%S``
       (inode change time on Linux)
   * - ``{dir}``
     - all modes
     - Name of the immediate parent folder
   * - ``{im:Field}``
     - all modes
     - EXIF or IPTC metadata field (images — see :ref:`image-fields`)
   * - ``{au:Field}``
     - all modes
     - Audio metadata field (mp3, ogg, flac… — see :ref:`audio-fields`)
   * - ``{vi:Field}``
     - all modes
     - Video metadata field (mp4, mkv, avi… — see :ref:`video-fields`)

.. _image-fields:

Image metadata fields ``{im:…}``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Requires **Pillow**.  Field names are case-insensitive.  A *default* is
strongly recommended — metadata may be absent from non-image files or images
without EXIF/IPTC data.

.. list-table::
   :header-rows: 1
   :widths: 28 16 56

   * - Field
     - Type
     - Description
   * - ``DateTimeOriginal``
     - datetime
     - Date/time the photo was taken
   * - ``DateTimeDigitized``
     - datetime
     - Date/time the image was digitised
   * - ``DateTime``
     - datetime
     - Date/time the file was last changed (EXIF)
   * - ``Make``
     - text
     - Camera manufacturer
   * - ``Model``
     - text
     - Camera model
   * - ``LensModel``
     - text
     - Lens model
   * - ``ISOSpeedRatings``
     - integer
     - ISO speed
   * - ``FNumber``
     - text
     - Aperture (e.g. ``2.8``)
   * - ``ExposureTime``
     - text
     - Shutter speed (e.g. ``1/125``)
   * - ``FocalLength``
     - text
     - Focal length in mm
   * - ``ImageDescription``
     - text
     - Image description / title
   * - ``Artist``
     - text
     - Photographer / creator (EXIF)
   * - ``Copyright``
     - text
     - Copyright notice
   * - ``ObjectName``
     - text
     - IPTC title / object name
   * - ``Caption``
     - text
     - IPTC caption / description
   * - ``By-line``
     - text
     - IPTC photographer / creator
   * - ``City``
     - text
     - IPTC city
   * - ``Country``
     - text
     - IPTC country
   * - ``DateCreated``
     - date
     - IPTC creation date
   * - ``Keywords``
     - text
     - IPTC keywords (semicolon-separated)
   * - ``Credit``
     - text
     - IPTC credit line
   * - ``Source``
     - text
     - IPTC source

.. _audio-fields:

Audio metadata fields ``{au:…}``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Requires **mutagen**.  Supported formats: mp3, ogg, flac, opus, aac/m4a and
others handled by mutagen.  Field names are case-insensitive.

.. list-table::
   :header-rows: 1
   :widths: 22 16 62

   * - Field
     - Type
     - Description
   * - ``title``
     - text
     - Track title
   * - ``artist``
     - text
     - Track artist
   * - ``albumartist``
     - text
     - Album artist
   * - ``album``
     - text
     - Album name
   * - ``tracknumber``
     - integer
     - Track number (strips ``/total`` if present)
   * - ``discnumber``
     - integer
     - Disc number (strips ``/total`` if present)
   * - ``date``
     - date/text
     - Release date — ``datetime.date`` when the full date is available
       (supports ``strftime`` format); plain text otherwise
   * - ``year``
     - integer
     - Release year (extracted from the ``date`` tag)
   * - ``genre``
     - text
     - Genre
   * - ``comment``
     - text
     - Comment
   * - ``composer``
     - text
     - Composer
   * - ``bpm``
     - integer
     - Beats per minute
   * - ``duration``
     - integer
     - Duration in seconds
   * - ``bitrate``
     - integer
     - Bitrate in kbps

.. _video-fields:

Video metadata fields ``{vi:…}``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Requires **pymediainfo** (and the MediaInfo system library).  Supported
formats: mp4, mkv, avi, mov, webm and others handled by MediaInfo.  Field
names are case-insensitive.

.. list-table::
   :header-rows: 1
   :widths: 22 16 62

   * - Field
     - Type
     - Description
   * - ``width``
     - integer
     - Video width in pixels
   * - ``height``
     - integer
     - Video height in pixels
   * - ``duration``
     - integer
     - Duration in seconds
   * - ``framerate``
     - text
     - Frame rate (e.g. ``29.970``)
   * - ``videocodec``
     - text
     - Video codec name (e.g. ``AVC``, ``HEVC``)
   * - ``audiocodec``
     - text
     - Audio codec name (e.g. ``AAC``, ``AC-3``)
   * - ``audiochannels``
     - integer
     - Number of audio channels
   * - ``bitrate``
     - integer
     - Overall bitrate in kbps
   * - ``title``
     - text
     - Title tag
   * - ``encodeddate``
     - datetime
     - Encoded date/time
   * - ``performer``
     - text
     - Performer / artist
   * - ``copyright``
     - text
     - Copyright notice
   * - ``comment``
     - text
     - Comment
   * - ``description``
     - text
     - Description
   * - ``genre``
     - text
     - Genre

Replacement examples
~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Pattern
     - Description
   * - ``{1}_{num:04}``
     - Capture group 1 followed by a 4-digit zero-padded counter (starts at 1)
   * - ``{1}_{num:04:10}``
     - Same, but counter starts at 10
   * - ``backup_{newnum:03}``
     - Conflict-free 3-digit counter: skips values where ``backup_NNN``
       already exists on disk
   * - ``{date}-{0}``
     - Today's date prepended to the matched text
   * - ``{im:DateTimeOriginal:%Y%m%d_%H%M%S:unknown}``
     - Shooting date/time compact; ``unknown`` if EXIF absent
   * - ``{im:Make::} {im:Model::}``
     - Camera make and model (empty string if absent)
   * - ``{au:artist::unknown}_{au:title::untitled}``
     - Audio artist and title; fallbacks if absent
   * - ``{au:date:%Y%m%d:00000000}_{au:tracknumber:02:00}_{au:title::untitled}``
     - Audio release date, zero-padded track number, title
   * - ``{vi:width::0}x{vi:height::0}_{vi:videocodec::unknown}``
     - Video resolution and codec (e.g. ``1920x1080_AVC``)
   * - ``{re:year}_{re:title}``
     - Named regex groups (regex mode only)
   * - ``{dir}_{mdatetime:%Y%m%d}_{num:03}``
     - Parent folder, file modification date, 3-digit counter

.. _cli-reference:

Headless CLI Reference
----------------------

Headless mode is activated when ``--search`` or ``--saved`` is provided.  No
window is opened; renames are performed and the process exits.

.. code-block:: text

    pbrenamer [--search TEXT | --saved NAME]
              [--replace TEXT]
              [--mode {pattern,regex,plain}]
              [--list {files,dirs,all}]
              [--recurse | --no-recurse]
              [--ext-mode {keep,lower,upper,normalize,modify}]
              [--sidecar-mode | --no-sidecar-mode]
              [--filter GLOB]
              [--select GLOB [--select GLOB ...]]
              [--sep {none,space-underscore,underscore-space,
                      space-dot,dot-space,space-dash,dash-space}]
              [--case {none,upper,lower,capitalize,title}]
              [--accent | --no-accent]
              [--dup | --no-dup]
              [--confirm | --no-confirm]
              [--dry-run | --no-dry-run]
              [-d | -v | -q]
              [--config-dir DIR]
              [DIR]

Rename source (mutually exclusive)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``--search TEXT``
    Search pattern/expression — activates headless mode.

``--saved NAME``
    Load a named save — activates headless mode.  Other options override
    values from the save.

Rename options
~~~~~~~~~~~~~~

``--replace TEXT``
    Replacement string (default: empty string).

``--mode {pattern,regex,plain}``
    Search mode: ``pattern`` (default), ``regex``, or ``plain``.

``--list {files,dirs,all}``
    Entry types to process: ``files`` (default), ``dirs``, or ``all``.

``--recurse`` / ``--no-recurse``
    Recurse into sub-directories (default: ``--no-recurse``).

``--ext-mode {keep,lower,upper,normalize,modify}``
    How to handle the extension during rename (default: ``keep``).  ``lower``
    / ``upper`` case-fold the extension; ``normalize`` maps it through the
    extension normalization table (managed from the GUI, **Edit → Settings…
    → Extension Normalization** tab); ``modify`` includes the extension in
    the search/replace pattern, same as *Modify extension* in the GUI.

``--sidecar-mode`` / ``--no-sidecar-mode``
    Group :ref:`sidecar files <sidecar-files>` with their base file when
    renaming (default: ``--no-sidecar-mode``).  Requires ``--ext-mode keep``,
    ``lower``, or ``upper``; combining it with ``normalize`` or ``modify`` is
    an error.  Category configuration (base extensions, sidecar suffixes) is
    shared with the GUI's **Edit → Sidecar Files…** dialog.

``--filter GLOB``
    Glob pattern to restrict the file listing (e.g. ``'*.jpg'``).

``--select GLOB``
    Restrict the rename to entries matching ``GLOB`` (basename match), as if
    selecting them by clicking in the GUI file list. May be given multiple
    times to accumulate (equivalent of Ctrl+click). With ``--sidecar-mode``,
    selecting a base file also selects its sidecars, and selecting a sidecar
    also selects its base file and every sibling sidecar — the same
    grouping the GUI applies when you click a row, including the same
    ambiguity handling (a sidecar matching more than one base file is still
    flagged and skipped, whether or not it was selected). Omit to act on
    every listed entry (default).

``--sep``
    Separator conversion applied after rename.  Default: ``none``.

``--case {none,upper,lower,capitalize,title}``
    Capitalisation applied after rename.  Default: ``none``.

``--accent`` / ``--no-accent``
    Strip diacritics from result names (default: ``--no-accent``).

``--dup`` / ``--no-dup``
    Collapse consecutive duplicate separators (default: ``--no-dup``).

``--confirm`` / ``--no-confirm``
    Preview changes and ask for confirmation before renaming
    (default: ``--no-confirm``).

``--dry-run`` / ``--no-dry-run``
    Print the equivalent ``mv`` commands to stdout instead of renaming
    anything (default: ``--no-dry-run``).  The output is a valid POSIX shell
    script — quoted with ``shlex.quote``, conflicts reported as ``#``
    comments — that can be piped to ``sh`` to actually perform the rename.
    Takes precedence over ``--confirm``: no interactive prompt is shown.

Logging
~~~~~~~

``-d`` / ``--debug``
    Enable debug output (overrides the saved preference).

``-v`` / ``--verbose``
    Enable verbose output — INFO level (overrides the saved preference).

``-q`` / ``--quiet``
    Suppress informational messages — WARNING level.

Advanced
~~~~~~~~

``--config-dir DIR``
    Override the configuration directory — see :ref:`config-files` for the
    platform defaults.  Intended for testing.

Self-update
~~~~~~~~~~~

``--auto-update``
    Download the latest release matching the running platform and
    architecture from `GitHub Releases
    <https://github.com/ppoilbarbe/PBRenamer/releases>`_ and replace the
    running executable with it, then exit.  Only available when running a
    pre-built (PyInstaller) executable — rejected with an error for a
    source checkout or a ``pip``/PyPI install, neither of which has a
    single running binary to replace.  Restart PBRenamer to use the new
    build; the update does not relaunch it automatically.

Help export
~~~~~~~~~~~

``--help-search``
    Print the search-field help HTML to stdout and exit.

``--help-replace``
    Print the replacement-field help HTML to stdout and exit.

.. _cli-examples:

CLI Examples
~~~~~~~~~~~~

Remove an ``IMG_`` prefix from all JPEG files in the current directory::

    pbrenamer --search "IMG_{X}" --replace "{1}" --filter "*.jpg"

Add the parent folder name and a zero-padded counter to every file,
recursively::

    pbrenamer --search "{X}" --replace "{dir}_{num:04}_{0}" --recurse ~/Pictures

Rename audio files using their tags, with fallbacks::

    pbrenamer --search "{X}" \
              --replace "{au:tracknumber:02:00}_{au:title::untitled}" \
              ~/Music/Album

Load a saved preset and override its separator setting::

    pbrenamer --saved my-photo-preset --sep space-underscore ~/Downloads

Preview changes before applying::

    pbrenamer --search "({L})_({#})" --replace "{2}_{1}" --confirm .

Print the equivalent ``mv`` commands without renaming anything::

    pbrenamer --search "({L})_({#})" --replace "{2}_{1}" --dry-run .

Only rename two specific files (and their sidecars) out of the directory::

    pbrenamer --search "img" --replace "photo" --sidecar-mode \
              --select "img1.jpg" --select "img2.jpg" ~/Photos
