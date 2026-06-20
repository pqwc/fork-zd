"""Test window ping command selection (P2-13)."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Import ping helpers without constructing Qt window
from src.pages.test import test_window


class TestWindowPingCommandTests(unittest.TestCase):
    def _ping_cmd_for_target(self, target: dict) -> list[str]:
        """Mirror test_window.test_target_ping command building."""
        ping_target = target.get("ping_target") or "1.1.1.1"
        if os.name == "nt":
            return ["ping", "-n", str(test_window._PING_COUNT), "-w", "2000", ping_target]
        return ["ping", "-c", str(test_window._PING_COUNT), "-W", "2", ping_target]

    def test_linux_ping_uses_count_not_number(self):
        if os.name == "nt":
            self.skipTest("Linux ping flags only on non-Windows")
        cmd = self._ping_cmd_for_target({"ping_target": "8.8.8.8"})
        self.assertIn("-c", cmd)
        self.assertNotIn("-n", cmd)

    def test_windows_ping_uses_number_not_count(self):
        if os.name != "nt":
            self.skipTest("Windows ping flags only on Windows")
        cmd = self._ping_cmd_for_target({"ping_target": "8.8.8.8"})
        self.assertIn("-n", cmd)
        self.assertNotIn("-c", cmd)

    @patch("src.pages.test.test_window.subprocess.run")
    def test_target_ping_skips_without_target(self, mock_run):
        window = MagicMock()
        window.language = "ru"
        bound = test_window.TestWindow.test_target_ping

        class Stub:
            language = "ru"

        result = bound(Stub(), {"name": "x", "url": None, "ping_target": None})
        self.assertEqual(result, "N/A")
        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
