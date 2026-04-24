from pathlib import Path

_HERE = Path(__file__).parent


def path(name: str) -> str:
    """Return the absolute path to a bundled resource file."""
    return str(_HERE / name)
