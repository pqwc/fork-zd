"""
Загрузка и кэш VS Code Codicons (@vscode/codicons) в AppData.

При первом запуске скачиваются только иконки, используемые приложением.
При ошибке сети используются встроенные fallback-иконки из embedded_assets.
"""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path

import requests

from src.shared.lib.path_utils import get_appdata_config_dir
from src.shared.lib.app_logging import setup_logging

logger = setup_logging()

CODICONS_VERSION = "0.0.45"
GITHUB_RAW_BASE = (
    f"https://raw.githubusercontent.com/microsoft/vscode-codicons/v{CODICONS_VERSION}/src/icons"
)

# Внутренние имена проекта -> имена файлов codicons (полный набор, используемый в UI)
ICON_ALIASES: dict[str, str] = {
    "add": "add",
    "broadcast": "broadcast",
    "check": "check",
    "chevron-down": "chevron-down",
    "chevron-right": "chevron-right",
    "close": "close",
    "debug-continue": "debug-continue",
    "debug-pause": "debug-pause",
    "debug-stop": "debug-stop",
    "edit": "edit",
    "file-code": "file-code",
    "folder": "folder",
    "folder-opened": "folder-opened",
    "globe": "globe",
    "go-to-file": "go-to-file",
    "list-tree": "list-tree",
    "output": "output",
    "play": "play",
    "plug": "plug",
    "refresh": "refresh",
    "repo-forked": "repo-forked",
    "settings-gear": "settings-gear",
    "star-empty": "star-empty",
    "star-full": "star-full",
    "terminal": "terminal",
    "trash": "trash",
}

REQUIRED_ICONS = tuple(ICON_ALIASES.keys())
_download_lock = threading.Lock()
_download_started = False


def _codicons_root() -> str:
    return os.path.join(get_appdata_config_dir(), "codicons")


def _icons_dir() -> str:
    return os.path.join(_codicons_root(), "icons")


def _version_file() -> str:
    return os.path.join(_codicons_root(), "version.txt")


def _expected_marker() -> str:
    return f"{CODICONS_VERSION}:{len(REQUIRED_ICONS)}"


def _codicon_filename(name: str) -> str:
    codicon = ICON_ALIASES.get(name, name)
    return f"{codicon}.svg"


def _icon_file_path(name: str) -> str:
    return os.path.join(_icons_dir(), _codicon_filename(name))


def _all_required_present() -> bool:
    return all(os.path.isfile(_icon_file_path(name)) for name in REQUIRED_ICONS)


def is_installed() -> bool:
    """True если все необходимые codicons скачаны и версия актуальна."""
    if not _all_required_present():
        return False
    try:
        with open(_version_file(), encoding="utf-8") as f:
            return f.read().strip() == _expected_marker()
    except OSError:
        return False


def get_icon_path(name: str, *, allow_download: bool = True) -> str | None:
    """Абсолютный путь к SVG codicon или None."""
    path = _icon_file_path(name)
    if os.path.isfile(path):
        return path
    if allow_download:
        with _download_lock:
            if os.path.isfile(path):
                return path
            _download_icon(name)
    return path if os.path.isfile(path) else None


def _apply_svg_color(svg_bytes: bytes, color: str) -> bytes:
    text = svg_bytes.decode("utf-8")
    text = text.replace("currentColor", color)
    # Старые codicons иногда без fill — задаём на корневом svg
    if 'fill="' not in text.split(">", 1)[0]:
        text = re.sub(
            r"(<svg\b[^>]*)(>)",
            rf'\1 fill="{color}"\2',
            text,
            count=1,
        )
    return text.encode("utf-8")


def get_svg_bytes(name: str, color: str | None = None) -> bytes | None:
    """Читает codicon SVG с диска, опционально перекрашивает."""
    path = get_icon_path(name)
    if not path:
        return None
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    if color:
        data = _apply_svg_color(data, color)
    return data


def _write_version_marker() -> None:
    os.makedirs(_codicons_root(), exist_ok=True)
    with open(_version_file(), "w", encoding="utf-8") as f:
        f.write(_expected_marker())


def _download_icon(name: str) -> bool:
    """Скачивает одну иконку с GitHub, если её ещё нет на диске."""
    path = _icon_file_path(name)
    if os.path.isfile(path):
        return True
    codicon = ICON_ALIASES.get(name, name)
    url = f"{GITHUB_RAW_BASE}/{codicon}.svg"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        os.makedirs(_icons_dir(), exist_ok=True)
        with open(path, "wb") as f:
            f.write(resp.content)
        return True
    except Exception as exc:
        logger.warning("Не удалось скачать codicon %s: %s", codicon, exc)
        return False


def _download_required_icons() -> bool:
    """Загрузка всех иконок, используемых приложением."""
    os.makedirs(_icons_dir(), exist_ok=True)
    ok = 0
    for name in REQUIRED_ICONS:
        if _download_icon(name):
            ok += 1
    if ok == len(REQUIRED_ICONS):
        _write_version_marker()
        logger.info("Codicons установлены: %s иконок", ok)
        return True
    logger.warning("Codicons: скачано %s из %s", ok, len(REQUIRED_ICONS))
    return False


def ensure_codicons(blocking: bool = True) -> bool:
    """
    Гарантирует наличие необходимых codicons.

    blocking=True: синхронная загрузка недостающих иконок.
    blocking=False: запускает фоновую догрузку недостающих иконок.
    """
    global _download_started

    if is_installed():
        return True

    with _download_lock:
        if is_installed():
            return True

        if blocking:
            return _download_required_icons()

        if _download_started:
            return _all_required_present()
        _download_started = True

    threading.Thread(target=_download_required_icons, daemon=True).start()
    return False


def ensure_codicons_background() -> None:
    """Фоновая догрузка недостающих иконок (если ещё не установлены)."""
    if is_installed():
        return
    threading.Thread(target=_download_required_icons, daemon=True).start()


def install_codicons_full() -> bool:
    """Синхронная установка всех необходимых codicons (для скриптов / первого запуска)."""
    if is_installed():
        return True
    return _download_required_icons()


def list_installed_icons() -> list[str]:
    icons = _icons_dir()
    if not os.path.isdir(icons):
        return []
    return sorted(p.stem for p in Path(icons).glob("*.svg"))


def get_themed_svg_bytes(name: str) -> bytes | None:
    """SVG codicon в цвете текущей темы."""
    try:
        from src.shared.ui import theme as ui_theme

        color = ui_theme.palette().fg_text
    except Exception:
        color = "#ececec"
    return get_svg_bytes(name, color=color)
