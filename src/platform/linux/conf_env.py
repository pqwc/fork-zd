"""Чтение и запись conf.env Linux-адаптера."""
from __future__ import annotations

import os
import re

CONF_FILENAME = "conf.env"
_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

_MANAGED_KEYS = (
    "interface",
    "gamefiltertcp",
    "gamefilterudp",
    "strategy",
    "firewall_backend",
)


def conf_env_path(runtime_root: str) -> str:
    return os.path.join(os.path.abspath(runtime_root), CONF_FILENAME)


def read_conf_env(runtime_root: str) -> dict[str, str]:
    path = conf_env_path(runtime_root)
    if not os.path.isfile(path):
        return {}
    data: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                match = _LINE_RE.match(line)
                if match:
                    data[match.group(1).lower()] = match.group(2).strip()
    except OSError:
        return {}
    return data


def write_conf_env(runtime_root: str, values: dict[str, str]) -> None:
    path = conf_env_path(runtime_root)
    existing = read_conf_env(runtime_root)
    merged = {**existing, **{k.lower(): v for k, v in values.items()}}
    managed_set = set(_MANAGED_KEYS)
    lines = [
        f"interface={merged.get('interface', 'any')}",
        f"gamefiltertcp={merged.get('gamefiltertcp', 'false')}",
        f"gamefilterudp={merged.get('gamefilterudp', 'false')}",
        f"strategy={merged.get('strategy', '')}",
        f"firewall_backend={merged.get('firewall_backend', 'auto')}",
    ]
    for key in sorted(merged):
        if key not in managed_set:
            lines.append(f"{key}={merged[key]}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def strategy_base_name(strategy: str) -> str:
    name = (strategy or "").strip()
    if name.lower().endswith(".bat"):
        return name[:-4]
    return name


def normalize_strategy_filename(strategy: str) -> str:
    name = (strategy or "").strip()
    if not name:
        return ""
    return name if name.lower().endswith(".bat") else f"{name}.bat"
