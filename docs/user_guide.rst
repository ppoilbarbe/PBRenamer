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

.. _optional-dependencies:

Optional dependencies
~~~~~~~~~~~~~~~~~~~~~

The executables include everything.  When PBRenamer is installed with
``pip``, some features need optional extras:

``pip install pbrenamer[meta]``
    Pillow, mutagen and pymediainfo: the ``{im:…}``, ``{au:…}`` and
    ``{vi:…}`` metadata fields.

``pip install pbrenamer[images]``
    pyexiv2, pillow-heif and Pillow: thumbnails of HEIC files, rotation,
    EXIF orientation, and the metadata panel of the image viewer.

Lossless rotation of JPEG files also needs the ``jpegtran`` program (from
libjpeg-turbo) on the ``PATH``.

Launching
---------

GUI mode
~~~~~~~~

Run the binary (or ``python -m pbrenamer`` from a development environment)::

    pbrenamer [DIR]

If *DIR* is omitted the current working directory is used as the starting
folder.  ``--profile NAME`` opens the window on a given :ref:`profile
<profiles>` instead of the last one used.  Qt platform options such as
``--style`` and ``--platform`` are forwarded to Qt and can be appended after
the positional argument.

Headless (no-GUI) mode
~~~~~~~~~~~~~~~~~~~~~~

Pass ``--search``, ``--saved`` or ``--schema`` to activate headless mode.
PBRenamer will list, rename, and exit without opening any window::

    pbrenamer --search PATTERN --replace REPLACEMENT [options] [DIR]
    pbrenamer --saved  NAME    [overrides…]            [DIR]
    pbrenamer --schema FIELDS  --dest ROOT [options]   [DIR]

See :ref:`cli-reference` for the full flag list and :ref:`cli-examples` for
worked examples.

The GUI
-------

The window has a directory tree on the left, the file list on the right, and
below them the rule panel with two tabs, **Pattern** (search and replace,
described in this chapter) and **Schema** (see :ref:`schema-mode`).  The
action bar at the bottom holds the **Undo**, **Preview**, **Clear**,
**Renumber** and **Rename** buttons.  The menus are **File**, **Edit**,
**Profile**, **Images**, **Shortcuts** and **Help**; the name of the current
:ref:`profile <profiles>` is shown in the window title.

Opening a folder
~~~~~~~~~~~~~~~~

Choose **File → Open folder…** (**Ctrl+O**), select a folder in the directory
tree, or drag a directory onto the window to load its contents.  Use the
**Recursive** checkbox to include sub-directories.  The **Filter** field
accepts a glob pattern (e.g. ``*.jpg``) to restrict the listing.

Use the **Show** combo to display *Files only*, *Directories only*, or *Files
and directories*.  The **By date** checkbox sorts the files by modification
date instead of by name, and **Reversed** reverses the order; folders always
stay first.  The list follows changes made on disk by other programs.

The file list
~~~~~~~~~~~~~

The main table shows:

* **Thumbnail** — optional, see :ref:`thumbnails`.
* **Original** — the current file name on disk.
* **Sidecar** — optional, see :ref:`sidecar-column`.
* **Preview** — the name after renaming.  The cell is empty when the current
  pattern does not match the file.  Rows shown in a distinct colour are
  directories.

Click **Preview** to compute the Preview column, or check **Auto-preview** to
recompute it whenever the pattern or an option changes (the delay is set in
:ref:`settings`).  **Clear** empties the column.

Rows with a naming conflict are highlighted in red.  The **Rename** button is
disabled until all conflicts are resolved.

You can select a subset of rows with the usual keyboard/mouse modifiers
(Shift+click, Ctrl+click).  Renaming then applies only to the selected files;
with no selection it applies to every listed file.  **Tab** moves the focus
between the directory tree and the file list.

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

.. _extension-mode:

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
  (``sidecar_config.json`` in the folder of the current profile), independently of
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

The search and replace combos keep a history of the patterns used (most
recent first); the button next to each combo adds the current pattern to it.
**Edit → History…** edits the search, replacement and :ref:`sidecar filter
<sidecar-filter>` histories: add, remove, reorder, sort, or clear.

The **Save** field gives the current settings a name: type a name and click
**Save**, pick it later from the same drop-down to restore it, or click
**Delete** to remove it.  Named saves can also be loaded with ``--saved`` in
headless mode.  Histories and named saves belong to the current
:ref:`profile <profiles>`.

Applying renames
~~~~~~~~~~~~~~~~

