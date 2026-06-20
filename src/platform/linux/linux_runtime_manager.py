"""Управление nfqws runtime на Linux (аналог WinwsManager)."""
from __future__ import annotations

import os
import time

import psutil

from src.shared.lib.path_utils import get_winws_path

from .conf_env import read_conf_env, strategy_base_name, write_conf_env
from .service_sh_runner import ServiceShRunner

NFQWS_PROCESS_NAMES = ("nfqws",)


class LinuxRuntimeManager:
    """Класс для управления zapret-linux и процессом nfqws."""

    @staticmethod
    def parse_stored_pid(pid) -> int | None:
        try:
            value = int(pid or 0)
            return value if value > 0 else None
        except (TypeError, ValueError):
            return None

    @property
    def runtime_root(self) -> str:
        return get_winws_path()

    @property
    def winws_folder(self) -> str:
        """Совместимость с WinwsManager."""
        return self.runtime_root

    @property
    def repo_dir(self) -> str:
        return os.path.join(self.runtime_root, "zapret-latest")

    @property
    def lists_folder(self) -> str:
        repo_lists = os.path.join(self.repo_dir, "lists")
        if os.path.isdir(repo_lists):
            return repo_lists
        user_lists = os.path.join(self.runtime_root, "user-lists")
        if os.path.isdir(user_lists):
            return user_lists
        return repo_lists

    @property
    def utils_folder(self) -> str:
        path = os.path.join(self.repo_dir, "utils")
        return path if os.path.isdir(path) else os.path.join(self.runtime_root, "utils")

    def _runner(self) -> ServiceShRunner:
        return ServiceShRunner(self.runtime_root)

    def _is_nfqws_process(self, proc: psutil.Process) -> bool:
        try:
            name = (proc.name() or "").lower()
            if name in NFQWS_PROCESS_NAMES or name.startswith("nfqws"):
                return True
            exe = (proc.exe() or "").lower()
            if exe.endswith("/nfqws") or exe.endswith("\\nfqws") or "/nfqws" in exe:
                return True
            cmdline = " ".join(proc.cmdline() or []).lower()
            return "nfqws" in cmdline
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False

    def get_running_process(self, stored_pid: int | None = None):
        stored = self.parse_stored_pid(stored_pid)
        if stored:
            try:
                proc = psutil.Process(stored)
                if proc.is_running() and self._is_nfqws_process(proc):
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if self._is_nfqws_process(proc):
                        return proc
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            return None
        return None

    def is_running(self, stored_pid: int | None = None) -> bool:
        return self.get_running_process(stored_pid) is not None

    def is_runtime_active(self, stored_pid: int | None = None) -> bool:
        """nfqws в процессах или активен systemd unit zapret."""
        if self.is_running(stored_pid):
            return True
        try:
            return self.service_is_active()
        except Exception:
            return False

    def stop_all(self) -> None:
        """Останавливает nfqws через service.sh и завершает оставшиеся процессы.

        Внимание: может завершить nfqws, запущенные вне ZapretDesktop (тот же бинарник).
        """
        runner = self._runner()
        if runner.is_available():
            if self.service_is_installed():
                runner.run(["service", "stop"], timeout=60)
            runner.run(["kill"], timeout=60)
            time.sleep(0.5)

        processes_to_kill = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if self._is_nfqws_process(proc):
                    processes_to_kill.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        for proc in processes_to_kill:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        if processes_to_kill:
            time.sleep(0.5)
        for proc in processes_to_kill:
            try:
                if proc.is_running():
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

    def list_strategy_files(self) -> list[str]:
        names: set[str] = set()
        custom = os.path.join(self.runtime_root, "custom-strategies")
        if os.path.isdir(custom):
            for filename in os.listdir(custom):
                lower = filename.lower()
                if lower.endswith(".bat") and not lower.startswith("service"):
                    if os.path.isfile(os.path.join(custom, filename)):
                        names.add(filename)

        repo = self.repo_dir
        if os.path.isdir(repo):
            for filename in os.listdir(repo):
                lower = filename.lower()
                if lower.endswith(".bat") and not lower.startswith("service"):
                    if os.path.isfile(os.path.join(repo, filename)):
                        names.add(filename)
        return sorted(names)

    def get_configured_strategy(self) -> str | None:
        conf = read_conf_env(self.runtime_root)
        strategy = conf.get("strategy", "").strip()
        if not strategy:
            return None
        return strategy_base_name(strategy)

    def service_is_installed(self) -> bool:
        result = self._runner().run(["service", "status"], timeout=30)
        installed, _active = self._parse_service_status(result.combined_output, result.returncode)
        if installed is not None:
            return installed
        return result.returncode != 1

    def service_is_active(self) -> bool:
        if self.is_running():
            return True
        result = self._runner().run(["service", "status"], timeout=30)
        _installed, active = self._parse_service_status(result.combined_output, result.returncode)
        if active is not None:
            return active
        return result.returncode == 2

    @staticmethod
    def _parse_service_status(text: str, returncode: int) -> tuple[bool | None, bool | None]:
        low = (text or "").lower()
        if returncode == 1 or "not installed" in low or "не установлен" in low:
            return False, False
        installed = True
        inactive_markers = (
            "inactive",
            "not active",
            "stopped",
            "dead",
            "failed",
            "не активен",
            "неактивен",
            "остановлен",
        )
        active_markers = (
            "active (running)",
            "active: active",
            "is active",
            "running",
            "активен",
            "запущен",
        )
        if any(marker in low for marker in inactive_markers):
            return installed, False
        if any(marker in low for marker in active_markers):
            return installed, True
        if returncode == 2:
            return installed, True
        if returncode == 0:
            return installed, False
        return installed, None

    # Game filter / ipset — на Linux через conf.env
    def is_game_filter_enabled(self) -> bool:
        conf = read_conf_env(self.runtime_root)
        return conf.get("gamefiltertcp", "false").lower() == "true" or conf.get(
            "gamefilterudp", "false"
        ).lower() == "true"

    def enable_game_filter(self) -> None:
        write_conf_env(
            self.runtime_root,
            {"gamefiltertcp": "true", "gamefilterudp": "true"},
        )

    def disable_game_filter(self) -> None:
        write_conf_env(
            self.runtime_root,
            {"gamefiltertcp": "false", "gamefilterudp": "false"},
        )

    def toggle_game_filter(self) -> bool:
        if self.is_game_filter_enabled():
            self.disable_game_filter()
            return False
        self.enable_game_filter()
        return True

    def get_ipset_mode(self) -> str:
        return "loaded"

    def set_ipset_mode(self, mode: str) -> None:
        raise NotImplementedError("IPSet mode on Linux is managed via list files")
