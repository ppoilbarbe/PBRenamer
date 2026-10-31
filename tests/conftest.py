# Force offscreen rendering before Qt is imported — required when DISPLAY is absent
# (CI headless, SSH without X forwarding, local test run without a compositor).
# Must come before any PySide6 import; setdefault lets the caller override it
# (e.g. QT_QPA_PLATFORM=xcb make test to debug with a visible display).
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def config_dir(tmp_path_factory):
    """Return a per-test config directory and redirect all settings I/O to it.

    Uses tmp_path_factory so the directory is independent from the test's own
    tmp_path, preventing directory-listing tests from seeing a spurious entry.
    Tests that need to inspect or write config files directly can request this
    fixture to obtain the path.
    """
    import pbrenamer.settings as _settings

    cfg = tmp_path_factory.mktemp("pbrcfg", numbered=True)
    _settings.configure(cfg)
    yield cfg
    _settings.configure()


@pytest.fixture(autouse=True)
def _isolated_config(config_dir):
    """Ensure every test runs with an isolated config directory."""


@pytest.fixture
def sample_png(tmp_path):
    """Return the path to a minimal valid 100x80 PNG image."""
    from PIL import Image

    path = tmp_path / "test.png"
    Image.new("RGB", (100, 80), color=(128, 64, 32)).save(str(path))
    return path


@pytest.fixture
def media_dir(tmp_path):
    """Return a directory of minimal valid PNG images and .xmp sidecars,
    one of them orphan (no base image)."""
    from PIL import Image

    d = tmp_path / "media"
    d.mkdir()
    for name in ["img_001.png", "img_002.png"]:
        Image.new("RGB", (1, 1), "red").save(str(d / name))
    (d / "img_001.xmp").write_text("<metadata/>")
    (d / "orphan.xmp").write_text("<orphan/>")
    return d
