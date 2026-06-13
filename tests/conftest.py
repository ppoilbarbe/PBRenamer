# Force offscreen rendering before Qt is imported — required when DISPLAY is absent
# (CI headless, SSH without X forwarding, local test run without a compositor).
# Must come before any PySide6 import; setdefault lets the caller override it
# (e.g. QT_QPA_PLATFORM=xcb make test to debug with a visible display).
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
