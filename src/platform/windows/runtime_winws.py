"""Runtime winws — status/stop через WinwsManager; start через StartWorker."""
from __future__ import annotations

from ..runtime_backend import RuntimeBackend
from ..types import RuntimeStatus, StrategyInfo
from .paths_win import WindowsPathsBackend


class WinwsRuntimeBackend(RuntimeBackend):
    def __init__(self, paths: WindowsPathsBackend | None = None) -> None:
        self._paths = paths or WindowsPathsBackend()

    def process_name(self) -> str:
        return "winws.exe"

    def is_configured(self) -> bool:
        ok, _ = self._paths.validate_runtime_folder(self._paths.get_runtime_path())
        return ok

    def list_strategies(self) -> list[StrategyInfo]:
        import os

        root = self._paths.get_runtime_path()
        if not os.path.isdir(root):
            return []
        names: list[StrategyInfo] = []
        for filename in sorted(os.listdir(root)):
            if (
                filename.endswith(".bat")
                and filename != "service.bat"
                and os.path.isfile(os.path.join(root, filename))
            ):
                names.append(StrategyInfo(name=filename[:-4]))
        return names

    def _manager(self):
        from src.entities.winws.winws_manager import WinwsManager

        return WinwsManager()

    def status(self) -> RuntimeStatus:
        proc = self._manager().get_running_process()
        if proc is None:
            return RuntimeStatus(running=False, detail="stopped")
        try:
            return RuntimeStatus(running=True, pid=proc.pid, detail="running")
        except Exception:
            return RuntimeStatus(running=True, detail="running")

    def start(self, strategy: str, **options) -> RuntimeStatus:
        return RuntimeStatus(running=False, detail="use_start_worker")

    def stop(self) -> None:
        self._manager().stop_all()
