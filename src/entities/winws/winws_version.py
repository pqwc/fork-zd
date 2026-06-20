import os
import re
from typing import Any, Optional, Iterable


_LOCAL_VERSION_PATTERNS = [
    # set "LOCAL_VERSION=1.9.7"
    re.compile(r'^\s*@?\s*set\s+"LOCAL_VERSION=([^"]+)"\s*$', re.IGNORECASE),
    # set LOCAL_VERSION=1.9.7
    re.compile(r'^\s*@?\s*set\s+LOCAL_VERSION=([^\s"]+)\s*$', re.IGNORECASE),
]


def _iter_candidate_service_paths(winws_root: str) -> Iterable[str]:
    """
    Генерирует пути-кандидаты к service.bat.
    Поддерживает ситуации, когда передали:
    - корень winws
    - папку bin
    - путь к winws.exe
    """
    if not winws_root:
        return

    p = os.path.abspath(winws_root)

    # Если передан файл (например, ...\bin\winws.exe) — берём папку файла
    if os.path.isfile(p):
        p = os.path.dirname(p)

    # 1) service.bat в текущей папке
    yield os.path.join(p, "service.bat")

    # Linux-адаптер: zapret-latest/service.bat (~/zapret-linux/zapret-latest)
    yield os.path.join(p, "zapret-latest", "service.bat")

    # 2) Если это папка bin — поднимаемся на уровень вверх
    if os.path.basename(p).lower() == "bin":
        yield os.path.join(os.path.dirname(p), "service.bat")

    # 3) На всякий случай — поднимаемся ещё на уровень вверх
    yield os.path.join(os.path.dirname(p), "service.bat")
    yield os.path.join(os.path.dirname(os.path.dirname(p)), "service.bat")


def read_local_version_from_service(service_bat_path: str) -> Optional[str]:
    """
    Возвращает значение LOCAL_VERSION из service.bat (строка вида: set "LOCAL_VERSION=1.9.7").
    """
    if not service_bat_path or not os.path.exists(service_bat_path):
        return None
    # service.bat обычно ASCII/ANSI; на всякий случай пробуем несколько кодировок.
    encodings = ("utf-8", "cp1251", "cp866", "latin-1")
    for enc in encodings:
        try:
            with open(service_bat_path, "r", encoding=enc, errors="ignore") as f:
                for _ in range(400):
                    line = f.readline()
                    if not line:
                        break
                    s = line.strip()
                    for rx in _LOCAL_VERSION_PATTERNS:
                        m = rx.match(s)
                        if m:
                            return m.group(1).strip()
        except Exception:
            continue
    return None


def read_local_version_from_winws_root(winws_root: str) -> Optional[str]:
    """
    Ищет service.bat и возвращает LOCAL_VERSION.
    На Linux приоритет: zapret-latest/service.bat.
    """
    if not winws_root:
        return None
    from src.platform import is_linux

    if is_linux():
        preferred = os.path.join(winws_root, "zapret-latest", "service.bat")
        version = read_local_version_from_service(preferred)
        if version:
            return version
    for candidate in _iter_candidate_service_paths(winws_root):
        version = read_local_version_from_service(candidate)
        if version:
            return version
    return None


def write_local_version_to_service(service_bat_path: str, version: str) -> bool:
    """Обновляет или добавляет строку LOCAL_VERSION в service.bat."""
    if not service_bat_path or not version or not os.path.isfile(service_bat_path):
        return False
    encodings = ("utf-8", "cp1251", "cp866", "latin-1")
    content = None
    used_encoding = "utf-8"
    for enc in encodings:
        try:
            with open(service_bat_path, "r", encoding=enc, errors="replace") as f:
                content = f.read()
            used_encoding = enc
            break
        except OSError:
            continue
    if content is None:
        return False

    lines = content.splitlines(keepends=True)
    replaced = False
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        matched = any(rx.match(stripped) for rx in _LOCAL_VERSION_PATTERNS)
        if matched:
            new_lines.append(f'set "LOCAL_VERSION={version}"\r\n')
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        insert_at = 0
        if new_lines and new_lines[0].strip().lower().startswith("@echo"):
            insert_at = 1
        new_lines.insert(insert_at, f'set "LOCAL_VERSION={version}"\r\n')

    try:
        with open(service_bat_path, "w", encoding=used_encoding, newline="") as f:
            f.writelines(new_lines)
        return True
    except OSError:
        return False


def write_local_version_to_winws_root(winws_root: str, version: str) -> bool:
    """Записывает LOCAL_VERSION в service.bat установки zapret."""
    if not winws_root or not version:
        return False
    from src.platform import is_linux

    if is_linux():
        candidates = [
            os.path.join(winws_root, "zapret-latest", "service.bat"),
            os.path.join(winws_root, "service.bat"),
        ]
    else:
        candidates = list(_iter_candidate_service_paths(winws_root))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return write_local_version_to_service(candidate, version)
    return False


def is_valid_winws_root(winws_root: str) -> bool:
    """Корень установки zapret winws: service.bat и bin/winws.exe."""
    if not winws_root or not os.path.isdir(winws_root):
        return False
    service = os.path.join(winws_root, "service.bat")
    winws_exe = os.path.join(winws_root, "bin", "winws.exe")
    return os.path.isfile(service) and os.path.isfile(winws_exe)


def _winws_root_from_filesystem_path(path: str) -> Optional[str]:
    """Возвращает корень winws, если path указывает на корень или bin/winws.exe."""
    if not path:
        return None
    p = os.path.abspath(path)
    if os.path.isfile(p):
        p = os.path.dirname(p)
    if os.path.basename(p).lower() == "bin":
        root = os.path.dirname(p)
        if is_valid_winws_root(root):
            return root
    if is_valid_winws_root(p):
        return p
    return None


def _same_winws_exe(process_exe: str, winws_root: str) -> bool:
    expected = os.path.join(winws_root, "bin", "winws.exe")
    if not process_exe or not os.path.isfile(expected):
        return False
    try:
        return os.path.samefile(process_exe, expected)
    except OSError:
        return (
            os.path.normcase(os.path.abspath(process_exe))
            == os.path.normcase(os.path.abspath(expected))
        )


def resolve_winws_root_from_process(proc: Any) -> Optional[str]:
    """
    Определяет корень zapret winws по процессу winws.exe.
    На Linux — корень zapret-linux при процессе nfqws.
    Возвращает None для «чужого» exe без layout service.bat + bin/winws.exe.
    """
    from src.platform import is_linux
    from src.shared.lib.path_utils import get_winws_path, validate_linux_runtime_folder

    if is_linux():
        try:
            name = (proc.name() or "").lower()
            cmdline = " ".join(proc.cmdline() or []).lower()
            if name not in ("nfqws",) and "nfqws" not in cmdline:
                return None
        except Exception:
            return None
        root = get_winws_path()
        ok, _ = validate_linux_runtime_folder(root)
        return root if ok else None

    process_exe = None
    try:
        process_exe = proc.exe()
    except Exception:
        process_exe = None

    if process_exe:
        root = _winws_root_from_filesystem_path(process_exe)
        if root and _same_winws_exe(process_exe, root):
            return root

    try:
        cwd = proc.cwd()
    except Exception:
        cwd = None
    if cwd and is_valid_winws_root(cwd):
        if process_exe and _same_winws_exe(process_exe, cwd):
            return cwd

    return None