Click **Rename** (**F2**) to apply the renames shown in the Preview column.
The button shows how many files will be renamed, e.g. **Rename (12)**, and is
only enabled when a preview is displayed and has no conflict.  The status bar
reports how many files were renamed.

Renaming is atomic: every target is checked first, and if one of them fails
during the operation, the renames already done are rolled back.  When the new
name contains a folder (a :ref:`schema <schema-mode>` or a ``{dest}``
template), missing folders are created, and source folders left empty below
the listed folder are removed.  After a rename the Preview column is cleared.

Undo
~~~~

Click **Undo** to revert the most recent batch.  Each rename batch is
recorded on an undo stack; the button label shows the number of available
batches (e.g. **Undo (3)**) when more than one is queued.  Moves made by drag
and drop, :ref:`rotations and EXIF orientation resets <image-rotation>` are
recorded on the same stack.

Shortcuts
~~~~~~~~~

The **Shortcuts** menu provides one-click navigation to common directories.

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
    Choose **Shortcuts → Edit shortcuts…** to open the *Edit Shortcuts*
    dialog, where shortcuts can be reordered with *Move up* / *Move down* or
    removed.

File information
~~~~~~~~~~~~~~~~

Choose **File → Information** (**Ctrl+I**, also in the **Images** menu) to
display a non-modal window listing the actual values of every replacement
field for the selected file.  Double-click a field to insert it into the
replacement pattern.

The window has three groups:

* **Universal fields** — ``{date}``, ``{datetime}``, ``{mdatetime}``,
  ``{cdatetime}``, ``{dir}``; values are read from the file system.
* **Batch fields** — ``{0}``, ``{1}``/``{2}``…, ``{num}``, ``{newnum}``,
  ``{re:name}``; labelled *Computed* (they depend on the active pattern).
* **Metadata fields** — ``{im:…}``, ``{au:…}``, or ``{vi:…}`` depending on
  the file type; values are read from the file's embedded metadata.

The window updates live whenever the selection changes.

Help
~~~~

The **Help** menu opens this **User guide** in the web browser, in the
language of the interface, and the **Keyboard and mouse shortcuts…** window
(**F1**), which lists every shortcut of the main window and of the image
viewer.

.. _profiles:

Profiles
--------

A **profile** is a named set of settings for one way of working: for
instance a ``default`` profile that renames documents in place with the
Pattern tab, and a ``photos`` profile that sorts pictures into a folder tree
with the Schema tab, thumbnails and the sidecar column.  Switching profiles
switches all of this at once.

A profile holds:

* the tab shown at start-up (Pattern or Schema) and the Schema tab settings
  (number and titles of the fields, destination, video marker and its
  position, fill gaps);
* the :ref:`sidecar <sidecar-files>` categories and suffixes;
* the display options (thumbnails and their size, sidecar column, sidecar
  filter, sort by date, history length) and the image options (viewer zoom,
  EXIF orientation, metadata panel, deletion);
* the histories (search, replacement, schema fields, sidecar filter) and the
  named saves;
* the last folder and the state of the option bar.

Managing profiles
~~~~~~~~~~~~~~~~~

The **Profile** menu lists the profiles: choose one to switch to it.  It also
offers:

**New profile…** (**Ctrl+N**)
    Create a profile with the default settings and switch to it.

**Duplicate profile…** (**Ctrl+Shift+D**)
    Copy the current profile under a new name and switch to the copy.

**Rename profile…**
    Give the current profile a new name.

**Delete profile…**
    Permanently delete a profile and all its settings.

**Profile configuration…** (**Ctrl+,**)
    Configure the current profile (see below).

Profile names may contain letters, digits, ``-`` and ``_``.  A profile whose
name starts with ``-`` is **hidden**: it is not listed in the menu and is
never reopened at start-up, but it can be used with ``--profile``.  At least
one visible profile always exists: the last one can be neither deleted nor
hidden, and ``default`` is created again if none is left.  Apart from that,
``default`` is a profile like any other.

PBRenamer reopens the last profile used.  ``--profile NAME`` selects another
one, in the GUI as in headless mode.

Profile configuration
~~~~~~~~~~~~~~~~~~~~~

**Profile → Profile configuration…** has three tabs.

**Schema**
    Number of fields of the schema, the title of each field (shown above it
    in the Schema tab), and the video marker (see :ref:`schema-mode`).

