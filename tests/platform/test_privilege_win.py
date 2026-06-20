"""Windows elevation (ShellExecute runas)."""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch


@unittest.skipUnless(sys.platform == "win32", "Windows only")
class WindowsPrivilegeElevationTests(unittest.TestCase):
    def test_request_elevation_success_when_shell_execute_returns_gt_32(self):
        from src.platform.windows.privilege_win import WindowsPrivilegeBackend

        backend = WindowsPrivilegeBackend()
        with patch.object(backend, "is_elevated", return_value=False):
            with patch("ctypes.windll.shell32.ShellExecuteW", return_value=42) as runas:
                ok = backend.request_elevation([r"C:\app\ZapretDesktop.py", "--help"])
        self.assertTrue(ok)
        runas.assert_called_once()

    def test_request_elevation_failure_when_user_cancels_uac(self):
        from src.platform.windows.privilege_win import WindowsPrivilegeBackend

        backend = WindowsPrivilegeBackend()
        with patch.object(backend, "is_elevated", return_value=False):
            with patch("ctypes.windll.shell32.ShellExecuteW", return_value=5):
                ok = backend.request_elevation([r"C:\app\ZapretDesktop.py"])
        self.assertFalse(ok)

    def test_request_elevation_skips_when_already_elevated(self):
        from src.platform.windows.privilege_win import WindowsPrivilegeBackend

        backend = WindowsPrivilegeBackend()
        with patch.object(backend, "is_elevated", return_value=True):
            with patch("ctypes.windll.shell32.ShellExecuteW") as runas:
                ok = backend.request_elevation()
        self.assertTrue(ok)
        runas.assert_not_called()


if __name__ == "__main__":
    unittest.main()
