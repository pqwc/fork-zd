# shared/ui/assets

Встроенные и кэшируемые графические ресурсы.

## Модули

| Файл | Роль |
|------|------|
| `embedded_assets.py` | Base64 SVG fallback, `get_app_icon()`, `get_svg_qbytearray()` |
| `embedded_style.py` | `EmbeddedStyle` — QProxyStyle с SVG indicators |
| `codicons_manager.py` | Загрузка codicons в AppData (26 иконок) |
| `codicon_utils.py` | `codicon_icon()`, `codicon_colored_pixmap()` |

## Codicons

```batch
python scripts/download_codicons.py
```

Кэш: `%APPDATA%\ZapretDesktop\codicons\`

## Цепочка SVG

`get_svg_qbytearray(name)` → codicons на диске → fallback из `SVG_BASE64`
