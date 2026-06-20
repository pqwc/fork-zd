"""Smoke-тесты артефактов упаковки Linux (фаза 4)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PackagingArtifactsTests(unittest.TestCase):
    def test_build_sh_exists(self):
        self.assertTrue((ROOT / "build.sh").is_file())

    def test_linux_spec_exists(self):
        self.assertTrue((ROOT / "ZapretDesktop-linux.spec").is_file())

    def test_win_spec_exists(self):
        self.assertTrue((ROOT / "ZapretDesktop-win.spec").is_file())

    def test_pyarmor_pack_script_exists(self):
        self.assertTrue((ROOT / "packaging" / "scripts" / "pyarmor_pack.py").is_file())

    def test_requirements_build_includes_pyarmor(self):
        text = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")
        self.assertIn("pyarmor", text.lower())

    def test_linux_install_doc_exists(self):
        self.assertTrue((ROOT / "docs" / "LINUX_INSTALL.md").is_file())

    def test_windows_install_doc_exists(self):
        self.assertTrue((ROOT / "docs" / "WINDOWS_INSTALL.md").is_file())

    def test_build_bat_exists(self):
        self.assertTrue((ROOT / "build.bat").is_file())

    def test_windows_release_readme_exists(self):
        self.assertTrue((ROOT / "packaging" / "assets" / "RELEASE_README_WINDOWS.txt").is_file())

    def test_requirements_dev_includes_pytest(self):
        text = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
        self.assertIn("pytest", text.lower())

    def test_core_docs_exist(self):
        docs = ROOT / "docs"
        for name in ("README.md", "DEVELOPMENT.md", "RELEASE.md", "SMOKE_CHECKLIST.md", "ARCHITECTURE_FSD.md"):
            self.assertTrue((docs / name).is_file(), name)

    def test_dependabot_config_exists(self):
        self.assertTrue((ROOT / ".github" / "dependabot.yml").is_file())

    def test_pyproject_has_ruff(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[tool.ruff]", text)

    def test_requirements_dev_includes_ruff(self):
        text = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
        self.assertIn("ruff", text.lower())

    def test_debian_desktop_and_metainfo(self):
        deb = ROOT / "packaging" / "debian"
        self.assertTrue((deb / "zapretdesktop.desktop").is_file())
        self.assertTrue((deb / "zapretdesktop.metainfo.xml").is_file())
        self.assertTrue((deb / "postinst").is_file())

    def test_make_scripts_exist(self):
        scripts = ROOT / "packaging" / "scripts"
        self.assertTrue((scripts / "make-deb.sh").is_file())
        self.assertTrue((scripts / "make-appimage.sh").is_file())
        self.assertTrue((scripts / "extract_icon.py").is_file())

    def test_version_readable_from_config(self):
        text = (ROOT / "src" / "entities" / "config" / "config_manager.py").read_text(
            encoding="utf-8"
        )
        match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', text, re.M)
        self.assertIsNotNone(match)
        self.assertRegex(match.group(1), r"^\d+\.\d+\.\d+")


if __name__ == "__main__":
    unittest.main()
