"""Tests for pbrenamer.migration — 1.x settings and PBPicat catalogues.

Runs on anonymised copies of real configurations (``tests/data/``), always
through a scratch configuration directory.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from pbrenamer import migration, profiles, settings
from pbrenamer.core import sidecar
from pbrenamer.ui.presets import PatternPresets
from pbrenamer.ui.window_state import WindowState

DATA = Path(__file__).parent / "data"


def _fingerprint(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): (
            hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir"
        )
        for p in sorted(root.rglob("*"))
    }


@pytest.fixture
def v1_config(config_dir):
    """Scratch config directory holding a PBRenamer 1.x configuration."""
    shutil.copytree(DATA / "pbrenamer_v1_config", config_dir, dirs_exist_ok=True)
    settings.configure(config_dir)
    return config_dir


@pytest.fixture
def pbpicat_dir(tmp_path):
    """Copy of an anonymised PBPicat configuration.

    The ``.HEROES`` history keeps the trailing commas of the real file it
    comes from (invalid JSON, which the repository's hooks reject).
    """
    src = tmp_path / "pbpicat"
    shutil.copytree(DATA / "pbpicat_config", src)
    (src / ".HEROES" / "history.json").write_text(
        '{\n  "field_0": [\n    "Heroes",\n  ],\n}\n', encoding="utf-8"
    )
    return src


@pytest.fixture
def imported(v1_config, pbpicat_dir):
    """1.x configuration migrated, PBPicat catalogues imported."""
    settings.configure(v1_config, pbpicat_dir=pbpicat_dir)
    profiles.current()
    return v1_config


def _profile(config_dir, name):
    return profiles.read_profile(config_dir / "profiles" / name)


def _sidecars(name):
    profiles.use(name, remember=False)
    return settings.get_sidecar_settings()


# ---------------------------------------------------------------------------
# PBRenamer 1.x
# ---------------------------------------------------------------------------


class TestMigrateV1:
    def test_presets_copied(self, v1_config):
        presets = PatternPresets()
        assert presets.get_replace() == ["20{1} - Bilan", "{1}"]
        assert presets.get_search()[1] == ("regex", "^IMG_(\\d+)")
        assert list(presets.get_saves()) == ["multi_french", "photos"]

    def test_sidecar_config_copied(self, v1_config):
        assert settings.get_sidecar_suffixes("image") == [
            "xmp",
            "info.json",
            "prompt.txt",
        ]

    def test_last_dir_and_toolbar_state(self, v1_config):
        assert settings.get_last_dir() == "/home/user/Catalogue/reel"
        assert settings.get_toolbar_state() == {
            "mode": 0,
            "recursive": False,
            "extension_mode": "keep",
            "sidecar_mode": True,
            "auto_preview": False,
            "filter": "",
        }
        assert profiles.load()["mode"] == "pattern"

    def test_globals_unchanged(self, v1_config):
        assert settings.get_extension_normalization() == [
            ("jpeg", "jpg"),
            ("yml", "yaml"),
        ]
        assert settings.get_shortcuts()[1] == (
            "Vidéo fête 2026",
            "/home/user/Documents/Vidéo fête 2026",
        )
        assert settings.get_restore_last_dir() is True
        assert WindowState().load_geometry("settings_dialog") == (95, 84, 866, 480)

    def test_originals_left_in_place(self, v1_config):
        before = _fingerprint(DATA / "pbrenamer_v1_config")
        profiles.current()
        after = {
            k: v for k, v in _fingerprint(v1_config).items() if "profiles" not in k
        }
        assert after == before

    def test_profile_changes_do_not_touch_originals(self, v1_config):
        PatternPresets().add_replace("new")
        original = json.loads((v1_config / "patterns" / "replace.json").read_text())
        assert original == ["20{1} - Bilan", "{1}"]

    def test_empty_config(self, config_dir):
        assert profiles.load() == profiles.DEFAULTS
        assert not (config_dir / "profiles" / "default" / "patterns").exists()

    def test_invalid_toolbar_state(self, config_dir):
        qs = QSettings(str(config_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/toolbar_state", "not json")
        qs.sync()
        assert profiles.load()["toolbar_state"] == {}

    def test_non_dict_toolbar_state(self, config_dir):
        qs = QSettings(str(config_dir / "pbrenamer.conf"), QSettings.Format.IniFormat)
        qs.setValue("behaviour/toolbar_state", "[1]")
        qs.sync()
        assert profiles.load()["toolbar_state"] == {}


# ---------------------------------------------------------------------------
# PBPicat
# ---------------------------------------------------------------------------


class TestImportPbpicat:
    def test_profiles_created(self, imported):
        assert profiles.list_profiles(include_hidden=True) == [
            ".HEROES",
            ".IA",
            "Icons",
            "default",
            "family",
            "parties",
            "pbpicat-default",
        ]

    def test_last_profile_stays_default(self, imported):
        assert profiles.current() == "default"
        assert _profile(imported, "default")["mode"] == "pattern"

    def test_collision_renamed(self, imported):
        data = _profile(imported, "pbpicat-default")
        assert data["mode"] == "schema"
        assert data["last_dir"] == "/home/user"

    def test_schema_settings(self, imported):
        family = _profile(imported, "family")
        assert family["mode"] == "schema"
        assert family["schema"] == {
            "field_count": 6,
            "field_titles": ["Category", "Date", "Place", "Kind", "Detail", "Number"],
            "dest": "/home/user/Catalog",
            "video_marker": "vid",
            "video_marker_pos": 0,
            "fill_gaps": False,
        }
        assert family["last_dir"] == "/home/user/Catalog/familly/beach"

    def test_ui_conf(self, imported):
        parties = _profile(imported, "parties")
        assert parties["schema"]["video_marker_pos"] == 1
        assert (
            parties["schema"]["dest"] == "/home/user/Documents/Party 2026/02-Saturday"
        )
        assert parties["last_dir"] == "/home/user/Documents/Video party 2026/original"

    def test_display_and_images(self, imported):
        ia = _profile(imported, ".IA")
        assert ia["schema"]["field_count"] == 8
        assert ia["display"] == {
            "thumbnail_max_width": 128,
            "thumbnail_max_height": 128,
            "history_max": 45,
            "thumbnails": True,
            "sidecar_column": True,
            "sidecar_filter": True,
            "sort_by_date": False,
            "sort_reverse": False,
        }
        assert ia["images"] == {
            "zoom_step_percent": 10,
            "zoom_max_percent": 400,
            "sidecar_new_extension": "prompt.txt",
            "delete_empty_sidecars": True,
            "delete_list_max_files": 12,
            "confirm_deletions": True,
            "use_trash": False,
            "exif_auto_rotate": False,
            "metadata_panel_side": "right",
        }

    def test_pattern_profile_display_off(self, imported):
        data = _profile(imported, "default")
        assert not data["display"]["thumbnails"]
        assert not data["display"]["sidecar_column"]
        assert not data["display"]["sidecar_filter"]
        assert not data["images"]["delete_empty_sidecars"]

    def test_missing_keys_take_defaults(self, imported):
        # The parties catalogue predates metadata_panel_side.
        assert _profile(imported, "parties")["images"]["metadata_panel_side"] == "right"

    def test_sidecar_config(self, imported):
        data = _sidecars("Icons")
        assert data["own_suffixes"]["image"] == [
            "xmp",
            "dop",
            "pp3",
            "prompt.txt",
            "description.json",
            "svg",
            "ico",
        ]
        assert data["own_suffixes"]["video"] == data["own_suffixes"]["image"]
        assert len(data["base_extensions"]["image"]) == 47
        assert "jpg" in data["base_extensions"]["image"]
        assert data["base_extensions"]["video"][:2] == ["mp4", "mov"]
        assert settings.get_sidecar_base_extensions("audio") == list(
            sidecar.DEFAULT_AUDIO_EXTENSIONS
        )
        config = settings.get_sidecar_config()
        assert config.category_of_extension("NEF") == "image"
        assert config.effective_suffixes("video") >= {"xmp", "ico"}

    def test_history(self, imported):
        profiles.use("family", remember=False)
        assert profiles.get_history("field_5") == ["####", ""]
        assert profiles.get_history("sidecar_filter") == []

    def test_invalid_history_ignored(self, imported):
        profiles.use(".HEROES", remember=False)
        assert profiles.get_all_history() == {}
        assert profiles.get_schema()["field_titles"][1] == "Nom"

    def test_open_with(self, imported):
        data = json.loads((imported / "open_with.json").read_text(encoding="utf-8"))
        assert data["video/mp4"] == ["vlc.desktop"]

    def test_viewer_options(self, imported):
        qs = QSettings(str(imported / "pbrenamer.conf"), QSettings.Format.IniFormat)
        assert qs.value("viewer/circular_navigation", type=bool) is False
        assert qs.value("viewer/metadata_panel_visible", type=bool) is True
        assert qs.value("log/level") == "INFO"

    def test_source_unchanged(self, v1_config, pbpicat_dir):
        before = _fingerprint(pbpicat_dir)
        settings.configure(v1_config, pbpicat_dir=pbpicat_dir)
        profiles.current()
        assert _fingerprint(pbpicat_dir) == before

    def test_imported_once(self, imported, pbpicat_dir):
        (pbpicat_dir / "new").mkdir()
        settings.configure(imported, pbpicat_dir=pbpicat_dir)
        assert not profiles.exists("new")

    def test_missing_source(self, config_dir, tmp_path):
        settings.configure(config_dir, pbpicat_dir=tmp_path / "none")
        assert profiles.list_profiles() == ["default"]

    def test_profile_usable_from_settings(self, imported):
        profiles.use("family")
        assert settings.get_last_dir() == "/home/user/Catalog/familly/beach"


class TestImportDetails:
    @pytest.fixture
    def root(self, tmp_path):
        root = tmp_path / "profiles"
        root.mkdir()
        return root

    def _import(self, tmp_path, root, catalogues):
        src = tmp_path / "src"
        for name, files in catalogues.items():
            (src / name).mkdir(parents=True)
            for filename, content in files.items():
                (src / name / filename).write_text(content, encoding="utf-8")
        conf = tmp_path / "conf"
        conf.mkdir()
        return migration.import_pbpicat(src, root, conf), conf

    @pytest.mark.parametrize(
        ("catalogue", "expected"),
        [
            ("mes photos", "mes_photos"),
            (".caché", ".caché"),
            ("-old", "-old"),
            ("a.b", "a_b"),
        ],
    )
    def test_names(self, tmp_path, root, catalogue, expected):
        created, _conf = self._import(tmp_path, root, {catalogue: {}})
        assert created == [expected]
        assert profiles.is_valid_name(expected)

    def test_hidden_collision(self, tmp_path, root):
        (root / ".x").mkdir()
        (root / ".pbpicat-x").mkdir()
        (root / ".pbpicat-x-2").mkdir()
        created, _conf = self._import(tmp_path, root, {".x": {}})
        assert created == [".pbpicat-x-3"]

    def test_only_dots_sanitised(self, tmp_path, root):
        created, _conf = self._import(tmp_path, root, {".$": {}})
        assert created == ["._"]

    def test_empty_catalogue_gets_defaults(self, tmp_path, root):
        self._import(tmp_path, root, {"c": {}})
        data = profiles.read_profile(root / "c")
        assert data["mode"] == "schema"
        assert data["schema"] == profiles.DEFAULTS["schema"]
        assert not (root / "c" / "sidecar_config.json").exists()
        assert not (root / "c" / "history.json").exists()

    def test_corrupt_files(self, tmp_path, root):
        self._import(
            tmp_path,
            root,
            {
                "c": {
                    "settings.json": "[1, 2]",
                    "ui.conf": "[schema]\nvideo_marker_pos=x\nfill_number_gaps=maybe\n",
                }
            },
        )
        assert (
            profiles.read_profile(root / "c")["schema"] == profiles.DEFAULTS["schema"]
        )

    def test_bad_values(self, tmp_path, root):
        settings_json = json.dumps(
            {
                "schema_field_titles": ["A", 1],
                "schema_field_count": "6",
                "image_extensions": [".JPG", "jpg", 3, "."],
                "video_extensions": "mp4",
                "sidecar_new_extension": ".",
            }
        )
        self._import(tmp_path, root, {"c": {"settings.json": settings_json}})
        data = profiles.read_profile(root / "c")
        assert data["schema"]["field_titles"] == []
        assert data["schema"]["field_count"] == 6
        assert data["images"]["sidecar_new_extension"] == "xmp"
        sidecars = json.loads((root / "c" / "sidecar_config.json").read_text())
        assert sidecars == {"base_extensions": {"image": ["jpg"]}}

    def test_ui_conf_true_values(self, tmp_path, root):
        ui = "[schema]\nfill_number_gaps=true\n"
        self._import(tmp_path, root, {"c": {"ui.conf": ui}})
        assert profiles.read_profile(root / "c")["schema"]["fill_gaps"] is True

    def test_invalid_open_with_skipped(self, tmp_path, root):
        src = tmp_path / "src"
        src.mkdir()
        (src / "open_with.json").write_text('{"image/png": "x"}')
        conf = tmp_path / "conf"
        conf.mkdir()
        migration.import_pbpicat(src, root, conf)
        assert not (conf / "open_with.json").exists()

    def test_existing_open_with_kept(self, tmp_path, root):
        src = tmp_path / "src"
        src.mkdir()
        (src / "open_with.json").write_text('{"image/png": ["a.desktop"]}')
        conf = tmp_path / "conf"
        conf.mkdir()
        (conf / "open_with.json").write_text("{}")
        migration.import_pbpicat(src, root, conf)
        assert (conf / "open_with.json").read_text() == "{}"

    def test_app_conf_without_viewer_keys(self, tmp_path, root):
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.conf").write_text("[main_window]\ngeometry=1\n")
        conf = tmp_path / "conf"
        conf.mkdir()
        migration.import_pbpicat(src, root, conf)
        qs = QSettings(str(conf / "pbrenamer.conf"), QSettings.Format.IniFormat)
        assert qs.childGroups() == []

    def test_import_logged(self, tmp_path, root, caplog):
        with caplog.at_level("INFO", logger="pbrenamer.migration"):
            self._import(tmp_path, root, {"c": {}})
        assert "Imported PBPicat catalogue 'c' as profile 'c'" in caplog.text


def test_catalogue_without_delete_option_deletes_empty_sidecars():
    data = migration._catalogue_profile({}, None)
    assert data["images"]["delete_empty_sidecars"] is True
    assert data["display"]["thumbnails"] is True
