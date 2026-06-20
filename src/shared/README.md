# shared

Слой **shared** — переиспользуемая инфраструктура без бизнес-сценариев.

## Сегменты

| Папка | Назначение |
|-------|------------|
| [i18n/](i18n/) | Локализация (`tr()`) |
| [lib/](lib/) | Утилиты: пути, версии, кодировки, логи |
| [ui/](ui/) | Тема, базовые окна, codicons, ассеты |

## Правила

- Shared **не** импортирует `entities`, `features`, `pages`.
- Исключение: lazy import `theme` из assets (shared → shared).

## Наиболее используемые импорты

```python
from src.shared.i18n.translator import tr
from src.shared.lib.path_utils import get_winws_path
from src.shared.ui import theme
from src.shared.ui.assets.embedded_assets import get_app_icon
```
