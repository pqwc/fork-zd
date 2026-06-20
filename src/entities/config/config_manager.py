import json
import os
from pathlib import Path
from src.shared.lib.path_utils import get_base_path, get_config_path as _get_config_path
from src.shared.lib.app_logging import setup_logging

logger = setup_logging()


VERSION = "1.6.6"
ZAPRET = "1.9.7b"
DEFAULT_APP_GITHUB_REPO = "pqwc/fork-zd"

class ConfigManager:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = _get_config_path()  # AppData/ZapretDesktop/config.json
        # Если путь относительный, делаем его абсолютным относительно папки настроек (AppData)
        if not os.path.isabs(config_path):
            config_dir = os.path.dirname(_get_config_path())
            self.config_path = os.path.join(config_dir, config_path)
        else:
            self.config_path = config_path
        # Не создаём папку json в каталоге программы — конфиг только в AppData
        base_path = get_base_path()
        try:
            base_norm = os.path.normpath(base_path) + os.sep
            path_norm = os.path.normpath(self.config_path)
            if path_norm.startswith(base_norm) and (os.sep + "json" + os.sep in path_norm or path_norm.endswith(os.sep + "json")):
                self.config_path = _get_config_path()
        except Exception as exc:
            logger.warning("Перенаправление config_path из каталога программы: %s", exc)
        self.default_settings = {
            'language': 'ru',
            'color_theme': 'dark',  # 'dark' | 'light'
            'show_in_tray': True,
            'close_winws_on_exit': True,
            'start_minimized': False,
            'auto_start_last_strategy': False,
            'add_b_flag_on_update': True,
            'last_strategy': '',
            'running_winws_pid': 0,  # PID winws, запущенного из программы (для распознавания после перезапуска)
            'favorite_strategies': [],  # Имена .bat стратегий в избранном
            'auto_restart_strategy': False,
            'winws_start_timeout_sec': 15,
            'auto_restart_apps_enabled': False,
            'game_filter_enabled': False,
            'ipset_filter_mode': 'loaded',  # 'loaded', 'none', 'any'
            'first_run_done': False,
            'autostart_enabled': False,
            'winws_path': '',  # Путь к папке winws; пусто = рядом с программой
            'runtime_path': '',  # Linux: каталог service.sh; Windows: alias winws_path
            'runtime_type': 'auto',  # auto | winws | zapret-linux
            'linux_interface': '',
            'linux_init_mode': 'auto',
            'linux_firewall_backend': 'auto',
            'linux_gamefilter_tcp': True,
            'linux_gamefilter_udp': True,
            'auto_restart_apps': [],  # Список имён процессов для автоперезапуска (discord.exe и т.п.)
            'zapret_repo': 'Flowseal/zapret-discord-youtube',  # Репозиторий zapret по умолчанию
            'app_repo': DEFAULT_APP_GITHUB_REPO,  # Репозиторий программы (для форков)
            'auto_update_mode': 'none',  # none | app | strategies | all
            'remove_check_updates': True,  # Удалять проверку обновлений zapret из стратегий
            'update_ignore_folders': ['lists'],  # Подпапки winws, не трогаемые при обновлении
            'diagnostics_auto_fix': True,  # Автоисправление при диагностике (TCP timestamps, WinDivert)
            'diagnostics_enabled_checks': {},  # Пусто = все проверки включены
        }
        self.default_config = {
            'app': self.default_settings.copy(),
            'zapret_version': {
                'version': ZAPRET
            }
        }
        self.ensure_config_file()
    
    def ensure_config_dir(self):
        """Создает папку конфигурации, если её нет"""
        config_dir = os.path.dirname(self.config_path)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
    
    def ensure_config_file(self):
        """Создает папку и файл конфигурации с настройками по умолчанию, если их нет"""
        self.ensure_config_dir()
        
        if not os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.default_config, f, indent=4, ensure_ascii=False)
            except IOError as e:
                logger.error("Ошибка при создании файла конфигурации: %s", e)
        else:
            # Миграция старого формата: пытаемся загрузить старые файлы и объединить в новый
            self._migrate_old_config()
    
    def _migrate_old_config(self):
        """Мигрирует старые конфигурационные файлы в новый формат"""
        try:
            # Загружаем текущий config.json
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Если это старый формат (плоский), мигрируем
            if 'app' not in config and any(key in config for key in self.default_settings.keys()):
                old_settings = config.copy()
                config = {
                    'app': {**self.default_settings, **old_settings},
                    'zapret_version': config.get('zapret_version', self.default_config['zapret_version'].copy())
                }
                # Сохраняем мигрированную конфигурацию
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
            
            # Пытаемся загрузить данные из старых файлов, если их еще нет
            base_path = get_base_path()
            old_app_json = os.path.join(base_path, "app/config/app.json")
            old_zapret_version_json = os.path.join(base_path, "app/config/zapret_version.json")
            
            updated = False
            
            # Мигрируем app.json
            if os.path.exists(old_app_json) and 'app' not in config:
                try:
                    with open(old_app_json, 'r', encoding='utf-8') as f:
                        old_app_config = json.load(f)
                        config['app'] = {**self.default_settings, **old_app_config}
                        updated = True
                except Exception as exc:
                    logger.warning("Не удалось мигрировать app.json: %s", exc)
            if os.path.exists(old_zapret_version_json) and 'zapret_version' not in config:
                try:
                    with open(old_zapret_version_json, 'r', encoding='utf-8') as f:
                        config['zapret_version'] = json.load(f)
                        updated = True
                except Exception as exc:
                    logger.warning("Не удалось мигрировать zapret_version.json: %s", exc)
            if 'app' not in config:
                config['app'] = self.default_settings.copy()
                updated = True
            if 'zapret_version' not in config:
                config['zapret_version'] = self.default_config['zapret_version'].copy()
                updated = True
            
            # Сохраняем обновленную конфигурацию
            if updated:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.exception("Ошибка при миграции конфигурации: %s", e)
    
    def load_all(self):
        """Загружает весь конфигурационный файл"""
        backup_path = self.config_path + '.bak'
        
        # Пробуем загрузить основной конфиг
        config = self._try_load_config(self.config_path)
        
        # Если не удалось, пробуем резервную копию
        if config is None and os.path.exists(backup_path):
            logger.warning("Восстановление конфигурации из резервной копии...")
            config = self._try_load_config(backup_path)
            if config is not None:
                try:
                    with open(self.config_path, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
                except Exception as exc:
                    logger.warning("Не удалось восстановить config из .bak: %s", exc)

        if config is None:
            return self.default_config.copy()
        
        # Убеждаемся, что все секции присутствуют
        merged_config = {
            'app': {**self.default_settings, **config.get('app', {})},
            'zapret_version': {**self.default_config['zapret_version'], **config.get('zapret_version', {})}
        }
        return merged_config
    
    def _try_load_config(self, path):
        """Пытается загрузить конфиг из указанного файла."""
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        return None
                    return json.loads(content)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Ошибка при загрузке %s: %s", path, e)
        return None
    
    def load_settings(self):
        """Загружает настройки приложения (секция app) из JSON файла"""
        try:
            config = self.load_all()
            return config.get('app', self.default_settings.copy())
        except Exception as e:
            logger.exception("Ошибка при загрузке настроек: %s", e)
            return self.default_settings.copy()
    
    def save_all(self, config):
        """Сохраняет весь конфигурационный файл"""
        try:
            # Убеждаемся, что папка существует
            self.ensure_config_dir()
            
            # Создаём резервную копию перед сохранением
            backup_path = self.config_path + '.bak'
            if os.path.exists(self.config_path):
                try:
                    import shutil
                    shutil.copy2(self.config_path, backup_path)
                except Exception as exc:
                    logger.warning("Не удалось создать резервную копию config: %s", exc)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return True
        except IOError as e:
            logger.error("Ошибка при сохранении конфигурации: %s", e)
            return False
    
    def save_settings(self, settings):
        """Сохраняет настройки приложения (секция app) в JSON файл"""
        try:
            config = self.load_all()
            config['app'] = settings
            return self.save_all(config)
        except Exception as e:
            logger.exception("Ошибка при сохранении настроек: %s", e)
            return False
    
    def get_setting(self, key, default=None):
        """Получает значение настройки"""
        settings = self.load_settings()
        return settings.get(key, default)
    
    def set_setting(self, key, value):
        """Устанавливает значение настройки и сохраняет. Возвращает True при успехе."""
        settings = self.load_settings()
        settings[key] = value
        return self.save_settings(settings)
    
    def update_settings(self, updates):
        """Обновляет несколько настроек одновременно. Возвращает True при успехе."""
        settings = self.load_settings()
        settings.update(updates)
        return self.save_settings(settings)
    
    def get_zapret_version(self):
        """Получает версию zapret"""
        config = self.load_all()
        return config.get('zapret_version', self.default_config['zapret_version'].copy())
    
    def set_zapret_version(self, version):
        """Устанавливает версию zapret. Возвращает True при успехе."""
        config = self.load_all()
        config['zapret_version'] = {'version': version}
        return self.save_all(config)

