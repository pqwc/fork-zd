"""Export bundle paths on Linux layout."""
from __future__ import annotations

import os
import zipfile
from unittest.mock import patch

from src.features.export.export_bundle import ExportOptions, build_export_zip, _linux_strategy_bat_files


def test_linux_strategy_bat_files_prefers_custom_over_repo(tmp_path):
    runtime = tmp_path / "zapret-linux"
    custom = runtime / "custom-strategies"
    repo = runtime / "zapret-latest"
    custom.mkdir(parents=True)
    repo.mkdir(parents=True)
    (custom / "mine.bat").write_text("@echo off\n", encoding="utf-8")
    (repo / "mine.bat").write_text("@echo off\nrepo\n", encoding="utf-8")
    (repo / "other.bat").write_text("@echo off\n", encoding="utf-8")

    paths = _linux_strategy_bat_files(str(runtime))
    names = {os.path.basename(p) for p in paths}
    assert names == {"mine.bat", "other.bat"}
    mine = next(p for p in paths if os.path.basename(p) == "mine.bat")
    assert mine.startswith(str(custom))


@patch("src.platform.is_linux", return_value=True)
def test_build_export_zip_linux_layout(_is_linux, tmp_path):
    runtime = tmp_path / "zapret-linux"
    repo = runtime / "zapret-latest"
    lists = repo / "lists"
    bin_dir = repo / "bin"
    lists.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (repo / "general.bat").write_text("@echo off\n", encoding="utf-8")
    (lists / "list.txt").write_text("example.com\n", encoding="utf-8")
    (bin_dir / "file.bin").write_bytes(b"\x00")
    (repo / "service.bat").write_text('set "LOCAL_VERSION=1.0"\n', encoding="utf-8")

    runtime_str = str(runtime)
    dest = tmp_path / "out.zip"
    count, err = build_export_zip(
        str(dest),
        ExportOptions(strategies=True, lists=True, bin=True, config=False, zapret=False),
        winws_folder=runtime_str,
    )
    assert err is None
    assert count >= 3
    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
    assert "strategies/general.bat" in names
    assert any(n.startswith("lists/") and n.endswith("list.txt") for n in names)
    assert any(n.startswith("bin/") and n.endswith("file.bin") for n in names)
