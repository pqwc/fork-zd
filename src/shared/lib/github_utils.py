"""Утилиты для работы с GitHub-репозиториями в настройках обновлений."""
from __future__ import annotations


def resolve_github_repo(repo_setting: str, default: str) -> str:
    """Преобразует owner/repo или URL GitHub в slug owner/repo."""
    value = (repo_setting or "").strip()
    if not value:
        return default

    if value.lower().startswith(("http://", "https://")):
        try:
            from urllib.parse import urlparse

            parsed = urlparse(value)
            path = (parsed.path or "").strip("/ ")
            parts = path.split("/")
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
        except Exception:
            pass
        return default

    if "/" in value:
        return value

    return default
