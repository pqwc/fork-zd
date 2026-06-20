# shared/i18n

Интернационализация ZapretDesktop (RU / EN).

## API

```python
from src.shared.i18n.translator import tr, tr_platform

# tr(key: str, language: str = "ru") -> str
label.setText(tr("home_start_button", self.language))

# Платформо-зависимый ключ: на Linux ищет "{base}_linux", иначе base
title.setText(tr_platform("menu_open_winws_folder", self.language))

# Плейсхолдеры — через str.format() на результате tr()
msg = tr("bin_creator_success", lang).format(path)
```

`language` — `"ru"` или `"en"` из настроек (`config.json` → `app.language`).

## Добавление строк

1. Добавьте ключ в **оба** словаря `TRANSLATIONS["ru"]` и `TRANSLATIONS["en"]` в `translator.py`.
2. Используйте префикс: `diag_`, `editor_`, `settings_`, `home_`, …
3. Запустите `python -m pytest tests/test_i18n_parity.py` — ключи RU/EN должны совпадать.

## Mnemonics

Qt mnemonics (`&Файл`) автоматически убираются для non-menu контекста функцией `_strip_mnemonics`.
