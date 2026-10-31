"""Performance of the file list on a directory of 5,000 photos.

Run with ``make perf`` (excluded from ``make test``).  The photos are
generated once in the pytest cache.  Each measure is printed, then checked
against a budget derived from PBPicat v1.21.0 on the same data (see
``merge_renamers.md``, task 5.6).
"""

from __future__ import annotations

import shutil
import time

import pytest
from PIL import Image

from pbrenamer import profiles
from pbrenamer.ui.main_window import MainWindow

pytestmark = pytest.mark.perf

N_PHOTOS = 5000
N_SIDECARS = 1000
_SCHEMA_TAB = 1

# Budgets in seconds: about three times PBPicat v1.21.0 on the same data
# (reload 0.35 s, first thumbnails 0.51 s, 0.009 s per page, filter 0.07 s);
# PBPicat has no preview column, the preview budgets are absolute.
BUDGET = {
    "reload": 1.0,
    "first_thumbnails": 1.5,
    "scroll_page": 0.03,
    "preview_pattern": 3.0,
    "preview_schema": 3.0,
    "sidecar_filter": 0.3,
}


@pytest.fixture(scope="session")
def photo_dir(request):
    """5,000 1600×1200 JPEG photos, one in five with an .xmp sidecar."""
    root = request.config.cache.mkdir("perf-photos")
    if len(list(root.glob("*.jpg"))) == N_PHOTOS:
        return root
    shutil.rmtree(root)
    root.mkdir()
    model = root / "model.jpg"
    img = Image.radial_gradient("L").resize((1600, 1200)).convert("RGB")
    img.save(model, quality=85)
    data = model.read_bytes()
    model.unlink()
    for i in range(N_PHOTOS):
        (root / f"IMG_{i:05}.jpg").write_bytes(data)
        if i % (N_PHOTOS // N_SIDECARS) == 0:
            place = "Paris" if i % 2 else "Lyon"
            (root / f"IMG_{i:05}.xmp").write_text(f"<dc:subject>{place}</dc:subject>")
    return root


@pytest.fixture
def window(qtbot):
    data = profiles.load()
    data["display"].update(thumbnails=True, sidecar_column=True, sidecar_filter=True)
    profiles.save(data)
    w = MainWindow()
    w._actions.set_auto_preview(False)
    qtbot.addWidget(w)
    w.resize(1100, 720)
    w.show()
    qtbot.waitExposed(w)
    qtbot.wait(50)  # let the startup navigation happen first
    return w


def _report(name: str, seconds: float) -> None:
    budget = BUDGET[name]
    print(f"\n  {name:<18} {seconds:7.3f} s  (budget {budget:g} s)")
    assert seconds <= budget


def _visible_loaded(window) -> bool:
    loader = window._files._thumbs
    first, last = loader.visible_rows()
    return all(
        loader.is_loaded(p)
        for p in loader._paths[first : last + 1]
        if p.endswith(".jpg")
    )


def test_reload_and_scroll(window, photo_dir, qtbot):
    start = time.perf_counter()
    window._files.set_directory(str(photo_dir))
    _report("reload", time.perf_counter() - start)
    assert window._ui.tblFiles.topLevelItemCount() == N_PHOTOS + N_SIDECARS

    qtbot.waitUntil(lambda: _visible_loaded(window), timeout=30000)
    _report("first_thumbnails", time.perf_counter() - start)

    bar = window._ui.tblFiles.verticalScrollBar()
    loader = window._files._thumbs
    pages = 0
    start = time.perf_counter()
    while bar.value() < bar.maximum():
        bar.setValue(bar.value() + bar.pageStep())
        loader.load_visible()
        qtbot.waitUntil(lambda: _visible_loaded(window), timeout=30000)
        pages += 1
    total = time.perf_counter() - start
    print(f"\n  scroll             {total:7.3f} s for {pages} pages")
    _report("scroll_page", total / max(pages, 1))


def test_previews(window, photo_dir):
    window._files.set_directory(str(photo_dir))
    window._ui.cmbPatternSearch.setEditText("IMG_{#}")
    window._ui.cmbPatternDest.setEditText("photo_{newnum:05}")
    start = time.perf_counter()
    window._on_preview()
    _report("preview_pattern", time.perf_counter() - start)
    assert window._ui.btnRename.isEnabled()

    window._ui.tabRules.setCurrentIndex(_SCHEMA_TAB)
    window._schema.edtDest.setText(str(photo_dir.parent / "perf-dest"))
    window._schema.set_fields(["Paris", "2024", "", "", "", "###"])
    start = time.perf_counter()
    window._on_preview()
    _report("preview_schema", time.perf_counter() - start)
    assert window._ui.btnRename.isEnabled()


def test_sidecar_filter(window, photo_dir):
    window._files.set_directory(str(photo_dir))
    window._ui.cmbSidecarFilter.setEditText("paris")
    start = time.perf_counter()
    window._files._apply_content_filter()
    _report("sidecar_filter", time.perf_counter() - start)
    assert window._ui.tblFiles.topLevelItemCount() == N_SIDECARS
