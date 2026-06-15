"""argparse helpers for passing Qt command-line options."""

import argparse


class _QtArgAction(argparse.Action):
    """Accumulate Qt flags into ``args.qt_args`` as single-dash tokens.

    ``--style fusion`` appends ``["-style", "fusion"]``;
    ``--reverse`` appends ``["-reverse"]``.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        current = list(getattr(namespace, self.dest) or [])
        current.append("-" + option_string.lstrip("-"))
        if isinstance(values, str):
            current.append(values)
        setattr(namespace, self.dest, current)


def add_qt_arguments(parser: argparse.ArgumentParser) -> None:
    """Add Qt command-line options to *parser*, collected in ``args.qt_args``.

    Each ``--option [value]`` is stored as ``["-option"]`` or
    ``["-option", "value"]`` and appended to ``args.qt_args``, ready to be
    passed directly to ``QApplication``.

    Qt options are hidden from the ``usage:`` line to reduce noise; they still
    appear in the "Qt options" section of the full ``--help`` output.
    """
    parser.set_defaults(qt_args=[])

    base_formatter = parser.formatter_class

    class _Formatter(base_formatter):
        def add_usage(self, usage, actions, groups, prefix=None):
            super().add_usage(
                usage,
                [a for a in actions if not isinstance(a, _QtArgAction)],
                groups,
                prefix,
            )

    parser.formatter_class = _Formatter
    group = parser.add_argument_group(
        "Qt options",
        "Passed through to the Qt framework (see Qt documentation for details).",
    )
    for flag, metavar, help_text in [
        ("style", "STYLE", "Qt widget style (e.g. fusion, windows)"),
        ("stylesheet", "FILE", "Qt stylesheet"),
        ("platform", "PLUGIN", "Qt platform plugin"),
        ("platformpluginpath", "PATH", "Qt platform plugin search path"),
        ("platformtheme", "THEME", "Qt platform theme"),
        ("plugin", "PLUGIN", "Qt plugin to load"),
        ("qmljsdebugger", "VALUE", "Qt QML/JS debugger options"),
        ("display", "DISPLAY", "X11 display name"),
        ("geometry", "GEOMETRY", "X11 window geometry"),
        ("fn", "FONT", "X11 font name (short form)"),
        ("font", "FONT", "X11 font name"),
        ("bg", "COLOR", "X11 background colour"),
        ("background", "COLOR", "X11 background colour"),
        ("fg", "COLOR", "X11 foreground colour"),
        ("foreground", "COLOR", "X11 foreground colour"),
        ("btn", "COLOR", "X11 button colour"),
        ("button", "COLOR", "X11 button colour"),
        ("name", "NAME", "X11 application name"),
        ("title", "TITLE", "X11 window title"),
        ("visual", "VISUAL", "X11 visual type"),
        ("ncols", "N", "X11 colour cube size"),
        ("im", "INPUTMETHOD", "X11 input method"),
        ("inputstyle", "STYLE", "X11 input style"),
    ]:
        group.add_argument(
            f"--{flag}",
            dest="qt_args",
            metavar=metavar,
            action=_QtArgAction,
            help=help_text,
        )
    for flag, help_text in [
        ("widgetcount", "Print widget count on exit"),
        ("reverse", "Right-to-left layout direction"),
        ("cmap", "Use private colour map on 8-bit display"),
    ]:
        group.add_argument(
            f"--{flag}",
            dest="qt_args",
            nargs=0,
            action=_QtArgAction,
            help=help_text,
        )
