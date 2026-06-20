"""Проверка доступности сети: ICMP ping и HTTP probe."""
from __future__ import annotations

import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Optional

_CACHE_TTL_SEC = 45
_cache: Optional["NetworkStatus"] = None
_cache_at = 0.0

_HTTP_PROBE_URL = "https://cloudflare.com/cdn-cgi/trace"
_HTTP_TIMEOUT_SEC = 5
_PING_TARGET = "1.1.1.1"


class NetworkState(str, Enum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    PING_ONLY = "ping_only"
    OFFLINE = "offline"


@dataclass(frozen=True)
class NetworkStatus:
    state: NetworkState
    ping_ok: bool
    http_ok: bool
    link_type: str = "unknown"  # wifi | ethernet | unknown

    @property
    def is_online(self) -> bool:
        return self.state in (NetworkState.ONLINE, NetworkState.PING_ONLY)


def _ping_cmd() -> list[str]:
    if os.name == "nt":
        return ["ping", "-n", "1", "-w", "2000", _PING_TARGET]
    return ["ping", "-c", "1", "-W", "2", _PING_TARGET]


def _ping_ok() -> bool:
    try:
        run_kwargs = {
            "capture_output": True,
            "timeout": 6,
        }
        if os.name == "nt":
            run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(
            _ping_cmd(),
            **run_kwargs,
        )
        if result.returncode != 0:
            return False
        for enc in ("utf-8", "cp866", "cp1251"):
            try:
                text = (result.stdout or b"").decode(enc).lower()
                if "ttl=" in text or "ttl =" in text:
                    return True
            except UnicodeDecodeError:
                continue
    except Exception:
        pass
    return False


def _http_ok() -> bool:
    try:
        req = urllib.request.Request(
            _HTTP_PROBE_URL,
            headers={"User-Agent": "ZapretDesktop/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SEC) as resp:
            return 200 <= int(resp.status) < 400
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return False


def _detect_link_type() -> str:
    """Определяет тип активного подключения: wifi, ethernet или unknown."""
    import socket

    try:
        import psutil
    except ImportError:
        return "unknown"

    wifi_hints = ("wi-fi", "wlan", "wireless", "wifi", "802.11")
    eth_hints = ("ethernet", "eth", "local area", "gigabit", "подключение по локальной")

    wifi = False
    eth = False
    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
    except Exception:
        return "unknown"

    for iface, stat in stats.items():
        if not stat.isup:
            continue
        name = iface.lower()
        if name.startswith("lo") or "loopback" in name:
            continue
        if any(
            skip in name
            for skip in (
                "virtual",
                "vmware",
                "hyper-v",
                "vpn",
                "vbox",
                "wsl",
                "bluetooth",
                "npcap",
                "tap",
                "teredo",
            )
        ):
            continue
        has_ip = False
        for addr in addrs.get(iface, ()):
            if addr.family == socket.AF_INET and addr.address:
                if not addr.address.startswith("169.254."):
                    has_ip = True
                    break
        if not has_ip:
            continue
        if any(h in name for h in wifi_hints):
            wifi = True
        elif any(h in name for h in eth_hints):
            eth = True

    if wifi and not eth:
        return "wifi"
    if eth and not wifi:
        return "ethernet"
    if wifi and eth:
        return "wifi"
    return "unknown"


def check_network_status(*, force: bool = False) -> NetworkStatus:
    """Проверяет ping + HTTP. Результат кэшируется на ~45 с."""
    global _cache, _cache_at
    now = time.monotonic()
    if not force and _cache is not None and (now - _cache_at) < _CACHE_TTL_SEC:
        return _cache

    ping = _ping_ok()
    http = _http_ok()
    if ping and http:
        state = NetworkState.ONLINE
    elif ping:
        state = NetworkState.PING_ONLY
    elif http:
        state = NetworkState.ONLINE
    else:
        state = NetworkState.OFFLINE

    _cache = NetworkStatus(
        state=state,
        ping_ok=ping,
        http_ok=http,
        link_type=_detect_link_type(),
    )
    _cache_at = now
    return _cache


def invalidate_network_cache() -> None:
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0
