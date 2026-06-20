# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Windows (onefile). Invoked via pyarmor gen --pack.

import os

block_cipher = None
project_root = os.path.abspath(SPECPATH)
icon_path = os.path.join(project_root, "packaging", "assets", "zapretdesktop.ico")

a = Analysis(
    [os.path.join(project_root, "ZapretDesktop.py")],
    pathex=[project_root],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PyQt6.QtSvg",
        "PyQt6.QtNetwork",
        "psutil",
        "src.platform.windows.paths_win",
        "src.platform.windows.privilege_win",
        "src.platform.windows.runtime_winws",
        "src.platform.linux.paths_xdg",
        "src.platform.linux.privilege_linux",
        "src.platform.linux.runtime_service_sh",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tests",
        "scripts",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ZapretDesktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path if os.path.isfile(icon_path) else None,
)
