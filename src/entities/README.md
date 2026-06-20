# entities

Слой **entities** — доменная логика без привязки к конкретному экрану.

## Сегменты

| Папка | Домен |
|-------|-------|
| [config/](config/) | Конфиг приложения (config.json) |
| [winws/](winws/) | Процессы winws, версия из service.bat |
| [strategy/](strategy/) | Генерация .bat стратегий |
| [diagnostics/](diagnostics/) | Runner и config диагностики |
| [network/](network/) | Ping/HTTP статус сети |
| [domain/](domain/) | Поиск доменных вариантов (crt.sh) |
| [zapret/](zapret/) | Обновление zapret с GitHub |

## Правила

- **Без PyQt** в идеале (исключение: минимальные зависимости допустимы, но избегайте).
- Импорт только из `shared/`.
- Не импортировать `features`, `pages`, `widgets`.

## Пример

```python
from src.entities.config.config_manager import ConfigManager
from src.entities.winws.winws_manager import WinwsManager
from src.entities.zapret.zapret_updater import ZapretUpdater
```
