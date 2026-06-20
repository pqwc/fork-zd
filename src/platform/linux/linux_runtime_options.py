"""Настройки Linux runtime: conf.env, init mode, firewall backend."""
from __future__ import annotations

from .conf_env import read_conf_env, write_conf_env

INIT_MODE_AUTO = "auto"
INIT_MODE_SYSTEMD = "systemd"
INIT_MODE_RUN = "run"

FIREWALL_AUTO = "auto"
FIREWALL_NFTABLES = "nftables"
FIREWALL_IPTABLES = "iptables"


def resolve_use_systemd(settings: dict | None) -> bool | None:
    """None = auto (systemd если unit установлен)."""
    settings = settings or {}
    mode = (settings.get("linux_init_mode") or INIT_MODE_AUTO).strip().lower()
    if mode == INIT_MODE_SYSTEMD:
        return True
    if mode == INIT_MODE_RUN:
        return False
    return None


def normalize_firewall_backend(value: str | None) -> str:
    raw = (value or FIREWALL_AUTO).strip().lower()
    if raw in (FIREWALL_AUTO, FIREWALL_NFTABLES, FIREWALL_IPTABLES):
        return raw
    return FIREWALL_AUTO


def sync_conf_env_from_settings(runtime_root: str, settings: dict) -> None:
    """Синхронизирует conf.env с ключами GUI (interface, gamefilter, firewall)."""
    settings = settings or {}
    iface = (settings.get("linux_interface") or "any").strip() or "any"
    gf_tcp = bool(settings.get("linux_gamefilter_tcp", True))
    gf_udp = bool(settings.get("linux_gamefilter_udp", True))
    firewall = normalize_firewall_backend(settings.get("linux_firewall_backend"))

    existing = read_conf_env(runtime_root)
    values = {
        "interface": iface,
        "gamefiltertcp": "true" if gf_tcp else "false",
        "gamefilterudp": "true" if gf_udp else "false",
        "firewall_backend": firewall,
    }
    if existing.get("strategy"):
        values["strategy"] = existing["strategy"]
    write_conf_env(runtime_root, values)


def detect_init_system() -> str:
    """Грубое определение init: systemd, openrc, runit или unknown."""
    import os

    if os.path.isdir("/run/systemd/system"):
        return "systemd"
    if os.path.isfile("/sbin/openrc"):
        return "openrc"
    if os.path.isdir("/etc/runit"):
        return "runit"
    return "unknown"