**Display**
    Thumbnails (shown or not, maximum width and height), the sidecar column
    and the sidecar content filter (shown or not), the extension of the
    sidecar created by a double-click, whether empty sidecar files are
    deleted when a folder is loaded, and the maximum number of entries kept
    in each history.

**Images**
    Image viewer: zoom step, maximum zoom, side of the metadata panel, and
    whether images are shown turned as their EXIF orientation says (also
    applies to the thumbnails).  Deletion: move deleted files to the trash
    instead of removing them permanently, ask for a confirmation, and the
    number of files above which the confirmation only gives their count.

.. _schema-mode:

Schema Mode
-----------

The **Schema** tab sorts files into a folder tree built from a few fields,
for instance a place, a year and a subject.  With the fields ``Paris``,
``2024``, *(empty)*, ``Street``, *(empty)*, ``###`` and the destination
``~/Photos``, the file ``IMG_0012.jpg`` becomes::

    ~/Photos/Paris/2024/Street/Paris_2024_Street_013.jpg

The rules are:

* every non-empty field, in order, is both a folder level under the
  destination and a part of the name, joined with ``_``;
* a field made only of ``#`` is the **counter**, padded to the number of
  ``#``; at most one field may be a counter, and it is always placed at the
  end of the name;
* empty fields are skipped;
* a field may not contain ``_``, ``.``, ``/`` or ``\``;
* the extension is kept, in lower case.

The counter continues after the highest number already used in the target
folder by files of the same name, so that a new batch never overwrites
earlier ones.  With **Fill gaps** checked, it takes the smallest free numbers
first.  Images and videos are numbered separately.

Each field keeps a history of its values (most recent first) in its
drop-down list.  The history is updated when a rename or a renumbering
succeeds.

Destination
~~~~~~~~~~~

The **Destination** field is the root of the folder tree.  It must be an
absolute path; **Browse…** chooses it.  Missing folders are created when
renaming, and source folders left empty are removed.

Video marker
~~~~~~~~~~~~

A **video marker** (set in **Profile configuration…**, *Schema* tab) is a text
added to the name of video files only, so that they are easy to tell apart:
with the marker ``vid``, a video becomes ``Paris_2024_Street_vid_001.mp4``.
The small radio buttons between the fields choose where the marker goes,
from before the first field to after the last one.

Sidecars in schema mode
~~~~~~~~~~~~~~~~~~~~~~~

Sidecar mode is always on in the Schema tab: each sidecar follows its base
file and takes its new name.  A sidecar without a base file (an *orphan*) is
neither renamed nor renumbered; its preview reads *orphan sidecar, not
renamed*.  **Images → Orphan sidecars…** lists them (see
:ref:`image-tools`).

Renumber
~~~~~~~~

When the schema has a counter, the **Renumber** button renumbers the
selected files (every listed file if none is selected) from 1, in place,
without moving them.  Like **Rename**, it is only enabled when a preview is
displayed.  Files are renamed through temporary names, so swapping numbers is
safe.

Template
~~~~~~~~

**Images → Template** fills the schema from the name of the selected file
and up to three of its parent folders: the parts of the name found in a
field's history go to that field, and a trailing number goes to the counter
field.  A dialog shows the proposed fields before they are filled in.

In headless mode, the same schema is given with ``--schema``, for instance
``--schema 'Paris,2024,,Street,,###' --dest ~/Photos`` (see
:ref:`cli-reference`).

.. _image-tools:

Image Tools
-----------

PBRenamer includes tools to look at and tidy up photos and videos before
sorting them.  Some depend on optional libraries (see
:ref:`optional-dependencies`); an action that cannot work is disabled.

.. _thumbnails:

Thumbnails
~~~~~~~~~~

The **Thumbnails** checkbox of the option bar adds a thumbnail column to the
file list.  Thumbnails are loaded in the background, visible rows first.
Their maximum size is set in **Profile configuration…**, *Display* tab.
Double-clicking a thumbnail opens the image in the viewer; double-clicking a
name opens the file with its default application.

.. _sidecar-column:

Sidecar column
~~~~~~~~~~~~~~

When enabled in **Profile configuration…**, the **Sidecar** column shows
whether a file has sidecars: ``●`` followed by their suffixes, or ``○`` for
an image, video or audio file without any.  Double-clicking it opens the sidecar (a menu lets you choose when
there are several).  On a file without a sidecar, it creates an empty one
with the extension set in the profile (for instance ``xmp``) and opens it.

.. _sidecar-filter:

Sidecar filter
~~~~~~~~~~~~~~

