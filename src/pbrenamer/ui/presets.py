"""Pattern presets — file-based persistence in the platform config directory."""

from pathlib import Path

from pbrenamer.platform import AppDirs

_CONFIG_DIR = AppDirs("pbrenamer").config_home / "patterns"

_DEFAULTS: dict[str, list[str]] = {
    "search": ["{X}"],
    "replace": ["{1}"],
}


class PatternPresets:
    def __init__(self, config_dir: Path = _CONFIG_DIR) -> None:
        self._dir = config_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._dir / key

    def get(self, key: str) -> list[str]:
        p = self._path(key)
        if not p.exists():
            defaults = _DEFAULTS.get(key, [])
            p.write_text("\n".join(defaults) + "\n", encoding="utf-8")
            return list(defaults)
        lines = p.read_text(encoding="utf-8").splitlines()
        return [ln for ln in (ln.strip() for ln in lines) if ln]

    def add(self, key: str, pattern: str) -> None:
        if pattern not in self.get(key):
            with self._path(key).open("a", encoding="utf-8") as fh:
                fh.write(pattern + "\n")

    def save(self, key: str, patterns: list[str]) -> None:
        self._path(key).write_text("\n".join(patterns) + "\n", encoding="utf-8")
