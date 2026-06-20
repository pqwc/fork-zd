"""Абстракция путей конфигурации и runtime."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .types import RuntimeKind


class PathsBackend(ABC):
    @abstractmethod
    def get_config_dir(self) -> str:
        """Каталог пользовательских настроек (AppData / XDG config)."""

    @abstractmethod
    def get_data_dir(self) -> str:
        """Каталог пользовательских данных (cache, codicons и т.п.)."""

    @abstractmethod
    def runtime_kind(self) -> RuntimeKind:
        ...

    @abstractmethod
    def get_runtime_path(self) -> str:
        """Корень runtime: winws/ (Windows) или каталог service.sh (Linux)."""

    @abstractmethod
    def validate_runtime_folder(self, path: str) -> tuple[bool, str]:
        """
        Проверяет каталог runtime.
        Возвращает (ok, reason); reason — пустая строка или код ошибки.
        """

    def get_config_path(self, relative_path: str = "config.json") -> str:
        import os

        return os.path.join(self.get_config_dir(), relative_path)