When enabled in **Profile configuration…**, a **Sidecar filter…** field
appears in the action bar.  Type a regular expression: only the files having
a sidecar whose content matches it remain listed (case-insensitive, across
lines), together with their sidecars.  The list is filtered as you type;
**Enter** also adds the expression to the filter's own history.  Empty the
field to list every file again.

The Images menu
~~~~~~~~~~~~~~~

The **Images** menu is also the context menu of the file list.  Its actions
apply to the selected files:

**Open** (**Ctrl+Enter**)
    Open the files with their default application.

**Open with…** (**Ctrl+Shift+O**)
    Choose the application that opens the file.

**Open sidecar**
    Open one of the sidecars of the file.

**View** (**Enter**)
    Show the selected images and videos in the image viewer.

**Template**
    Fill the schema from the file name (see :ref:`schema-mode`).

**Delete** (**Del**)
    Delete the files and their sidecars, to the trash or permanently,
    after a confirmation, as set in the profile.

**Orphan sidecars…**
    List the sidecar files of the folder that have no base file, then
    delete the selected ones or all of them.

**Rotate 90° left / 180° / 90° right** (**F6** / **F7** / **F8**)
    Rotate the images without loss.

**Apply EXIF orientation** (**F9**)
    Rotate the pixels as the EXIF orientation tag says, then reset the tag.

**Force EXIF orientation to 0°** (**F10**)
    Set the EXIF orientation tag to normal without rotating the pixels.

**Information** (**Ctrl+I**) and **Refresh** (**F5**)
    Show the file information window; read the folder again.

.. _image-rotation:

Rotation and EXIF orientation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

JPEG files are rotated with ``jpegtran`` (from libjpeg-turbo), which turns
them without recompressing; other formats are saved by Pillow, without loss
where the format allows it.  Rotations and EXIF resets can be undone with
**Undo**.

The image viewer
~~~~~~~~~~~~~~~~

**Images → View** opens the image viewer on the selected images and videos
(a video is shown as a placeholder).  The viewer follows the selection of the
file list.  It offers:

* zoom modes in the toolbar: fit window (**0** or **X**), actual size
  (**1** or **Z**), fit width (**W**), fit height (**H**), and zoom in and
  out (**+** and **−**); drag to pan, double-click to centre on a point,
  **Ctrl+click** and **Ctrl+right-click** to zoom on a point;
* navigation with the arrow keys: within the selection when several files
  are selected, otherwise to the previous or next file of the list; a
  toolbar button switches between linear navigation (stop at the ends) and
  circular navigation (wrap around);
* a strip of thumbnails of the selection, when several files are selected:
  click one to show it;
* a metadata panel (**I**) showing the EXIF, IPTC and XMP data of the image;
  double-click a field to insert it into the replacement pattern;
* the image actions: open, open with, delete, rotations and EXIF orientation,
  with the same shortcuts as in the main window; **Esc** closes the viewer.

The full list is in **Help → Keyboard and mouse shortcuts…** (**F1**).

.. _settings:

Settings
--------

**Edit → Settings…** holds the options shared by every profile.

*General* tab:

**Language**
    Select the UI language.  Several languages are bundled; the change takes
    effect at the next start.

**Log level**
    Controls diagnostic output written to the console.  Choices: ``DEBUG``,
    ``INFO`` (default), ``WARNING``, ``ERROR``, ``CRITICAL``.  Can be
    overridden at launch with ``--debug``, ``--verbose``, or ``--quiet``.

**Restore last opened directory** *(Behaviour group)*
    When enabled, the app reopens the directory that was active in the
    previous session of the profile.  A directory passed on the command line
    always takes priority.  Default: disabled (current working directory is
    used).

**Restore toolbar state** *(Behaviour group)*
    When enabled, the options of the option bar and of the Pattern tab are
    restored as they were left.

**Auto-preview delay** *(Behaviour group)*
    Delay, in milliseconds, before the preview is recomputed when
    **Auto-preview** is checked.

*Extension Normalization* tab: the table used by the *Normalize extension*
mode (see :ref:`extension-mode`).

The settings of a profile are in **Profile → Profile configuration…** (see
:ref:`profiles`).

.. _config-files:

Configuration Files
--------------------

Everything the Settings dialog and other panels persist — preferences,
profiles, presets, and per-feature configuration — is stored as plain-text
files (Qt INI and JSON) under a single per-user configuration directory.  No
system directories or registry keys are touched.

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
configurations side by side.

Files
~~~~~

