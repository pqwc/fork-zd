# Packaging (Windows + Linux)

Скрипты сборки release-артефактов.

## Быстрый старт

### Windows

```bat
set PYARMOR_REGFILE=C:\path\to\pyarmor-regfile-xxxx.zip
build.bat
REM → dist\ZapretDesktop.exe
```

### Linux

```bash
chmod +x build.sh packaging/scripts/*.sh
export PYARMOR_REGFILE=/path/to/pyarmor-regfile-xxxx.zip
./build.sh --target all
```

## Структура

| Путь | Назначение |
|------|------------|
| `build.bat` | Windows: venv, PyArmor, PyInstaller onefile |
| `build.sh` | Linux: venv, PyArmor, onedir, tarball, deb, appimage |
| `ZapretDesktop-win.spec` | PyInstaller onefile (Windows) |
| `ZapretDesktop-linux.spec` | PyInstaller onedir (Linux) |
| `packaging/scripts/pyarmor_pack.py` | obfuscate + pack + verify (no plain `.py` in dist) |
| `requirements-build.txt` | PyInstaller + PyArmor |
| `requirements-dev.txt` | pytest, ruff, pip-audit |
| `packaging/linux-runtime/` | README-заглушка (копируется в dist) |
| `packaging/debian/` | `.desktop`, metainfo, postinst |
| `packaging/scripts/make-deb.sh` | `dpkg-deb` |
| `packaging/scripts/make-appimage.sh` | AppDir + appimagetool |
| `packaging/scripts/extract_icon.py` | ICO/PNG из embedded icon |
| `packaging/assets/RELEASE_README_WINDOWS.txt` | readme в Windows zip |

## Цели Linux (`build.sh`)

```bash
./build.sh --target portable   # dist/ZapretDesktop + .tar.gz
./build.sh --target deb        # dist/zapretdesktop_*.deb
./build.sh --target appimage   # dist/*.AppImage (нужен appimagetool)
./build.sh --target all
```

## `.deb`

PyInstaller-сборка в `/opt/zapretdesktop`.  
Runtime-зависимости: `nftables`, `curl`, `iproute2`, `iputils-ping`, `sudo`, `bash`.  
`nfqws` — через отдельный [Linux-адаптер](https://github.com/Sergeydigl3/zapret-discord-youtube-linux).

## AppImage

[appimagetool](https://github.com/AppImage/AppImageKit/releases) в `packaging/tools/` или PATH.

## PyArmor

Trial **не покрывает** полный проект.

```bash
# Локально
export PYARMOR_REGFILE=/path/to/pyarmor-regfile-xxxx.zip   # Linux
set PYARMOR_REGFILE=C:\path\to\pyarmor-regfile-xxxx.zip    # Windows

# CI: base64 regfile → secret PYARMOR_CI_REGFILE_B64
```

См. [docs/RELEASE.md](../docs/RELEASE.md), [docs/WINDOWS_INSTALL.md](../docs/WINDOWS_INSTALL.md) §8, [docs/LINUX_INSTALL.md](../docs/LINUX_INSTALL.md) §8.

## GitHub Release

Workflow `release.yml` публикует: Windows zip, Linux tarball, `.deb`, `SHA256SUMS.txt`.
