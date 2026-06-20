"""
Утилита для определения правильных путей к файлам и папкам приложения.
Работает как при обычном запуске, так и после компиляции (PyInstaller).
"""
import os
import sys


def get_base_path():
    """
    Возвращает базовую директорию приложения.

    Для PyInstaller (скомпилированное приложение):
    - sys._MEIPASS содержит временную папку с распакованными файлами
    - sys.executable содержит путь к .exe файлу
    - Базовая директория - это директория, где находится .exe файл

    Для обычного запуска:
    - Базовая директория - это директория, где находится main.py (корень проекта)
    """
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(os.path.abspath(sys.executable))
    else:
        _here = os.path.abspath(__file__)
        for _ in range(3):
            _here = os.path.dirname(_here)
        base_path = _here
    return base_path


def get_resource_path(relative_path):
    """
    Возвращает абсолютный путь к ресурсу.

    Для PyInstaller:
    - Ресурсы могут быть в sys._MEIPASS (временная папка) или рядом с .exe

    Args:
        relative_path: Относительный путь к ресурсу (например, "resources/assets/icon.ico")

    Returns:
        Абсолютный путь к ресурсу
    """
    base_path = get_base_path()

    resource_path = os.path.join(base_path, relative_path)
    if os.path.exists(resource_path):
        return resource_path

    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        resource_path = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(resource_path):
            return resource_path

    return os.path.join(base_path, relative_path)


def get_appdata_config_dir():
    """
    Каталог настроек пользователя.
    Windows: %APPDATA%\\ZapretDesktop
    Linux:   $XDG_CONFIG_HOME/ZapretDesktop (~/.config/ZapretDesktop)
    """
    from src.platform import get_paths_backend

    return get_paths_backend().get_config_dir()


def get_config_path(relative_path="config.json"):
    """
    Возвращает путь к файлу конфигурации.

    Args:
        relative_path: Имя файла или относительный путь внутри каталога настроек

    Returns:
        Абсолютный путь к файлу конфигурации
    """
    from src.platform import get_paths_backend

    return get_paths_backend().get_config_path(relative_path)


WINWS_EXE_REL = os.path.join("bin", "winws.exe")


def validate_winws_folder(path: str) -> tuple[bool, str]:
    """
    Проверяет папку winws (Windows). Пустая строка — допустима (путь по умолчанию).
    Возвращает (ok, reason): reason — ``missing_exe`` | ``not_directory`` | ``""``.
    """
    from src.platform import get_paths_backend

    return get_paths_backend().validate_runtime_folder(path)


def validate_linux_runtime_folder(path: str) -> tuple[bool, str]:
    """Проверяет каталог Linux-адаптера (наличие service.sh)."""
    from src.platform import get_paths_backend

    return get_paths_backend().validate_runtime_folder(path)


def has_runtime_installation() -> bool:
    """True, если runtime (winws или zapret-linux) настроен."""
    from src.platform import is_linux

    root = get_winws_path()
    if is_linux():
        ok, _ = validate_linux_runtime_folder(root)
        return ok
    if not os.path.isdir(root):
        return False
    return (
        os.path.isfile(os.path.join(root, "service.bat"))
        or os.path.isfile(os.path.join(root, "bin", "winws.exe"))
    )


def get_winws_path():
    """
    Возвращает путь к корню runtime.
    Windows: папка winws с bin/winws.exe
    Linux:   каталог zapret-linux с service.sh
    """
    from src.platform import get_paths_backend

    return get_paths_backend().get_runtime_path()
