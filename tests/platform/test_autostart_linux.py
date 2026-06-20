"""Linux autostart (XDG .desktop) tests."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.features.autostart.autostart_linux import LinuxAutostartManager


class LinuxAutostartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="zd-autostart-")
        self.manager = LinuxAutostartManager("ZapretDesktopTest")

    def tearDown(self) -> None:
        desktop = self.manager.desktop_path
        if os.path.isfile(desktop):
            os.remove(desktop)
        if os.path.isdir(os.path.dirname(desktop)):
            try:
                os.rmdir(os.path.dirname(desktop))
            except OSError:
                pass
        if os.path.isdir(self.tmp):
            try:
                os.rmdir(self.tmp)
            except OSError:
                pass

    @patch("src.features.autostart.autostart_linux._xdg_autostart_dir")
    def test_enable_writes_icon_and_exec(self, autostart_dir):
        autostart_dir.return_value = self.tmp
        self.manager.desktop_path = os.path.join(self.tmp, "ZapretDesktopTest.desktop")
        exec_dir = os.path.join(self.tmp, "app")
        os.makedirs(exec_dir)
        exe = os.path.join(exec_dir, "ZapretDesktop")
        icon = os.path.join(exec_dir, "icon.png")
        open(exe, "a", encoding="utf-8").close()
        open(icon, "a", encoding="utf-8").close()
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", exe):
                self.assertTrue(self.manager.enable())

        content = open(self.manager.desktop_path, encoding="utf-8").read()
        self.assertIn(f"Icon={icon}", content)
        self.assertIn(f'Exec="{exe}"', content)
        self.assertIn("X-GNOME-Autostart-enabled=true", content)

    @patch("src.features.autostart.autostart_linux._xdg_autostart_dir")
    def test_disable_removes_desktop_file(self, autostart_dir):
        autostart_dir.return_value = self.tmp
        self.manager.desktop_path = os.path.join(self.tmp, "ZapretDesktopTest.desktop")
        with open(self.manager.desktop_path, "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\n")
        self.assertTrue(self.manager.is_enabled())
        self.assertTrue(self.manager.disable())
        self.assertFalse(self.manager.is_enabled())


if __name__ == "__main__":
    unittest.main()
