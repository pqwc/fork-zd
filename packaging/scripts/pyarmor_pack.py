#!/usr/bin/env python3
"""Obfuscate application sources with PyArmor and pack with PyInstaller.

Ensures release artifacts contain only obfuscated bytecode — no plain .py sources.
"""
from __future__ import annotations

import argparse
import base64
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Only application code is obfuscated; dev/test tooling stays out of the bundle.
OBFUSCATE_PATHS = ("ZapretDesktop.py", "src")

# Paths allowed to contain .py inside dist (PyArmor runtime stubs only).
_RUNTIME_PY_ALLOWLIST = re.compile(r"pyarmor_runtime[^/\\]*[/\\].*\.py$", re.I)


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print(f"[pyarmor] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, check=True)


def _pyarmor_cmd() -> list[str]:
    """Resolve PyArmor CLI via ``python -m pyarmor.cli`` (works when Scripts/ is not on PATH)."""
    override = os.environ.get("PYARMOR_BIN", "").strip()
    if override:
        return [override]
    return [sys.executable, "-m", "pyarmor.cli"]


def _verify_dist(dist_dir: Path) -> None:
    """Fail the build if plain application sources leaked into dist."""
    if not dist_dir.is_dir():
        raise RuntimeError(f"dist directory missing: {dist_dir}")

    leaked: list[Path] = []
    for py_file in dist_dir.rglob("*.py"):
        rel = py_file.relative_to(dist_dir).as_posix()
        if _RUNTIME_PY_ALLOWLIST.search(rel):
            continue
        if rel.endswith("__init__.py") and "pyarmor_runtime" in rel:
            continue
        leaked.append(py_file)

    if leaked:
        sample = "\n  ".join(str(p.relative_to(PROJECT_ROOT)) for p in leaked[:10])
        raise RuntimeError(
            "Release verification failed: plain .py files found in dist "
            f"({len(leaked)} total). Sample:\n  {sample}"
        )

    print(f"[verify] OK — no plain application .py in {dist_dir.relative_to(PROJECT_ROOT)}")


def _register_pyarmor_license() -> None:
    """Register PyArmor from env before obfuscation (required for projects larger than trial)."""
    b64 = os.environ.get("PYARMOR_CI_REGFILE_B64", "").strip()
    reg_path = os.environ.get("PYARMOR_REGFILE", "").strip()

    if b64:
        reg_file = PROJECT_ROOT / ".pyarmor-regfile-ci.zip"
        reg_file.write_bytes(base64.b64decode(b64))
        try:
            _run([*_pyarmor_cmd(), "reg", str(reg_file)])
        finally:
            reg_file.unlink(missing_ok=True)
        return

    if reg_path:
        _run([*_pyarmor_cmd(), "reg", reg_path])
        return

    probe = subprocess.run(
        [*_pyarmor_cmd(), "-v"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{probe.stdout}\n{probe.stderr}".lower()
    if "trial" in output:
        print(
            "[WARN] PyArmor trial is active. Large projects fail with 'out of license'.\n"
            "       Local:  set PYARMOR_REGFILE=path\\to\\pyarmor-regfile-xxxx.zip\n"
            "       CI:     add GitHub secret PYARMOR_CI_REGFILE_B64 (base64 of pyarmor-ci-*.zip)"
        )


def _clean_intermediates() -> None:
    pyarmor_dir = PROJECT_ROOT / ".pyarmor"
    if pyarmor_dir.is_dir():
        shutil.rmtree(pyarmor_dir)
        print(f"[clean] removed {pyarmor_dir.relative_to(PROJECT_ROOT)}")

    for patched in PROJECT_ROOT.glob("*.patched.spec"):
        patched.unlink()
        print(f"[clean] removed {patched.name}")


def pack(
    spec: Path,
    *,
    clean_intermediates: bool = True,
    verify: bool = True,
    extra_pyarmor_args: list[str] | None = None,
) -> None:
    spec = spec.resolve()
    if not spec.is_file():
        raise FileNotFoundError(f"Spec file not found: {spec}")

    _register_pyarmor_license()

    obfuscate_targets = [str(PROJECT_ROOT / p) for p in OBFUSCATE_PATHS]

    cmd = [
        *_pyarmor_cmd(),
        "gen",
        "--pack",
        str(spec),
        "-r",
        *obfuscate_targets,
    ]
    if os.environ.get("PYARMOR_PRIVATE", "").strip() in ("1", "true", "yes"):
        cmd.insert(-len(obfuscate_targets), "--private")
    if extra_pyarmor_args:
        cmd.extend(extra_pyarmor_args)

    _run(cmd)

    dist_dir = PROJECT_ROOT / "dist"
    if verify:
        _verify_dist(dist_dir)

    if clean_intermediates:
        _clean_intermediates()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spec",
        type=Path,
        required=True,
        help="PyInstaller .spec file (e.g. ZapretDesktop-win.spec)",
    )
    parser.add_argument(
        "--keep-intermediates",
        action="store_true",
        help="Keep .pyarmor/ after build (debug only)",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip post-build check for plain .py in dist/",
    )
    parser.add_argument(
        "pyarmor_extra",
        nargs="*",
        help="Extra arguments forwarded to pyarmor gen",
    )
    args = parser.parse_args()

    try:
        pack(
            args.spec,
            clean_intermediates=not args.keep_intermediates,
            verify=not args.skip_verify,
            extra_pyarmor_args=args.pyarmor_extra or None,
        )
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] PyArmor/PyInstaller failed (exit {exc.returncode})", file=sys.stderr)
        return exc.returncode or 1
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print("[pyarmor] Pack completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
