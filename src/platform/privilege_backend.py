"""Проверка и запрос повышенных привилегий."""
from __future__ import annotations

from abc import ABC, abstractmethod


class PrivilegeBackend(ABC):
    @abstractmethod
    def is_elevated(self) -> bool:
        """True, если процесс уже с повышенными правами (admin / root)."""

    @abstractmethod
    def requires_elevation_for_gui(self) -> bool:
        """Нужны ли повышенные права для запуска GUI."""

    @abstractmethod
    def requires_elevation_for_runtime(self) -> bool:
        """Нужны ли повышенные права для управления zapret runtime."""

    @abstractmethod
    def request_elevation(self, argv: list[str] | None = None) -> bool:
        """
        Пытается перезапустить приложение с повышенными правами.
        Возвращает True, если текущий процесс уже elevated или перезапуск инициирован.
        """

    def get_ui_font_family(self) -> str:
        return "Segoe UI"
