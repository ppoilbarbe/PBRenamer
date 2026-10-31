"""Tests for SchemaRulePanel, instantiated on its own.

Ports the cases of PBPicat's ``tests/test_ui_schema_frame.py`` (validator,
field histories, video marker position, rebuild) and adds the preview and
renumbering plans computed by the panel.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QFileDialog

from pbrenamer import profiles
from pbrenamer.ui.file_list import PreviewEntry
from pbrenamer.ui.rule_panel_schema import (
    ForbiddenCharValidator,
    SchemaRulePanel,
    field_title,
)


@pytest.fixture
def panel(qtbot):
    widget = SchemaRulePanel()
    qtbot.addWidget(widget)
    return widget


def _set(panel, *values):
    panel.set_fields(list(values) + [""] * (len(panel.fields()) - len(values)))


# ---------------------------------------------------------------------------
# Validator and titles
# ---------------------------------------------------------------------------


class TestValidator:
    @pytest.mark.parametrize("text", ["a_b", "a.b", "a/b", "a\\b"])
    def test_forbidden(self, text):
        v = ForbiddenCharValidator("_./\\")
        assert v.validate(text, 0)[0] == QValidator.State.Invalid

    @pytest.mark.parametrize("text", ["", "Paris", "###", "Été 2024"])
    def test_accepted(self, text):
        v = ForbiddenCharValidator("_./\\")
        assert v.validate(text, 0)[0] == QValidator.State.Acceptable

    def test_field_combo_rejects_forbidden_chars(self, panel, qtbot):
        line = panel._fields[0].combo.lineEdit()
        qtbot.keyClicks(line, "a_b.c")
        assert line.text() == "abc"


class TestTitles:
    def test_field_title(self):
        assert field_title(["Place", ""], 0) == "Place"
        assert field_title(["Place", ""], 1) == "Field 2"
        assert field_title([], 4) == "Field 5"

    def test_titles_from_profile(self, qtbot):
        profiles.set_schema(field_count=3, field_titles=["Place", "Year"])
        widget = SchemaRulePanel()
        qtbot.addWidget(widget)
        assert [f.label.text() for f in widget._fields] == [
            "Place",
            "Year",
            "Field 3",
        ]


# ---------------------------------------------------------------------------
# Layout and profile settings
# ---------------------------------------------------------------------------


class TestProfile:
    def test_default_layout(self, panel):
        assert len(panel.fields()) == 6
        assert len(panel._marker_group.buttons()) == 7
        assert panel.video_marker_pos() == 0
        assert panel.dest() == ""
        assert not panel.chkFillGaps.isChecked()

    def test_loads_profile_values(self, qtbot, tmp_path):
        profiles.set_schema(
            field_count=2, dest=str(tmp_path), video_marker_pos=2, fill_gaps=True
        )
        widget = SchemaRulePanel()
        qtbot.addWidget(widget)
        assert len(widget.fields()) == 2
        assert widget.video_marker_pos() == 2
        assert widget.dest() == str(tmp_path)
        assert widget.chkFillGaps.isChecked()

    def test_marker_position_saved(self, panel, qtbot):
        with qtbot.waitSignal(panel.changed, timeout=1000):
            panel._marker_group.button(3).setChecked(True)
        assert profiles.get_schema()["video_marker_pos"] == 3

    def test_fill_gaps_saved(self, panel, qtbot):
        with qtbot.waitSignal(panel.changed, timeout=1000):
            panel.chkFillGaps.setChecked(True)
        assert profiles.get_schema()["fill_gaps"] is True

    def test_dest_saved_on_request_only(self, panel, tmp_path):
        panel.edtDest.setText(str(tmp_path))
        assert profiles.get_schema()["dest"] == ""
        panel.save_dest()
        assert profiles.get_schema()["dest"] == str(tmp_path)

    def test_dest_expands_user(self, panel):
        panel.edtDest.setText("~/x")
        assert not panel.dest().startswith("~")

    def test_reload_profile_rebuilds_fields(self, panel):
        profiles.set_schema(field_count=3)
        panel.reload_profile()
        assert len(panel.fields()) == 3
        assert len(panel._marker_group.buttons()) == 4

    def test_edits_emit(self, panel, qtbot):
        with qtbot.waitSignal(panel.edited, timeout=1000):
            panel._fields[0].combo.setCurrentText("A")
        with qtbot.waitSignal(panel.edited, timeout=1000):
            panel.edtDest.setText("/x")

    def test_set_fields(self, panel):
        _set(panel, "A", "", "B")
        assert panel.fields() == ["A", "", "B", "", "", ""]

    def test_has_counter(self, panel):
        _set(panel, "A")
        assert not panel.has_counter()
        _set(panel, "A", "###")
        assert panel.has_counter()


class TestBrowse:
    def test_choose(self, panel, tmp_path, monkeypatch, qtbot):
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path)
        )
        with qtbot.waitSignal(panel.changed, timeout=1000):
            panel.btnBrowse.click()
        assert panel.dest() == str(tmp_path)
        assert profiles.get_schema()["dest"] == str(tmp_path)

    def test_cancel(self, panel, monkeypatch):
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: "")
        panel.btnBrowse.click()
        assert panel.dest() == ""


# ---------------------------------------------------------------------------
# Field histories
# ---------------------------------------------------------------------------


class TestHistory:
    def test_loaded_from_profile(self, qtbot):
        profiles.set_history("field_0", ["Paris", "Lyon"])
        widget = SchemaRulePanel()
        qtbot.addWidget(widget)
        combo = widget._fields[0].combo
        assert [combo.itemText(i) for i in range(combo.count())] == ["Paris", "Lyon"]
        assert widget.fields()[0] == "Paris"

    def test_empty_history_gives_empty_field(self, panel):
        assert panel._fields[0].combo.count() == 1
        assert panel.fields()[0] == ""

    def test_record_history_is_lru(self, qtbot):
        profiles.set_history("field_0", ["Paris", "Lyon"])
        widget = SchemaRulePanel()
        qtbot.addWidget(widget)
        _set(widget, "Lyon")
        widget.record_history()
        assert profiles.get_history("field_0") == ["Lyon", "Paris"]
        _set(widget, "Nice")
        widget.record_history()
        assert profiles.get_history("field_0") == ["Nice", "Lyon", "Paris"]

    def test_first_entry_unchanged(self, qtbot):
        profiles.set_history("field_0", ["Paris"])
        widget = SchemaRulePanel()
        qtbot.addWidget(widget)
        widget.record_history()
        assert profiles.get_history("field_0") == ["Paris"]

    def test_history_max(self, qtbot):
        data = profiles.load()
        data["display"]["history_max"] = 2
        profiles.save(data)
        profiles.set_history("field_0", ["a", "b"])
        widget = SchemaRulePanel()
        qtbot.addWidget(widget)
        _set(widget, "c")
        widget.record_history()
        assert profiles.get_history("field_0") == ["c", "a"]


# ---------------------------------------------------------------------------
# Rule, preview, renumbering
# ---------------------------------------------------------------------------


class TestRule:
    def test_missing_dest(self, panel):
        _set(panel, "A")
        assert panel.rule() is None
        assert "destination" in panel.lblMessage.text()

    def test_relative_dest(self, panel):
        _set(panel, "A")
        panel.edtDest.setText("relative")
        assert panel.rule() is None
        assert "absolute" in panel.lblMessage.text()

    def test_invalid_schema(self, panel, tmp_path):
        panel.edtDest.setText(str(tmp_path))
        _set(panel, "##", "###")
        assert panel.rule() is None
        assert "numeric" in panel.lblMessage.text()

    def test_valid_clears_message(self, panel, tmp_path):
        panel.lblMessage.setText("old")
        panel.edtDest.setText(str(tmp_path))
        _set(panel, "A")
        rule = panel.rule()
        assert rule is not None
        assert rule.dest_root == str(tmp_path)
        assert panel.lblMessage.text() == ""

    def test_video_marker_from_profile(self, qtbot, tmp_path):
        profiles.set_schema(video_marker="vid", dest=str(tmp_path))
        widget = SchemaRulePanel()
        qtbot.addWidget(widget)
        _set(widget, "A")
        assert "{if:video:vid" in widget.rule().replace


class TestPreview:
    def test_none_when_invalid(self, panel, tmp_path):
        assert panel.preview([str(tmp_path / "a.jpg")]) is None

    def test_relative_to_destination(self, panel, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        dest = tmp_path / "dest"
        panel.edtDest.setText(str(dest))
        _set(panel, "Paris", "", "2024", "###")
        entries = panel.preview([str(src / "IMG_1.JPG")])
        target = dest / "Paris" / "2024" / "Paris_2024_001.jpg"
        assert entries == [
            PreviewEntry("Paris/2024/Paris_2024_001.jpg", target=str(target))
        ]

    def test_sidecar_follower_gets_empty_entry(self, panel, tmp_path):
        panel.edtDest.setText(str(tmp_path / "dest"))
        _set(panel, "A")
        base, sc = str(tmp_path / "a.jpg"), str(tmp_path / "a.xmp")
        entries = panel.preview([base, sc], {base: [(sc, "xmp")]})
        assert entries[1] == PreviewEntry("")

    def test_error_entry(self, panel, tmp_path, monkeypatch):
        from pbrenamer.core import filetools, planner

        panel.edtDest.setText(str(tmp_path))
        _set(panel, "A")
        err = filetools.TargetPathError(filetools.TargetPathError.ABSOLUTE, "x")
        monkeypatch.setattr(
            planner, "compute_names", lambda *a, **k: [planner.PlanEntry(error=err)]
        )
        entries = panel.preview([str(tmp_path / "a.jpg")])
        assert entries[0].error


class TestRenumberPlan:
    def test_requires_counter(self, panel, tmp_path):
        _set(panel, "A")
        assert panel.renumber_plan([str(tmp_path / "A_5.jpg")]) is None
        assert "numeric" in panel.lblMessage.text()

    def test_plan_with_sidecars(self, panel, tmp_path):
        _set(panel, "A", "###")
        files = [tmp_path / "A_005.jpg", tmp_path / "A_001.jpg", tmp_path / "A_005.xmp"]
        for f in files:
            f.write_text("x")
        base, other, sc = (str(f) for f in files)
        pairs = panel.renumber_plan([base, other, sc], {base: [(sc, "xmp")]})
        assert pairs == [
            (base, str(tmp_path / "A_001.jpg")),
            (sc, str(tmp_path / "A_001.xmp")),
            (other, str(tmp_path / "A_002.jpg")),
        ]

    def test_already_numbered(self, panel, tmp_path):
        _set(panel, "A", "###")
        f = tmp_path / "A_001.jpg"
        f.write_text("x")
        assert panel.renumber_plan([str(f)]) == []

    def test_error_reported(self, panel, tmp_path, monkeypatch):
        from pbrenamer.core import filetools, planner

        _set(panel, "A", "###")
        err = filetools.TargetPathError(filetools.TargetPathError.ABSOLUTE, "x")
        monkeypatch.setattr(
            planner, "compute_names", lambda *a, **k: [planner.PlanEntry(error=err)]
        )
        assert panel.renumber_plan([str(tmp_path / "b.jpg")]) is None
        assert panel.lblMessage.text().startswith("b.jpg: ")

    def test_unmatched_entry_skipped(self, panel, tmp_path, monkeypatch):
        from pbrenamer.core import planner

        _set(panel, "A", "###")
        monkeypatch.setattr(
            planner, "compute_names", lambda *a, **k: [planner.PlanEntry()]
        )
        assert panel.renumber_plan([str(tmp_path / "b.jpg")]) == []
