# features

Слой **features** — пользовательские сценарии: диалоги, окна, действия с UI.

## Сегменты

| Папка | Сценарий |
|-------|----------|
| [settings/](settings/) | Диалог настроек |
| [diagnostics/](diagnostics/) | UI диагностики системы |
| [updates/](updates/) | Обновления app/zapret, VSUpdateDialog, addons |
| [winws_setup/](winws_setup/) | Первичная настройка папки winws |
| [editor/](editor/) | Редактор lists/etc/strategies |
| [strategy/](strategy/) | Конструктор .bat стратегий |
| [tools/](tools/) | Bin creator |
| [export/](export/) | Экспорт bundle ZIP |
| [autostart/](autostart/) | Task Scheduler автозапуск |
| [setup/](setup/) | First run (не используется) |

## Структура сегмента

```
features/<name>/
  README.md
  ui/          # PyQt окна и диалоги
  lib/         # опционально: логика без Qt
  model/       # опционально: будущие model/api
```

## Правила

- Feature импортирует: `entities`, `shared`, `widgets`.
- Feature **не** импортирует другие features напрямую (через pages/mixins — OK).
- Доменную логику выносите в `entities/`.

## Подключение к главному окну

Через mixin в `pages/main/mixins/` или menu/tools mixin.
