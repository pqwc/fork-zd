"""Абстракция zapret runtime (winws / service.sh)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .types import RuntimeStatus, StrategyInfo


class RuntimeBackend(ABC):
    @abstractmethod
    def process_name(self) -> str:
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    def list_strategies(self) -> list[StrategyInfo]:
        ...

    @abstractmethod
    def status(self) -> RuntimeStatus:
        ...

    @abstractmethod
    def start(self, strategy: str, **options) -> RuntimeStatus:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...
