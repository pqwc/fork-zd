"""Параметры запуска ZapretDesktop (CLI + fallback для exe без argv)."""
from __future__ import annotations

import argparse
import os
import shlex
import sys
from dataclasses import dataclass, replace

from src.app.launch_registry import (
    LAUNCH_FLAG_SPECS,
    format_flag_token,
    format_launch_reference_text,
    launch_args_fallback_path,
)


@dataclass(frozen=True)
class LaunchOptions:
    autostart: bool = False
    recover: bool = False
    full_reset: bool = False
    skip_winws_setup: bool = False
    no_auto_start_strategy: bool = False
    reset_single_instance: bool = False
    start_minimized: bool = False
    check_updates: bool = False
    check_zapret: bool = False
    check_app: bool = False
    no_updates: bool = False
    safe_mode: bool = False
    install_deps: bool = False


_LAUNCH_OPTIONS: LaunchOptions | None = None


def _read_fallback_argv() -> list[str]:
    path = launch_args_fallback_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f.readlines() if ln.strip() and not ln.strip().startswith("#")]
        if not lines:
            return []
        return shlex.split(" ".join(lines), posix=False)
    except OSError:
        return []


def _normalize_argv(argv: list[str] | None) -> list[str]:
    raw = list(argv if argv is not None else sys.argv[1:])
    if not raw:
        raw = _read_fallback_argv()
    return raw


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    for spec in LAUNCH_FLAG_SPECS:
        flags: list[str] = []
        if spec.short:
            flags.append(f"-{spec.short}")
        flags.append(f"--{spec.long}")
        parser.add_argument(*flags, dest=spec.attr, action="store_true")
    parser.add_argument("-h", "--help", action="store_true", dest="help")
    return parser


def _apply_derived_flags(opts: LaunchOptions) -> LaunchOptions:
    """Производные и взаимоисключающие флаги."""
    if opts.full_reset:
        opts = replace(
            opts,
            recover=False,
            reset_single_instance=True,
            no_auto_start_strategy=True,
            no_updates=True,
        )
    if opts.safe_mode:
        opts = replace(
            opts,
            no_auto_start_strategy=True,
            no_updates=True,
            reset_single_instance=True,
        )
    if opts.no_updates and (opts.check_updates or opts.check_zapret or opts.check_app):
        opts = replace(opts, check_updates=False, check_zapret=False, check_app=False)
    if opts.check_updates:
        opts = replace(opts, check_zapret=False, check_app=False)
    return opts


def parse_launch_options(argv: list[str] | None = None) -> LaunchOptions:
    global _LAUNCH_OPTIONS
    if _LAUNCH_OPTIONS is not None:
        return _LAUNCH_OPTIONS

    parser = _build_parser()
    args, _unknown = parser.parse_known_args(_normalize_argv(argv))

    if args.help:
        lang = "ru"
        try:
            from src.entities.config.config_manager import ConfigManager

            lang = ConfigManager().load_settings().get("language", "ru")
        except Exception:
            pass
        print(format_launch_reference_text(lang))
        sys.exit(0)

    fields = {spec.attr: bool(getattr(args, spec.attr, False)) for spec in LAUNCH_FLAG_SPECS}
    _LAUNCH_OPTIONS = _apply_derived_flags(LaunchOptions(**fields))
    return _LAUNCH_OPTIONS


def mark_full_reset_consumed() -> None:
    global _LAUNCH_OPTIONS
    if _LAUNCH_OPTIONS is not None:
        _LAUNCH_OPTIONS = replace(_LAUNCH_OPTIONS, full_reset=False)


def get_launch_options() -> LaunchOptions:
    return _LAUNCH_OPTIONS or LaunchOptions()


def format_launch_args(options: LaunchOptions | None = None, *, prefer_short: bool = True) -> str:
    opts = options or get_launch_options()
    parts: list[str] = []
    for spec in LAUNCH_FLAG_SPECS:
        if getattr(opts, spec.attr, False):
            parts.append(format_flag_token(spec, prefer_short=prefer_short))
    return " ".join(parts)


def has_active_launch_flags(options: LaunchOptions | None = None) -> bool:
    opts = options or get_launch_options()
    return any(getattr(opts, spec.attr, False) for spec in LAUNCH_FLAG_SPECS)


def format_launch_status_tooltip(lang: str = "ru", options: LaunchOptions | None = None) -> str:
    from src.shared.i18n.translator import tr

    opts = options or get_launch_options()
    lines = [tr("launch_ref_title", lang), ""]
    for spec in LAUNCH_FLAG_SPECS:
        if getattr(opts, spec.attr, False):
            token = format_flag_token(spec, prefer_short=False)
            lines.append(f"{token} — {tr(spec.desc_key, lang)}")
    return "\n".join(lines).strip()


def should_skip_updates() -> bool:
    opts = get_launch_options()
    return opts.no_updates or opts.safe_mode or opts.full_reset


def forced_update_mode() -> str | None:
    """none | strategies | app | all — принудительная проверка из CLI."""
    opts = get_launch_options()
    if should_skip_updates():
        return None
    if opts.check_updates:
        return "all"
    if opts.check_zapret:
        return "strategies"
    if opts.check_app:
        return "app"
    return None
