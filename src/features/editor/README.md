# features/editor

Редактор списков, hosts (drivers\etc) и .bat стратегий.

## Структура

| Папка | Содержимое |
|-------|------------|
| `ui/` | `unified_editor_window.py` (основной), legacy editors, find/country/domain dialogs |
| `lib/` | line editor, highlighters, prompts, autocomplete |

## Точка входа

```python
from src.features.editor.ui.unified_editor_window import get_unified_editor_window
```

Singleton-окно редактора.

## Mixin

- `pages/main/mixins/tools_mixin.py`
