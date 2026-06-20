# Установка ZapretDesktop на Windows

Руководство для **Windows 10/11** (x64).

ZapretDesktop — GUI на PyQt6. Сетевой обход DPI выполняет **winws** (WinDivert + `winws.exe` и `.bat`-стратегии). Папка `winws` **не входит** в репозиторий и обычно **не входит** в GitHub Release (см. ниже).

---

## 1. Требования

| Компонент | Назначение |
|-----------|------------|
| Windows 10/11 x64 | ОС |
| Права администратора | WinDivert, winws, BFE, firewall |
| Интернет | Загрузка winws и обновлений |

---

## 2. Установка winws (обязательно)

### Вариант A — мастер первого запуска (рекомендуется)

1. Запустите `ZapretDesktop.exe` **от имени администратора** (или подтвердите UAC при первом запуске).
2. Если winws не настроен, откроется мастер настройки.
3. Следуйте шагам: загрузка архива с GitHub или указание существующей папки.

### Вариант B — вручную

Рядом с `ZapretDesktop.exe` создайте структуру:

```
winws\
  bin\winws.exe
  *.bat          ← файлы стратегий
  service.bat    ← опционально
```

Путь можно изменить в **Настройки → Путь к winws**.

> **Важно:** пустая папка `winws` не считается установкой — мастер настройки появится снова.

---

## 3. Способы получения приложения

### 3.1 GitHub Release (рекомендуется)

Скачайте архив `ZapretDesktop-*-windows-x64.zip` из [Releases](https://github.com/pqwc/fork-zd/releases).

Содержимое:

- `ZapretDesktop.exe` — защищённая сборка (PyArmor + PyInstaller)
- `RELEASE_README_WINDOWS.txt` — краткая инструкция

После распаковки выполните шаг **§2** (winws).

### 3.2 Сборка из исходников

```bat
git clone https://github.com/pqwc/fork-zd.git
cd fork-zd
python -m venv .venv-build
.venv-build\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-build.txt
build.bat
```

**PyArmor:** trial-лицензия не покрывает весь проект. Для release-сборки нужна лицензия:

```bat
set PYARMOR_REGFILE=C:\path\to\pyarmor-regfile-xxxx.zip
build.bat
```

Результат: `dist\ZapretDesktop.exe` (+ `dist\winws\`, если папка была в корне проекта при сборке).

### 3.3 Запуск из исходников (разработка)

```bat
pip install -r requirements.txt
pip install -r requirements-dev.txt
python ZapretDesktop.py
```

---

## 4. Первый запуск

1. Подтвердите запрос **прав администратора** (UAC).
2. Пройдите мастер winws, если требуется.
3. Выберите стратегию на главной странице и нажмите **Запуск**.

Флаги командной строки:

| Флаг | Описание |
|------|----------|
| `--skip-winws-setup` | Пропустить мастер winws |
| `--reset-single-instance` | Сброс блокировки второго экземпляра |
| `--help` | Справка |

---

## 5. Автозапуск

**Настройки → Автозапуск Windows** — создаёт задачу Task Scheduler с правами администратора (`ONLOGON`, `HIGHEST`).

Для включения автозапуска приложение должно быть запущено **от администратора**.

---

## 6. Обновления

| Компонент | Как обновляется |
|-----------|-----------------|
| ZapretDesktop (exe) | Меню **Обновления** → проверка GitHub Release |
| winws / zapret | Меню **Обновления** → обновление компонентов |

Self-update заменяет только `ZapretDesktop.exe`. Папка `winws` не затрагивается. При ошибке автообновления скачайте новый zip из Releases вручную.

> **Остановка winws:** команда «Стоп» / смена стратегии вызывает `stop_all()` — завершает **все** процессы `winws.exe` в системе, не только запущенные из ZapretDesktop.

---

## 7. Диагностика

**Меню → Диагностика** — проверки BFE, firewall, WinDivert, winws, proxy и др.

На вкладке **Результаты**:

- верхняя панель — полный лог;
- нижняя — фильтр по категориям (по умолчанию: ошибки, критические, предупреждения).

**Пользовательские команды** (JSON `custom_commands` в конфиге диагностики) выполняются от имени пользователя с правами приложения (часто admin). Добавляйте только доверенные команды; по умолчанию встроенные проверки не требуют правки конфига.

---

## 8. Сборка release (maintainers)

| Файл | Назначение |
|------|------------|
| `build.bat` | venv, PyArmor, PyInstaller, копирование winws |
| `ZapretDesktop-win.spec` | spec PyInstaller (onefile) |
| `packaging/scripts/pyarmor_pack.py` | obfuscate + pack + verify |
| `requirements-build.txt` | PyInstaller + PyArmor |

Секрет CI для GitHub Actions:

1. Локально: `pyarmor reg -C pyarmor-regfile-xxxx.zip` → `pyarmor-ci-xxxx.zip`
2. Base64 → секрет репозитория **`PYARMOR_CI_REGFILE_B64`**

Подробнее: `packaging/README.md`, `docs/RELEASE.md`.

---

## 9. Устранение неполадок

| Симптом | Решение |
|---------|---------|
| «Не удалось запросить права администратора» | Запустите exe **ПКМ → Запуск от имени администратора**; проверьте UAC |
| Стратегии не запускаются | Проверьте `winws\bin\winws.exe` и `.bat`; запустите диагностику |
| Пустая папка winws | Удалите или заполните; должен сработать мастер setup |
| Второй экземпляр не открывается | `ZapretDesktop.exe --reset-single-instance` |
| Self-update не сработал | Скачайте zip из Releases вручную |

---

## 10. См. также

- [LINUX_INSTALL.md](LINUX_INSTALL.md) — Linux
- [DEVELOPMENT.md](DEVELOPMENT.md) — разработка
- [RELEASE.md](RELEASE.md) — сборка и публикация релиза
- [SMOKE_CHECKLIST.md](SMOKE_CHECKLIST.md) — QA перед stable
