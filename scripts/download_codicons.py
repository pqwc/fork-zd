#!/usr/bin/env python3
"""Скрипт для ручной установки необходимых codicons в AppData (для разработки)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.shared.ui.assets.codicons_manager import (
    CODICONS_VERSION,
    REQUIRED_ICONS,
    install_codicons_full,
    is_installed,
    list_installed_icons,
)


def main():
    print(f"Установка codicons {CODICONS_VERSION} ({len(REQUIRED_ICONS)} иконок)...")
    ok = install_codicons_full()
    if ok or is_installed():
        icons = list_installed_icons()
        print(f"Готово: {len(icons)} иконок в кэше")
        return 0
    print("Ошибка установки codicons")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
