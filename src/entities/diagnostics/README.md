# entities/diagnostics

Логика диагностики системы (без UI).

## Модули

| Файл | Роль |
|------|------|
| `diagnostics_runner.py` | ~30 проверок BFE, WinDivert, DNS, hosts… |
| `diagnostics_config.py` | Пользовательские команды, i18n конфига |

## UI

`features/diagnostics/ui/diagnostics_dialog.py`

## Конфиг на диске

`%APPDATA%\ZapretDesktop\diagnostics_config.json`