Shared by every profile:

``pbrenamer.conf``
    Qt INI settings: log level, language override, behaviour options,
    preview delay, last profile, image viewer options.

``shortcuts.json``
    User-defined directory shortcuts (**Shortcuts** menu).

``extension_normalization.json``
    Per-extension normalization table used by extension mode ``normalize``.

``open_with.json``
    Applications recently chosen with **Open with…**.

``window_state.json``
    Main window geometry, position, and splitter ratios.

One folder per profile, ``profiles/NAME/``:

``profile.json``
    Tab shown at start-up, Schema tab settings, display and image options,
    last directory, option bar state.

``history.json``
    Histories of the schema fields and of the sidecar filter.

``sidecar_config.json``
    :ref:`Sidecar file <sidecar-files>` category configuration (base
    extensions / sidecar suffixes per category), managed from
    **Edit → Sidecar Files…**.

``patterns/search.json`` / ``patterns/replace.json``
    Most-recently-used search and replacement patterns.

``patterns/saves.json``
    Named saves, also loadable headlessly with ``--saved NAME``.

None of these files are required to exist — deleting any one of them simply
resets that piece of state to its default the next time PBRenamer starts.
Deleting the ``profiles`` folder recreates the profiles from the 1.x
configuration and PBPicat's catalogues, as on the first start of version 2.

.. _pbpicat-migration:

Migrating from PBPicat
----------------------

PBRenamer 2 includes every function of PBPicat, which it replaces: the
schema, the destination tree, renumbering, the video marker, the image
viewer, rotations, the sidecar tools and the catalogues.

Automatic import
~~~~~~~~~~~~~~~~

On its first start, PBRenamer 2 reads PBPicat's configuration (without
modifying it) and turns each **catalogue** into a **profile** of the same
name, or ``pbpicat-NAME`` if a profile already has that name.  The imported
profile opens on the Schema tab with thumbnails, the sidecar column and the
sidecar filter, and keeps:

* the number and titles of the schema fields, the destination, the video
  marker and its position, fill gaps;
* the image and video extensions and the sidecar extensions;
* the display, viewer and deletion options;
* the field histories and the last folder.

The **Open with** application lists and the viewer's navigation and
metadata panel options are imported too.  Window sizes, the language and
PBPicat's defaults for new catalogues are not.  The settings of PBRenamer
1.x go to the ``default`` profile.

Where things are now
~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - PBPicat
     - PBRenamer 2
   * - Catalogue, catalogue menu
     - Profile, **Profile** menu
   * - Catalogue settings, program settings
     - **Profile → Profile configuration…**, **Edit → Settings…**
   * - Schema fields, destination, video marker buttons
     - **Schema** tab
   * - *Rename All* / *Rename selection*
     - **Rename** (the selection, or every listed file when none is
       selected), after a preview
   * - *Renumber from 1*
     - **Renumber** (Schema tab with a counter field)
   * - Tooltip preview of the new name
     - **Preview** column
   * - Rotations, EXIF, open, open with, delete, template, orphan sidecars
     - **Images** menu and context menu of the file list
   * - Image viewer
     - **Images → View** (**Enter**)
   * - Catalogue on the command line
     - ``pbrenamer --profile NAME``

What changes
~~~~~~~~~~~~

* There is no ``pbpicat`` command: start ``pbrenamer``, or
  ``pbrenamer --profile NAME`` for a given profile.
* **Rename** and **Renumber** apply what the Preview column shows: compute
  the preview first (or check **Auto-preview**).
