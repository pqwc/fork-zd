"""
Платформенный слой ZapretDesktop.

pages/ и features/ должны импортировать OS-специфику отсюда, а не напрямую
ctypes / schtasks / service.sh.
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache

from .paths_backend import PathsBackend
from .privilege_backend import PrivilegeBackend
from .runtime_backend import RuntimeBackend
from .types import PlatformName

__all__ = [
    "detect_platform",
    "get_paths_backend",
    "get_privilege_backend",
    "get_runtime_backend",
    "is_linux",
    "is_windows",
    "linux_runtime_configured",
    "platform_feature_available",
]


def detect_platform() -> PlatformName:
    forced = os.environ.get("ZAPRETDESKTOP_PLATFORM", "").strip().lower()
    if sys.platform == "win32":
        native: PlatformName = "windows"
    elif sys.platform == "darwin":
        native = "darwin"
    else:
        native = "linux"
    if forced in ("windows", "linux", "darwin"):
        if forced == "windows" and native != "windows":
            return native
        if forced == "linux" and native == "windows":
            return native
        return forced  # type: ignore[return-value]
    return native


def is_windows() -> bool:
    return detect_platform() == "windows"


def is_linux() -> bool:
    return detect_platform() == "linux"


@lru_cache(maxsize=1)
def get_paths_backend() -> PathsBackend:
    if is_windows():
        from .windows.paths_win import WindowsPathsBackend

        return WindowsPathsBackend()
    from .linux.paths_xdg import LinuxPathsBackend

    return LinuxPathsBackend()


@lru_cache(maxsize=1)
def get_privilege_backend() -> PrivilegeBackend:
    if is_windows():
        from .windows.privilege_win import WindowsPrivilegeBackend

        return WindowsPrivilegeBackend()
    from .linux.privilege_linux import LinuxPrivilegeBackend

    return LinuxPrivilegeBackend()


@lru_cache(maxsize=1)
def get_runtime_backend() -> RuntimeBackend:
    if is_windows():
        from .windows.runtime_winws import WinwsRuntimeBackend

        return WinwsRuntimeBackend()
    from .linux.runtime_service_sh import ServiceShRuntimeBackend

    return ServiceShRuntimeBackend()


def linux_runtime_configured() -> bool:
    if not is_linux():
        return True
    paths = get_paths_backend()
    ok, _ = paths.validate_runtime_folder(paths.get_runtime_path())
    return ok


def platform_feature_available(feature: str) -> bool:
    """Грубая матрица доступности функций до полного паритета."""
    if is_windows():
        return True
    wip: set[str] = set()
    return feature not in wip
