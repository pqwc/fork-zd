"""Сравнение версий с поддержкой суффиксов (например 1.9.7b)."""
import re
from typing import List, Optional, Tuple


VersionPart = Tuple[int, str]


def _parse_version(version: str) -> Optional[List[VersionPart]]:
    if not version:
        return None
    normalized = version.lstrip('vV').strip()
    if not normalized or normalized.lower() == 'unknown':
        return None
    parts: List[VersionPart] = []
    for segment in normalized.split('.'):
        match = re.match(r'^(\d+)(.*)$', segment.strip())
        if match:
            parts.append((int(match.group(1)), match.group(2).lower()))
        else:
            parts.append((0, segment.strip().lower()))
    return parts or None


def compare_versions(version1: str, version2: str) -> Optional[int]:
    """Сравнивает версии. -1 / 0 / 1 или None, если нужен строковый fallback."""
    parts1 = _parse_version(version1)
    parts2 = _parse_version(version2)
    if parts1 is None or parts2 is None:
        return None

    max_len = max(len(parts1), len(parts2))
    for i in range(max_len):
        num1, suffix1 = parts1[i] if i < len(parts1) else (0, '')
        num2, suffix2 = parts2[i] if i < len(parts2) else (0, '')
        if num1 != num2:
            return 1 if num1 > num2 else -1
        if suffix1 != suffix2:
            return 1 if suffix1 > suffix2 else -1
    return 0


def is_version_newer(latest: str, current: str) -> bool:
    """True, если latest строго новее current."""
    if not latest or not current:
        return bool(latest and latest != current)
    if latest == current:
        return False
    cmp = compare_versions(latest, current)
    if cmp is not None:
        return cmp > 0
    return latest != current
