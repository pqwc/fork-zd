"""Запуск внешних терминалов и оболочек (Windows / Linux / macOS)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Literal

ShellKind = Literal["default", "cmd", "powershell", "bash"]


def _windows_creation_flags() -> int:
    return getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def launch_shell_in_directory(
    directory: str,
    *,
    shell: ShellKind = "default",
) -> subprocess.Popen | None:
    """Открывает новый терминал в каталоге directory."""
    directory = os.path.abspath(directory)
    if not os.path.isdir(directory):
        return None

    if sys.platform == "win32":
        flags = _windows_creation_flags()
        if shell == "powershell":
            return subprocess.Popen(["powershell.exe"], cwd=directory, creationflags=flags)
        return subprocess.Popen(["cmd.exe"], cwd=directory, creationflags=flags)

    if sys.platform == "darwin":
        script = f'tell application "Terminal" to do script "cd {directory!r}; exec bash -l"'
        return subprocess.Popen(["osascript", "-e", script], start_new_session=True)

    bash = shutil.which("bash") or "/bin/bash"
    candidates: list[list[str]] = [
        ["x-terminal-emulator", "-e", bash, "-l"],
        ["gnome-terminal", "--working-directory", directory, "--", bash, "-l"],
        ["konsole", "--workdir", directory, "-e", bash, "-l"],
        ["xfce4-terminal", "--working-directory", directory, "-e", bash, "-l"],
        ["alacritty", "-e", bash, "-l"],
        ["kitty", "bash", "-l"],
        ["xterm", "-e", bash, "-l"],
    ]
    for cmd in candidates:
        exe = cmd[0]
        if not shutil.which(exe):
            continue
        try:
            if exe == "gnome-terminal":
                return subprocess.Popen(cmd, start_new_session=True)
            if exe in ("konsole", "xfce4-terminal"):
                return subprocess.Popen(cmd, start_new_session=True)
            if exe == "x-terminal-emulator":
                return subprocess.Popen(cmd, cwd=directory, start_new_session=True)
            return subprocess.Popen(cmd, cwd=directory, start_new_session=True)
        except OSError:
            continue
    return None


def launch_file_in_shell(path: str, *, shell: ShellKind = "default") -> subprocess.Popen | None:
    """Запускает файл в новом терминале."""
    path = os.path.abspath(path)
    folder = os.path.dirname(path) or os.getcwd()
    name = os.path.basename(path)

    if sys.platform == "win32":
        flags = _windows_creation_flags()
        if shell == "powershell":
            return subprocess.Popen(
                ["powershell.exe", "-NoExit", "-File", path],
                creationflags=flags,
            )
        return subprocess.Popen(
            ["cmd.exe", "/K", name],
            cwd=folder,
            creationflags=flags,
        )

    if path.endswith(".bat"):
        return launch_shell_in_directory(folder, shell="bash")

    bash = shutil.which("bash") or "/bin/bash"
    return launch_shell_in_directory(folder, shell="bash") or subprocess.Popen(
        [bash, path],
        cwd=folder,
        start_new_session=True,
    )
