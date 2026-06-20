"""Автозапуск ZapretDesktop на Linux (XDG .desktop)."""
from __future__ import annotations

import os
import sys

from src.app.launch_options import LaunchOptions, format_launch_args
from src.shared.lib.app_logging import setup_logging

logger = setup_logging()


def _xdg_autostart_dir() -> str:
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = xdg if xdg else os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "autostart")


class LinuxAutostartManager:
    """XDG autostart entry для GUI (без root)."""

    def __init__(self, app_name: str = "ZapretDesktop") -> None:
        self.app_name = app_name
        self.desktop_path = os.path.join(_xdg_autostart_dir(), f"{app_name}.desktop")

    def is_enabled(self) -> bool:
        return os.path.isfile(self.desktop_path)

    def _build_exec_line(self) -> str:
        launch_args = format_launch_args(
            LaunchOptions(autostart=True, recover=True),
            prefer_short=True,
        )
        if getattr(sys, "frozen", False):
            target = sys.executable
            return f'"{target}" {launch_args}'.strip()

        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        script = os.path.join(project_root, "ZapretDesktop.py")
        return f'"{sys.executable}" "{script}" {launch_args}'.strip()

    def _icon_line(self) -> str:
        if getattr(sys, "frozen", False):
            icon_path = os.path.join(os.path.dirname(sys.executable), "icon.png")
            if os.path.isfile(icon_path):
                return f"Icon={icon_path}"
        return "Icon=zapretdesktop"

    def enable(self) -> bool:
        try:
            os.makedirs(_xdg_autostart_dir(), exist_ok=True)
            exec_line = self._build_exec_line()
            content = "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    f"Name={self.app_name}",
                    f"Exec={exec_line}",
                    self._icon_line(),
                    "Terminal=false",
                    "StartupWMClass=ZapretDesktop",
                    "X-GNOME-Autostart-enabled=true",
                    "",
                ]
            )
            with open(self.desktop_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as exc:
            logger.exception("Linux autostart enable failed: %s", exc)
            return False

    def disable(self) -> bool:
        try:
            if os.path.isfile(self.desktop_path):
                os.remove(self.desktop_path)
            return True
        except Exception as exc:
            logger.exception("Linux autostart disable failed: %s", exc)
            return False

    def toggle(self) -> bool:
        if self.is_enabled():
            return self.disable()
        return self.enable()
