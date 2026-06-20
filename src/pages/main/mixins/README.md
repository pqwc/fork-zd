# pages/main/mixins

Mixin-модули главного окна — композиция features на уровне page.

| Mixin | Ответственность |
|-------|-----------------|
| `lifecycle_mixin` | Startup/shutdown, tray, winws watcher |
| `strategy_run_mixin` | Start/stop .bat, process monitor |
| `strategy_list_mixin` | Discovery стратегий, combo |
| `updates_mixin` | App/zapret updates, addons |
| `settings_mixin` | Settings dialog |
| `menu_mixin` | Menus, shortcuts |
| `ui_mixin` | Layout, footer, progress |
| `tools_mixin` | Test, editor, bin, creator |
| `diagnostics_mixin` | Diagnostics dialog |
| `strategy_flags_mixin` | Mass /B flags |
| `filters_mixin` | Game/IPSet filters |
| `version_mixin` | Footer version info |
| `network_mixin` | Footer network icon |

## MRO

Порядок в `window.py` влияет на `super()` в lifecycle-методах. При изменении — проверьте `closeEvent`, `__init__`, `showEvent`.

## Правило

Mixin импортирует features/entities, **не** другие mixins (кроме shared state через `self`).
