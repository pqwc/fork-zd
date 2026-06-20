# Установка ZapretDesktop на Linux

Руководство для **Debian 12**, **Ubuntu 24.04 LTS** и родственных дистрибутивов.

ZapretDesktop — GUI на PyQt6. Сетевой обход DPI выполняет **Linux-адаптер**
[zapret-discord-youtube-linux](https://github.com/Sergeydigl3/zapret-discord-youtube-linux)
(`service.sh`, `nfqws`, `nftables`). Бинарник `nfqws` **не входит** в пакет GUI.

---

## 1. Требования

| Компонент | Назначение |
|-----------|------------|
| **amd64** (x86_64) | Сборки `.deb`, tarball и AppImage — только amd64 |
| Python 3.10+ | только при запуске из исходников |
| nftables | firewall backend адаптера |
| curl | обновления и тесты HTTP |
| iproute2 | `ip link`, маршруты |
| iputils-ping | диагностика |
| sudo или polkit | запуск nfqws от root |
| bash | `service.sh` |

Минимальная установка зависимостей (Debian/Ubuntu):

```bash
sudo apt update
sudo apt install -y nftables curl iproute2 iputils-ping sudo bash git
sudo systemctl enable --now nftables 2>/dev/null || true
```

Для запуска **из исходников** дополнительно:

```bash
sudo apt install -y python3 python3-venv python3-pip python3-pyqt6 python3-pyqt6.qtsvg
```

---

## 2. Установка Linux-адаптера (обязательно)

```bash
git clone https://github.com/Sergeydigl3/zapret-discord-youtube-linux.git ~/zapret-linux
cd ~/zapret-linux
```

Следуйте README адаптера. Минимальный порядок:

```bash
# Права для nfqws (sudo без пароля или polkit — см. адаптер)
./service.sh setup-permissions

# Стратегии и бинарник nfqws
./service.sh download-deps --default

# Проверка
./service.sh strategy list
```

Запомните путь к каталогу с `service.sh` (например `~/zapret-linux`).

---

## 3. Способы установки GUI

### 3.1 Готовый .deb (рекомендуется для Debian/Ubuntu)

**GitHub Release** публикует `zapretdesktop_*_amd64.deb` вместе с portable tarball.

```bash
# Скачайте .deb из релиза или соберите локально:
chmod +x build.sh
./build.sh --target deb
sudo apt install ./dist/zapretdesktop_*_amd64.deb
```

Запуск: меню приложений **ZapretDesktop** или `zapretdesktop`.

> **AppImage** в релиз не входит — соберите `./build.sh --target appimage` при наличии `appimagetool`.

### 3.2 Portable tarball (PyInstaller onedir)

```bash
./build.sh --target portable
tar -xzf dist/ZapretDesktop-*-linux-x86_64.tar.gz -C ~/apps
~/apps/ZapretDesktop/ZapretDesktop
```

Рядом с архивом лежит заглушка `linux-runtime/` с напоминанием про адаптер.

### 3.3 AppImage

```bash
# Нужен appimagetool: https://github.com/AppImage/AppImageKit/releases
./build.sh --target appimage
chmod +x dist/ZapretDesktop-*-x86_64.AppImage
./dist/ZapretDesktop-*-x86_64.AppImage
```

### 3.4 Из исходников (разработка)

```bash
git clone <repo-url> ZapretDesktop
cd ZapretDesktop
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python ZapretDesktop.py
```

На Linux **права root для GUI не требуются** — повышение прав нужно только адаптеру при старте nfqws.

---

## 4. Первый запуск GUI

1. Запустите ZapretDesktop.
2. Если адаптер не найден, откроется диалог **Настройка Linux runtime** — укажите каталог с `service.sh`.
3. В **Настройки** задайте сетевой интерфейс (`linux_interface`, например `enp0s3` или `any`).
4. Выберите стратегию и нажмите **Запуск**.

Путь к runtime хранится в `~/.config/ZapretDesktop/config.json` (`runtime_path`, `runtime_type`).

---

## 5. Обновления

| Что | Как |
|-----|-----|
| Стратегии / nfqws | Меню обновлений → **Zapret update** (`service.sh download-deps`) |
| GUI (.deb) | Новый .deb из релиза или `sudo apt install ./zapretdesktop_*.deb` |
| GUI (AppImage) | Скачать новый AppImage |
| GUI (исходники) | `git pull` + `pip install -r requirements.txt` |

GitHub Release включает `SHA256SUMS.txt` — проверка: `sha256sum -c SHA256SUMS.txt`.

> **Остановка nfqws:** «Стоп» в GUI может завершить все процессы `nfqws`, связанные с адаптером, не только запущенные из ZapretDesktop.

---

## 6. Автозапуск

В настройках ZapretDesktop включите автозапуск — создаётся XDG entry
`~/.config/autostart/ZapretDesktop.desktop` с флагами `--autostart --recover` и полем `Icon=`.

Для автозапуска **самого nfqws** используйте systemd unit адаптера:

```bash
cd ~/zapret-linux
./service.sh service install
./service.sh service start
```

---

## 7. Диагностика

**Инструменты → Диагностика** (Ctrl+Shift+D) на Linux проверяет:

- наличие `service.sh` и `conf.env`
- процесс `nfqws`, nftables, DNS, маршруты
- sudo, systemd unit адаптера, `/etc/hosts`

Пользовательские команды в JSON (`custom_commands`) выполняются от вашего пользователя (часто через `sudo` внутри проверок). Редактируйте конфиг только если понимаете последствия.

---

## 8. Сборка всех артефактов

```bash
chmod +x build.sh packaging/scripts/*.sh
./build.sh --target all
```

Результаты в `dist/`:

| Файл | Описание |
|------|----------|
| `ZapretDesktop/` | PyInstaller onedir |
| `ZapretDesktop-*-linux-x86_64.tar.gz` | portable |
| `zapretdesktop_*_amd64.deb` | пакет Debian |
| `ZapretDesktop-*-x86_64.AppImage` | portable AppImage |

**Flatpak:** черновик в `packaging/flatpak/` — не публикуется в Release; используйте `.deb` или tarball.

Зависимости сборки: `requirements.txt`, `requirements-build.txt` (PyInstaller + **PyArmor**), `requirements-dev.txt` (pytest).

Release-сборка (`./build.sh`) требует лицензию PyArmor (trial не покрывает проект):

```bash
export PYARMOR_REGFILE=/path/to/pyarmor-regfile-xxxx.zip
./build.sh --target portable
```

CI: секрет GitHub `PYARMOR_CI_REGFILE_B64` (base64 от `pyarmor reg -C pyarmor-regfile-xxxx.zip`).

---

## 9. Частые проблемы

### «No module named PyQt6.QtSvg»

Модуль SVG не входит в базовый пакет `python3-pyqt6` в Debian/Ubuntu:

```bash
sudo apt install python3-pyqt6.qtsvg
```

При установке через venv (`pip install -r requirements.txt`) QtSvg уже включён в wheel PyQt6.

### «QMessageBox has no attribute StandardButtons»

Исправлено в коде: в PyQt6 используется `QMessageBox.StandardButton`, а не `StandardButtons`. Обновите исходники (`git pull`).

### «Не найден service.sh»

Укажите правильный каталог адаптера в настройках. В каталоге должен быть исполняемый `service.sh`.

### Стратегии не запускаются

```bash
cd ~/zapret-linux
./service.sh download-deps --default
./service.sh setup-permissions
sudo ./service.sh run --config conf.env   # проверка вручную
```

### sudo запрашивает пароль при каждом старте

Выполните `setup-permissions` в адаптере или настройте polkit.

### nftables не активен

```bash
sudo systemctl enable --now nftables
sudo nft list ruleset
```

---

## 10. См. также

- [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md) — Windows
- [DEVELOPMENT.md](DEVELOPMENT.md) — разработка
- [RELEASE.md](RELEASE.md) — релиз и CI
- [src/platform/README.md](../src/platform/README.md) — platform layer
- [packaging/flatpak/](../packaging/flatpak/) — черновик Flatpak (не в Release)
- [zapret-discord-youtube-linux](https://github.com/Sergeydigl3/zapret-discord-youtube-linux) — CLI-адаптер

### Расширенные настройки (фаза 5)

В **Настройки → Путь к runtime** (Linux):

- **Init mode** — `auto` / `systemd` / `run` (как запускается nfqws). OpenRC/runit не поддерживаются.
- **Firewall backend** — `auto` / `nftables` / `iptables` → `conf.env`

**Инструменты → Создание стратегии** сохраняет `.bat` в `custom-strategies/`.

---
