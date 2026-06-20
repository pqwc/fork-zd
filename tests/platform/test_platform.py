import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.platform import (
    detect_platform,
    get_privilege_backend,
    is_linux,
    is_windows,
)
from src.platform.__init__ import get_paths_backend as _get_paths_backend_fn
from src.platform.linux.paths_xdg import LinuxPathsBackend
from src.platform.windows.paths_win import WindowsPathsBackend


def _reset_platform_cache() -> None:
    _get_paths_backend_fn.cache_clear()
    from src.platform import get_privilege_backend as gpb
    from src.platform import get_runtime_backend as grb

    gpb.cache_clear()
    grb.cache_clear()


class _PlatformTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_platform_cache()

    def tearDown(self) -> None:
        _reset_platform_cache()
        os.environ.pop("ZAPRETDESKTOP_PLATFORM", None)
        os.environ.pop("XDG_CONFIG_HOME", None)


class DetectPlatformTests(_PlatformTestCase):
    def test_forced_linux(self):
        os.environ["ZAPRETDESKTOP_PLATFORM"] = "linux"
        _reset_platform_cache()
        if sys.platform == "win32":
            self.assertEqual(detect_platform(), "windows")
        else:
            self.assertEqual(detect_platform(), "linux")
            self.assertTrue(is_linux())

    def test_forced_windows(self):
        os.environ["ZAPRETDESKTOP_PLATFORM"] = "windows"
        _reset_platform_cache()
        if sys.platform == "win32":
            self.assertEqual(detect_platform(), "windows")
            self.assertTrue(is_windows())
        else:
            self.assertEqual(detect_platform(), "linux")
            self.assertFalse(is_windows())

    def test_auto_matches_sys_platform(self):
        os.environ.pop("ZAPRETDESKTOP_PLATFORM", None)
        _reset_platform_cache()
        if sys.platform == "win32":
            self.assertEqual(detect_platform(), "windows")
        else:
            self.assertEqual(detect_platform(), "linux")


class WindowsPathsTests(_PlatformTestCase):
    def test_config_dir_uses_appdata(self):
        with patch.dict(os.environ, {"APPDATA": r"C:\FakeAppData\Roaming"}, clear=False):
            paths = WindowsPathsBackend()
            expected = os.path.join(r"C:\FakeAppData\Roaming", "ZapretDesktop")
            self.assertEqual(os.path.normpath(paths.get_config_dir()), os.path.normpath(expected))

    def test_validate_empty_winws_path_ok(self):
        paths = WindowsPathsBackend()
        ok, reason = paths.validate_runtime_folder("")
        self.assertTrue(ok)
        self.assertEqual(reason, "")


class LinuxPathsTests(_PlatformTestCase):
    def test_xdg_config_dir(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/zd-test-config"}, clear=False):
            paths = LinuxPathsBackend()
            expected = os.path.join("/tmp/zd-test-config", "ZapretDesktop")
            self.assertEqual(os.path.normpath(paths.get_config_dir()), os.path.normpath(expected))

    def test_validate_runtime_requires_service_sh(self):
        paths = LinuxPathsBackend()
        with tempfile.TemporaryDirectory() as tmp:
            ok, reason = paths.validate_runtime_folder(tmp)
            self.assertFalse(ok)
            self.assertEqual(reason, "missing_service_sh")

            service = os.path.join(tmp, "service.sh")
            with open(service, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\n")
            ok, reason = paths.validate_runtime_folder(tmp)
            self.assertTrue(ok)
            self.assertEqual(reason, "")


class PrivilegeBackendTests(_PlatformTestCase):
    def test_windows_requires_admin_for_gui(self):
        with patch("src.platform.detect_platform", return_value="windows"):
            _reset_platform_cache()
            priv = get_privilege_backend()
            self.assertTrue(priv.requires_elevation_for_gui())

    def test_linux_gui_without_root(self):
        with patch("src.platform.detect_platform", return_value="linux"):
            _reset_platform_cache()
            priv = get_privilege_backend()
            self.assertFalse(priv.requires_elevation_for_gui())
            self.assertEqual(priv.get_ui_font_family(), "DejaVu Sans")


if __name__ == "__main__":
    unittest.main()
