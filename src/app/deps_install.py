"""Установка Python-зависимостей из requirements.txt (запуск из исходников)."""
from __future__ import annotations

import os
import subprocess
import sys

_INSTALL_FLAGS = ("--install-deps", "-d")


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def requirements_path() -> str:
    return os.path.join(project_root(), "requirements.txt")


def has_install_deps_flag(argv: list[str] | None = None) -> bool:
    args = argv if argv is not None else sys.argv[1:]
    for arg in args:
        if arg in _INSTALL_FLAGS:
            return True
        for flag in _INSTALL_FLAGS:
            if arg.startswith(f"{flag}="):
                return True
    return False


def should_skip_bootstrap(argv: list[str] | None = None) -> bool:
    args = argv if argv is not None else sys.argv[1:]
    return any(arg in ("--help", "-h") for arg in args)


def missing_required_modules() -> list[str]:
    required = ("PyQt6", "psutil", "requests")
    missing: list[str] = []
    for name in required:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    return missing


def install_project_dependencies(*, quiet: bool = False) -> tuple[bool, str]:
    """pip install -r requirements.txt. Для frozen-сборок — no-op."""
    if is_frozen():
        return True, "skipped: bundled executable"

    req_path = requirements_path()
    if not os.path.isfile(req_path):
        return False, f"requirements.txt not found: {req_path}"

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "-r", req_path]
    if quiet:
        cmd.append("-q")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "pip install timed out"
    except OSError as exc:
        return False, str(exc)

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        return False, detail or f"pip exited with code {proc.returncode}"
    return True, "ok"


def early_bootstrap(argv: list[str] | None = None) -> None:
    """Вызывается до import PyQt6 при `python ZapretDesktop.py --install-deps`."""
    args = argv if argv is not None else sys.argv[1:]
    if should_skip_bootstrap(args) or not has_install_deps_flag(args):
        return
    if is_frozen():
        print("[deps] skipped: dependencies are bundled in this build", file=sys.stderr)
        return

    print("[deps] installing from requirements.txt …")
    ok, message = install_project_dependencies(quiet=False)
    if not ok:
        print(f"[deps] failed: {message}", file=sys.stderr)
        sys.exit(1)
    still_missing = missing_required_modules()
    if still_missing:
        print(
            f"[deps] warning: after install still missing: {', '.join(still_missing)}",
            file=sys.stderr,
        )
    else:
        print("[deps] done")
