"""Smoke-тесты gate первого запуска (runtime / winws)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_startup_uses_has_runtime_installation():
    text = (ROOT / "ZapretDesktop.py").read_text(encoding="utf-8")
    assert "has_runtime_installation()" in text
    assert "elif not has_runtime_installation()" in text


def test_has_runtime_installation_checks_winws_binary():
    text = (ROOT / "src" / "shared" / "lib" / "path_utils.py").read_text(encoding="utf-8")
    assert "winws.exe" in text
    assert "service.bat" in text
