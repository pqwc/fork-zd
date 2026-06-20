"""
Модуль диагностики системы для ZapretDesktop.
Каждая проверка возвращает список кортежей (status, message), где status: pass | fail | warn | info.
"""
from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Union

import psutil

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment,misc]

from src.shared.lib.path_utils import get_winws_path
from src.shared.i18n.translator import tr

ResultLine = Tuple[str, str]
CheckFunc = Callable[["DiagnosticsContext"], List[ResultLine]]
CommandSpec = Union[str, List[str]]
StopCallback = Callable[[], bool]
ProgressCallback = Callable[[str, str], None]

_MOJIBAKE_RE = re.compile(r"[\u0420\u0421][\u0400-\u04FF]")
_BOX_DRAWING = tuple(chr(c) for c in range(0x2500, 0x2580))


def _windows_console_encodings() -> List[str]:
    encodings: List[str] = []
    if os.name == "nt":
        for getter in (
            getattr(ctypes.windll.kernel32, "GetOEMCP", None),
            getattr(ctypes.windll.kernel32, "GetACP", None),
        ):
            if getter is None:
                continue
            try:
                cp = int(getter())
            except (OSError, AttributeError, ValueError):
                continue
            enc = "utf-8" if cp == 65001 else f"cp{cp}"
            if enc not in encodings:
                encodings.append(enc)
    for enc in ("cp866", "cp1251"):
        if enc not in encodings:
            encodings.append(enc)
    return encodings


def _text_encoding_score(text: str) -> float:
    if not text:
        return 0.0
    cyr = sum(1 for c in text if "\u0400" <= c <= "\u04FF")
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    repl = text.count("\ufffd")
    box = sum(1 for c in text if c in _BOX_DRAWING)
    mojibake = len(_MOJIBAKE_RE.findall(text))
    ctrl = sum(1 for c in text if ord(c) < 32 and c not in "\r\n\t")
    return cyr * 4 + latin * 0.3 - repl * 40 - box * 20 - mojibake * 12 - ctrl * 8


def _decode_bytes(data: bytes | None) -> str:
    if not data:
        return ""
    if data.startswith(b"\xff\xfe"):
        try:
            return data[2:].decode("utf-16-le")
        except UnicodeDecodeError:
            pass
    if data.startswith(b"\xfe\xff"):
        try:
            return data[2:].decode("utf-16-be")
        except UnicodeDecodeError:
            pass

    try:
        text = data.decode("utf-8")
        if _text_encoding_score(text) >= 0:
            return text
    except UnicodeDecodeError:
        pass

    best_text = ""
    best_score = float("-inf")
    for enc in _windows_console_encodings():
        try:
            text = data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        score = _text_encoding_score(text)
        if score > best_score:
            best_score = score
            best_text = text
    if best_text:
        return best_text
    return data.decode("utf-8", errors="replace")


def _text_from_bytes(data: bytes | None) -> str:
    return _decode_bytes(data)


def _bytes_match_any(data: bytes | None, *phrases: str) -> bool:
    if not data or not phrases:
        return False
    needles = [p.lower() for p in phrases if p]
    for enc in ("utf-8", *_windows_console_encodings()):
        try:
            text = data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        low = text.lower()
        if any(n in low for n in needles):
            return True
    return False


def _bytes_extract_line(data: bytes | None, *markers: str, limit: int = 120) -> str:
    if not data:
        return ""
    best = ""
    best_score = float("-inf")
    for enc in ("utf-8", *_windows_console_encodings()):
        try:
            text = data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        score = _text_encoding_score(text)
        if score <= best_score:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            low = stripped.lower()
            if any(m.lower() in low for m in markers):
                best = stripped[:limit]
                best_score = score
                break
        if best:
            break
    return best


def _prepare_command(command: CommandSpec, shell: bool) -> Tuple[CommandSpec, bool]:
    """На Windows строковые shell-команды выполняются через cmd.exe /c."""
    if os.name == "nt" and shell and isinstance(command, str):
        return ["cmd.exe", "/c", command], False
    return command, shell


def _run_command(
    command: CommandSpec,
    *,
    shell: bool = False,
    timeout: int = 10,
    cwd: Optional[str] = None,
) -> Tuple[int, str, str]:
    command, shell = _prepare_command(command, shell)
    run_kwargs: dict = {
        "capture_output": True,
        "timeout": timeout,
        "shell": shell,
        "cwd": cwd,
    }
    if os.name == "nt":
        run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(command, **run_kwargs)
        return (
            int(result.returncode),
            _decode_bytes(result.stdout),
            _decode_bytes(result.stderr),
        )
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as exc:
        return -1, "", str(exc)


