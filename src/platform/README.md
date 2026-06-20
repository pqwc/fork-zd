# Platform layer (`src/platform/`)

OS-специфичная логика ZapretDesktop: пути, привилегии, runtime.

## Правило

`pages/` и `features/` импортируют только `src.platform`, не `ctypes` / `schtasks` / `service.sh` напрямую.

## API

```python
from src.platform import (
    detect_platform,
    is_linux,
    is_windows,
    get_paths_backend,
    get_privilege_backend,
    get_runtime_backend,
    linux_runtime_configured,
    platform_feature_available,
)
```

## Override для тестов

```bash
export ZAPRETDESKTOP_PLATFORM=linux
export ZAPRETDESKTOP_RUNTIME_PATH=/path/to/zapret-linux
```

На Windows/Linux host override игнорируется, если не совпадает с реальной ОС.

## Модули

| Backend | Windows | Linux |
|---------|---------|-------|
| PathsBackend | `paths_win.py` | `paths_xdg.py` |
| PrivilegeBackend | UAC elevation | без root в GUI |
| RuntimeBackend | `runtime_winws.py` (winws.exe) | `runtime_service_sh.py` (service.sh) |
| LinuxRuntimeManager | — | nfqws lifecycle, systemd |

## Init systems (Linux)

Поддерживается **systemd** (через `service.sh service …`) и ручной запуск.  
**OpenRC / runit** — не поддерживаются.

## Документация

- [docs/LINUX_INSTALL.md](../../docs/LINUX_INSTALL.md) — установка адаптера
- [docs/DEVELOPMENT.md](../../docs/DEVELOPMENT.md) — разработка и тесты
