"""Тесты Linux runtime options (фаза 5)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.platform.linux.conf_env import read_conf_env
from src.platform.linux.linux_runtime_options import (
    normalize_firewall_backend,
    resolve_use_systemd,
    sync_conf_env_from_settings,
)


class LinuxRuntimeOptionsTests(unittest.TestCase):
    def test_resolve_use_systemd_modes(self):
        self.assertTrue(resolve_use_systemd({"linux_init_mode": "systemd"}))
        self.assertFalse(resolve_use_systemd({"linux_init_mode": "run"}))
        self.assertIsNone(resolve_use_systemd({"linux_init_mode": "auto"}))

    def test_normalize_firewall_backend(self):
        self.assertEqual(normalize_firewall_backend("nftables"), "nftables")
        self.assertEqual(normalize_firewall_backend("invalid"), "auto")

    def test_sync_conf_env_from_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = {
                "linux_interface": "eth0",
                "linux_gamefilter_tcp": False,
                "linux_gamefilter_udp": True,
                "linux_firewall_backend": "iptables",
            }
            sync_conf_env_from_settings(tmp, settings)
            conf = read_conf_env(tmp)
            self.assertEqual(conf.get("interface"), "eth0")
            self.assertEqual(conf.get("gamefiltertcp"), "false")
            self.assertEqual(conf.get("gamefilterudp"), "true")
            self.assertEqual(conf.get("firewall_backend"), "iptables")


if __name__ == "__main__":
    unittest.main()
