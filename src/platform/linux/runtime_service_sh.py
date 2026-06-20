"""Runtime Linux через service.sh (фаза 2)."""
from __future__ import annotations

import os
import time
from collections.abc import Callable

from ..runtime_backend import RuntimeBackend
from ..types import RuntimeStatus, StrategyInfo
from .conf_env import normalize_strategy_filename, read_conf_env, strategy_base_name
from .linux_runtime_manager import LinuxRuntimeManager
from .linux_runtime_options import resolve_use_systemd, sync_conf_env_from_settings
from .paths_xdg import LinuxPathsBackend
from .service_sh_runner import CommandResult, ServiceShRunner

_WAIT_POLL_SEC = 0.4
LogSink = Callable[[str], None]


def _emit_command_log(result: CommandResult, log_sink: LogSink | None) -> None:
    text = result.combined_output.strip()
    if text and log_sink is not None:
        log_sink(text)


class ServiceShRuntimeBackend(RuntimeBackend):
    def __init__(self, paths: LinuxPathsBackend | None = None) -> None:
        self._paths = paths or LinuxPathsBackend()
        self._manager = LinuxRuntimeManager()

    def _root(self) -> str:
        return self._paths.get_runtime_path()

    def _runner(self) -> ServiceShRunner:
        return ServiceShRunner(self._root())

    def process_name(self) -> str:
        return "nfqws"

    def is_configured(self) -> bool:
        ok, _ = self._paths.validate_runtime_folder(self._root())
        return ok

    def list_strategies(self) -> list[StrategyInfo]:
        if not self.is_configured():
            return []
        files = self._manager.list_strategy_files()
        return [StrategyInfo(name=strategy_base_name(f), source=f) for f in files]

    def _process_status(self) -> RuntimeStatus:
        proc = self._manager.get_running_process()
        if proc:
            try:
                return RuntimeStatus(running=True, pid=proc.pid, detail="running")
            except Exception:
                return RuntimeStatus(running=True, detail="running")
        return RuntimeStatus(running=False, detail="stopped")

    def _wait_for_process(self, timeout: float) -> RuntimeStatus:
        deadline = time.time() + max(0.0, timeout)
        while time.time() < deadline:
            status = self._process_status()
            if status.running:
                return status
            time.sleep(_WAIT_POLL_SEC)
        return RuntimeStatus(running=False, detail="nfqws did not start")

    def status(self) -> RuntimeStatus:
        if not self.is_configured():
            return RuntimeStatus(running=False, detail="not_configured")
        return self._process_status()

    def _resolve_prefer_systemd(self, settings: dict, use_systemd: bool | None) -> bool:
        prefer_systemd = use_systemd
        if prefer_systemd is None:
            prefer_systemd = resolve_use_systemd(settings)
        if prefer_systemd is None:
            prefer_systemd = self._manager.service_is_installed()
        return bool(prefer_systemd)

    def _apply_strategy_config(
        self,
        runner: ServiceShRunner,
        strategy_file: str,
        iface: str,
        *,
        gamefilter_tcp: bool,
        gamefilter_udp: bool,
        log_sink: LogSink | None = None,
    ) -> RuntimeStatus | None:
        config_args = ["config", "set", strategy_file, iface, "-n"]
        if gamefilter_tcp:
            config_args.insert(-1, "-gt")
        if gamefilter_udp:
            config_args.insert(-1, "-gu")
        config_result = runner.run(config_args, timeout=120)
        _emit_command_log(config_result, log_sink)
        if config_result.ok:
            return None
        return RuntimeStatus(
            running=False,
            detail=config_result.combined_output or "config_set_failed",
        )

    def _start_via_systemd(self, runner: ServiceShRunner, *, wait_sec: float) -> RuntimeStatus:
        if self._manager.is_running():
            return self._process_status()

        start_result = runner.run(["service", "start"], timeout=120)
        status = self._wait_for_process(wait_sec)
        if status.running:
            return RuntimeStatus(
                running=True,
                pid=status.pid,
                detail=start_result.combined_output or "started_via_service",
            )

        if self._manager.service_is_installed():
            restart_result = runner.run(["service", "restart"], timeout=120)
            status = self._wait_for_process(wait_sec)
            if status.running:
                return RuntimeStatus(
                    running=True,
                    pid=status.pid,
                    detail=restart_result.combined_output or "restarted_via_service",
                )
            detail = (
                restart_result.combined_output
                or start_result.combined_output
                or "service_start_failed"
            )
            return RuntimeStatus(running=False, detail=detail)

        return RuntimeStatus(
            running=False,
            detail=start_result.combined_output or "service_start_failed",
        )

    def start(
        self,
        strategy: str,
        *,
        interface: str | None = None,
        gamefilter_tcp: bool = True,
        gamefilter_udp: bool = True,
        use_systemd: bool | None = None,
        wait_sec: float = 15.0,
    ) -> RuntimeStatus:
        if not self.is_configured():
            return RuntimeStatus(running=False, detail="not_configured")

        from src.entities.config.config_manager import ConfigManager

        settings = ConfigManager().load_settings()
        sync_conf_env_from_settings(self._root(), settings)

        strategy_file = normalize_strategy_filename(strategy)
        if not strategy_file:
            return RuntimeStatus(running=False, detail="empty_strategy")

        iface = (interface or read_conf_env(self._root()).get("interface") or "any").strip() or "any"
        runner = self._runner()

        config_error = self._apply_strategy_config(
            runner,
            strategy_file,
            iface,
            gamefilter_tcp=gamefilter_tcp,
            gamefilter_udp=gamefilter_udp,
        )
        if config_error is not None:
            return config_error

        if self._resolve_prefer_systemd(settings, use_systemd):
            return self._start_via_systemd(runner, wait_sec=wait_sec)

        runner.run(
            ["run", "--config", os.path.join(self._root(), "conf.env")],
            timeout=120,
        )
        status = self._wait_for_process(wait_sec)
        if status.running:
            return RuntimeStatus(
                running=True,
                pid=status.pid,
                detail="started_via_run",
            )
        return RuntimeStatus(running=False, detail=status.detail or "run_failed")

    def start_background(
        self,
        strategy: str,
        *,
        interface: str | None = None,
        gamefilter_tcp: bool = True,
        gamefilter_udp: bool = True,
        use_systemd: bool | None = None,
        log_sink: LogSink | None = None,
    ) -> tuple[RuntimeStatus, object | None]:
        """Запуск с удержанием service.sh run в фоне (для GUI)."""
        if not self.is_configured():
            return RuntimeStatus(running=False, detail="not_configured"), None

        from src.entities.config.config_manager import ConfigManager

        settings = ConfigManager().load_settings()
        sync_conf_env_from_settings(self._root(), settings)

        strategy_file = normalize_strategy_filename(strategy)
        if not strategy_file:
            return RuntimeStatus(running=False, detail="empty_strategy"), None

        iface = (interface or read_conf_env(self._root()).get("interface") or "any").strip() or "any"
        runner = self._runner()

        config_error = self._apply_strategy_config(
            runner,
            strategy_file,
            iface,
            gamefilter_tcp=gamefilter_tcp,
            gamefilter_udp=gamefilter_udp,
            log_sink=log_sink,
        )
        if config_error is not None:
            return config_error, None

        if self._resolve_prefer_systemd(settings, use_systemd):
            requested = strategy_base_name(strategy_file)
            if self._manager.is_running():
                current = self._manager.get_configured_strategy()
                if current == requested:
                    return self._process_status(), None
                restart_result = runner.run(["service", "restart"], timeout=120)
                _emit_command_log(restart_result, log_sink)
                if not restart_result.ok and not self._manager.is_running():
                    return RuntimeStatus(
                        running=False,
                        detail=restart_result.combined_output or "service_restart_failed",
                    ), None
                return RuntimeStatus(running=False, detail="starting_via_service"), None

            start_result = runner.run(["service", "start"], timeout=120)
            _emit_command_log(start_result, log_sink)
            if not self._manager.is_running() and self._manager.service_is_installed():
                restart_result = runner.run(["service", "restart"], timeout=120)
                _emit_command_log(restart_result, log_sink)
                if not restart_result.ok and not self._manager.is_running():
                    return RuntimeStatus(
                        running=False,
                        detail=restart_result.combined_output or "service_start_failed",
                    ), None
            elif not start_result.ok and not self._manager.is_running():
                return RuntimeStatus(
                    running=False,
                    detail=start_result.combined_output or "service_start_failed",
                ), None
            return RuntimeStatus(running=False, detail="starting_via_service"), None

        conf_path = os.path.join(self._root(), "conf.env")
        proc = runner.popen(["run", "--config", conf_path])
        return RuntimeStatus(running=False, detail="background_run"), proc

    def stop(self) -> None:
        self._manager.stop_all()
