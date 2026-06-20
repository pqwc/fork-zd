# shared/ui

Design system приложения: тема, базовые окна, нативный chrome Windows.

## Модули

| Файл | Роль |
|------|------|
| `theme.py` | Dark/light палитры, QSS-хелперы |
| `standard_window.py` | `StandardMainWindow` |
| `standard_dialog.py` | `StandardDialog` |
| `message_box_utils.py` | Themed QMessageBox |
| `system_tray.py` | Иконка и меню трея |
| `update_progress.py` | Фабрика диалога прогресса |
| `window_styles.py` / `native_window_styles.py` | Win10/11 оформление |
| [assets/](assets/) | SVG, codicons, EmbeddedStyle |

## Импорт темы

```python
from src.shared.ui import theme

theme.palette().fg_text
theme.is_light()
```
