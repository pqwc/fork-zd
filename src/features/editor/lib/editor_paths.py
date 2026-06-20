"""Пути и файлы редактора списков / hosts / стратегий (Windows и Linux)."""
from __future__ import annotations

import os

from src.shared.lib.path_utils import get_winws_path


def get_editor_bin_folder() -> str:
    """Каталог bin: на Linux предпочитает zapret-latest/bin."""
    from src.platform import is_linux

    runtime = get_winws_path()
    if not is_linux():
        return os.path.join(runtime, "bin")

    from src.platform.linux.linux_runtime_manager import LinuxRuntimeManager

    mgr = LinuxRuntimeManager()
    bin_in_repo = os.path.join(mgr.repo_dir, "bin")
    if os.path.isdir(bin_in_repo):
        return bin_in_repo
    fallback = os.path.join(runtime, "bin")
    return fallback


def resolve_strategy_bat_path(runtime_root: str, name: str) -> str:
    """Абсолютный путь к .bat стратегии или пустая строка."""
    if not runtime_root or not name:
        return ""
    from src.platform import is_linux

    base = name if name.endswith(".bat") else f"{name}.bat"
    if is_linux():
        candidates = [
            os.path.join(runtime_root, "custom-strategies", base),
            os.path.join(runtime_root, "zapret-latest", base),
            os.path.join(runtime_root, base),
        ]
        return next((p for p in candidates if os.path.isfile(p)), "")
    path = os.path.join(runtime_root, base)
    return path if os.path.isfile(path) else ""


def get_editor_lists_folder() -> str:
    from src.platform import is_linux

    runtime = get_winws_path()
    if is_linux():
        from src.platform.linux.linux_runtime_manager import LinuxRuntimeManager

        return LinuxRuntimeManager().lists_folder
    return os.path.join(runtime, "lists")


def get_editor_bat_setup() -> tuple[str, list[str], dict[str, str]]:
    """
    Возвращает (cwd для терминала, имена .bat, карта имя -> абсолютный путь).
    """
    from src.platform import is_linux

    runtime = get_winws_path()
    if not is_linux():
        names = _bat_files_in_folder(runtime)
        return runtime, names, {name: os.path.join(runtime, name) for name in names}

    from src.platform.linux.linux_runtime_manager import LinuxRuntimeManager

    mgr = LinuxRuntimeManager()
    names = mgr.list_strategy_files()
    paths: dict[str, str] = {}
    custom = os.path.join(runtime, "custom-strategies")
    repo = mgr.repo_dir
    for name in names:
        for base in (custom, repo, runtime):
            candidate = os.path.join(base, name)
            if os.path.isfile(candidate):
                paths[name] = candidate
                break

    service_sh = os.path.join(runtime, "service.sh")
    cwd = runtime if os.path.isfile(service_sh) else (repo if os.path.isdir(repo) else runtime)
    return cwd, names, paths


def resolve_editor_file_path(folder: str, filename: str, file_paths: dict[str, str] | None) -> str:
    if file_paths and filename in file_paths:
        return file_paths[filename]
    return os.path.join(folder, filename)


def bat_run_terminal_command(bat_path: str, runtime_root: str | None = None) -> str:
    """Команда для запуска текущего .bat во встроенном терминале."""
    import sys

    full_path = os.path.abspath(bat_path)
    if sys.platform == "win32":
        return f'start "" "{full_path}"'

    runtime = runtime_root or get_winws_path()
    name = os.path.basename(full_path)
    service = os.path.join(runtime, "service.sh")
    if os.path.isfile(service):
        return f'./service.sh config set {name} && ./service.sh service restart'
    return f'echo "service.sh not found in {runtime}"'


def _bat_files_in_folder(winws_folder: str) -> list[str]:
    bat_files: list[str] = []
    if os.path.exists(winws_folder):
        for filename in os.listdir(winws_folder):
            if filename.endswith(".bat") and os.path.isfile(os.path.join(winws_folder, filename)):
                bat_files.append(filename)
        bat_files.sort()
    return bat_files
