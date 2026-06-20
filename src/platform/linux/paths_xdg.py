"""Пути Linux (XDG Base Directory)."""
from __future__ import annotations

import json
import os
import sys

from ..paths_backend import PathsBackend
from ..types import RuntimeKind

SERVICE_SH = "service.sh"
LINUX_RUNTIME_ENV = "ZAPRETDESKTOP_RUNTIME_PATH"


def _xdg_config_home() -> str:
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        return xdg
    return os.path.join(os.path.expanduser("~"), ".config")


def _xdg_data_home() -> str:
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return xdg
    return os.path.join(os.path.expanduser("~"), ".local", "share")


def _get_base_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))

    _here = os.path.abspath(__file__)
    for _ in range(4):
        _here = os.path.dirname(_here)
    return _here


class LinuxPathsBackend(PathsBackend):
    def get_config_dir(self) -> str:
        return os.path.join(_xdg_config_home(), "ZapretDesktop")

    def get_data_dir(self) -> str:
        return os.path.join(_xdg_data_home(), "ZapretDesktop")

    def runtime_kind(self) -> RuntimeKind:
        return "zapret-linux"

    def validate_runtime_folder(self, path: str) -> tuple[bool, str]:
        path = (path or "").strip()
        if not path:
            return False, "not_configured"
        if not os.path.isdir(path):
            return False, "not_directory"
        service = os.path.join(os.path.abspath(path), SERVICE_SH)
        if not os.path.isfile(service):
            return False, "missing_service_sh"
        return True, ""

    def get_runtime_path(self) -> str:
        env_path = os.environ.get(LINUX_RUNTIME_ENV, "").strip()
        if env_path:
            abs_env = os.path.abspath(env_path)
            ok, _ = self.validate_runtime_folder(abs_env)
            if ok:
                return abs_env

        try:
            config_path = self.get_config_path()
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    app = data.get("app") or {}
                    for key in ("runtime_path", "winws_path"):
                        custom = (app.get(key) or "").strip()
                        if custom:
                            abs_custom = os.path.abspath(custom)
                            ok, _ = self.validate_runtime_folder(abs_custom)
                            if ok:
                                return abs_custom
        except Exception:
            pass

        for candidate in (
            os.path.join(_get_base_path(), "linux-runtime"),
            os.path.join(_get_base_path(), "zapret-linux"),
        ):
            ok, _ = self.validate_runtime_folder(candidate)
            if ok:
                return os.path.abspath(candidate)

        return ""
