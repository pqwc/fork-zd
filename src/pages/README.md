# pages

Слой **pages** — полноэкранные композиции (экраны приложения).

## Сегменты

| Папка | Описание |
|-------|----------|
| [main/](main/) | Главное окно `MainWindow`, workers, mixins |
| [test/](test/) | Окно тестирования стратегий `TestWindow` |

## Правила

- Pages **собирают** features, entities, widgets и shared.
- Бизнес-логику держите в `entities` или `features`, не в pages.
- Mixins — единственное место «склейки» главного окна с features.

## Импорты

```python
from src.pages.main import MainWindow
from src.pages.test.test_window import TestWindow
```
