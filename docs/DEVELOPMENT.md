# Разработка ZapretDesktop

## Требования

| Компонент | Windows | Linux |
|-----------|---------|-------|
| Python | 3.10+ (3.11 в CI) | 3.10+ |
| GUI | PyQt6 (`pip`) | `python3-pyqt6` (системный или pip) |
| Тесты | `requirements-dev.txt` | то же |

## Быстрый старт

```bash
git clone https://github.com/pqwc/fork-zd.git
cd fork-zd

python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux:   source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt

python ZapretDesktop.py
```

### Linux: системные пакеты

```bash
sudo apt install python3-pyqt6 python3-pyqt6.qtsvg
```

## Тесты

```bash
python -m pytest tests/ -v
python -m compileall -q ZapretDesktop.py src tests
```

Покрытие включает: platform backends, packaging, config, zapret merge, i18n parity, lifecycle contracts.

## Lint и аудит зависимостей

Конфигурация: `pyproject.toml`.

```bash
pip install -r requirements-dev.txt

# Неопределённые имена (F821) — в CI обязательно
python -m ruff check ZapretDesktop.py src tests

# Расширенная проверка локально (опционально)
python -m ruff check ZapretDesktop.py src tests --select E,F,W,I --ignore E501,F403,F405,I001

# Уязвимости в runtime-зависимостях — в CI
pip-audit -r requirements.txt

# Типы (опционально, PyQt без stubs)
python -m mypy src --config-file pyproject.toml
```

CI (`.github/workflows/ci.yml`): `test-windows`, `test-linux`, `lint`, `packaging-linux`.  
Dependabot: `.github/dependabot.yml` (pip + GitHub Actions, еженедельно).

## Структура проекта

```
ZapretDesktop.py       # Точка входа
src/
  app/                 # bootstrap, launch options, crash dialog
  pages/               # MainWindow, TestWindow
  features/            # settings, diagnostics, updates, editor, …
  entities/            # config, winws, zapret, network, diagnostics
  platform/            # Windows / Linux backends
  shared/              # i18n, UI, lib
  widgets/             # переиспользуемые Qt-виджеты
tests/                 # pytest + unittest
packaging/             # deb, AppImage, скрипты сборки
build.bat / build.sh   # release-сборка
```

Подробнее: [ARCHITECTURE_FSD.md](ARCHITECTURE_FSD.md).

## Platform layer

Код UI не импортирует OS-specific API напрямую — только `src.platform`:

```python
from src.platform import is_linux, get_runtime_backend, get_privilege_backend
```

Override для тестов:

```bash
export ZAPRETDESKTOP_PLATFORM=linux
export ZAPRETDESKTOP_RUNTIME_PATH=/path/to/zapret-linux
```

См. [src/platform/README.md](../src/platform/README.md).

## Release-сборка (локально)

| OS | Команда | Результат |
|----|---------|-----------|
| Windows | `build.bat` | `dist/ZapretDesktop.exe` |
| Linux portable | `./build.sh --target portable` | `dist/ZapretDesktop/` + tarball |
| Linux .deb | `./build.sh --target deb` | `dist/zapretdesktop_*_amd64.deb` |

**PyArmor:** trial не покрывает проект. Нужна лицензия:

```bash
# Windows
set PYARMOR_REGFILE=C:\path\to\pyarmor-regfile-xxxx.zip

# Linux
export PYARMOR_REGFILE=/path/to/pyarmor-regfile-xxxx.zip
```

Подробнее: [RELEASE.md](RELEASE.md), [packaging/README.md](../packaging/README.md).

## Архивные скрипты

| Файл | Статус |
|------|--------|
| `scripts/main_window_source.py` | **ARCHIVED** — монолит до FSD; запуск запрещён |
| `scripts/migrate_fsd.py` | Исторический, не для runtime |
| `scripts/split_main_window.py` | Утилита извлечения mixins |

## i18n

Строки в `src/shared/i18n/translator.py`. Ключи RU и EN должны совпадать (тест `tests/test_i18n_parity.py`).

```python
from src.shared.i18n.translator import tr, tr_platform

label.setText(tr("home_start_button", self.language))
title.setText(tr_platform("menu_open_winws_folder", self.language))
message = tr("bin_creator_success", lang).format(path)
```

См. [src/shared/i18n/README.md](../src/shared/i18n/README.md).

## Известные ограничения

- `stop_all()` завершает **все** процессы winws/nfqws в системе (by design).
- Linux: OpenRC/runit не поддерживаются — только systemd или ручной `service.sh`.
- Self-update на Linux — ручная установка `.deb`/AppImage из Releases.
- Flatpak — черновик в `packaging/flatpak/`, не в Release.
- Артефакты `.pyarmor/` и `pyarmor.bug.log` — локальные, в `.gitignore`.
