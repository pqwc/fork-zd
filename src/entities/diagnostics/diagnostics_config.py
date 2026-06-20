"""Конфигурация диагностики: пользовательские команды и расширенные проверки."""
from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from typing import Any

from src.shared.lib.path_utils import get_appdata_config_dir
from src.shared.i18n.translator import tr

CONFIG_VERSION = 1

_DIAG_CMD_NAME_KEYS: dict[str, str] = {
    "ping_cloudflare_dns": "diag_cmd_name_ping",
    "ipconfig_all": "diag_cmd_name_ipconfig",
    "route_print": "diag_cmd_name_route",
    "netstat_winws": "diag_cmd_name_netstat",
    "nslookup_discord": "diag_cmd_name_nslookup",
    "query_zapret_service": "diag_cmd_name_sc_zapret",
    "tasklist_winws": "diag_cmd_name_tasklist",
    "netsh_winsock": "diag_cmd_name_winsock",
    "pgrep_nfqws": "diag_cmd_name_pgrep_nfqws",
    "ip_route": "diag_cmd_name_ip_route",
    "resolvectl_status": "diag_cmd_name_resolvectl",
}

DEFAULT_DIAGNOSTICS_CONFIG: dict[str, Any] = {
    "version": CONFIG_VERSION,
    "custom_commands": [
        {
            "id": "ping_cloudflare_dns",
            "name": "Ping 1.1.1.1",
            "enabled": False,
            "command": "ping -n 2 1.1.1.1",
            "shell": True,
            "timeout": 15,
            "expect_stdout": "TTL=",
            "fail_if_stdout": "100% packet loss",
            "critical": False,
        },
        {
            "id": "ipconfig_all",
            "name": "Network adapters (ipconfig /all)",
            "enabled": False,
            "command": "ipconfig /all",
            "shell": True,
            "timeout": 20,
            "critical": False,
        },
        {
            "id": "route_print",
            "name": "Routing table (route print)",
            "enabled": False,
            "command": "route print",
            "shell": True,
            "timeout": 15,
            "critical": False,
        },
        {
            "id": "netstat_winws",
            "name": "winws connections (netstat)",
            "enabled": False,
            "command": "netstat -ano | findstr /i winws",
            "shell": True,
            "timeout": 15,
            "critical": False,
        },
        {
            "id": "nslookup_discord",
            "name": "DNS discord.com (nslookup)",
            "enabled": False,
            "command": "nslookup discord.com",
            "shell": True,
            "timeout": 15,
            "expect_returncode": 0,
            "critical": False,
        },
        {
            "id": "query_zapret_service",
            "name": "zapret service (sc query)",
            "enabled": False,
            "command": ["sc", "query", "zapret"],
            "shell": False,
            "timeout": 8,
            "expect_returncode": 0,
            "critical": False,
        },
        {
            "id": "tasklist_winws",
            "name": "winws process (tasklist)",
            "enabled": False,
            "command": "tasklist /fi \"imagename eq winws.exe\"",
            "shell": True,
            "timeout": 10,
            "expect_stdout": "winws.exe",
            "critical": False,
        },
        {
            "id": "netsh_winsock",
            "name": "Winsock (netsh winsock show catalog)",
            "enabled": False,
            "command": "netsh winsock show catalog",
            "shell": True,
            "timeout": 12,
            "expect_returncode": 0,
            "critical": False,
        },
    ],
}

DEFAULT_LINUX_DIAGNOSTICS_CONFIG: dict[str, Any] = {
    "version": CONFIG_VERSION,
    "custom_commands": [
        {
            "id": "ping_cloudflare_dns",
            "name": "Ping 1.1.1.1",
            "enabled": False,
            "command": "ping -c 2 1.1.1.1",
            "shell": True,
            "timeout": 15,
            "expect_stdout": "ttl=",
            "fail_if_stdout": "100% packet loss",
            "critical": False,
        },
        {
            "id": "pgrep_nfqws",
            "name": "nfqws process (pgrep)",
            "enabled": False,
            "command": "pgrep -a nfqws",
            "shell": True,
            "timeout": 10,
            "ignore_returncode": True,
            "critical": False,
        },
        {
            "id": "ip_route",
            "name": "Routing table (ip route)",
            "enabled": False,
            "command": "ip route",
            "shell": True,
            "timeout": 15,
            "critical": False,
        },
        {
            "id": "resolvectl_status",
            "name": "DNS (resolvectl status)",
            "enabled": False,
            "command": "resolvectl status",
            "shell": True,
            "timeout": 15,
            "ignore_returncode": True,
            "critical": False,
        },
    ],
}


