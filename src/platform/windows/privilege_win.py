"""Права администратора Windows."""
from __future__ import annotations

import os
import subprocess
import sys

from ..privilege_backend import PrivilegeBackend


class WindowsPrivilegeBackend(PrivilegeBackend):
    def is_elevated(self) -> bool:
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def requires_elevation_for_gui(self) -> bool:
        return True

    def requires_elevation_for_runtime(self) -> bool:
        return True

    def request_elevation(self, argv: list[str] | None = None) -> bool:
        if self.is_elevated():
            return True

        argv = argv if argv is not None else sys.argv
        try:
            import ctypes

            if getattr(sys, "frozen", False):
                executable = sys.executable
                arguments = subprocess.list2cmdline(argv[1:]) if len(argv) > 1 else ""
            else:
                script = os.path.abspath(argv[0])
                executable = sys.executable
                arguments = subprocess.list2cmdline([script, *argv[1:]])

            work_dir = os.path.dirname(os.path.abspath(argv[0])) or None
            if getattr(sys, "frozen", False):
                work_dir = os.path.dirname(os.path.abspath(sys.executable)) or work_dir

            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                executable,
                arguments or None,
                work_dir,
                1,
            )
            # ShellExecute: >32 — успех (запущен elevated-процесс), <=32 — ошибка/отмена UAC.
            return int(result) > 32
        except Exception:
            return False

    def get_ui_font_family(self) -> str:
        return "Segoe UI"
