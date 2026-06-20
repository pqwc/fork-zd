"""Network status ping command tests (P2-01)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.entities.network import network_status


class PingCommandTests(unittest.TestCase):
    @patch("src.entities.network.network_status.os.name", "nt")
    def test_ping_cmd_windows(self):
        self.assertEqual(
            network_status._ping_cmd(),
            ["ping", "-n", "1", "-w", "2000", "1.1.1.1"],
        )

    @patch("src.entities.network.network_status.os.name", "posix")
    def test_ping_cmd_linux(self):
        self.assertEqual(
            network_status._ping_cmd(),
            ["ping", "-c", "1", "-W", "2", "1.1.1.1"],
        )

    @patch("src.entities.network.network_status.subprocess.run")
    @patch("src.entities.network.network_status.os.name", "posix")
    def test_ping_ok_linux_uses_count_flag(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"64 bytes from 1.1.1.1: ttl=64")
        self.assertTrue(network_status._ping_ok())
        cmd = mock_run.call_args[0][0]
        self.assertIn("-c", cmd)
        self.assertNotIn("-n", cmd)


if __name__ == "__main__":
    unittest.main()
