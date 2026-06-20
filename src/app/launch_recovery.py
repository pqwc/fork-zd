"""Полное восстановление / сброс данных приложения в AppData."""
from __future__ import annotations

import os
import shutil

from src.shared.lib.app_logging import setup_logging
from src.shared.lib.path_utils import get_appdata_config_dir

logger = setup_logging()

_RESET_FILES = (
    "config.json",
    "config.json.bak",
    "diagnostics.json",
    "launch_args.txt",
)

_RESET_DIRS = (
    "codicons",
)


def perform_full_reset() -> list[str]:
    """
    Полный сброс: конфиг, кэш codicons, диагностика, launch_args.
    Папку winws не трогает.
    """
    cfg_dir = get_appdata_config_dir()
    os.makedirs(cfg_dir, exist_ok=True)
    removed: list[str] = []

    for name in _RESET_FILES:
        path = os.path.join(cfg_dir, name)
        if os.path.isfile(path):
            try:
                os.remove(path)
                removed.append(path)
            except OSError as exc:
                logger.warning("Не удалось удалить %s: %s", path, exc)

    for name in _RESET_DIRS:
        path = os.path.join(cfg_dir, name)
        if os.path.isdir(path):
            try:
                shutil.rmtree(path)
                removed.append(path)
            except OSError as exc:
                logger.warning("Не удалось удалить %s: %s", path, exc)

    if removed:
        logger.info("Полный сброс: удалено %s элементов", len(removed))
    return removed
