"""Обновление стратегий zapret на Linux через service.sh."""
from __future__ import annotations

import os

from src.platform.linux.service_sh_runner import ServiceShRunner
from src.shared.lib.path_utils import get_winws_path


def download_deps_default(*, timeout: float = 600.0) -> tuple[bool, str]:
    root = get_winws_path()
    runner = ServiceShRunner(root)
    if not runner.is_available():
        return False, "service.sh not found"
    result = runner.run(["download-deps", "--default"], timeout=timeout)
    if result.ok:
        return True, result.stdout.strip() or "ok"
    return False, result.combined_output or f"exit {result.returncode}"


def runtime_has_strategies() -> bool:
    root = get_winws_path()
    repo = os.path.join(root, "zapret-latest")
    if not os.path.isdir(repo):
        return False
    for name in os.listdir(repo):
        if name.endswith(".bat"):
            return True
    custom = os.path.join(root, "custom-strategies")
    if os.path.isdir(custom):
        for name in os.listdir(custom):
            if name.endswith(".bat"):
                return True
    return False