def _run_command_bytes(
    command: CommandSpec,
    *,
    shell: bool = False,
    timeout: int = 10,
    cwd: Optional[str] = None,
) -> Tuple[int, bytes, bytes]:
    command, shell = _prepare_command(command, shell)
    run_kwargs: dict = {
        "capture_output": True,
        "timeout": timeout,
        "shell": shell,
        "cwd": cwd,
    }
    if os.name == "nt":
        run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(command, **run_kwargs)
        return (
            int(result.returncode),
            result.stdout or b"",
            result.stderr or b"",
        )
    except subprocess.TimeoutExpired:
        return -1, b"", b"timeout"
    except Exception as exc:
        return -1, b"", str(exc).encode("utf-8", errors="replace")


@dataclass
class CheckDefinition:
    check_id: str
    category: str
    critical: bool
    run: CheckFunc
    platform: str = "windows"  # windows | linux | all


@dataclass
class DiagnosticsContext:
  lang: str
  auto_fix: bool = False
  stop_requested: StopCallback = field(default=lambda: False, repr=False)
  _services_cache: Optional[str] = field(default=None, repr=False)

  def should_stop(self) -> bool:
      try:
          return bool(self.stop_requested())
      except Exception:
          return False

  def t(self, key: str, *args) -> str:
      msg = tr(key, self.lang)
      return msg.format(*args) if args else msg

  def services_output(self) -> str:
      if self._services_cache is None:
          try:
              _, stdout, _ = _run_command(
                  ['sc', 'query', 'state=', 'all'],
                  timeout=8,
              )
              self._services_cache = stdout or ''
          except Exception:
              self._services_cache = ''
      return self._services_cache

  def service_state(self, name: str) -> Optional[str]:
      out = self.services_output()
      if not out:
          return None
      target = name.strip().lower()
      blocks = re.split(r'(?=SERVICE_NAME:)', out, flags=re.IGNORECASE)
      for block in blocks:
          m_name = re.match(r'SERVICE_NAME:\s*(.+?)\s*$', block, re.IGNORECASE | re.MULTILINE)
          if not m_name:
              continue
          if m_name.group(1).strip().lower() != target:
              continue
          m_state = re.search(r'STATE\s*:\s*\d+\s+(\w+)', block, re.IGNORECASE)
          if m_state:
              return m_state.group(1).upper()
          return 'UNKNOWN'
      return None

  def process_names(self) -> set:
      names = set()
      try:
          for proc in psutil.process_iter(['name']):
              n = proc.info.get('name')
              if n:
                  names.add(n.lower())
      except Exception:
          pass
      return names


def _is_user_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _tcp_timestamps_enabled(stdout: str) -> Optional[bool]:
    """True/False по строке netsh с timestamps; None если строка не найдена."""
    for line in (stdout or "").splitlines():
        low = line.lower()
        if "timestamp" not in low:
            continue
        if "disabled" in low:
            return False
        if "enabled" in low:
            return True
    return None


def _pass(ctx: DiagnosticsContext, key: str, *args) -> ResultLine:
    return ('pass', ctx.t(key, *args))


def _fail(ctx: DiagnosticsContext, key: str, *args) -> ResultLine:
    return ('fail', ctx.t(key, *args))


def _warn(ctx: DiagnosticsContext, key: str, *args) -> ResultLine:
    return ('warn', ctx.t(key, *args))


def _info(ctx: DiagnosticsContext, key: str, *args) -> ResultLine:
    return ('info', ctx.t(key, *args))


def _err(ctx: DiagnosticsContext, key: str, exc: Exception) -> ResultLine:
    return ('warn', ctx.t(key, str(exc)))


# --- Проверки: система ---

