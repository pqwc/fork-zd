"""
Класс для проверки и обновления самой программы ZapretDesktop.exe
"""
import os
import requests
import shutil
import sys
import subprocess
from pathlib import Path
from src.entities.config.config_manager import ConfigManager, DEFAULT_APP_GITHUB_REPO, VERSION
from src.shared.lib.path_utils import get_base_path
from src.shared.lib.version_utils import is_version_newer
from src.shared.lib.github_utils import resolve_github_repo
from src.shared.lib.app_logging import setup_logging

logger = setup_logging()


class AppUpdater:
    """Класс для проверки и обновления программы ZapretDesktop.exe"""
    
    GITHUB_REPO = DEFAULT_APP_GITHUB_REPO

    def __init__(self):
        self.config_manager = ConfigManager()
        repo_setting = ""
        try:
            repo_setting = (self.config_manager.get_setting("app_repo", "") or "").strip()
        except Exception:
            repo_setting = ""
        self.github_repo = resolve_github_repo(repo_setting, self.GITHUB_REPO)
        self.github_api_url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
        # Текущая версия всегда берётся из константы VERSION,
        # чтобы конфиг не мог «сломать» логику обновлений.
        self.current_version = self.get_current_version()
        self.base_path = get_base_path()
    
    def get_current_version(self):
        """Получает текущую установленную версию из константы VERSION."""
        return VERSION
  
    
    def check_for_updates(self):
        """Проверяет наличие обновлений на GitHub"""
        try:
            response = requests.get(self.github_api_url, timeout=10)
            response.raise_for_status()
            release_data = response.json()
            
            latest_version = release_data.get('tag_name', '').lstrip('v')
            download_url = None
            zip_url = None
            exe_url = None

            for asset in release_data.get('assets', []):
                asset_name = asset.get('name', '').lower()
                url = asset.get('browser_download_url')
                if not url:
                    continue
                if asset_name.endswith('.zip') and 'zapretdesktop' in asset_name and 'windows' in asset_name:
                    zip_url = url
                elif asset_name.endswith('.exe') and 'zapretdesktop' in asset_name:
                    exe_url = url

            if sys.platform == 'win32':
                download_url = exe_url or zip_url
            else:
                for asset in release_data.get('assets', []):
                    asset_name = asset.get('name', '').lower()
                    if asset_name.endswith(('.deb', '.appimage', '.tar.gz')):
                        download_url = asset.get('browser_download_url')
                        break

            if not download_url and exe_url:
                download_url = exe_url
            if not download_url and zip_url:
                download_url = zip_url

            if not download_url:
                for asset in release_data.get('assets', []):
                    if asset.get('name', '').endswith('.exe'):
                        download_url = asset.get('browser_download_url')
                        break
            
            return {
                'has_update': is_version_newer(latest_version, self.current_version),
                'latest_version': latest_version,
                'current_version': self.current_version,
                'download_url': download_url,
                'release_url': release_data.get('html_url', ''),
                'release_notes': release_data.get('body', '')
            }
        except requests.RequestException as e:
            return {
                'has_update': False,
                'error': f'Ошибка при проверке обновлений: {str(e)}'
            }
        except Exception as e:
            return {
                'has_update': False,
                'error': f'Неожиданная ошибка: {str(e)}'
            }
    
    def _compare_versions(self, version1, version2):
        """Сравнивает две версии. Возвращает True если version1 > version2."""
        return is_version_newer(version1, version2)
    
    def download_update(self, download_url, progress_callback=None):
        """Скачивает обновление"""
        try:
            from urllib.parse import urlparse

            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()

            temp_dir = os.path.join(self.base_path, 'temp_update')
            os.makedirs(temp_dir, exist_ok=True)

            asset_name = os.path.basename(urlparse(download_url).path) or 'ZapretDesktop_new.exe'
            dest_path = os.path.join(temp_dir, asset_name)
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            progress_callback(progress)

            return dest_path
        except Exception as e:
            raise Exception(f'Ошибка при скачивании: {str(e)}')

    def install_update(self, exe_path, version):
        """Устанавливает обновление (Windows: замена exe через update.bat).

        Обновляет только ZapretDesktop.exe; папка winws и настройки в %%APPDATA%% не затрагиваются.
        При ошибке copy/restart смотрите %%TEMP%%\\zapretdesktop_update.err (если создан).
        """
        if sys.platform != 'win32':
            raise Exception('Automatic install is supported on Windows only')
        if not exe_path or not os.path.isfile(exe_path):
            raise Exception(f'Файл обновления не найден: {exe_path}')
        try:
            current_exe = sys.executable

            if not current_exe.lower().endswith('.exe'):
                current_exe = os.path.join(self.base_path, 'ZapretDesktop.exe')

            if not os.path.isfile(current_exe):
                raise Exception(f'Не найден текущий exe для замены: {current_exe}')

            exe_name = os.path.basename(current_exe)
            update_dir = os.path.join(self.base_path, 'temp_update')
            update_script = os.path.join(update_dir, 'update.bat')
            error_log = os.path.join(os.environ.get('TEMP', update_dir), 'zapretdesktop_update.err')
            os.makedirs(update_dir, exist_ok=True)

            with open(update_script, 'w', encoding='utf-8') as f:
                f.write('@echo off\n')
                f.write('setlocal EnableDelayedExpansion\n')
                f.write(f'del /F /Q "{error_log}" >nul 2>&1\n')
                f.write('timeout /t 2 /nobreak >nul\n')
                f.write(f'taskkill /F /IM "{exe_name}" >nul 2>&1\n')
                f.write('timeout /t 1 /nobreak >nul\n')
                f.write(f'copy /Y "{exe_path}" "{current_exe}" >nul\n')
                f.write('if errorlevel 1 (\n')
                f.write(f'    echo copy failed: "{exe_path}" -^> "{current_exe}" > "{error_log}"\n')
                f.write('    exit /b 1\n')
                f.write(')\n')
                f.write(f'if not exist "{current_exe}" (\n')
                f.write(f'    echo target missing after copy: "{current_exe}" > "{error_log}"\n')
                f.write('    exit /b 1\n')
                f.write(')\n')
                f.write(f'start "" "{current_exe}"\n')
                f.write(f'rmdir /S /Q "{update_dir}" >nul 2>&1\n')

            subprocess.Popen(
                ['cmd.exe', '/c', update_script],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            logger.info("Запущен скрипт self-update для версии %s → %s", self.current_version, version)
            return True
        except OSError as e:
            logger.exception("Ошибка при установке обновления")
            raise Exception(f'Ошибка при установке (файловая система): {e}') from e
        except Exception as e:
            logger.exception("Ошибка при установке обновления")
            raise Exception(f'Ошибка при установке: {e}') from e
