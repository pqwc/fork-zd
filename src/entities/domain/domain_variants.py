"""Поиск реальных доменов и поддоменов сайта (Certificate Transparency и др.)."""
from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import quote, urlparse

try:
    import requests
except ImportError:
    requests = None

COMPOUND_SUFFIXES = (
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au",
    "co.jp", "ne.jp", "or.jp", "com.br", "com.mx", "com.ar", "co.nz",
    "com.tr", "com.ua", "com.pl", "co.in", "com.cn", "com.hk", "com.sg",
    "com.tw", "co.kr", "com.co", "com.pe", "com.ve", "com.ec", "com.my",
    "com.ph", "com.pk", "co.za", "co.id", "com.vn", "com.sa", "com.eg",
)

_HOSTNAME_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    re.IGNORECASE,
)

OnDomainCallback = Callable[[str], None]
OnStatusCallback = Callable[[str], None]


def _normalize_input(value: str) -> str:
    value = (value or "").strip().lower()
    if not value:
        return ""
    if "://" in value:
        try:
            parsed = urlparse(value)
            value = parsed.netloc or parsed.path.split("/")[0]
        except Exception:
            pass
    if value.startswith("www."):
        value = value[4:]
    if ":" in value:
        value = value.split(":", 1)[0]
    return value.strip(".").strip()


def extract_apex_domain(value: str) -> str:
    """example.com из www.api.example.com или https://example.co.uk/path."""
    domain = _normalize_input(value)
    if not domain or "." not in domain:
        raise ValueError("invalid_domain")

    for suffix in sorted(COMPOUND_SUFFIXES, key=len, reverse=True):
        needle = f".{suffix}"
        if domain == suffix or domain.endswith(needle):
            host = domain[: -len(needle)] if domain != suffix else ""
            if host:
                label = host.split(".")[-1]
                return f"{label}.{suffix}"
            break

    parts = domain.split(".")
    if len(parts) < 2:
        raise ValueError("invalid_domain")
    return ".".join(parts[-2:])


def _clean_hostname(name: str, apex: str) -> str | None:
    name = (name or "").strip().lower()
    if not name:
        return None
    if name.startswith("*."):
        name = name[2:]
    if name.startswith("."):
        name = name[1:]
    if ":" in name:
        name = name.split(":", 1)[0]
    if not _HOSTNAME_RE.match(name):
        return None
    if name == apex or name.endswith(f".{apex}"):
        return name
    return None


def _emit_domain(found: set[str], host: str, on_domain: OnDomainCallback | None) -> None:
    if host in found:
        return
    found.add(host)
    if on_domain:
        on_domain(host)


def _fetch_crtsh(
    apex: str,
    found: set[str],
    on_domain: OnDomainCallback | None = None,
    timeout: int = 45,
) -> str | None:
    if not requests:
        return "requests_missing"

    url = f"https://crt.sh/?q={quote('%.' + apex)}&output=json"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return str(exc)

    if not isinstance(data, list):
        return None

    for entry in data:
        raw = entry.get("name_value") or entry.get("common_name") or ""
        for part in str(raw).split("\n"):
            host = _clean_hostname(part, apex)
            if host:
                _emit_domain(found, host, on_domain)
    return None


def _fetch_hackertarget(
    apex: str,
    found: set[str],
    on_domain: OnDomainCallback | None = None,
    timeout: int = 20,
) -> str | None:
    if not requests:
        return "requests_missing"

    url = f"https://api.hackertarget.com/hostsearch/?q={quote(apex)}"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        text = response.text.strip()
    except Exception as exc:
        return str(exc)

    if not text or text.lower().startswith("error"):
        return text or None

    for line in text.splitlines():
        host_part = line.split(",")[0].strip()
        host = _clean_hostname(host_part, apex)
        if host:
            _emit_domain(found, host, on_domain)
    return None


def discover_site_domains(
    root: str,
    on_domain: OnDomainCallback | None = None,
    on_status: OnStatusCallback | None = None,
) -> tuple[list[str], str | None]:
    """
    Ищет домены/поддомены через crt.sh и hostsearch.
    on_domain вызывается при нахождении каждого нового домена.
  """
    apex = extract_apex_domain(root)
    found: set[str] = set()
    errors: list[str] = []

    _emit_domain(found, apex, on_domain)

    if on_status:
        on_status("crt.sh")
    crt_err = _fetch_crtsh(apex, found, on_domain)
    if crt_err and crt_err != "requests_missing":
        errors.append(f"crt.sh: {crt_err}")

    if on_status:
        on_status("hostsearch")
    ht_err = _fetch_hackertarget(apex, found, on_domain)
    if ht_err and ht_err not in ("requests_missing", "API count exceeded", "error"):
        errors.append(f"hostsearch: {ht_err}")

    if not requests:
        return sorted(found), "requests_missing"

    if len(found) <= 1 and errors:
        return [], errors[0]

    note = "; ".join(errors) if errors else None
    return sorted(found, key=lambda d: (d.count("."), d)), note


# Обратная совместимость
def generate_domain_variants(root: str, **_kwargs) -> list[str]:
    domains, err = discover_site_domains(root)
    if err and not domains:
        raise ValueError(err)
    return domains
