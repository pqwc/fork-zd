"""
Генератор .bat стратегий для Linux-адаптера (custom-strategies/).
Использует тот же формат Flowseal, что и Windows BatGenerator.
"""
from __future__ import annotations

import os

from src.entities.strategy.bat_generator import BatGenerator
from src.platform.linux.linux_runtime_manager import LinuxRuntimeManager


class ShellStrategyGenerator(BatGenerator):
    """Стратегии сохраняются в runtime/custom-strategies/."""

    CUSTOM_DIR = "custom-strategies"

    def __init__(self) -> None:
        mgr = LinuxRuntimeManager()
        self.runtime_root = mgr.runtime_root
        self.winws_folder = os.path.join(self.runtime_root, self.CUSTOM_DIR)
        os.makedirs(self.winws_folder, exist_ok=True)
        self.winws_manager = None  # type: ignore[assignment]

        repo = mgr.repo_dir
        bin_in_repo = os.path.join(repo, "bin")
        self.bin_folder = bin_in_repo if os.path.isdir(bin_in_repo) else os.path.join(self.runtime_root, "bin")
        self.lists_folder = mgr.lists_folder
