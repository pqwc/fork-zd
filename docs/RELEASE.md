# Release ZapretDesktop

Руководство для maintainers: сборка, CI, публикация тега.

**Версия** задаётся в `src/entities/config/config_manager.py` (`VERSION`).

---

## Артефакты GitHub Release

| Файл | Платформа |
|------|-----------|
| `ZapretDesktop-*-windows-x64.zip` | Windows (exe + readme) |
| `ZapretDesktop.exe` | Windows (отдельно) |
| `ZapretDesktop-*-linux-x86_64.tar.gz` | Linux portable |
| `zapretdesktop_*_amd64.deb` | Debian/Ubuntu |
| `SHA256SUMS.txt` | Контрольные суммы всех файлов |

**Не входит в Release:** winws/nfqws (настраивается отдельно), AppImage (сборка локально).

---

## CI / workflows

| Workflow | Триггер | Назначение |
|----------|---------|------------|
| `ci.yml` | push, PR | pytest, ruff (F821), pip-audit, packaging validate |
| `release.yml` | tag `v*` | validate → build → publish Release |

Protected build (PyArmor) в CI — только при секрете **`PYARMOR_CI_REGFILE_B64`** на `main`.

### Настройка PyArmor для CI

```bash
pyarmor reg -C pyarmor-regfile-xxxx.zip
# → pyarmor-ci-xxxx.zip
base64 -w0 pyarmor-ci-xxxx.zip   # Linux
# Windows: [Convert]::ToBase64String([IO.File]::ReadAllBytes("pyarmor-ci-xxxx.zip"))
```

Добавить результат в GitHub → Settings → Secrets → `PYARMOR_CI_REGFILE_B64`.

---

## Локальная сборка перед тегом

### Windows

```bat
set PYARMOR_REGFILE=C:\path\to\pyarmor-regfile-xxxx.zip
build.bat
dir dist
```

### Linux

```bash
export PYARMOR_REGFILE=/path/to/pyarmor-regfile-xxxx.zip
chmod +x build.sh packaging/scripts/*.sh
./build.sh --target deb    # portable + .deb
ls -la dist/
```

---

## Публикация релиза

1. Обновить `VERSION` в `config_manager.py`.
2. `python -m pytest tests/ -v` — зелёный.
3. Пройти [SMOKE_CHECKLIST.md](SMOKE_CHECKLIST.md) на VM (Windows + Linux).
4. Commit + tag:

```bash
git tag v1.6.6
git push origin v1.6.6
```

5. Workflow `Release` создаст GitHub Release автоматически.

---

## Release notes (шаблон)

```markdown
## Windows
- Скачайте `ZapretDesktop-*-windows-x64.zip`
- Запуск от администратора; winws настраивается при первом запуске
- См. docs/WINDOWS_INSTALL.md

## Linux
- Рекомендуется `zapretdesktop_*_amd64.deb` или portable tarball
- Требуется [Linux-адаптер](https://github.com/Sergeydigl3/zapret-discord-youtube-linux)
- См. docs/LINUX_INSTALL.md

## Проверка целостности
sha256sum -c SHA256SUMS.txt
```

---

## Known limitations (для release notes)

- winws / nfqws не bundled
- `stop_all()` affects all winws/nfqws processes system-wide
- Linux app self-update — manual `.deb` install
- AppImage / Flatpak — local build only
- amd64 only on Linux
