# ZapretDesktop (fork-zd)

Кроссплатформенный GUI для управления **zapret** / **winws** (Windows) и **nfqws** (Linux).

**Версия:** 1.6.6 — см. `src/entities/config/config_manager.py`

---

## Скачать

| Платформа | Release | Документация |
|-----------|---------|--------------|
| **Windows** | [`*-windows-x64.zip`](https://github.com/pqwc/fork-zd/releases) | [docs/WINDOWS_INSTALL.md](docs/WINDOWS_INSTALL.md) |
| **Linux** | `.deb` или `*-linux-x86_64.tar.gz` | [docs/LINUX_INSTALL.md](docs/LINUX_INSTALL.md) |

### Windows — 3 шага

1. Распакуйте `ZapretDesktop-*-windows-x64.zip`.
2. Запустите `ZapretDesktop.exe` **от администратора** (UAC).
3. Настройте **winws** в мастере первого запуска.

### Linux — 3 шага

1. Установите [Linux-адаптер](https://github.com/Sergeydigl3/zapret-discord-youtube-linux) (`service.sh`, `nfqws`).
2. Установите `.deb` из Release или распакуйте portable tarball.
3. Укажите путь к адаптеру в мастере настройки.

---

## Возможности

- Запуск и остановка DPI-стратегий (`.bat` / `service.sh`)
- Редактор стратегий, списков, hosts
- Диагностика сети и runtime (фильтры по категориям)
- Обновление приложения и zapret-компонентов
- Autostart (Task Scheduler / XDG)
- RU / EN интерфейс

---

## Разработка

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m pytest tests/ -v
python ZapretDesktop.py
```

Подробнее: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)

---

## Сборка release

| OS | Команда |
|----|---------|
| Windows | `build.bat` |
| Linux | `./build.sh --target portable` |

Требуется лицензия **PyArmor** (trial не покрывает проект).  
Maintainers: [docs/RELEASE.md](docs/RELEASE.md)

---

## Документация

Полный индекс: [docs/README.md](docs/README.md)

| Документ | Описание |
|----------|----------|
| [ARCHITECTURE_FSD.md](docs/ARCHITECTURE_FSD.md) | Структура `src/` |
| [SMOKE_CHECKLIST.md](docs/SMOKE_CHECKLIST.md) | QA перед релизом |
| [packaging/README.md](packaging/README.md) | deb, AppImage, PyArmor |

---

## CI

- **Push / PR:** compile, pytest, ruff, pip-audit
- **Tag `v*`:** protected build → GitHub Release (zip, deb, tarball, SHA256SUMS)

Секрет CI: `PYARMOR_CI_REGFILE_B64`

---

## Лицензия

[LICENSE.txt](LICENSE.txt)
