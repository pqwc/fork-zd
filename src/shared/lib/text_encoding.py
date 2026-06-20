"""Чтение текстовых файлов с определением кодировки."""
from __future__ import annotations

import locale
import os
from typing import Optional


def encoding_name_to_codec(name: str) -> str:
    mapping = {
        "UTF-8": "utf-8",
        "UTF-8 BOM": "utf-8-sig",
        "Windows-1251": "cp1251",
    }
    return mapping.get(name, name or "utf-8")


def read_text_file(
    path: str,
    *,
    encoding: Optional[str] = None,
    fallback_encodings: Optional[list[str]] = None,
) -> tuple[str, str, bool]:
    """
    Читает текстовый файл.

    Returns:
        (text, codec_used, decode_issues) — decode_issues True, если использован errors=replace.
    """
    if not path or not os.path.isfile(path):
        return "", encoding or "utf-8", False

    with open(path, "rb") as f:
        raw = f.read()

    if not raw:
        return "", encoding or "utf-8", False

    candidates: list[str] = []
    if encoding:
        candidates.append(encoding_name_to_codec(encoding))
    if fallback_encodings:
        candidates.extend(fallback_encodings)
    else:
        pref = locale.getpreferredencoding(False) or "cp1251"
        candidates.extend(["utf-8-sig", "utf-8", "cp1251", pref])

    seen: set[str] = set()
    ordered: list[str] = []
    for enc in candidates:
        enc = (enc or "").strip()
        if not enc or enc in seen:
            continue
        seen.add(enc)
        ordered.append(enc)

    for enc in ordered:
        try:
            return raw.decode(enc, errors="strict"), enc, False
        except UnicodeDecodeError:
            continue

    enc = ordered[-1] if ordered else "utf-8"
    text = raw.decode(enc, errors="replace")
    return text, enc, True
