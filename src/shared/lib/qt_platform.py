"""Qt platform tweaks for Linux (portal / desktop integration)."""
from __future__ import annotations

import os
import sys


def configure_qt_desktop_file_name() -> None:
    """
    Регистрирует App ID для xdg-desktop-portal только если .desktop найден в системе.
    Без установленного .desktop вызов setDesktopFileName() даёт QDBusError в лог.
    """
    if sys.platform != "linux":
        return

    from PyQt6.QtGui import QGuiApplication

    candidates: list[str] = []
    flatpak_id = os.environ.get("FLATPAK_ID", "").strip()
    if flatpak_id:
        candidates.append(flatpak_id)
    candidates.extend(
        [
            "io.github.pqwc.fork-zd.ZapretDesktop",
            "zapretdesktop",
            "ZapretDesktop",
        ]
    )

    search_dirs: list[str] = [
        "/usr/share/applications",
        "/usr/local/share/applications",
        os.path.join(os.path.expanduser("~"), ".local/share/applications"),
    ]
    xdg_data = os.environ.get("XDG_DATA_DIRS", "")
    for part in xdg_data.split(":"):
        part = part.strip()
        if part:
            search_dirs.append(os.path.join(part, "applications"))

    for app_id in candidates:
        for directory in search_dirs:
            desktop_path = os.path.join(directory, f"{app_id}.desktop")
            if os.path.isfile(desktop_path):
                QGuiApplication.setDesktopFileName(app_id)
                return