* A sidecar without a base file is not renamed in schema mode.
* Every rename can be undone with **Undo**, like rotations and EXIF resets.
* Schemas can also be applied without the GUI, with ``--schema``.

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
    {name:^fmt}              centre
    {name:+}                 upper case  (also - lower, ! capitalise,
                             * Title Case, = unchanged)
    {{                       literal '{' character

The case character comes first, before the alignment, e.g. ``{1:+<10}``.

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
     - Counter that continues after the highest number already used on disk
       by names of the same form in the target folder (``backup_007`` →
       next is ``backup_008``), so that numbering never conflicts.  With
       ``--fill-gaps`` it takes the smallest free numbers first; with
       ``--renumber`` it ignores the disk and starts from its start value
   * - ``{dest}``
     - all modes
     - Destination root (``--dest`` in headless mode).  Only valid at the
       very start of the template, which may then contain ``/`` to place the
       file in sub-folders, created as needed: ``{dest}/{im:Make::}/{0}``
   * - ``{if:category:text}``
     - all modes
     - *text* when the file belongs to *category* (``image``, ``video``,
       ``audio`` or ``other``), nothing otherwise: ``{0}{if:video:_vid}``
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

Read with **pyexiv2**, or **Pillow** when pyexiv2 is not available (see
:ref:`optional-dependencies`).  Field names are case-insensitive.  A *default* is
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
     - Conflict-free 3-digit counter: continues after the highest
       ``backup_NNN`` already on disk
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

Headless mode is activated when ``--search``, ``--saved`` or ``--schema`` is
provided.  No window is opened; renames are performed and the process exits.
Settings that are not given on the command line come from the profile chosen
with ``--profile``, or from the last profile used in the GUI.

Renaming is atomic: if any target is in conflict, nothing is renamed and the
command exits with an error listing the conflicts.

.. code-block:: text

    pbrenamer [--search TEXT | --saved NAME | --schema LIST]
              [--dest DIR]
              [--fill-gaps | --no-fill-gaps]
              [--renumber]
              [--video-marker TEXT] [--video-marker-pos N]
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
              [--profile NAME]
              [--config-dir DIR]
              [DIR]

Rename source (mutually exclusive)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``--search TEXT``
    Search pattern/expression — activates headless mode.

``--saved NAME``
    Load a named save — activates headless mode.  Other options override
    values from the save.

``--schema LIST``
    Rename :ref:`schema <schema-mode>`: comma-separated fields, e.g.
    ``'Trip,,Paris,###'`` — activates headless mode.  Non-empty fields form
    both the folder tree under ``--dest`` and the name (joined with ``_``);
    a field of ``#`` only is the counter, padded to the number of ``#``;
    empty fields are skipped.  Sidecar mode is always on.

Schema options
~~~~~~~~~~~~~~

``--dest DIR``
    Destination root.  With ``--schema``, defaults to the profile's
    destination and is required if it has none (except with
    ``--renumber``).  Also the value of the ``{dest}`` field in
    ``--replace``.

``--fill-gaps`` / ``--no-fill-gaps``
    ``{newnum}`` takes the smallest free number instead of continuing after
    the highest one (default: the profile's setting with ``--schema``,
    ``--no-fill-gaps`` otherwise).

``--renumber``
    ``{newnum}`` runs from its start value, ignoring the numbers already
    used on disk; with ``--schema``, renumber the files in place.

``--video-marker TEXT``
    With ``--schema``: text added to the name of video files (default: the
    profile's marker).

``--video-marker-pos N``
    With ``--schema``: position of the video marker between the fields
    (0 = before the first field; default: the profile's position).

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

``--profile NAME``
    Use the :ref:`profile <profiles>` *NAME* (settings, presets, sidecar
    configuration, schema defaults) instead of the last one used in the
    GUI.  In GUI mode, open the window on that profile.

``--config-dir DIR``
    Override the configuration directory — see :ref:`config-files` for the
    platform defaults.  Intended for testing.

``--install-desktop-entry`` / ``--uninstall-desktop-entry``
    Linux only: install (or remove) a desktop menu entry and icon for the
    current user, then exit.  Useful after a ``pip`` install, which has no
    post-install hook to do it.

Self-update
~~~~~~~~~~~

``--auto-update``
    Download the latest release matching the running platform and
    architecture from `GitHub Releases
    <https://github.com/ppoilbarbe/PBRenamer/releases>`_ and replace the
    running executable with it, then exit.  This option is only offered
    when running a pre-built (PyInstaller) executable; a source checkout
    or a ``pip``/PyPI install has no single running binary to replace, so
    the option is absent from ``--help`` and rejected as an unknown
    argument there.  Restart PBRenamer to use the new build; the update
    does not relaunch it automatically.

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

Sort the pictures of a folder into ``~/Photos/Paris/2024/Street/``, with a
3-digit counter, using the settings of the ``photos`` profile::

    pbrenamer --profile photos --schema "Paris,2024,,Street,,###" \
              --dest ~/Photos ~/Downloads/card

Renumber the files of a folder from 1, in place::

    pbrenamer --schema "Paris,2024,Street,###" --renumber \
              ~/Photos/Paris/2024/Street

Move files into one folder per camera model, with a counter, sidecars
following their picture::

    pbrenamer --search "{X}" --replace "{dest}/{im:Model::unknown}/{newnum:04}" \
              --sidecar-mode --dest ~/Sorted ~/Downloads/card
