"""Проверки диагностики для Linux."""
from __future__ import annotations

import os
from typing import List

import psutil

from src.entities.diagnostics.diagnostics_runner import DiagnosticsContext, ResultLine, _run_command
from src.platform.linux.conf_env import read_conf_env
from src.platform.linux.linux_runtime_manager import LinuxRuntimeManager
from src.shared.lib.path_utils import get_winws_path


def _pass(ctx: DiagnosticsContext, key: str, *args) -> ResultLine:
    return ("pass", ctx.t(key, *args))


def _fail(ctx: DiagnosticsContext, key: str, *args) -> ResultLine:
    return ("fail", ctx.t(key, *args))


def _warn(ctx: DiagnosticsContext, key: str, *args) -> ResultLine:
    return ("warn", ctx.t(key, *args))


def _info(ctx: DiagnosticsContext, key: str, *args) -> ResultLine:
    return ("info", ctx.t(key, *args))


def check_linux_runtime_adapter(ctx: DiagnosticsContext) -> List[ResultLine]:
    root = get_winws_path()
    service = os.path.join(root, "service.sh")
    if os.path.isfile(service):
        return [_pass(ctx, "diag_linux_runtime_ok", root)]
    return [_fail(ctx, "diag_linux_runtime_missing")]


def check_linux_conf_env(ctx: DiagnosticsContext) -> List[ResultLine]:
    conf = read_conf_env(get_winws_path())
    required = ("interface", "strategy", "gamefiltertcp", "gamefilterudp")
    missing = [k for k in required if not conf.get(k)]
    if missing:
        return [_warn(ctx, "diag_linux_conf_incomplete", ", ".join(missing))]
    return [_pass(ctx, "diag_linux_conf_ok", conf.get("strategy", ""))]


def check_linux_nfqws_process(ctx: DiagnosticsContext) -> List[ResultLine]:
    mgr = LinuxRuntimeManager()
    proc = mgr.get_running_process()
    if proc:
        try:
            return [_pass(ctx, "diag_linux_nfqws_running", proc.pid)]
        except Exception:
            return [_pass(ctx, "diag_linux_nfqws_running", "?")]
    return [_warn(ctx, "diag_linux_nfqws_stopped")]


def check_linux_nftables(ctx: DiagnosticsContext) -> List[ResultLine]:
    code, stdout, _ = _run_command(["nft", "list", "ruleset"], timeout=8)
    if code == 0 and stdout.strip():
        return [_pass(ctx, "diag_linux_nftables_ok")]
    code2, _, _ = _run_command(["systemctl", "is-active", "nftables"], timeout=5)
    if code2 == 0:
        return [_pass(ctx, "diag_linux_nftables_service")]
    return [_warn(ctx, "diag_linux_nftables_unknown")]


def check_linux_dns(ctx: DiagnosticsContext) -> List[ResultLine]:
    code, stdout, _ = _run_command(["resolvectl", "status"], timeout=8)
    if code == 0 and stdout.strip():
        return [_info(ctx, "diag_linux_dns_resolvectl")]
    code2, stdout2, _ = _run_command(["cat", "/etc/resolv.conf"], timeout=5)
    if code2 == 0 and stdout2.strip():
        return [_info(ctx, "diag_linux_dns_resolv")]
    return [_warn(ctx, "diag_linux_dns_unknown")]


def check_linux_routes(ctx: DiagnosticsContext) -> List[ResultLine]:
    code, stdout, _ = _run_command(["ip", "route"], timeout=5)
    if code == 0 and stdout.strip():
        return [_pass(ctx, "diag_linux_routes_ok")]
    return [_warn(ctx, "diag_linux_routes_failed")]


def check_linux_sudo(ctx: DiagnosticsContext) -> List[ResultLine]:
    code, _, _ = _run_command(["sudo", "-n", "true"], timeout=5)
    if code == 0:
        return [_pass(ctx, "diag_linux_sudo_nopasswd")]
    return [_warn(ctx, "diag_linux_sudo_password")]


def check_linux_systemd_zapret(ctx: DiagnosticsContext) -> List[ResultLine]:
    mgr = LinuxRuntimeManager()
    if not mgr.service_is_installed():
        return [_info(ctx, "diag_linux_systemd_not_installed")]
    if mgr.service_is_active():
        return [_pass(ctx, "diag_linux_systemd_active")]
    return [_warn(ctx, "diag_linux_systemd_inactive")]


def check_linux_strategies(ctx: DiagnosticsContext) -> List[ResultLine]:
    mgr = LinuxRuntimeManager()
    files = mgr.list_strategy_files()
    if files:
        return [_pass(ctx, "diag_linux_strategies_ok", len(files))]
    return [_fail(ctx, "diag_linux_strategies_missing")]


def check_linux_hosts(ctx: DiagnosticsContext) -> List[ResultLine]:
    path = "/etc/hosts"
    if not os.path.isfile(path):
        return [_fail(ctx, "diag_linux_hosts_missing")]
    if os.access(path, os.R_OK):
        return [_pass(ctx, "diag_linux_hosts_readable")]
    return [_warn(ctx, "diag_linux_hosts_not_readable")]


def check_linux_iptables(ctx: DiagnosticsContext) -> List[ResultLine]:
    code, stdout, _ = _run_command(["iptables", "-L", "-n"], timeout=8)
    if code == 0 and stdout.strip():
        return [_info(ctx, "diag_linux_iptables_ok")]
    return [_info(ctx, "diag_linux_iptables_unavailable")]


def check_linux_init_backend(ctx: DiagnosticsContext) -> List[ResultLine]:
    from src.platform.linux.linux_runtime_options import detect_init_system

    init_sys = detect_init_system()
    conf = read_conf_env(get_winws_path())
    fw = conf.get("firewall_backend", "auto")
    return [_info(ctx, "diag_linux_init_backend", init_sys, fw)]


def check_linux_network_connectivity(ctx: DiagnosticsContext) -> List[ResultLine]:
    code, _, _ = _run_command(["ping", "-c", "1", "-W", "2", "1.1.1.1"], timeout=6)
    if code == 0:
        return [_pass(ctx, "diag_linux_ping_ok")]
    return [_fail(ctx, "diag_linux_ping_failed")]
