"""Tests for P2/P3 audit fixes."""
import io
import os
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from src.platform import detect_platform
from src.platform.__init__ import get_paths_backend as _get_paths_backend_fn
from src.platform.linux.linux_runtime_manager import LinuxRuntimeManager
from src.platform.linux.paths_xdg import LinuxPathsBackend
from src.platform.windows.runtime_winws import WinwsRuntimeBackend
from src.shared.lib.safe_zip import safe_extractall


def _reset_platform_cache() -> None:
    _get_paths_backend_fn.cache_clear()
    from src.platform import get_privilege_backend as gpb
    from src.platform import get_runtime_backend as grb

    gpb.cache_clear()
    grb.cache_clear()


class SafeZipTests(unittest.TestCase):
    def test_safe_extractall_blocks_traversal(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../evil.txt", "x")
        buf.seek(0)
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(buf) as zf:
                with self.assertRaises(ValueError):
                    safe_extractall(zf, tmp)

    def test_safe_extractall_allows_normal_files(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("ok.txt", "hello")
        buf.seek(0)
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(buf) as zf:
                safe_extractall(zf, tmp)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "ok.txt")))


class ServiceStatusParseTests(unittest.TestCase):
    def test_inactive_ru(self):
        installed, active = LinuxRuntimeManager._parse_service_status(
            "Unit zapret.service: не активен", 0
        )
        self.assertTrue(installed)
        self.assertFalse(active)

    def test_active_en(self):
        installed, active = LinuxRuntimeManager._parse_service_status(
            "Active: active (running)", 0
        )
        self.assertTrue(installed)
        self.assertTrue(active)

    def test_not_installed(self):
        installed, active = LinuxRuntimeManager._parse_service_status(
            "Service not installed", 1
        )
        self.assertFalse(installed)
        self.assertFalse(active)


class PlatformOverrideTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("ZAPRETDESKTOP_PLATFORM", None)
        _reset_platform_cache()

    def test_linux_forced_on_windows_host_ignored(self):
        if sys.platform != "win32":
            self.skipTest("Windows host only")
        os.environ["ZAPRETDESKTOP_PLATFORM"] = "linux"
        _reset_platform_cache()
        self.assertEqual(detect_platform(), "windows")

    def test_windows_forced_on_linux_host_ignored(self):
        if sys.platform == "win32":
            self.skipTest("Linux host only")
        os.environ["ZAPRETDESKTOP_PLATFORM"] = "windows"
        _reset_platform_cache()
        self.assertEqual(detect_platform(), "linux")


class LinuxPathsFallbackTests(unittest.TestCase):
    def test_unconfigured_runtime_returns_empty(self):
        paths = LinuxPathsBackend()
        with patch.object(paths, "validate_runtime_folder", return_value=(False, "missing")):
            with patch("src.platform.linux.paths_xdg._get_base_path", return_value="/tmp/zd-no-runtime"):
                self.assertEqual(paths.get_runtime_path(), "")


class WinwsRuntimeBackendTests(unittest.TestCase):
    @patch("src.platform.windows.runtime_winws.WinwsRuntimeBackend._manager")
    def test_stop_delegates_to_manager(self, mgr_factory):
        mgr = mgr_factory.return_value
        backend = WinwsRuntimeBackend()
        backend.stop()
        mgr.stop_all.assert_called_once()

    @patch("src.platform.windows.runtime_winws.WinwsRuntimeBackend._manager")
    def test_status_stopped(self, mgr_factory):
        mgr = mgr_factory.return_value
        mgr.get_running_process.return_value = None
        backend = WinwsRuntimeBackend()
        self.assertFalse(backend.status().running)


if __name__ == "__main__":
    unittest.main()
