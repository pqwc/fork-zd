"""filters_mixin methods for MainWindow."""
from PyQt6.QtWidgets import *
from src.shared.i18n.translator import tr
from src.shared.ui.message_box_utils import configure_message_box
from src.platform import is_linux


class FiltersMixin:
    def update_filter_statuses(self):
        """Синхронизирует настройки Game Filter и IPSet Filter из файлов с конфигом"""
        game_filter_enabled = self.winws_manager.is_game_filter_enabled()
        if game_filter_enabled != self.settings.get('game_filter_enabled', False):
            self._persist_setting('game_filter_enabled', game_filter_enabled, silent=True)
        ipset_mode = self.winws_manager.get_ipset_mode()
        if ipset_mode != self.settings.get('ipset_filter_mode', 'loaded'):
            self._persist_setting('ipset_filter_mode', ipset_mode, silent=True)

    def toggle_game_filter(self):
        """Переключает Game Filter"""
        lang = self.settings.get('language', 'ru')
        
        try:
            game_filter_enabled = self.winws_manager.toggle_game_filter()
            
            if not self._persist_setting('game_filter_enabled', game_filter_enabled):
                return
            # Показываем сообщение
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('settings_game_filter', lang))
            status_text = tr('msg_game_filter_enabled', lang) if game_filter_enabled else tr('msg_game_filter_disabled', lang)
            msg.setText(tr('msg_game_filter_restart', lang).format(status_text))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            
            # Обновляем статус
            self.update_filter_statuses()
        except Exception as e:
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_game_filter_toggle_error', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()

    def toggle_ipset_filter(self):
        """Переключает IPSet Filter между режимами: loaded -> none -> any -> loaded"""
        lang = self.settings.get('language', 'ru')

        if is_linux():
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('settings_ipset_filter', lang))
            msg.setText(tr('linux_ipset_not_available', lang))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            return
        
        try:
            current_mode = self.winws_manager.get_ipset_mode()
            
            # Определяем следующий режим в цикле: loaded -> none -> any -> loaded
            mode_cycle = {'loaded': 'none', 'none': 'any', 'any': 'loaded'}
            next_mode = mode_cycle.get(current_mode, 'loaded')
            
            self.winws_manager.set_ipset_mode(next_mode)
            
            if not self._persist_setting('ipset_filter_mode', next_mode):
                return
            
            # Показываем сообщение
            mode_names = {
                'loaded': ('loaded', 'loaded'),
                'none': ('none', 'none'),
                'any': ('any', 'any')
            }
            mode_name_ru, mode_name_en = mode_names.get(next_mode, ('unknown', 'unknown'))
            mode_name = mode_name_ru if lang == 'ru' else mode_name_en
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('settings_ipset_filter', lang))
            msg.setText(tr('msg_ipset_filter_restart', lang).format(mode_name))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            
            # Обновляем статус
            self.update_filter_statuses()
        except Exception as e:
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            error_text = str(e)
            if 'Backup file not found' in error_text or 'Backup not found' in error_text:
                error_text = tr('msg_backup_not_found_short', lang)
            else:
                error_text = tr('msg_ipset_filter_toggle_error', lang).format(str(e))
            msg.setText(error_text)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()

