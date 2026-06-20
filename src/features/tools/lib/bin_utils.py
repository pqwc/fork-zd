"""Утилиты для bin-файлов winws (fake TLS/QUIC/HTTP и др., bol-van/zapret)."""
from __future__ import annotations

import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable

ZAPRET_FAKE_BIN_BASE = "https://raw.githubusercontent.com/bol-van/zapret/master/files/fake"

# Популярные шаблоны из files/fake репозитория zapret
ZAPRET_TEMPLATE_BINS: tuple[str, ...] = (
    "tls_clienthello_www_google_com.bin",
    "tls_clienthello_iana_org.bin",
    "tls_clienthello_vk_com.bin",
    "quic_initial_www_google_com.bin",
    "quic_initial_vk_com.bin",
    "http_iana_org.bin",
    "zero_256.bin",
    "zero_512.bin",
    "zero_1024.bin",
    "stun.bin",
    "wireguard_initiation.bin",
    "dtls_clienthello_w3_org.bin",
)


@dataclass(frozen=True)
class BinFileInfo:
    name: str
    size: int
    category: str
    category_key: str
    winws_options: tuple[str, ...]
    description_key: str
    magic_hint: str = ""


def get_bin_folder(winws_folder: str | None = None) -> str:
    from src.features.editor.lib.editor_paths import get_editor_bin_folder
    from src.shared.lib.path_utils import get_winws_path

    if winws_folder is None:
        return get_editor_bin_folder()
    root = winws_folder
    if os.path.normpath(root) == os.path.normpath(get_winws_path()):
        return get_editor_bin_folder()
    return os.path.join(root, "bin")


def list_bin_files(bin_folder: str | None = None) -> list[str]:
    folder = bin_folder or get_bin_folder()
    if not os.path.isdir(folder):
        return []
    names = [
        name
        for name in os.listdir(folder)
        if name.lower().endswith(".bin") and os.path.isfile(os.path.join(folder, name))
    ]
    names.sort(key=str.lower)
    return names


def parse_hex_text(hex_text: str) -> bytes:
    hex_str = re.sub(r"[^0-9a-fA-F]", "", hex_text or "")
    if not hex_str:
        raise ValueError("empty")
    if len(hex_str) % 2 != 0:
        raise ValueError("odd")
    return bytes.fromhex(hex_str)


def format_bytes_as_hex(data: bytes, *, bytes_per_line: int = 16, uppercase: bool = True) -> str:
    if not data:
        return ""
    lines: list[str] = []
    for offset in range(0, len(data), bytes_per_line):
        chunk = data[offset : offset + bytes_per_line]
        parts = [f"{b:02X}" if uppercase else f"{b:02x}" for b in chunk]
        lines.append(" ".join(parts))
    return "\n".join(lines)


def normalize_bin_name(name: str, *, default: str = "custom.bin") -> str:
    value = (name or "").strip()
    if not value:
        value = default
    base = os.path.basename(value)
    if not base.lower().endswith(".bin"):
        base += ".bin"
    return base


def _match_prefix(name_lower: str, prefix: str) -> bool:
    return name_lower.startswith(prefix)