def check_bfe(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        state = ctx.service_state('BFE')
        if state == 'RUNNING':
            return [_pass(ctx, 'diag_bfe_passed')]
        return [_fail(ctx, 'diag_bfe_failed')]
    except Exception as e:
        return [_err(ctx, 'diag_error_bfe', e)]


def check_firewall(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        state = ctx.service_state('MpsSvc')
        if state == 'RUNNING':
            return [_pass(ctx, 'diag_firewall_passed')]
        if state is None:
            return [_warn(ctx, 'diag_firewall_not_found')]
        return [_fail(ctx, 'diag_firewall_failed')]
    except Exception as e:
        return [_err(ctx, 'diag_error_firewall', e)]


def check_tcp_timestamps(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        _, stdout, _ = _run_command(
            ['netsh', 'interface', 'tcp', 'show', 'global'],
            timeout=5,
        )
        ts_state = _tcp_timestamps_enabled(stdout or '')
        if ts_state is True:
            return [_pass(ctx, 'diag_tcp_passed')]
        if ts_state is None:
            return [_warn(ctx, 'diag_tcp_unknown')]
        lines = [_warn(ctx, 'diag_tcp_disabled')]
        if ctx.auto_fix:
            if not _is_user_admin():
                lines.append(_warn(ctx, 'diag_autofix_need_admin'))
            else:
                code, _, _ = _run_command(
                    ['netsh', 'interface', 'tcp', 'set', 'global', 'timestamps=enabled'],
                    timeout=5,
                )
                lines.append(_pass(ctx, 'diag_tcp_enabled') if code == 0 else _fail(ctx, 'diag_tcp_failed'))
        return lines
    except Exception as e:
        return [_err(ctx, 'diag_error_tcp', e)]


def check_admin(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            return [_pass(ctx, 'diag_admin_yes')]
        return [_fail(ctx, 'diag_admin_no')]
    except Exception as e:
        return [_err(ctx, 'diag_error_admin', e)]


def check_windows_version(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        release = platform.release()
        version = platform.version()
        arch = platform.machine()
        lines = [_pass(ctx, 'diag_windows_version', release, version, arch)]
        if arch.lower() not in ('amd64', 'x86_64'):
            lines.append(_warn(ctx, 'diag_arch_warning', arch))
        return lines
    except Exception as e:
        return [_err(ctx, 'diag_error_windows', e)]


# --- Сеть ---

def check_system_proxy(ctx: DiagnosticsContext) -> List[ResultLine]:
    key = None
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if proxy_enable:
            proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
            return [
                _warn(ctx, 'diag_proxy_enabled', proxy_server),
                _warn(ctx, 'diag_proxy_check_proxy'),
            ]
        return [_pass(ctx, 'diag_proxy_passed')]
    except FileNotFoundError:
        return [_pass(ctx, 'diag_proxy_passed')]
    except Exception as e:
        return [_err(ctx, 'diag_error_proxy', e)]
    finally:
        if key is not None:
            try:
                winreg.CloseKey(key)
            except Exception:
                pass


def check_winhttp_proxy(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        _, stdout_b, _ = _run_command_bytes(['netsh', 'winhttp', 'show', 'proxy'], timeout=5)
        if _bytes_match_any(
            stdout_b,
            'direct access',
            'no proxy server',
            'прямой доступ',
            'без прокси',
        ):
            return [_pass(ctx, 'diag_winhttp_passed')]
        summary = _bytes_extract_line(
            stdout_b,
            'http://',
            'https://',
            'proxy',
            'прокси',
            limit=120,
        )
        if not summary:
            summary = _text_from_bytes(stdout_b).strip().splitlines()
            summary = summary[-1][:120] if summary else "?"
        return [_warn(ctx, 'diag_winhttp_proxy', summary)]
    except Exception as e:
        return [_err(ctx, 'diag_error_winhttp', e)]


def check_dns_servers(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        _, stdout, _ = _run_command(['ipconfig', '/all'], timeout=8)
        dns_servers = []
        for line in (stdout or '').split('\n'):
            if 'DNS Servers' in line or 'DNS-серверы' in line or 'dns-серверы' in line.lower():
                parts = line.split(':', 1)
                if len(parts) > 1:
                    dns = parts[1].strip()
                    if dns and dns not in dns_servers:
                        dns_servers.append(dns)
        if dns_servers:
            return [_pass(ctx, 'diag_dns_servers', ', '.join(dns_servers[:5]))]
        return [_warn(ctx, 'diag_dns_not_detected')]
    except Exception as e:
        return [_err(ctx, 'diag_error_dns', e)]


def check_secure_dns(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        ps_cmd = (
            "Get-ChildItem -Recurse -Path 'HKLM:System\\CurrentControlSet\\Services\\"
            "Dnscache\\InterfaceSpecificParameters\\' -ErrorAction SilentlyContinue | "
            "Get-ItemProperty -ErrorAction SilentlyContinue | "
            "Where-Object { $_.DohFlags -gt 0 } | Measure-Object | Select-Object -ExpandProperty Count"
        )
        _, stdout, _ = _run_command(
            ['powershell', '-NoProfile', '-Command', ps_cmd],
            timeout=12,
        )
        count = (stdout or '').strip()
        if count.isdigit() and int(count) > 0:
            return [_pass(ctx, 'diag_secure_dns_passed')]
        return [_warn(ctx, 'diag_dns_configure'), _warn(ctx, 'diag_dns_win11')]
    except Exception:
        return [_warn(ctx, 'diag_dns_unknown')]


def check_adapters(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        _, stdout, _ = _run_command(['ipconfig'], timeout=8)
        adapters = []
        for line in (stdout or '').split('\n'):
            low = line.lower()
            if 'adapter' in low or 'адаптер' in low:
                adapters.append(line.strip())
        if adapters:
            return [_pass(ctx, 'diag_adapters_found', len(adapters))]
        return [_warn(ctx, 'diag_adapters_not_detected')]
    except Exception as e:
        return [_err(ctx, 'diag_error_adapters', e)]


# --- Конфликты ---

def check_adguard(ctx: DiagnosticsContext) -> List[ResultLine]:
    names = ctx.process_names()
    if 'adguardsvc.exe' in names or 'adguard.exe' in names:
        return [
            _fail(ctx, 'diag_adguard_found'),
            _info(ctx, 'diag_link_issue', 'https://github.com/Flowseal/zapret-discord-youtube/issues/417'),
        ]
    return [_pass(ctx, 'diag_adguard_passed')]


def check_killer(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        if 'Killer' in ctx.services_output():
            return [
                _fail(ctx, 'diag_killer_found'),
                _info(ctx, 'diag_link_issue', 'https://github.com/Flowseal/zapret-discord-youtube/issues/2512#issuecomment-2821119513'),
            ]
        return [_pass(ctx, 'diag_killer_passed')]
    except Exception as e:
        return [_err(ctx, 'diag_error_killer', e)]


def check_intel_connectivity(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        out = ctx.services_output()
        if 'Intel' in out and 'Connectivity' in out:
            return [
                _fail(ctx, 'diag_intel_found'),
                _info(ctx, 'diag_link_issue', 'https://github.com/ValdikSS/GoodbyeDPI/issues/541#issuecomment-2661670982'),
            ]
        return [_pass(ctx, 'diag_intel_passed')]
    except Exception as e:
        return [_err(ctx, 'diag_error_intel', e)]


def check_checkpoint(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        out = ctx.services_output()
        if 'TracSrvWrapper' in out or 'EPWD' in out:
            return [_fail(ctx, 'diag_checkpoint_found'), _fail(ctx, 'diag_checkpoint_uninstall')]
        return [_pass(ctx, 'diag_checkpoint_passed')]
    except Exception as e:
        return [_err(ctx, 'diag_error_checkpoint', e)]


def check_smartbyte(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        if 'SmartByte' in ctx.services_output():
            return [_fail(ctx, 'diag_smartbyte_found'), _fail(ctx, 'diag_smartbyte_uninstall')]
        return [_pass(ctx, 'diag_smartbyte_passed')]
    except Exception as e:
        return [_err(ctx, 'diag_error_smartbyte', e)]


def check_vpn(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        vpn_services = []
        for line in ctx.services_output().split('\n'):
            if 'VPN' in line.upper() and 'SERVICE_NAME' in line:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    vpn_services.append(parts[1].strip())
        if vpn_services:
            return [
                _warn(ctx, 'diag_vpn_found', ', '.join(vpn_services[:5])),
                _warn(ctx, 'diag_vpn_disable'),
            ]
        return [_pass(ctx, 'diag_vpn_passed')]
    except Exception as e:
        return [_err(ctx, 'diag_error_vpn', e)]


def check_warp(ctx: DiagnosticsContext) -> List[ResultLine]:
    names = ctx.process_names()
    out = ctx.services_output()
    if any(x in names for x in ('warp-svc.exe', 'cloudflare warp.exe')) or 'CloudflareWARP' in out:
        return [_warn(ctx, 'diag_warp_found'), _warn(ctx, 'diag_warp_disable')]
    return [_pass(ctx, 'diag_warp_passed')]


def check_proxifier(ctx: DiagnosticsContext) -> List[ResultLine]:
    names = ctx.process_names()
    if 'proxifier.exe' in names:
        return [_warn(ctx, 'diag_proxifier_found')]
    return [_pass(ctx, 'diag_proxifier_passed')]


def check_security_software(ctx: DiagnosticsContext) -> List[ResultLine]:
    suspects = {
        'norton': 'Norton',
        'ns.exe': 'Norton',
        'avp.exe': 'Kaspersky',
        'ekrn.exe': 'ESET',
        'mcafee': 'McAfee',
        'bdagent.exe': 'Bitdefender',
        'msmpeng.exe': 'Windows Defender',
    }
    names = ctx.process_names()
    found = []
    for proc, label in suspects.items():
        if proc in names:
            found.append(label)
    if found:
        return [_warn(ctx, 'diag_av_found', ', '.join(sorted(set(found))))]
    return [_pass(ctx, 'diag_av_passed')]


# --- Zapret / winws ---

def check_windivert_sys(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        bin_path = os.path.join(get_winws_path(), 'bin')
        sys_files = [f for f in os.listdir(bin_path) if f.lower().endswith('.sys')] if os.path.isdir(bin_path) else []
        if not sys_files:
            return [_fail(ctx, 'diag_windivert_not_found')]
        return [_pass(ctx, 'diag_windivert_found', ', '.join(sys_files))]
    except Exception as e:
        return [_err(ctx, 'diag_error_windivert', e)]


def check_winws_binary(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        exe = os.path.join(get_winws_path(), 'bin', 'winws.exe')
        if os.path.isfile(exe):
            return [_pass(ctx, 'diag_winws_binary_ok', exe)]
        return [_fail(ctx, 'diag_winws_binary_missing')]
    except Exception as e:
        return [_err(ctx, 'diag_error_winws_binary', e)]


def check_service_bat(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        path = os.path.join(get_winws_path(), 'service.bat')
        if os.path.isfile(path):
            return [_pass(ctx, 'diag_service_bat_ok')]
        return [_fail(ctx, 'diag_service_bat_missing')]
    except Exception as e:
        return [_err(ctx, 'diag_error_service_bat', e)]


def check_windivert_conflict(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        winws_running = 'winws.exe' in {p.lower() for p in ctx.process_names()}
        wd_state = ctx.service_state('WinDivert')
        windivert_active = wd_state in ('RUNNING', 'STOP_PENDING')
        if not winws_running and windivert_active:
            lines = [_warn(ctx, 'diag_windivert_attempt')]
            if ctx.auto_fix:
                if not _is_user_admin():
                    lines.append(_warn(ctx, 'diag_autofix_need_admin'))
                else:
                    try:
                        _run_command(['net', 'stop', 'WinDivert'], timeout=5)
                        _run_command(['sc', 'delete', 'WinDivert'], timeout=5)
                        if ctx.service_state('WinDivert') is None:
                            lines.append(_pass(ctx, 'diag_windivert_removed'))
                        else:
                            lines.append(_fail(ctx, 'diag_windivert_delete_failed'))
                    except Exception as e:
                        lines.append(_fail(ctx, 'diag_windivert_error', str(e)))
            return lines
        return [_pass(ctx, 'diag_windivert_conflict_passed')]
    except Exception as e:
        return [_err(ctx, 'diag_error_windivert_conflict', e)]


def check_zapret_service(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        state = ctx.service_state('zapret')
        if state is None:
            return [_warn(ctx, 'diag_zapret_not_installed')]
        if state == 'RUNNING':
            lines = [_pass(ctx, 'diag_zapret_running')]
            key = None
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"System\CurrentControlSet\Services\zapret",
                )
                strategy_path, _ = winreg.QueryValueEx(key, "zapret-discord-youtube")
                lines.append(_pass(ctx, 'diag_zapret_strategy', strategy_path))
            except Exception:
                pass
            finally:
                if key is not None:
                    try:
                        winreg.CloseKey(key)
                    except Exception:
                        pass
            return lines
        if state == 'STOPPED':
            return [_warn(ctx, 'diag_zapret_stopped')]
        return [_warn(ctx, 'diag_zapret_unknown')]
    except Exception as e:
        return [_err(ctx, 'diag_error_zapret', e)]


def check_winws_process(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        pids = []
        for proc in psutil.process_iter(['name', 'pid']):
            if (proc.info.get('name') or '').lower() == 'winws.exe':
                pids.append(proc.info['pid'])
        if not pids:
            return [_warn(ctx, 'diag_winws_not_running')]
        if len(pids) > 1:
            return [
                _warn(ctx, 'diag_winws_multiple', len(pids)),
                _pass(ctx, 'diag_winws_running', pids[0]),
            ]
        return [_pass(ctx, 'diag_winws_running', pids[0])]
    except Exception as e:
        return [_err(ctx, 'diag_error_winws', e)]


def check_winws_folder(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        folder = get_winws_path()
        if not os.path.isdir(folder):
            return [_fail(ctx, 'diag_winws_folder_missing', folder)]
        lines = [_pass(ctx, 'diag_winws_folder_ok', folder)]
        test_file = os.path.join(folder, '.zd_write_test')
        try:
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write('ok')
            os.remove(test_file)
            lines.append(_pass(ctx, 'diag_winws_folder_writable'))
        except OSError:
            lines.append(_fail(ctx, 'diag_winws_folder_not_writable'))
        free = shutil.disk_usage(folder).free // (1024 * 1024)
        if free < 50:
            lines.append(_warn(ctx, 'diag_disk_low', free))
        else:
            lines.append(_pass(ctx, 'diag_disk_ok', free))
        return lines
    except Exception as e:
        return [_err(ctx, 'diag_error_winws_folder', e)]


def check_strategies(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        folder = get_winws_path()
        if not os.path.isdir(folder):
            return [_warn(ctx, 'diag_strategies_not_found')]
        bats = [
            f for f in os.listdir(folder)
            if f.endswith('.bat') and f.lower() != 'service.bat'
            and os.path.isfile(os.path.join(folder, f))
        ]
        if bats:
            return [_pass(ctx, 'diag_strategies_found', len(bats))]
        return [_warn(ctx, 'diag_strategies_empty')]
    except Exception as e:
        return [_err(ctx, 'diag_error_strategies', e)]


def check_targets(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        path = os.path.join(get_winws_path(), 'utils', 'targets.txt')
        if not os.path.isfile(path):
            return [_warn(ctx, 'diag_targets_not_found')]
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            count = len([ln for ln in f if ln.strip() and not ln.strip().startswith('#')])
        if count == 0:
            return [_warn(ctx, 'diag_targets_empty')]
        return [_pass(ctx, 'diag_targets_found', count)]
    except Exception as e:
        return [_err(ctx, 'diag_error_targets', e)]


def check_hosts(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        if not os.path.isfile(hosts_path):
            return [_fail(ctx, 'diag_hosts_not_found')]
        with open(hosts_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines_count = len([ln for ln in f if ln.strip() and not ln.strip().startswith('#')])
        result = [_pass(ctx, 'diag_hosts_found', lines_count)]
        if not os.access(hosts_path, os.W_OK):
            result.append(_warn(ctx, 'diag_hosts_not_writable'))
        return result
    except Exception as e:
        return [_err(ctx, 'diag_error_hosts', e)]


def check_network_connectivity(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        code, stdout, stderr = _run_command(
            ['ping', '-n', '1', '-w', '2000', '1.1.1.1'],
            timeout=6,
        )
        combined = f"{stdout}\n{stderr}".lower()
        if code == 0 and ('ttl=' in combined or 'ttl =' in combined):
            return [_pass(ctx, 'diag_network_ping_ok')]
        return [_warn(ctx, 'diag_network_ping_fail')]
    except Exception as e:
        return [_err(ctx, 'diag_error_network_ping', e)]


def check_http_connectivity(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        from src.entities.network.network_status import check_network_status

        status = check_network_status(force=True)
        if status.http_ok:
            return [_pass(ctx, 'diag_http_ok')]
        return [_warn(ctx, 'diag_http_fail')]
    except Exception as e:
        return [_err(ctx, 'diag_error_http', e)]


def check_default_gateway(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        _, stdout, _ = _run_command(['ipconfig'], timeout=8)
        gateways = []
        for line in (stdout or '').splitlines():
            low = line.lower()
            if 'default gateway' in low or 'основной шлюз' in low:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    gw = parts[1].strip()
                    if gw and gw not in gateways:
                        gateways.append(gw)
        if gateways:
            return [_pass(ctx, 'diag_gateway_found', ', '.join(gateways[:3]))]
        return [_warn(ctx, 'diag_gateway_not_found')]
    except Exception as e:
        return [_err(ctx, 'diag_error_gateway', e)]


def check_loopback(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        code, stdout, _ = _run_command(['ping', '-n', '1', '-w', '1000', '127.0.0.1'], timeout=4)
        if code == 0 and 'ttl' in (stdout or '').lower():
            return [_pass(ctx, 'diag_loopback_ok')]
        return [_warn(ctx, 'diag_loopback_fail', '127.0.0.1')]
    except Exception as e:
        return [_err(ctx, 'diag_error_loopback', e)]


def check_uac_policy(ctx: DiagnosticsContext) -> List[ResultLine]:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System",
        )
        enable_lua, _ = winreg.QueryValueEx(key, "EnableLUA")
        consent_prompt, _ = winreg.QueryValueEx(key, "ConsentPromptBehaviorAdmin")
        winreg.CloseKey(key)
        if enable_lua:
            return [_pass(ctx, 'diag_uac_enabled', consent_prompt)]
        return [_warn(ctx, 'diag_uac_disabled')]
    except Exception as e:
        return [_err(ctx, 'diag_error_uac', e)]


def run_custom_command(ctx: DiagnosticsContext, spec: dict) -> List[ResultLine]:
    name = str(spec.get('name') or spec.get('id') or 'custom')
    command = spec.get('command')
    if not command:
        return [_warn(ctx, 'diag_custom_empty_command', name)]

    shell = bool(spec.get('shell', isinstance(command, str)))
    timeout = int(spec.get('timeout', 10) or 10)
    lines: List[ResultLine] = [_info(ctx, 'diag_custom_start', name)]

    code, stdout, stderr = _run_command(command, shell=shell, timeout=timeout)
    output = '\n'.join(part for part in (stdout, stderr) if part).strip()
    if output:
        lines.append(_info(ctx, 'diag_custom_output_label'))
        output_lines = output.splitlines()
        max_lines = 80
        if len(output_lines) > max_lines:
            output_lines = output_lines[:max_lines] + ['...']
        for line in output_lines:
            lines.append(('output', line))

    ignore_returncode = bool(spec.get('ignore_returncode'))

    expect_code = spec.get('expect_returncode')
    if expect_code is not None and code != int(expect_code):
        return lines + [_fail(ctx, 'diag_custom_returncode', name, code, expect_code)]

    expect_stdout = spec.get('expect_stdout')
    if expect_stdout and expect_stdout not in (stdout or ''):
        return lines + [_fail(ctx, 'diag_custom_expect_stdout', name, expect_stdout)]

    fail_if_stdout = spec.get('fail_if_stdout')
    if fail_if_stdout and fail_if_stdout in (stdout or ''):
        return lines + [_fail(ctx, 'diag_custom_fail_pattern', name, fail_if_stdout)]

    fail_if_stderr = spec.get('fail_if_stderr')
    if fail_if_stderr and fail_if_stderr in (stderr or ''):
        return lines + [_fail(ctx, 'diag_custom_fail_stderr', name, fail_if_stderr)]

    if code != 0 and expect_code is None and not ignore_returncode:
        return lines + [_fail(ctx, 'diag_custom_failed', name, code)]

    return lines + [_pass(ctx, 'diag_custom_passed', name)]


# Реестр всех проверок
DIAGNOSTIC_CHECKS: List[CheckDefinition] = [
    # Система
    CheckDefinition('bfe', 'cat_system', True, check_bfe),
    CheckDefinition('firewall', 'cat_system', True, check_firewall),
    CheckDefinition('tcp_timestamps', 'cat_system', True, check_tcp_timestamps),
    CheckDefinition('admin', 'cat_system', True, check_admin),
    CheckDefinition('windows_version', 'cat_system', False, check_windows_version),
    CheckDefinition('uac_policy', 'cat_system', False, check_uac_policy),
    # Сеть
    CheckDefinition('system_proxy', 'cat_network', True, check_system_proxy),
    CheckDefinition('winhttp_proxy', 'cat_network', False, check_winhttp_proxy),
    CheckDefinition('dns_servers', 'cat_network', False, check_dns_servers),
    CheckDefinition('secure_dns', 'cat_network', False, check_secure_dns),
    CheckDefinition('adapters', 'cat_network', False, check_adapters),
    CheckDefinition('network_connectivity', 'cat_network', True, check_network_connectivity),
    CheckDefinition('http_connectivity', 'cat_network', False, check_http_connectivity, platform='all'),
    CheckDefinition('default_gateway', 'cat_network', False, check_default_gateway),
    CheckDefinition('loopback', 'cat_network', False, check_loopback),
    # Конфликты
    CheckDefinition('adguard', 'cat_conflicts', True, check_adguard),
    CheckDefinition('killer', 'cat_conflicts', True, check_killer),
    CheckDefinition('intel_connectivity', 'cat_conflicts', True, check_intel_connectivity),
    CheckDefinition('checkpoint', 'cat_conflicts', True, check_checkpoint),
    CheckDefinition('smartbyte', 'cat_conflicts', True, check_smartbyte),
    CheckDefinition('vpn', 'cat_conflicts', True, check_vpn),
    CheckDefinition('warp', 'cat_conflicts', True, check_warp),
    CheckDefinition('proxifier', 'cat_conflicts', False, check_proxifier),
    CheckDefinition('security_software', 'cat_conflicts', False, check_security_software),
    # Zapret
    CheckDefinition('windivert_sys', 'cat_zapret', True, check_windivert_sys),
    CheckDefinition('winws_binary', 'cat_zapret', True, check_winws_binary),
    CheckDefinition('service_bat', 'cat_zapret', True, check_service_bat),
    CheckDefinition('winws_folder', 'cat_zapret', True, check_winws_folder),
    CheckDefinition('strategies', 'cat_zapret', True, check_strategies),
    CheckDefinition('targets', 'cat_zapret', False, check_targets),
    CheckDefinition('hosts', 'cat_zapret', False, check_hosts),
    CheckDefinition('windivert_conflict', 'cat_zapret', True, check_windivert_conflict),
    CheckDefinition('zapret_service', 'cat_zapret', False, check_zapret_service),
    CheckDefinition('winws_process', 'cat_zapret', False, check_winws_process),
]

from src.platform.linux.diagnostics_linux import (  # noqa: E402
    check_linux_conf_env,
    check_linux_dns,
    check_linux_hosts,
    check_linux_init_backend,
    check_linux_iptables,
    check_linux_network_connectivity,
    check_linux_nfqws_process,
    check_linux_nftables,
    check_linux_routes,
    check_linux_runtime_adapter,
    check_linux_strategies,
    check_linux_sudo,
    check_linux_systemd_zapret,
)

LINUX_DIAGNOSTIC_CHECKS: List[CheckDefinition] = [
    CheckDefinition('linux_runtime', 'cat_zapret', True, check_linux_runtime_adapter, platform='linux'),
    CheckDefinition('linux_conf_env', 'cat_zapret', True, check_linux_conf_env, platform='linux'),
    CheckDefinition('linux_strategies', 'cat_zapret', True, check_linux_strategies, platform='linux'),
    CheckDefinition('linux_nfqws_process', 'cat_zapret', False, check_linux_nfqws_process, platform='linux'),
    CheckDefinition('linux_systemd_zapret', 'cat_zapret', False, check_linux_systemd_zapret, platform='linux'),
    CheckDefinition('linux_nftables', 'cat_system', True, check_linux_nftables, platform='linux'),
    CheckDefinition('linux_sudo', 'cat_system', True, check_linux_sudo, platform='linux'),
    CheckDefinition('linux_dns', 'cat_network', False, check_linux_dns, platform='linux'),
    CheckDefinition('linux_routes', 'cat_network', False, check_linux_routes, platform='linux'),
    CheckDefinition('linux_network_connectivity', 'cat_network', True, check_linux_network_connectivity, platform='linux'),
    CheckDefinition('linux_hosts', 'cat_zapret', False, check_linux_hosts, platform='linux'),
    CheckDefinition('linux_iptables', 'cat_system', False, check_linux_iptables, platform='linux'),
    CheckDefinition('linux_init_backend', 'cat_system', False, check_linux_init_backend, platform='linux'),
]

DIAGNOSTIC_CHECKS = DIAGNOSTIC_CHECKS + LINUX_DIAGNOSTIC_CHECKS

CHECKS_BY_ID: Dict[str, CheckDefinition] = {c.check_id: c for c in DIAGNOSTIC_CHECKS}


def checks_for_platform(platform: str | None = None) -> List[CheckDefinition]:
    from src.platform import detect_platform

    current = platform or detect_platform()
    return [c for c in DIAGNOSTIC_CHECKS if c.platform in (current, "all")]


def default_enabled_checks() -> Dict[str, bool]:
    return {c.check_id: True for c in checks_for_platform()}


def critical_check_ids() -> List[str]:
    return [c.check_id for c in checks_for_platform() if c.critical]


def run_diagnostics(
    lang: str,
    enabled: Optional[Dict[str, bool]] = None,
    auto_fix: bool = False,
    custom_config: Optional[dict] = None,
    stop_requested: Optional[StopCallback] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> Tuple[List[ResultLine], Dict[str, int]]:
    """Выполняет выбранные проверки. Возвращает (строки, сводка)."""
    stop_cb = stop_requested or (lambda: False)
    ctx = DiagnosticsContext(lang=lang, auto_fix=auto_fix, stop_requested=stop_cb)
    enabled = enabled or default_enabled_checks()
    results: List[ResultLine] = []
    summary = {'pass': 0, 'fail': 0, 'warn': 0, 'info': 0}

    def _emit(status: str, msg: str) -> None:
        results.append((status, msg))
        if progress_callback is not None:
            progress_callback(status, msg)

    by_category: Dict[str, List[CheckDefinition]] = {}
    for check in checks_for_platform():
        if enabled.get(check.check_id, True):
            by_category.setdefault(check.category, []).append(check)

    for category, checks in by_category.items():
        if ctx.should_stop():
            _emit('info', tr('diag_stopped', lang))
            break
        _emit('info', f'=== {tr(category, lang)} ===')
        for check in checks:
            if ctx.should_stop():
                _emit('info', tr('diag_stopped', lang))
                break
            try:
                lines = check.run(ctx)
            except Exception as e:
                lines = [('warn', ctx.t('diag_check_error', check.check_id, str(e)))]
            for status, msg in lines:
                if status == "fail" and check.critical:
                    status = "critical"
                _emit(status, msg)
                if status in summary:
                    summary[status] += 1
                elif status == "critical":
                    summary["fail"] += 1

    custom_commands = []
    if isinstance(custom_config, dict):
        raw_cmds = custom_config.get('custom_commands')
        if isinstance(raw_cmds, list):
            custom_commands = [c for c in raw_cmds if isinstance(c, dict)]

    if custom_commands and not ctx.should_stop():
        _emit('info', f'=== {tr("cat_custom", lang)} ===')
        for spec in custom_commands:
            if ctx.should_stop():
                _emit('info', tr('diag_stopped', lang))
                break
            if not spec.get('enabled', True):
                continue
            try:
                lines = run_custom_command(ctx, spec)
            except Exception as e:
                name = spec.get('name') or spec.get('id') or 'custom'
                lines = [('warn', ctx.t('diag_custom_error', name, str(e)))]
            for status, msg in lines:
                if status == "fail" and spec.get("critical"):
                    status = "critical"
                _emit(status, msg)
                if status in summary:
                    summary[status] += 1
                elif status == "critical":
                    summary["fail"] += 1

    return results, summary
