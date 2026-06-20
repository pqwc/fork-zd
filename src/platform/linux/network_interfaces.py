"""Список сетевых интерфейсов Linux."""
from __future__ import annotations

import os
import subprocess


def list_network_interfaces(*, include_any: bool = True) -> list[str]:
    names: list[str] = []
    sys_net = "/sys/class/net"
    if os.path.isdir(sys_net):
        try:
            names = sorted(
                n
                for n in os.listdir(sys_net)
                if os.path.isdir(os.path.join(sys_net, n))
            )
        except OSError:
            names = []

    if not names:
        try:
            completed = subprocess.run(
                ["ip", "-o", "link", "show"],
                capture_output=True,
                text=True,
                timeout=5,
                errors="replace",
            )
            if completed.returncode == 0:
                for line in completed.stdout.splitlines():
                    parts = line.split(":", 2)
                    if len(parts) >= 2:
                        iface = parts[1].strip().split("@", 1)[0]
                        if iface and iface not in names:
                            names.append(iface)
                names.sort()
        except Exception:
            pass

    if include_any:
        return ["any", *names]
    return names
