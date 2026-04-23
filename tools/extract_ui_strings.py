#!/usr/bin/env python3
"""Extract translatable strings from pyside6-uic generated Python files.

Parses each file's AST and writes _("…") stubs that xgettext can process.
This is necessary because xgettext does not support dotted keyword names
such as ``QCoreApplication.translate``.

Usage::

    python tools/extract_ui_strings.py src/pbrenamer/ui/main_window_ui.py \
        >> src/pbrenamer/locale/pbrenamer.pot
"""

import ast
import sys
from pathlib import Path


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def extract(path: str) -> None:
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match QCoreApplication.translate(context, source_text, ...)
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "translate"
            and isinstance(func.value, ast.Name)
            and func.value.id == "QCoreApplication"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            continue
        text = node.args[1].value
        if text.strip():
            print(f'_("{_escape(text)}")')


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        extract(arg)
