"""Background workers for strategy start/stop."""
from PyQt6.QtCore import QThread, pyqtSignal
import subprocess
import os
import time


class BatOutputReader(QThread):
    """Читает stdout/stderr процесса .bat и передаёт строки в UI."""

    output = pyqtSignal(str)

    def __init__(self, process):
        super().__init__()
        self._process = process

    def run(self):
        try:
            stream = getattr(self._process, "stdout", None)
            if stream is None:
                return
            while True:
                chunk = stream.readline()
                if not chunk:
                    break
                if isinstance(chunk, bytes):
                    text = chunk.decode("utf-8", errors="replace")
                else:
                    text = str(chunk)
                if text:
                    self.output.emit(text)
        except Exception:
            pass


class StartWorker(QThread):
    """Фоновый запуск .bat: автоперезапуск приложений и Popen. Не блокирует UI."""
    done_signal = pyqtSignal(bool, object, str)  # success, process, error_message

    def __init__(self, main_win, bat_path_abs, bat_dir, is_nt):
        super().__init__()
        self._main_win = main_win
        self._bat_path_abs = bat_path_abs
        self._bat_dir = bat_dir
        self._is_nt = is_nt

    def run(self):
        try:
            time.sleep(0.5)
            self._main_win._prepare_auto_restart_apps()
            if self._is_nt:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                proc = subprocess.Popen(
                    ['cmd.exe', '/c', self._bat_path_abs],
                    cwd=self._bat_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                proc = subprocess.Popen(
                    [self._bat_path_abs],
                    cwd=self._bat_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            def _cancelled() -> bool:
                return bool(getattr(self._main_win, "_pending_stop_after_start", False))

            mgr = getattr(self._main_win, "winws_manager", None)
            if mgr is not None and hasattr(mgr, "is_running"):
                timeout = float(
                    getattr(self._main_win, "_get_winws_start_timeout", lambda: 15)()
                )
                deadline = time.time() + timeout
                while time.time() < deadline:
                    if _cancelled():
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        self.done_signal.emit(False, None, "cancelled")
                        return
                    if mgr.is_running():
                        break
                    time.sleep(0.4)
                if _cancelled():
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    self.done_signal.emit(False, None, "cancelled")
                    return
                if mgr.is_running():
                    self.done_signal.emit(True, proc, '')
                else:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    self.done_signal.emit(False, None, "winws did not start")
                return

            self.done_signal.emit(True, proc, '')
        except Exception as e:
            self.done_signal.emit(False, None, str(e))

class StopWorker(QThread):
    """Фоновое завершение процессов winws.exe. Не блокирует UI."""
    done_signal = pyqtSignal()

    def __init__(self, main_win):
        super().__init__()
        self._main_win = main_win

    def run(self):
        try:
            self._main_win._do_stop_winws_process()
        except Exception:
            pass
        self.done_signal.emit()


class LinuxStartWorker(QThread):
    """Фоновый запуск стратегии через service.sh (Linux)."""
    done_signal = pyqtSignal(bool, object, str)
    output_signal = pyqtSignal(str)

    def __init__(self, main_win, strategy_name: str):
        super().__init__()
        self._main_win = main_win
        self._strategy_name = strategy_name

    def run(self):
        import time

        from src.platform.linux.runtime_service_sh import ServiceShRuntimeBackend
        from src.platform import get_runtime_backend

        try:
            time.sleep(0.3)
            self._main_win._prepare_auto_restart_apps()
            runtime = get_runtime_backend()
            if not isinstance(runtime, ServiceShRuntimeBackend):
                self.done_signal.emit(False, None, "invalid runtime backend")
                return

            settings = self._main_win.settings
            interface = (settings.get("linux_interface") or "any").strip() or "any"
            gamefilter_tcp = bool(settings.get("linux_gamefilter_tcp", True))
            gamefilter_udp = bool(settings.get("linux_gamefilter_udp", True))
            from src.platform.linux.linux_runtime_options import resolve_use_systemd

            use_systemd = resolve_use_systemd(settings)

            def emit_log(text: str) -> None:
                if text and text.strip():
                    self.output_signal.emit(text)

            status, proc = runtime.start_background(
                self._strategy_name,
                interface=interface,
                gamefilter_tcp=gamefilter_tcp,
                gamefilter_udp=gamefilter_udp,
                use_systemd=use_systemd,
                log_sink=emit_log,
            )

            fatal_details = frozenset({"not_configured", "empty_strategy", "config_set_failed"})
            if status.detail in fatal_details:
                self.done_signal.emit(False, None, status.detail)
                return

            mgr = self._main_win.winws_manager
            if status.running and mgr.is_running():
                self.done_signal.emit(True, proc, "")
                return

            timeout = float(
                getattr(self._main_win, "_get_winws_start_timeout", lambda: 15)()
            )
            deadline = time.time() + timeout
            while time.time() < deadline:
                if getattr(self._main_win, "_pending_stop_after_start", False):
                    if proc is not None:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                    self.done_signal.emit(False, None, "cancelled")
                    return
                if mgr.is_running():
                    break
                time.sleep(0.4)

            if mgr.is_running():
                self.done_signal.emit(True, proc, "")
            else:
                detail = status.detail or "nfqws did not start"
                if proc is not None:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                self.done_signal.emit(False, None, detail)
        except Exception as exc:
            self.done_signal.emit(False, None, str(exc))


class LinuxStopWorker(QThread):
    """Фоновая остановка nfqws через service.sh kill."""
    done_signal = pyqtSignal()

    def __init__(self, main_win):
        super().__init__()
        self._main_win = main_win

    def run(self):
        try:
            self._main_win._do_stop_winws_process()
        except Exception:
            pass
        self.done_signal.emit()