def _default_config_template() -> dict[str, Any]:
    from src.platform import is_linux

    if is_linux():
        return deepcopy(DEFAULT_LINUX_DIAGNOSTICS_CONFIG)
    return deepcopy(DEFAULT_DIAGNOSTICS_CONFIG)


def localize_diagnostics_config(cfg: dict, lang: str = "ru") -> dict:
    """Подставляет локализованные имена для встроенных custom_commands по id."""
    out = deepcopy(cfg)
    for cmd in out.get("custom_commands", []):
        if not isinstance(cmd, dict):
            continue
        cmd_id = cmd.get("id")
        key = _DIAG_CMD_NAME_KEYS.get(cmd_id or "")
        if key:
            cmd["name"] = tr(key, lang)
    return out


def get_default_diagnostics_config(lang: str = "ru") -> dict:
    return localize_diagnostics_config(_default_config_template(), lang)


def make_windows_command_template(*, index: int = 1, lang: str = "ru") -> dict[str, Any]:
    """Шаблон новой Windows-команды для вставки в custom_commands."""
    return {
        "id": f"windows_cmd_{index}",
        "name": tr("diag_cmd_name_template", lang),
        "enabled": False,
        "command": "ipconfig /all",
        "shell": True,
        "timeout": 20,
        "critical": False,
    }


def make_linux_command_template(*, index: int = 1, lang: str = "ru") -> dict[str, Any]:
    """Шаблон новой Linux-команды для вставки в custom_commands."""
    return {
        "id": f"linux_cmd_{index}",
        "name": tr("diag_cmd_name_template", lang),
        "enabled": False,
        "command": "ip route",
        "shell": True,
        "timeout": 15,
        "critical": False,
    }


def make_command_template(*, index: int = 1, lang: str = "ru") -> dict[str, Any]:
    from src.platform import is_linux

    if is_linux():
        return make_linux_command_template(index=index, lang=lang)
    return make_windows_command_template(index=index, lang=lang)


def _built_in_checks_summary(lang: str) -> str:
    from src.entities.diagnostics.diagnostics_runner import checks_for_platform

    categories: dict[str, list[str]] = {}
    for check in checks_for_platform():
        categories.setdefault(check.category, []).append(check.check_id)
    lines = []
    for cat_id, check_ids in categories.items():
        lines.append(f"- {cat_id}: {', '.join(check_ids)}")
    return "\n".join(lines)


