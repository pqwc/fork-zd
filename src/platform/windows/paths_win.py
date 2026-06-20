"""Пути Windows — поведение идентично прежнему path_utils."""
from __future__ import annotations

import json
import os
import sys

from ..paths_backend import PathsBackend
from ..types import RuntimeKind

WINWS_EXE_REL = os.path.join("bin", "winws.exe")


def _get_windows_appdata_dir() -> str:
    appdata = os.environ.get("APPDATA", "")

    if not appdata:
        try:
            import ctypes
            from ctypes import wintypes

            CSIDL_APPDATA = 26
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_APPDATA, None, 0, buf)
            if buf.value:
                appdata = buf.value
        except Exception:
            pass

    if not appdata:
        userprofile = os.environ.get("USERPROFILE", "")
        if userprofile:
            appdata = os.path.join(userprofile, "AppData", "Roaming")

    if not appdata:
        home = os.path.expanduser("~")
        if home and home != "~":
            appdata = os.path.join(home, "AppData", "Roaming")

    if not appdata:
        appdata = os.path.join("C:", os.sep, "Users", "Default", "AppData", "Roaming")

    return os.path.join(appdata, "ZapretDesktop")


def _detect_winws_folder(base_path: str) -> str | None:
    if not base_path or not os.path.isdir(base_path):
        return None

    default_winws = os.path.join(base_path, "winws")
    if os.path.isfile(os.path.join(default_winws, WINWS_EXE_REL)):
        return os.path.abspath(default_winws)

    candidates: list[str] = []
    try:
        for name in os.listdir(base_path):
            subdir = os.path.join(base_path, name)
            if os.path.isdir(subdir) and os.path.isfile(os.path.join(subdir, WINWS_EXE_REL)):
                candidates.append(os.path.abspath(subdir))
    except OSError:
        pass

    if not candidates:
        return None

    for path in candidates:
        if os.path.basename(path).lower() == "winws":
            return path
    return candidates[0]


def _get_base_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))

    _here = os.path.abspath(__file__)
    for _ in range(4):
        _here = os.path.dirname(_here)
    return _here


class WindowsPathsBackend(PathsBackend):
    def get_config_dir(self) -> str:
        return _get_windows_appdata_dir()

    def get_data_dir(self) -> str:
        return self.get_config_dir()

    def runtime_kind(self) -> RuntimeKind:
        return "winws"

    def validate_runtime_folder(self, path: str) -> tuple[bool, str]:
        path = (path or "").strip()
        if not path:
            return True, ""
        if not os.path.isdir(path):
            return False, "not_directory"
        if not os.path.isfile(os.path.join(os.path.abspath(path), WINWS_EXE_REL)):
            return False, "missing_exe"
        return True, ""

    def get_runtime_path(self) -> str:
        try:
            config_path = self.get_config_path()
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    custom = (data.get("app") or {}).get("winws_path", "").strip()
                    if not custom:
                        custom = (data.get("app") or {}).get("runtime_path", "").strip()
                    if custom:
                        abs_custom = os.path.abspath(custom)
                        if os.path.isfile(os.path.join(abs_custom, WINWS_EXE_REL)):
                            return abs_custom
        except Exception:
            pass

        base_path = _get_base_path()
        detected = _detect_winws_folder(base_path)
        if detected:
            return detected
        return os.path.join(base_path, "winws")
