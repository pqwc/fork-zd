"""Unit-тесты ConfigManager (save/load, backup, migration)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.entities.config.config_manager import ConfigManager


class ConfigManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = Path(self._get_tmp()) / "zd-config-test"
        self._tmpdir.mkdir(parents=True, exist_ok=True)
        self.config_path = str(self._tmpdir / "config.json")

    def tearDown(self) -> None:
        import shutil

        if self._tmpdir.exists():
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    @staticmethod
    def _get_tmp() -> str:
        import tempfile

        return tempfile.gettempdir()

    def test_roundtrip_settings(self):
        cm = ConfigManager(self.config_path)
        self.assertTrue(cm.set_setting("language", "en"))
        self.assertEqual(cm.get_setting("language"), "en")

    def test_corrupt_json_restores_from_backup(self):
        cm = ConfigManager(self.config_path)
        good = {
            "app": {**cm.default_settings, "last_strategy": "general", "language": "en"},
            "zapret_version": cm.default_config["zapret_version"],
        }
        Path(self.config_path).write_text(json.dumps(good, ensure_ascii=False, indent=4), encoding="utf-8")
        Path(self.config_path + ".bak").write_text(json.dumps(good, ensure_ascii=False, indent=4), encoding="utf-8")
        Path(self.config_path).write_text("{not-json", encoding="utf-8")

        settings = cm.load_settings()
        self.assertEqual(settings.get("last_strategy"), "general")
        self.assertEqual(settings.get("language"), "en")

    def test_empty_config_file_uses_defaults(self):
        Path(self.config_path).write_text("", encoding="utf-8")
        cm = ConfigManager(self.config_path)
        settings = cm.load_settings()
        self.assertIn("language", settings)
        self.assertEqual(settings["language"], "ru")

    def test_migrate_flat_format_to_app_section(self):
        flat = {"language": "en", "last_strategy": "test"}
        Path(self.config_path).write_text(json.dumps(flat), encoding="utf-8")
        cm = ConfigManager(self.config_path)
        loaded = cm.load_all()
        self.assertIn("app", loaded)
        self.assertEqual(loaded["app"]["language"], "en")

    def test_set_zapret_version(self):
        cm = ConfigManager(self.config_path)
        self.assertTrue(cm.set_zapret_version("2.0.0"))
        self.assertEqual(cm.get_zapret_version()["version"], "2.0.0")

    @patch("src.entities.config.config_manager.get_base_path")
    def test_redirects_config_under_program_dir(self, mock_base):
        mock_base.return_value = str(self._tmpdir / "program")
        (self._tmpdir / "program" / "json").mkdir(parents=True, exist_ok=True)
        bad_path = str(self._tmpdir / "program" / "json" / "config.json")
        with patch("src.entities.config.config_manager._get_config_path", return_value=self.config_path):
            cm = ConfigManager(bad_path)
            self.assertEqual(cm.config_path, self.config_path)


if __name__ == "__main__":
    unittest.main()
