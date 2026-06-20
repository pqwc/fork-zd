"""Windows autostart (Task Scheduler) tests."""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

from src.features.autostart.autostart_manager import AutostartManager


class AutostartManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        if sys.platform != "win32":
            self.skipTest("Windows autostart tests")
        self.manager = AutostartManager("ZapretDesktopTest")

    @patch("src.features.autostart.autostart_manager.subprocess.run")
    def test_is_enabled_true_when_schtasks_succeeds(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(self.manager.is_enabled())
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args[0][0][0], "schtasks")

    @patch("src.features.autostart.autostart_manager.subprocess.run")
    def test_is_enabled_false_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        self.assertFalse(self.manager.is_enabled())

    @patch("src.features.autostart.autostart_manager.subprocess.run")
    def test_enable_creates_onlogon_highest_task(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
        with patch.dict("os.environ", {"USERNAME": "TestUser"}, clear=False):
            with patch.object(sys, "frozen", True, create=True):
                with patch.object(sys, "executable", r"C:\Apps\ZapretDesktop.exe"):
                    result = self.manager.enable()
        self.assertTrue(result)
        create_call = mock_run.call_args_list[-1]
        cmd = create_call[0][0]
        self.assertIn("/Create", cmd)
        self.assertIn("/SC", cmd)
        idx = cmd.index("/SC")
        self.assertEqual(cmd[idx + 1], "ONLOGON")
        self.assertIn("/RL", cmd)
        rl_idx = cmd.index("/RL")
        self.assertEqual(cmd[rl_idx + 1], "HIGHEST")

    @patch("src.features.autostart.autostart_manager.subprocess.run")
    def test_disable_deletes_task(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(self.manager.disable())
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "schtasks")
        self.assertIn("/delete", cmd)


if __name__ == "__main__":
    unittest.main()
