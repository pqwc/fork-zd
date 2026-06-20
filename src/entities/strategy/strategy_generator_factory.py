"""Фабрика генератора стратегий по платформе."""
from __future__ import annotations

from src.platform import is_linux


def get_strategy_generator():
    if is_linux():
        from src.platform.linux.shell_strategy_generator import ShellStrategyGenerator

        return ShellStrategyGenerator()
    from src.entities.strategy.bat_generator import BatGenerator

    return BatGenerator()
