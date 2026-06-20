# app

Слой **app** — глобальная инициализация приложения и обработчики, не привязанные к конкретной странице.

## Содержимое

| Файл | Назначение |
|------|------------|
| `launch_options.py` | Разбор CLI / launch_args.txt |
| `launch_registry.py` | Реестр флагов (-r, --recover, …) |
| `launch_recovery.py` | Полный сброс AppData (`-F`) |
| `launch_args_display.py` | Справка с подсветкой в настройках |
| `critical_error_dialog.py` | Диалог критической ошибки (excepthook) |

## CLI / параметры запуска

```batch
ZapretDesktop.exe -h
ZapretDesktop.exe -F -I
ZapretDesktop.exe -a -r -u
python ZapretDesktop.py --full-reset
```

| Короткий | Длинный | Назначение |
|----------|---------|------------|
| `-F` | `--full-reset` | Полный сброс config + кэш |
| `-r` | `--recover` | Восстановить winws/стратегию |
| `-u` | `--check-updates` | Проверить все обновления |
| `-z` | `--check-zapret` | Только zapret |
| `-p` | `--check-app` | Только программа |
| `-U` | `--no-updates` | Без проверки обновлений |
| `-a` | `--autostart` | Автозагрузка |
| `-m` | `--minimized` | Старт в трей |
| `-S` | `--skip-winws-setup` | Без диалога winws |
| `-N` | `--no-auto-start-strategy` | Без автозапуска стратегии |
| `-I` | `--reset-single-instance` | Сброс блокировки экземпляра |
| `-s` | `--safe-mode` | Безопасный режим |

**Exe без argv:** `%APPDATA%\ZapretDesktop\launch_args.txt` (одна строка, `#` — комментарий).

Справка с подсветкой: **Настройки → Дополнительно → Параметры запуска**.

## Правила

- Не импортировать `pages` и `features` (кроме lib без UI-циклов).
- Точка входа: `ZapretDesktop.py`.
