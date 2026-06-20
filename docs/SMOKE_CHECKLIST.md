# Smoke checklist before stable tag

Run on clean VMs before pushing `v*`. Mark each item pass/fail and note build/commit.

**Build under test:** _______________  
**Tester / date:** _______________

---

## Windows (Windows 10/11 x64)

| # | Check | Pass |
|---|--------|------|
| 1 | Launch without admin → UAC prompt → elevated instance starts **without** false “elevation failed” | [ ] |
| 2 | First run with empty/missing `winws` → setup dialog appears | [ ] |
| 3 | Configure winws path or download → `bin/winws.exe` present | [ ] |
| 4 | Start a strategy → process runs; stop → process ends | [ ] |
| 5 | Autostart toggle → Task Scheduler entry created/removed | [ ] |
| 6 | Diagnostics → run checks; filtered panel shows categories | [ ] |
| 7 | Self-update check finds release (manual install OK) | [ ] |
| 8 | Protected build: `build.bat` → `dist/ZapretDesktop.exe` runs | [ ] |
| 9 | Release zip contains exe + `RELEASE_README_WINDOWS.txt` | [ ] |

---

## Linux (Ubuntu 24.04 + Debian 12)

| # | Check | Pass |
|---|--------|------|
| 1 | Install Linux adapter (`service.sh`, `nfqws`) per `docs/LINUX_INSTALL.md` | [ ] |
| 2 | Install `.deb` from release or `./build.sh --target deb` | [ ] |
| 3 | Launch from menu / `zapretdesktop` → main window opens | [ ] |
| 4 | Point runtime to adapter directory → strategies listed | [ ] |
| 5 | Start / stop strategy via GUI | [ ] |
| 6 | Portable tarball extracts and `./ZapretDesktop/ZapretDesktop` runs | [ ] |
| 7 | Diagnostics completes without crash | [ ] |
| 8 | App update opens GitHub releases (manual `.deb` install) | [ ] |

---

## CI / release pipeline

| # | Check | Pass |
|---|--------|------|
| 1 | `pytest tests/` green on Windows and Linux (CI) | [ ] |
| 2 | `PYARMOR_CI_REGFILE_B64` set → protected-build jobs pass on `main` | [ ] |
| 3 | Tag push → release `validate` job passes before build | [ ] |
| 4 | GitHub Release contains: Windows zip, Linux tarball, `.deb`, `SHA256SUMS.txt` | [ ] |

---

## Sign-off

- [ ] All critical items passed on **Windows**
- [ ] All critical items passed on **Linux**
- [ ] Ready to tag stable: _______________
