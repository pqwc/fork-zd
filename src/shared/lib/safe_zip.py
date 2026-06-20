"""Безопасная распаковка ZIP (защита от path traversal)."""
from __future__ import annotations

import os
import zipfile


def safe_extractall(zip_ref: zipfile.ZipFile, dest_dir: str) -> None:
    dest_abs = os.path.abspath(dest_dir)
    os.makedirs(dest_abs, exist_ok=True)
    prefix = dest_abs + os.sep
    for member in zip_ref.namelist():
        if member.endswith("/"):
            continue
        target = os.path.abspath(os.path.join(dest_abs, member))
        if target != dest_abs and not target.startswith(prefix):
            raise ValueError(f"Unsafe zip entry path: {member}")
    zip_ref.extractall(dest_abs)
