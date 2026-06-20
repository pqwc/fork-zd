"""Тесты merge/rollback ZapretUpdater."""
from __future__ import annotations

import os
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.entities.zapret.zapret_updater import ZapretUpdater


@pytest.fixture
def winws_tree(tmp_path):
    root = tmp_path / "winws"
    root.mkdir()
    (root / "general.bat").write_text("@echo off\n", encoding="utf-8")
    (root / "lists").mkdir()
    (root / "lists" / "list.txt").write_text("keep-me\n", encoding="utf-8")
    return root


def _make_zip(tmp_path: Path, inner_name: str = "general.bat") -> str:
    zpath = tmp_path / "update.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr(inner_name, "@echo off\nrem updated\n")
    return str(zpath)


@patch("src.platform.is_linux", return_value=False)
@patch("time.sleep", return_value=None)
def test_merge_updates_bat_file(_sleep, _linux, tmp_path, winws_tree):
    updater = ZapretUpdater.__new__(ZapretUpdater)
    updater.WINWS_FOLDER = str(winws_tree)
    updater.current_version = "1.0.0"
    updater.save_version = lambda _v: None  # type: ignore[method-assign]

    zip_path = _make_zip(tmp_path)
    updater._do_extract_and_merge(zip_path)

    content = (winws_tree / "general.bat").read_text(encoding="utf-8")
    assert "rem updated" in content
    assert (winws_tree / "lists" / "list.txt").read_text(encoding="utf-8") == "keep-me\n"


@patch("src.platform.is_linux", return_value=False)
@patch("time.sleep", return_value=None)
def test_merge_rollback_on_failure(_sleep, _linux, tmp_path, winws_tree):
    updater = ZapretUpdater.__new__(ZapretUpdater)
    updater.WINWS_FOLDER = str(winws_tree)
    original = (winws_tree / "general.bat").read_text(encoding="utf-8")

    zip_path = _make_zip(tmp_path)

    def _fail_copy(*_args, **_kwargs):
        raise PermissionError("denied")

    with patch("shutil.copy2", side_effect=_fail_copy):
        with pytest.raises(Exception, match="Ошибка при обновлении"):
            updater._do_extract_and_merge(zip_path)

    assert (winws_tree / "general.bat").read_text(encoding="utf-8") == original
    backup = f"{winws_tree}_backup"
    assert not os.path.exists(backup) or os.path.isdir(backup)
