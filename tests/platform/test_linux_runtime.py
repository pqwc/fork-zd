import os
import tempfile
import unittest
from unittest import mock

from src.platform.linux.conf_env import (
    normalize_strategy_filename,
    read_conf_env,
    strategy_base_name,
    write_conf_env,
)
from src.platform.linux.linux_runtime_manager import LinuxRuntimeManager


class ConfEnvTests(unittest.TestCase):
    def test_read_write_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_conf_env(
                tmp,
                {
                    "interface": "eth0",
                    "gamefiltertcp": "true",
                    "gamefilterudp": "false",
                    "strategy": "general.bat",
                },
            )
            data = read_conf_env(tmp)
            self.assertEqual(data.get("interface"), "eth0")
            self.assertEqual(data.get("strategy"), "general.bat")

    def test_write_preserves_custom_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "conf.env")
            with open(path, "w", encoding="utf-8") as f:
                f.write("interface=any\n")
                f.write("custom_flag=yes\n")
                f.write("strategy=general.bat\n")
            write_conf_env(tmp, {"interface": "wlan0"})
            data = read_conf_env(tmp)
            self.assertEqual(data.get("interface"), "wlan0")
            self.assertEqual(data.get("custom_flag"), "yes")
            self.assertEqual(data.get("strategy"), "general.bat")

    def test_strategy_base_name(self):
        self.assertEqual(strategy_base_name("general.bat"), "general")
        self.assertEqual(normalize_strategy_filename("discord"), "discord.bat")


class LinuxRuntimeManagerTests(unittest.TestCase):
    def test_list_strategy_files_from_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = os.path.join(tmp, "zapret-latest")
            custom = os.path.join(tmp, "custom-strategies")
            os.makedirs(repo)
            os.makedirs(custom)
            with open(os.path.join(repo, "general.bat"), "w", encoding="utf-8") as f:
                f.write("@echo off\n")
            with open(os.path.join(repo, "youtube.bat"), "w", encoding="utf-8") as f:
                f.write("@echo off\n")
            with open(os.path.join(custom, "mine.bat"), "w", encoding="utf-8") as f:
                f.write("@echo off\n")
            with mock.patch(
                "src.platform.linux.linux_runtime_manager.get_winws_path",
                return_value=tmp,
            ):
                mgr = LinuxRuntimeManager()
                files = mgr.list_strategy_files()
                self.assertIn("general.bat", files)
                self.assertIn("youtube.bat", files)
                self.assertIn("mine.bat", files)


class ServiceShRuntimeBackendTests(unittest.TestCase):
    def test_status_requires_nfqws_process(self):
        from src.platform.linux.runtime_service_sh import ServiceShRuntimeBackend

        backend = ServiceShRuntimeBackend()
        with mock.patch.object(backend, "is_configured", return_value=True), mock.patch.object(
            backend._manager,
            "get_running_process",
            return_value=None,
        ), mock.patch.object(
            backend._manager,
            "service_is_active",
            return_value=True,
        ):
            status = backend.status()
            self.assertFalse(status.running)
            self.assertEqual(status.detail, "stopped")


class WinwsVersionTests(unittest.TestCase):
    def test_read_version_from_zapret_latest(self):
        from src.entities.winws.winws_version import read_local_version_from_winws_root

        with tempfile.TemporaryDirectory() as tmp:
            repo = os.path.join(tmp, "zapret-latest")
            os.makedirs(repo)
            with open(os.path.join(repo, "service.bat"), "w", encoding="utf-8") as f:
                f.write('@echo off\r\nset "LOCAL_VERSION=1.9.9a"\r\n')
            version = read_local_version_from_winws_root(tmp)
            self.assertEqual(version, "1.9.9a")


if __name__ == "__main__":
    unittest.main()
