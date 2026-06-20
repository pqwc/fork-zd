@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo   ZapretDesktop - Protected Build
echo   (PyArmor + PyInstaller)
echo ========================================
echo.

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

set "VENV_DIR=.venv-build"
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [1/6] Creating build venv: %VENV_DIR%
    python -m venv "%VENV_DIR%"
) else (
    echo [1/6] Using build venv: %VENV_DIR%
)

call "%VENV_DIR%\Scripts\activate.bat"

echo [2/6] Installing dependencies...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q
python -m pip install -r requirements-build.txt -q

if defined PYARMOR_REGFILE (
    echo [2b/6] Registering PyArmor license...
    python -m pyarmor.cli reg "%PYARMOR_REGFILE%"
)

echo.
echo [3/6] Extracting application icon...
python packaging\scripts\extract_icon.py -o packaging\assets\zapretdesktop.ico --format ICO
if errorlevel 1 (
    echo [ERROR] Icon extraction failed.
    pause
    exit /b 1
)

echo.
echo [4/6] Cleaning previous build artifacts...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if exist ".pyarmor" rmdir /s /q .pyarmor
for %%F in (*.patched.spec) do del /q "%%F" 2>nul

echo.
echo [5/6] Obfuscating and building (PyArmor + PyInstaller)...
python packaging\scripts\pyarmor_pack.py --spec ZapretDesktop-win.spec
if errorlevel 1 (
    echo.
    echo [ERROR] Protected build failed.
    echo Trial PyArmor cannot obfuscate this project — register a license:
    echo   set PYARMOR_REGFILE=path\to\pyarmor-regfile-xxxx.zip
    echo   build.bat
    pause
    exit /b 1
)

echo.
echo [6/6] Copying winws folder to dist...
if exist "winws" (
    xcopy /E /I /Y "winws" "dist\winws" >nul
    echo winws folder copied.
) else (
    echo winws folder not found - skipped.
)

echo.
echo ========================================
echo   Build completed successfully!
echo   Output: dist\ZapretDesktop.exe
echo   Sources are obfuscated; no plain .py in dist.
echo ========================================
echo.
pause
