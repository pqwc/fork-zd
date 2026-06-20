"""Реестр CLI-параметров ZapretDesktop (короткие/длинные формы, справка, UI)."""
from __future__ import annotations

from dataclasses import dataclass

from src.shared.i18n.translator import tr
from src.shared.lib.path_utils import get_appdata_config_dir

_LAUNCH_ARGS_FILE = "launch_args.txt"


@dataclass(frozen=True)
class LaunchFlagSpec:
    attr: str
    long: str
    short: str
    desc_key: str
    category: str  # recovery | updates | startup | other


LAUNCH_FLAG_SPECS: tuple[LaunchFlagSpec, ...] = (
    LaunchFlagSpec("full_reset", "full-reset", "F", "launch_flag_full_reset", "recovery"),
    LaunchFlagSpec("recover", "recover", "r", "launch_flag_recover", "recovery"),
    LaunchFlagSpec("check_updates", "check-updates", "u", "launch_flag_check_updates", "updates"),
    LaunchFlagSpec("check_zapret", "check-zapret", "z", "launch_flag_check_zapret", "updates"),
    LaunchFlagSpec("check_app", "check-app", "p", "launch_flag_check_app", "updates"),
    LaunchFlagSpec("no_updates", "no-updates", "U", "launch_flag_no_updates", "updates"),
    LaunchFlagSpec("autostart", "autostart", "a", "launch_flag_autostart", "startup"),
    LaunchFlagSpec("start_minimized", "minimized", "m", "launch_flag_minimized", "startup"),
    LaunchFlagSpec("skip_winws_setup", "skip-winws-setup", "S", "launch_flag_skip_winws", "startup"),
    LaunchFlagSpec("no_auto_start_strategy", "no-auto-start-strategy", "N", "launch_flag_no_auto_strategy", "startup"),
    LaunchFlagSpec("reset_single_instance", "reset-single-instance", "I", "launch_flag_reset_instance", "startup"),
    LaunchFlagSpec("install_deps", "install-deps", "d", "launch_flag_install_deps", "startup"),
    LaunchFlagSpec("safe_mode", "safe-mode", "s", "launch_flag_safe_mode", "other"),
)

_CATEGORY_ORDER = ("recovery", "updates", "startup", "other")
_CATEGORY_TITLE_KEYS = {
    "recovery": "launch_category_recovery",
    "updates": "launch_category_updates",
    "startup": "launch_category_startup",
    "other": "launch_category_other",
}


def launch_args_fallback_path() -> str:
    import os

    return os.path.join(get_appdata_config_dir(), _LAUNCH_ARGS_FILE)


def format_flag_token(spec: LaunchFlagSpec, *, prefer_short: bool = True) -> str:
    if prefer_short and spec.short:
        return f"-{spec.short}"
    return f"--{spec.long}"


def format_launch_reference_text(lang: str = "ru") -> str:
    """Текст справки по параметрам для UI и --help."""
    lines = [
        f"# {tr('launch_ref_title', lang)}",
        f"# {tr('launch_ref_usage', lang)}",
        "#",
        f"# {tr('launch_ref_fallback', lang).format(launch_args_fallback_path())}",
        "#",
        f"# {tr('launch_ref_example', lang)}",
        "ZapretDesktop.exe -r -u -m",
        "python ZapretDesktop.py -F -I",
        "",
    ]
    for category in _CATEGORY_ORDER:
        specs = [s for s in LAUNCH_FLAG_SPECS if s.category == category]
        if not specs:
            continue
        lines.append(f"# {tr(_CATEGORY_TITLE_KEYS[category], lang)}")
        for spec in specs:
            short = f"-{spec.short:<2}" if spec.short else "   "
            long = f"--{spec.long}"
            desc = tr(spec.desc_key, lang)
            lines.append(f"{short}  {long:<28} {desc}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
