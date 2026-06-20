"""Windows paths backend tests."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.platform.windows.paths_win import WindowsPathsBackend, _detect_winws_folder


class WindowsPathsTests(unittest.TestCase):
    def test_detect_winws_prefers_default_folder(self):
        with patch("os.listdir", return_value=["winws", "other-winws"]), patch(
            "os.path.isdir", side_effect=lambda p: True
        ), patch(
            "os.path.isfile",
            side_effect=lambda p: p.endswith(os.path.join("winws", "bin", "winws.exe")),
        ):
            found = _detect_winws_folder(r"C:\Apps")
        self.assertTrue(found.endswith("winws"))

    def test_detect_winws_returns_none_without_exe(self):
        with patch("os.path.isdir", return_value=True), patch("os.listdir", return_value=["empty"]):
            with patch("os.path.isfile", return_value=False):
                self.assertIsNone(_detect_winws_folder(r"C:\Apps"))

    def test_validate_runtime_requires_winws_exe(self):
        backend = WindowsPathsBackend()
        with patch.object(backend, "get_runtime_path", return_value=r"C:\Apps\winws"):
            with patch("os.path.isdir", return_value=True):
                with patch("os.path.isfile", return_value=False):
                    ok, reason = backend.validate_runtime_folder(r"C:\Apps\winws")
        self.assertFalse(ok)

    @patch.dict(os.environ, {"APPDATA": r"C:\FakeAppData\Roaming"}, clear=False)
    def test_get_config_dir(self):
        backend = WindowsPathsBackend()
        expected = os.path.join(r"C:\FakeAppData\Roaming", "ZapretDesktop")
        self.assertEqual(os.path.normpath(backend.get_config_dir()), os.path.normpath(expected))


if __name__ == "__main__":
    unittest.main()