def analyze_bin_file(name: str, data: bytes | None = None) -> BinFileInfo:
    lower = (name or "").lower()
    size = len(data) if data is not None else 0
    magic_hint = ""
    if data:
        magic_hint = format_bytes_as_hex(data[:8], bytes_per_line=8)

    if _match_prefix(lower, "tls_clienthello"):
        return BinFileInfo(
            name=name,
            size=size,
            category="TLS ClientHello",
            category_key="bin_kind_tls",
            winws_options=("--dpi-desync-fake-tls", "--dpi-desync-fake-tls-mod"),
            description_key="bin_desc_tls",
            magic_hint=magic_hint,
        )
    if _match_prefix(lower, "quic_initial") or lower.startswith("quic_short"):
        return BinFileInfo(
            name=name,
            size=size,
            category="QUIC Initial",
            category_key="bin_kind_quic",
            winws_options=("--dpi-desync-fake-quic",),
            description_key="bin_desc_quic",
            magic_hint=magic_hint,
        )
    if _match_prefix(lower, "http_"):
        return BinFileInfo(
            name=name,
            size=size,
            category="HTTP",
            category_key="bin_kind_http",
            winws_options=("--dpi-desync-fake-http",),
            description_key="bin_desc_http",
            magic_hint=magic_hint,
        )
    if _match_prefix(lower, "dtls_"):
        return BinFileInfo(
            name=name,
            size=size,
            category="DTLS ClientHello",
            category_key="bin_kind_dtls",
            winws_options=("--dpi-desync-fake-unknown-udp",),
            description_key="bin_desc_dtls",
            magic_hint=magic_hint,
        )
    if _match_prefix(lower, "zero_"):
        return BinFileInfo(
            name=name,
            size=size,
            category="Zero padding",
            category_key="bin_kind_zero",
            winws_options=("--dpi-desync-split-seqovl-pattern",),
            description_key="bin_desc_zero",
            magic_hint=magic_hint,
        )
    if _match_prefix(lower, "wireguard_"):
        return BinFileInfo(
            name=name,
            size=size,
            category="WireGuard",
            category_key="bin_kind_wireguard",
            winws_options=("--dpi-desync-fake-unknown-udp",),
            description_key="bin_desc_wireguard",
            magic_hint=magic_hint,
        )
    if lower in ("stun.bin",) or "discord" in lower or lower.startswith("dht_"):
        return BinFileInfo(
            name=name,
            size=size,
            category="UDP / STUN / DHT",
            category_key="bin_kind_udp",
            winws_options=("--dpi-desync-fake-unknown-udp",),
            description_key="bin_desc_udp",
            magic_hint=magic_hint,
        )
    if _match_prefix(lower, "isakmp"):
        return BinFileInfo(
            name=name,
            size=size,
            category="ISAKMP",
            category_key="bin_kind_isakmp",
            winws_options=("--dpi-desync-fake-unknown-udp",),
            description_key="bin_desc_isakmp",
            magic_hint=magic_hint,
        )

    # Эвристика по содержимому
    if data and len(data) >= 3 and data[0] == 0x16 and data[1] == 0x03:
        return BinFileInfo(
            name=name,
            size=size,
            category="TLS ClientHello",
            category_key="bin_kind_tls",
            winws_options=("--dpi-desync-fake-tls", "--dpi-desync-fake-tls-mod"),
            description_key="bin_desc_tls",
            magic_hint=magic_hint,
        )

    return BinFileInfo(
        name=name,
        size=size,
        category="Custom",
        category_key="bin_kind_custom",
        winws_options=("--dpi-desync-fake-tls", "--dpi-desync-fake-quic", "--dpi-desync-fake-unknown-udp"),
        description_key="bin_desc_custom",
        magic_hint=magic_hint,
    )


def winws_arg_example(filename: str, info: BinFileInfo) -> str:
    from src.platform import is_linux

    name = os.path.basename(filename)
    placeholder = f"bin/{name}" if is_linux() else f"%BIN%{name}"
    lines: list[str] = []
    for opt in info.winws_options:
        if opt == "--dpi-desync-fake-tls-mod":
            lines.append(f"{opt}=rndsni,dupsid")
        else:
            lines.append(f'{opt}="{placeholder}"')
    return "\n".join(lines)


def read_bin_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def write_bin_file(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def download_zapret_template(name: str, dest_folder: str) -> str:
    url = f"{ZAPRET_FAKE_BIN_BASE}/{name}"
    dest_path = os.path.join(dest_folder, name)
    os.makedirs(dest_folder, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
    except urllib.error.URLError as e:
        raise OSError(str(e)) from e
    write_bin_file(dest_path, data)
    return dest_path


def iter_template_groups() -> Iterable[tuple[str, tuple[str, ...]]]:
    tls = tuple(n for n in ZAPRET_TEMPLATE_BINS if n.startswith("tls_"))
    quic = tuple(n for n in ZAPRET_TEMPLATE_BINS if n.startswith("quic_"))
    other = tuple(n for n in ZAPRET_TEMPLATE_BINS if n not in tls and n not in quic)
    yield ("bin_tpl_group_tls", tls)
    yield ("bin_tpl_group_quic", quic)
    yield ("bin_tpl_group_other", other)
