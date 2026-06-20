"""Открытие файлов и папок через системный обработчик (кроссплатформенно)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys


def open_path(path: str) -> None:
    """Открывает файл или папку в проводнике / файловом менеджере / ассоциированном приложении."""
    target = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(target):
        raise FileNotFoundError(target)

    if sys.platform == "win32":
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(
            ["open", target],
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    else:
        _open_path_linux(target)


def _run_detached(cmd: list[str]) -> int:
    try:
        proc = subprocess.run(
            cmd,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            timeout=15,
            check=False,
        )
        return int(proc.returncode or 0)
    except (OSError, subprocess.TimeoutExpired):
        return 1


def _linux_desktop_user() -> str | None:
    for key in ("SUDO_USER", "CURSOR_SUDO_USER", "LOGNAME", "USER"):
        user = (os.environ.get(key) or "").strip()
        if user and user != "root":
            return user
    return None


def _open_path_linux(target: str) -> None:
    folder = target if os.path.isdir(target) else os.path.dirname(target)
    folder = os.path.abspath(folder)

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        desktop_user = _linux_desktop_user()
        if desktop_user:
            if shutil.which("runuser"):
                if _run_detached(["runuser", "-u", desktop_user, "--", "xdg-open", folder]) == 0:
                    return
            if shutil.which("sudo"):
                if _run_detached(["sudo", "-u", desktop_user, "-H", "xdg-open", folder]) == 0:
                    return

    candidates: list[list[str]] = []
    for binary in ("nautilus", "dolphin", "thunar", "pcmanfm-qt", "pcmanfm", "caja", "nemo"):
        if shutil.which(binary):
            candidates.append([binary, folder])
    if shutil.which("xdg-open"):
        candidates.append(["xdg-open", folder])

    last_error = folder
    for cmd in candidates:
        if _run_detached(cmd) == 0:
            return
        last_error = " ".join(cmd)

    raise RuntimeError(last_error)


def reveal_path_in_file_manager(path: str) -> None:
    """Открывает файловый менеджер с выделением указанного файла (если поддерживается)."""
    target = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(target):
        raise FileNotFoundError(target)

    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(target)])
    elif sys.platform == "darwin":
        subprocess.Popen(
            ["open", "-R", target],
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    else:
        if os.path.isfile(target) and shutil.which("nautilus"):
            if _run_detached(["nautilus", "--select", target]) == 0:
                return
        open_path(os.path.dirname(target) if os.path.isfile(target) else target)
