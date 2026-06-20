"""Привилегии Linux — GUI без root, runtime через sudo (фаза 2)."""
from __future__ import annotations

import os
import sys

from ..privilege_backend import PrivilegeBackend


class LinuxPrivilegeBackend(PrivilegeBackend):
    def is_elevated(self) -> bool:
        try:
            return os.geteuid() == 0  # type: ignore[attr-defined]
        except AttributeError:
            return False

    def requires_elevation_for_gui(self) -> bool:
        return False

    def requires_elevation_for_runtime(self) -> bool:
        return True

    def request_elevation(self, argv: list[str] | None = None) -> bool:
        # Перезапуск GUI через pkexec/sudo — не в MVP; runtime elevates отдельно.
        return self.is_elevated()

    def get_ui_font_family(self) -> str:
        return "DejaVu Sans"
