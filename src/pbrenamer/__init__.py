"""PBRenamer — A graphical batch file renaming utility."""

import builtins

__version__ = "0.1.0"
__author__ = "Marcel Spock"
__email__ = "mrspock@cardolan.net"
__license__ = "GPLv3"

# No-op fallback so _() is always defined even when i18n.setup() is not called
# (e.g. during unit tests or direct imports without launching the app).
if not hasattr(builtins, "_"):
    builtins._ = lambda s: s  # type: ignore[assignment]
