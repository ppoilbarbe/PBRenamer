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

Keep extension
^^^^^^^^^^^^^^

When checked (default), the search/replace pattern is applied to the file
*stem* only; the extension is preserved unchanged.  Uncheck to apply the
pattern to the full file name including the extension.

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
Only one level of undo is available.

Settings
--------

Open **Edit → Settings** to configure:

**Language**
    Select the UI language.  English and French are bundled.  The selection
    takes effect immediately and is persisted.

**Log level**
    Controls diagnostic output written to the console.  Choices: ``DEBUG``,
    ``INFO`` (default), ``WARNING``, ``ERROR``, ``CRITICAL``.  Can be
    overridden at launch with ``--debug``, ``--verbose``, or ``--quiet``.

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
full name if *Keep extension* is unchecked).

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

+------------------------------------+------------+------------------+
| Search                             | Replace    | Result           |
+====================================+============+==================+
| ``(\\d{4})-(\\d{2})-(\\d{2})``     | ``{3}/{2}/{1}`` | 2024-06-15  |
|                                    |            | → 15/06/2024     |
+------------------------------------+------------+------------------+

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
              [--keep-ext | --no-keep-ext]
              [--filter GLOB]
              [--sep {none,space-underscore,underscore-space,
                      space-dot,dot-space,space-dash,dash-space}]
              [--case {none,upper,lower,capitalize,title}]
              [--accent | --no-accent]
              [--dup | --no-dup]
              [--confirm | --no-confirm]
              [-d | -v | -q]
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

``--keep-ext`` / ``--no-keep-ext``
    Preserve the file extension during rename (default: ``--keep-ext``).

``--filter GLOB``
    Glob pattern to restrict the file listing (e.g. ``'*.jpg'``).

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

Logging
~~~~~~~

``-d`` / ``--debug``
    Enable debug output (overrides the saved preference).

``-v`` / ``--verbose``
    Enable verbose output — INFO level (overrides the saved preference).

``-q`` / ``--quiet``
    Suppress informational messages — WARNING level.

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