def build_ai_diagnostics_prompt(
    *,
    lang: str = "ru",
    app_version: str = "",
    winws_path: str = "",
    os_info: str = "",
    current_config: dict | None = None,
) -> str:
    """Промпт для ИИ: составить diagnostics.json под проблему «zapret не работает»."""
    from src.platform import is_linux

    on_linux = is_linux()
    checks = _built_in_checks_summary(lang)
    current_json = ""
    if current_config:
        current_json = json.dumps(current_config, ensure_ascii=False, indent=2)

    if lang == "ru":
        if on_linux:
            intro = (
                "Ты помогаешь настроить диагностику для ZapretDesktop на Linux — GUI над zapret "
                "(nfqws, service.sh). Пользователь запускает встроенные проверки и дополнительные "
                "команды из diagnostics.json (вкладка «Настройки и конфиг»).\n\n"
                "Задача: составь или улучши diagnostics.json, чтобы выяснить, почему zapret не работает "
                "(не стартует nfqws, сайты не открываются, nftables/iptables, DNS, прокси и т.д.)."
            )
            runtime_label = "Папка zapret-linux (runtime)"
            schema_shell = (
                "- Для shell-команд Linux (ping, ip, ss, curl, resolvectl, journalctl, pgrep, "
                "grep, pipe |) используй строку command и \"shell\": true.\n"
                "- Для прямого запуска бинарника используй массив command и \"shell\": false.\n"
            )
            examples = (
                "Примеры (Linux):\n"
                '- "command": "ping -c 2 1.1.1.1", "shell": true, "expect_stdout": "ttl="\n'
                '- "command": "pgrep -a nfqws", "shell": true, "ignore_returncode": true\n'
                '- "command": "ss -tunlp | grep nfqws", "shell": true, "ignore_returncode": true\n'
            )
        else:
            intro = (
                "Ты помогаешь настроить диагностику для ZapretDesktop — GUI-обёртки над zapret/winws "
                "на Windows. Пользователь запускает встроенные проверки и дополнительные команды из "
                "файла diagnostics.json (вкладка «Настройки и конфиг» в окне диагностики).\n\n"
                "Задача: составь или улучши diagnostics.json, чтобы выяснить, почему zapret не работает "
                "(не стартует winws, сайты не открываются, блокировки не обходятся, конфликты ПО и т.д.)."
            )
            runtime_label = "Папка winws"
            schema_shell = (
                "- Для обычных Windows-команд (ping, ipconfig, netstat, route, nslookup, tracert, "
                "sc, tasklist, netsh, findstr, pipe |) используй строку command и \"shell\": true.\n"
                "- Для прямого запуска exe без cmd используй массив command и \"shell\": false.\n"
            )
            examples = (
                "Примеры:\n"
                '- "command": "ping -n 2 1.1.1.1", "shell": true, "expect_stdout": "TTL="\n'
                '- "command": "netstat -ano | findstr /i winws", "shell": true, "ignore_returncode": true\n'
                '- "command": ["sc", "query", "zapret"], "shell": false, "expect_returncode": 0\n'
            )
        context = (
            f"Контекст системы:\n"
            f"- Версия ZapretDesktop: {app_version or '?'}\n"
            f"- {runtime_label}: {winws_path or '?'}\n"
            f"- ОС: {os_info or '?'}\n\n"
            f"Встроенные проверки (уже есть в приложении, не дублируй их командами):\n{checks}\n"
        )
        schema = (
            "Формат diagnostics.json:\n"
            "{\n"
            '  "version": 1,\n'
            '  "custom_commands": [\n'
            "    {\n"
            '      "id": "уникальный_id",\n'
            '      "name": "Название в отчёте",\n'
            '      "enabled": true,\n'
            '      "command": "строка shell или массив [\"exe\", \"arg1\"]",\n'
            '      "shell": true,\n'
            '      "timeout": 20,\n'
            '      "expect_returncode": 0,\n'
            '      "expect_stdout": "фрагмент успеха",\n'
            '      "fail_if_stdout": "фрагмент ошибки",\n'
            '      "fail_if_stderr": "фрагмент ошибки в stderr",\n'
            '      "ignore_returncode": false,\n'
            '      "critical": false\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Правила:\n"
            f"{schema_shell}"
            "- timeout в секундах; critical=true помечает провал как критичный.\n"
            "- expect_returncode / expect_stdout / fail_if_stdout / fail_if_stderr — опционально.\n"
            "- ignore_returncode: true — не считать ненулевой код ошибкой.\n"
            "- id только латиница, цифры и подчёркивание.\n"
            "- Добавь 5–12 релевантных команд под типичные проблемы zapret/DPI/DNS.\n"
        )
        output = (
            "Ответь ТОЛЬКО одним markdown-блоком кода с языком json, чтобы пользователь мог "
            "скопировать конфиг одним кликом:\n"
            "```json\n"
            "{ ... содержимое diagnostics.json ... }\n"
            "```\n"
            "Не добавляй текст до или после блока кода."
        )
        current_block = (
            f"\nТекущий конфиг пользователя (можно улучшить):\n```\n{current_json}\n```\n"
            if current_json
            else ""
        )
        symptoms = (
            "\nСимптомы пользователя (заполнит сам после вставки промпта):\n"
            "- Что не работает:\n"
            "- Когда началось:\n"
            "- Текст ошибки / лог:\n"
        )
        return "\n".join((intro, context, schema, examples, current_block, symptoms, output))

    if on_linux:
        intro = (
            "Help configure diagnostics for ZapretDesktop on Linux (nfqws, service.sh). "
            "Built-in checks run from the app; extra checks come from diagnostics.json.\n\n"
            "Task: create or improve diagnostics.json to find why zapret is not working "
            "(nfqws won't start, sites blocked, nftables, DNS, proxy, etc.)."
        )
        runtime_label = "zapret-linux runtime folder"
        schema_extra = (
            "- Linux shell (ping, ip, ss, curl, resolvectl, journalctl, pgrep, grep, pipes): "
            "command string with \"shell\": true.\n"
        )
        examples_en = (
            "Examples (Linux):\n"
            '- "command": "ping -c 2 1.1.1.1", "shell": true, "expect_stdout": "ttl="\n'
            '- "command": "pgrep -a nfqws", "shell": true, "ignore_returncode": true\n'
        )
    else:
        intro = (
            "Help configure diagnostics for ZapretDesktop — a Windows GUI for zapret/winws. "
            "Built-in checks run from the app; extra checks come from diagnostics.json "
            "(Settings & config tab in the diagnostics window).\n\n"
            "Task: create or improve diagnostics.json to find why zapret is not working "
            "(winws won't start, sites blocked, bypass fails, software conflicts, etc.)."
        )
        runtime_label = "winws folder"
        schema_extra = (
            "- Windows CMD strings (ping, ipconfig, netstat, route, nslookup, sc, tasklist, "
            "netsh, pipes): use command string with \"shell\": true.\n"
        )
        examples_en = (
            "Examples:\n"
            '- "command": "ping -n 2 1.1.1.1", "shell": true, "expect_stdout": "TTL="\n'
            '- "command": "netstat -ano | findstr /i winws", "shell": true, "ignore_returncode": true\n'
        )
    context = (
        f"System context:\n"
        f"- ZapretDesktop version: {app_version or '?'}\n"
        f"- {runtime_label}: {winws_path or '?'}\n"
        f"- OS: {os_info or '?'}\n\n"
        f"Built-in checks (already in the app, do not duplicate):\n{checks}\n"
    )
    schema = (
        "diagnostics.json format:\n"
        "{\n"
        '  "version": 1,\n'
        '  "custom_commands": [ { "id", "name", "enabled", "command", "shell", '
        '"timeout", "expect_returncode", "expect_stdout", "fail_if_stdout", '
        '"fail_if_stderr", "ignore_returncode", "critical" } ]\n'
        "}\n\n"
        "Rules:\n"
        f"{schema_extra}"
        "- Direct exe: command array with \"shell\": false.\n"
        "- Add 5–12 relevant commands for zapret/DPI/DNS issues.\n"
    )
    current_block = (
        f"\nUser's current config:\n```\n{current_json}\n```\n"
        if current_json
        else ""
    )
    symptoms = (
        "\nUser symptoms (fill in after pasting):\n"
        "- What fails:\n"
        "- When it started:\n"
        "- Error text / logs:\n"
    )
    output = (
        "Reply with a single markdown json code block only, so the user can copy in one click:\n"
        "```json\n"
        "{ ... diagnostics.json contents ... }\n"
        "```\n"
        "No text before or after the code block."
    )
    return "\n".join((intro, context, schema, examples_en, current_block, symptoms, output))


