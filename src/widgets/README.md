# widgets

Слой **widgets** — переиспользуемые UI-компоненты без привязки к домену zapret.

## Компоненты

| Файл | Назначение |
|------|------------|
| `codicon_button.py` | Кнопка с SVG-иконкой codicon |
| `custom_combobox.py` | Combobox с темой и chevron |
| `custom_checkbox.py` | Checkbox через EmbeddedStyle |
| `custom_scrollbar.py` / `custom_overlay_scrollbar.py` | Кастомный скролл |
| `custom_context_widgets.py` | LineEdit/SpinBox/TextEdit с контекстным меню |
| `style_menu.py` | Themed QMenu |
| `unified_toolbar.py` | Панель с codicons |
| `breadcrumb_widget.py` | Хлебные крошки редактора |
| `animated_progressbar.py` | Indeterminate progress |
| `fake_header_table.py` | Таблица с кастомным заголовком |
| `label_menu_widget.py` | Label + выпадающее меню |
| `rounded_clip.py` | Скруглённая обрезка |

## Правила

- Только `shared` (+ другие `widgets`).
- **Не** импортировать `features`, `entities`, `pages`.
- Строки UI — через `tr()` из `shared/i18n`.

## Пример

```python
from src.widgets.codicon_button import CodiconButton
from src.widgets.custom_combobox import CustomComboBox
```
