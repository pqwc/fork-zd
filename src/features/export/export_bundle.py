"""Сборка zip-архива с данными стратегии / winws / конфигурации."""
from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass

from src.shared.lib.path_utils import get_appdata_config_dir, get_winws_path


@dataclass
class ExportOptions:
    strategies: bool = True
    lists: bool = True
    bin: bool = True
    config: bool = True
    zapret: bool = True


def _add_path_to_zip(
    zf: zipfile.ZipFile,
    source_path: str,
    arc_prefix: str,
    counter: list[int],
) -> None:
    if os.path.isfile(source_path):
        arcname = os.path.join(arc_prefix, os.path.basename(source_path)).replace("\\", "/")
        zf.write(source_path, arcname)
        counter[0] += 1
        return
    if not os.path.isdir(source_path):
        return
    for root, _dirs, files in os.walk(source_path):
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, source_path)
            arcname = os.path.join(arc_prefix, rel).replace("\\", "/")
            zf.write(full, arcname)
            counter[0] += 1


def _strategy_bat_files(winws_folder: str) -> list[str]:
    bats: list[str] = []
    if not os.path.isdir(winws_folder):
        return bats
    for name in os.listdir(winws_folder):
        if name.lower().endswith(".bat") and name.lower() != "service.bat":
            bats.append(os.path.join(winws_folder, name))
    return sorted(bats)


def _linux_strategy_bat_files(runtime_root: str) -> list[str]:
    repo = os.path.join(runtime_root, "zapret-latest")
    by_name: dict[str, str] = {}
    folders = (
        os.path.join(runtime_root, "custom-strategies"),
        repo,
        runtime_root,
    )
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if not name.lower().endswith(".bat") or name.lower() == "service.bat":
                continue
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                by_name.setdefault(name.lower(), path)
    return sorted(by_name.values(), key=lambda p: os.path.basename(p).lower())


def _export_paths(runtime_root: str) -> tuple[str, str, str, str]:
    """(strategies_scan_root, lists_dir, bin_dir, zapret_extra_root)."""
    from src.platform import is_linux

    if not is_linux():
        return runtime_root, os.path.join(runtime_root, "lists"), os.path.join(runtime_root, "bin"), runtime_root

    repo = os.path.join(runtime_root, "zapret-latest")
    lists_dir = os.path.join(repo, "lists")
    if not os.path.isdir(lists_dir):
        user_lists = os.path.join(runtime_root, "user-lists")
        if os.path.isdir(user_lists):
            lists_dir = user_lists
    bin_dir = os.path.join(repo, "bin")
    if not os.path.isdir(bin_dir):
        bin_dir = os.path.join(runtime_root, "bin")
    return runtime_root, lists_dir, bin_dir, repo


def _zapret_extra_paths(winws_folder: str) -> list[str]:
    """Файлы и папки winws, не покрытые strategies/lists/bin."""
    skip_dirs = {"bin", "lists", "__pycache__"}
    paths: list[str] = []
    if not os.path.isdir(winws_folder):
        return paths
    for name in os.listdir(winws_folder):
        full = os.path.join(winws_folder, name)
        if os.path.isfile(full):
            if name.lower().endswith(".bat"):
                continue
            paths.append(full)
        elif os.path.isdir(full) and name not in skip_dirs:
            paths.append(full)
    return sorted(paths, key=lambda p: (not os.path.isfile(p), os.path.basename(p).lower()))


def build_export_zip(
    dest_zip: str,
    options: ExportOptions,
    winws_folder: str | None = None,
    config_dir: str | None = None,
) -> tuple[int, str | None]:
    """
    Создаёт zip по выбранным секциям.
    Возвращает (число файлов, текст ошибки или None).
    """
    from src.platform import is_linux

    runtime = winws_folder or get_winws_path()
    _strategies_root, lists_dir, bin_dir, zapret_root = _export_paths(runtime)
    cfg_dir = config_dir or get_appdata_config_dir()
    counter = [0]

    if not any(
        [
            options.strategies,
            options.lists,
            options.bin,
            options.config,
            options.zapret,
        ]
    ):
        return 0, "nothing_selected"

    try:
        with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            if options.strategies:
                bats = (
                    _linux_strategy_bat_files(runtime)
                    if is_linux()
                    else _strategy_bat_files(_strategies_root)
                )
                for bat in bats:
                    arc = os.path.join("strategies", os.path.basename(bat))
                    zf.write(bat, arc.replace("\\", "/"))
                    counter[0] += 1

            if options.lists:
                _add_path_to_zip(zf, lists_dir, "lists", counter)

            if options.bin:
                _add_path_to_zip(zf, bin_dir, "bin", counter)

            if options.config and os.path.isdir(cfg_dir):
                _add_path_to_zip(zf, cfg_dir, "config", counter)

            if options.zapret:
                for path in _zapret_extra_paths(zapret_root):
                    if os.path.isfile(path):
                        arc = os.path.join("zapret", os.path.basename(path))
                        zf.write(path, arc.replace("\\", "/"))
                        counter[0] += 1
                    else:
                        _add_path_to_zip(zf, path, os.path.join("zapret", os.path.basename(path)), counter)

        if counter[0] == 0:
            return 0, "empty"
        return counter[0], None
    except OSError as exc:
        return 0, str(exc)
