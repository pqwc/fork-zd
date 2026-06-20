"""Qt desktop file name detection on Linux."""
from __future__ import annotations

import os
from unittest.mock import patch

from src.shared.lib.qt_platform import configure_qt_desktop_file_name


def test_configure_skips_when_no_desktop_file(tmp_path):
  called = False

  class FakeGui:
    @staticmethod
    def setDesktopFileName(app_id: str) -> None:
      nonlocal called
      called = True

  with patch("src.shared.lib.qt_platform.sys.platform", "linux"):
      with patch("PyQt6.QtGui.QGuiApplication", FakeGui):
          configure_qt_desktop_file_name()
  assert not called


def test_configure_uses_flatpak_id(tmp_path):
  apps = tmp_path / "applications"
  apps.mkdir()
  desktop = apps / "io.test.App.desktop"
  desktop.write_text("[Desktop Entry]\n", encoding="utf-8")
  chosen = []

  class FakeGui:
    @staticmethod
    def setDesktopFileName(app_id: str) -> None:
      chosen.append(app_id)

  env = {"FLATPAK_ID": "io.test.App", "XDG_DATA_DIRS": str(tmp_path)}
  with patch.dict(os.environ, env, clear=False):
      with patch("src.shared.lib.qt_platform.sys.platform", "linux"):
          with patch("PyQt6.QtGui.QGuiApplication", FakeGui):
              configure_qt_desktop_file_name()
  assert chosen == ["io.test.App"]
