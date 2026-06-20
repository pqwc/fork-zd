"""Общие типы платформенного слоя."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PlatformName = Literal["windows", "linux", "darwin"]
RuntimeKind = Literal["winws", "zapret-linux", "unknown"]


@dataclass(frozen=True)
class RuntimeStatus:
    running: bool
    pid: int | None = None
    detail: str = ""


@dataclass(frozen=True)
class StrategyInfo:
    name: str
    source: str = ""
