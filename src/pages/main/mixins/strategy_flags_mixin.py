"""strategy_flags_mixin methods for MainWindow."""
from PyQt6.QtWidgets import *
from src.shared.i18n.translator import tr
from src.shared.lib.path_utils import get_winws_path
from src.shared.ui.message_box_utils import configure_message_box
from src.platform import is_linux
import os


class StrategyFlagsMixin:
    def toggle_add_b_flag_on_update(self):
        """Переключает настройку добавления /B флага при обновлении"""
        value = self.add_b_flag_on_update_action.isChecked()
        if not self._persist_setting(
            'add_b_flag_on_update',
            value,
            revert_callback=lambda v: self.add_b_flag_on_update_action.setChecked(bool(v)),
        ):
            return

    def sync_linux_conf_env_from_settings(self, silent=False):
        """Синхронизирует conf.env с настройками GUI (Linux)."""
        if not is_linux():
            return
        lang = self.settings.get('language', 'ru')
        runtime_root = get_winws_path()
        if not os.path.isdir(runtime_root):
            if not silent:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_error', lang))
                msg.setText(tr('msg_winws_not_found', lang))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
            return
        try:
            from src.platform.linux.linux_runtime_options import sync_conf_env_from_settings

            sync_conf_env_from_settings(runtime_root, self.settings)
            if not silent:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_information', lang))
                msg.setText(tr('linux_conf_env_sync_ok', lang))
                msg.setIcon(QMessageBox.Icon.Information)
                msg.exec()
        except Exception as exc:
            if not silent:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_error', lang))
                msg.setText(tr('linux_conf_env_sync_failed', lang).format(exc))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()

    def add_b_flag_to_all_strategies(self, silent=False):
        """Добавляет /B флаг во все .bat файлы стратегий
        
        Args:
            silent: Если True, не показывает диалоги подтверждения и результатов
        """
        if is_linux():
            self.sync_linux_conf_env_from_settings(silent=silent)
            return
        lang = self.settings.get('language', 'ru')
        winws_folder = get_winws_path()
        
        if not os.path.exists(winws_folder):
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_winws_not_found', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        # Ищем все .bat файлы
        bat_files = []
        for filename in os.listdir(winws_folder):
            if filename.endswith('.bat') and os.path.isfile(os.path.join(winws_folder, filename)):
                bat_files.append(filename)
        
        if not bat_files:
            if not silent:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_information', lang))
                msg.setText(tr('msg_no_bat_to_process', lang))
                msg.setIcon(QMessageBox.Icon.Information)
                msg.exec()
            return
        
        # Подтверждение (только если не silent режим)
        if not silent:
            old_s = 'start "zapret: %~n0" /min'
            new_s = 'start "zapret: %~n0" /B /min'
            reply = QMessageBox.question(
                self,
                tr('msg_add_b_flag_title', lang),
                tr('msg_add_b_flag_text', lang).format(len(bat_files), old_s, new_s),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Обрабатываем файлы
        processed_count = 0
        modified_count = 0
        errors = []
        
        for filename in bat_files:
            file_path = os.path.join(winws_folder, filename)
            try:
                # Читаем файл
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Ищем и заменяем строку
                old_string = 'start "zapret: %~n0" /min'
                new_string = 'start "zapret: %~n0" /B /min'
                
                if old_string in content:
                    # Заменяем все вхождения
                    new_content = content.replace(old_string, new_string)
                    
                    # Сохраняем файл
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    modified_count += 1
                
                processed_count += 1
            except Exception as e:
                errors.append(f'{filename}: {str(e)}')
        
        # Показываем результат (только если не silent режим)
        if not silent:
            result_text = tr('msg_processed_count', lang).format(processed_count, modified_count)
            if errors:
                result_text += '\n\n' + tr('msg_errors_section', lang) + '\n'.join(errors)
            
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_result', lang))
            msg.setText(result_text)
            if errors:
                msg.setIcon(QMessageBox.Icon.Warning)
            else:
                msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()

    def remove_b_flag_from_all_strategies(self, silent=False):
        """Удаляет /B флаг из всех .bat файлов стратегий
        
        Args:
            silent: Если True, не показывает диалоги подтверждения и результатов
        """
        if is_linux():
            return
        lang = self.settings.get('language', 'ru')
        winws_folder = get_winws_path()
        
        if not os.path.exists(winws_folder):
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_winws_not_found', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        # Ищем все .bat файлы
        bat_files = []
        for filename in os.listdir(winws_folder):
            if filename.endswith('.bat') and os.path.isfile(os.path.join(winws_folder, filename)):
                bat_files.append(filename)
        
        if not bat_files:
            if not silent:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_information', lang))
                msg.setText(tr('msg_no_bat_to_process', lang))
                msg.setIcon(QMessageBox.Icon.Information)
                msg.exec()
            return
        
        # Подтверждение (только если не silent режим)
        if not silent:
            old_s = 'start "zapret: %~n0" /B /min'
            new_s = 'start "zapret: %~n0" /min'
            reply = QMessageBox.question(
                self,
                tr('msg_remove_b_flag_title', lang),
                tr('msg_remove_b_flag_text', lang).format(len(bat_files), old_s, new_s),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Обрабатываем файлы
        processed_count = 0
        modified_count = 0
        errors = []
        
        for filename in bat_files:
            file_path = os.path.join(winws_folder, filename)
            try:
                # Читаем файл
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Ищем и заменяем строку
                old_string = 'start "zapret: %~n0" /B /min'
                new_string = 'start "zapret: %~n0" /min'
                
                if old_string in content:
                    # Заменяем все вхождения
                    new_content = content.replace(old_string, new_string)
                    
                    # Сохраняем файл
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    modified_count += 1
                
                processed_count += 1
            except Exception as e:
                errors.append(f'{filename}: {str(e)}')
        
        # Показываем результат (только если не silent режим)
        if not silent:
            result_text = tr('msg_processed_count', lang).format(processed_count, modified_count)
            if errors:
                result_text += '\n\n' + tr('msg_errors_section', lang) + '\n'.join(errors)
            
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_result', lang))
            msg.setText(result_text)
            
            if errors:
                msg.setIcon(QMessageBox.Icon.Warning)
            else:
                msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()

    def remove_check_updates_from_all_strategies(self, silent=False):
        """Удаляет строку "call service.bat check_updates" из всех .bat файлов стратегий
        
        Args:
            silent: Если True, не показывает диалоги подтверждения и результатов
        """
        lang = self.settings.get('language', 'ru')
        winws_folder = get_winws_path()
        
        if not os.path.exists(winws_folder):
            if not silent:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_error', lang))
                msg.setText(tr('msg_winws_not_found', lang))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
            return
        
        bat_files: list[str] = []
        if is_linux():
            from src.platform.linux.linux_runtime_manager import LinuxRuntimeManager

            for name in LinuxRuntimeManager().list_strategy_files():
                bat_files.append(f"{name}.bat" if not name.endswith(".bat") else name)
        else:
            for filename in os.listdir(winws_folder):
                if filename.endswith('.bat') and os.path.isfile(os.path.join(winws_folder, filename)):
                    bat_files.append(filename)
        
        if not bat_files:
            return
        
        # Обрабатываем файлы
        processed_count = 0
        modified_count = 0
        errors = []
        
        for filename in bat_files:
            if is_linux():
                from src.features.editor.lib.editor_paths import resolve_strategy_bat_path

                stem = filename[:-4] if filename.endswith(".bat") else filename
                file_path = resolve_strategy_bat_path(winws_folder, stem)
                if not file_path:
                    continue
            else:
                file_path = os.path.join(winws_folder, filename)
            try:
                # Читаем файл
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                # Удаляем строки с "call service.bat check_updates"
                new_lines = []
                modified = False
                for line in lines:
                    # Проверяем, содержит ли строка "call service.bat check_updates"
                    # Учитываем возможные пробелы и регистр
                    stripped_line = line.strip()
                    # Проверяем точное совпадение или с возможными пробелами
                    if (stripped_line.lower() == 'call service.bat check_updates' or
                        'call service.bat check_updates' in stripped_line.lower()):
                        modified = True
                        continue  # Пропускаем эту строку
                    new_lines.append(line)
                
                if modified:
                    # Сохраняем файл
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
                    modified_count += 1
                
                processed_count += 1
            except Exception as e:
                errors.append(f'{filename}: {str(e)}')
        
        # Показываем результат (только если не silent режим)
        if not silent and (modified_count > 0 or errors):
            result_text = tr('msg_processed_count', lang).format(processed_count, modified_count)
            if errors:
                result_text += '\n\n' + tr('msg_errors_section', lang) + '\n'.join(errors)
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_result', lang))
            msg.setText(result_text)
            if errors:
                msg.setIcon(QMessageBox.Icon.Warning)
            else:
                msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()

    def toggle_remove_check_updates(self):
        """Переключает настройку удаления проверки обновлений"""
        checked = self.remove_check_updates_action.isChecked()
        if not self._persist_setting(
            'remove_check_updates',
            checked,
            revert_callback=lambda v: self.remove_check_updates_action.setChecked(bool(v)),
        ):
            return

