"""Утилиты для управления процессами по PID."""
from __future__ import annotations

import subprocess


def terminate_process_tree(pid: int, *, timeout: float = 3.0) -> None:
    """Завершает только процесс с указанным PID и его дочерние."""
    if pid <= 0:
        return
    try:
        import psutil
    except ImportError:
        _taskkill_tree(pid)
        return

    try:
        parent = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return

    procs = [parent]
    try:
        procs.extend(parent.children(recursive=True))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    for proc in procs:
        try:
            proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    _gone, alive = psutil.wait_procs(procs, timeout=timeout)
    for proc in alive:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def _taskkill_tree(pid: int) -> None:
    import sys

    if sys.platform != "win32":
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass
