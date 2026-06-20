"""Linux paths for editor, bin, and strategy resolution."""
from __future__ import annotations

from unittest.mock import patch

from src.features.editor.lib.editor_paths import resolve_strategy_bat_path


def test_resolve_strategy_bat_path_custom_and_repo(tmp_path):
    runtime = tmp_path / "runtime"
    custom = runtime / "custom-strategies"
    repo = runtime / "zapret-latest"
    custom.mkdir(parents=True)
    repo.mkdir(parents=True)
    (custom / "mine.bat").write_text("@echo off\n", encoding="utf-8")
    (repo / "general.bat").write_text("@echo off\n", encoding="utf-8")

    with patch("src.platform.is_linux", return_value=True):
        mine = resolve_strategy_bat_path(str(runtime), "mine")
        general = resolve_strategy_bat_path(str(runtime), "general")
        assert mine.replace("\\", "/").endswith("custom-strategies/mine.bat")
        assert general.replace("\\", "/").endswith("zapret-latest/general.bat")
        assert resolve_strategy_bat_path(str(runtime), "missing") == ""


def test_resolve_strategy_bat_path_windows_root(tmp_path):
    runtime = tmp_path / "winws"
    runtime.mkdir()
    (runtime / "general.bat").write_text("@echo off\n", encoding="utf-8")

    with patch("src.platform.is_linux", return_value=False):
        path = resolve_strategy_bat_path(str(runtime), "general")
        assert path == str(runtime / "general.bat")