def get_diagnostics_config_path() -> str:
    return os.path.join(get_appdata_config_dir(), "diagnostics.json")


def config_to_text(config: dict | None = None) -> str:
    data = config if config is not None else DEFAULT_DIAGNOSTICS_CONFIG
    return json.dumps(data, ensure_ascii=False, indent=2)


def parse_config_text(text: str) -> dict:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Root must be a JSON object")
    return data


def _assign_command_id(item: dict, index: int) -> str:
    raw_id = (item.get("id") or "").strip()
    if raw_id:
        return raw_id
    name = (item.get("name") or "").strip()
    if name:
        slug = re.sub(r"[^a-zA-Z0-9_]+", "_", name.lower()).strip("_")
        if slug:
            return slug[:48]
    return f"custom_cmd_{index + 1}"


def normalize_config(raw: dict | None) -> dict:
    cfg = _default_config_template()
    if not isinstance(raw, dict):
        return cfg
    if isinstance(raw.get("version"), int):
        cfg["version"] = raw["version"]
    commands = raw.get("custom_commands")
    if isinstance(commands, list):
        cleaned = []
        for index, item in enumerate(commands):
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            entry["id"] = _assign_command_id(entry, index)
            cleaned.append(entry)
        cfg["custom_commands"] = cleaned
    return cfg


def load_diagnostics_config() -> dict:
    path = get_diagnostics_config_path()
    if not os.path.isfile(path):
        return _default_config_template()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return normalize_config(json.load(f))
    except (OSError, json.JSONDecodeError):
        return _default_config_template()


def save_diagnostics_config(config: dict) -> None:
    path = get_diagnostics_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    normalized = normalize_config(config)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)


def ensure_diagnostics_config() -> dict:
    path = get_diagnostics_config_path()
    if os.path.isfile(path):
        return load_diagnostics_config()
    cfg = _default_config_template()
    save_diagnostics_config(cfg)
    return cfg
