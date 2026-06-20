"""Фоновые workers для обновлений (не блокируют UI-поток)."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


class LinuxDepsWorker(QThread):
    """service.sh download-deps в отдельном потоке."""

    finished = pyqtSignal(bool, str)

    def run(self) -> None:
        try:
            from src.platform.linux.zapret_download import download_deps_default

            ok, detail = download_deps_default(timeout=600.0)
            self.finished.emit(bool(ok), detail or "")
        except Exception as exc:
            self.finished.emit(False, str(exc))


class CallableWorker(QThread):
    """Выполняет callable в фоне и возвращает результат через сигнал."""

    finished = pyqtSignal(object)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            result = {"error": str(exc), "has_update": False}
        self.finished.emit(result)
