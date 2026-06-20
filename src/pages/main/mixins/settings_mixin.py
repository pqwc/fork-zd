"""settings_mixin methods for MainWindow."""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from src.shared.i18n.translator import tr
from src.shared.lib.app_logging import setup_logging
from src.features.settings.ui.settings_dialog import SettingsDialog
from src.shared.ui.message_box_utils import configure_message_box

_logger = setup_logging()


class SettingsMixin:
    def _persist_setting(self, key, value, *, silent=False, revert_callback=None):
        """Сохраняет настройку на диск; при ошибке откатывает RAM и опционально UI."""
        previous = self.settings.get(key)
        self.settings[key] = value
        if self.config.set_setting(key, value):
            return True
        self.settings[key] = previous
        _logger.error("Failed to save setting %s to config", key)
        if revert_callback:
            revert_callback(previous)
        elif not silent:
            lang = self.settings.get('language', 'ru')
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_config_save_failed', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
        return False

    def toggle_show_in_tray(self):
        """Переключает отображение в трее"""
        value = self.show_tray_action.isChecked()
        if not self._persist_setting(
            'show_in_tray',
            value,
            revert_callback=lambda v: self.show_tray_action.setChecked(v if v is not None else True),
        ):
            return
        # Применяем настройку
        if value:
            if hasattr(self, 'tray') and self.tray:
                self.tray.show()
        else:
            if hasattr(self, 'tray') and self.tray:
                self.tray.hide()
        # Обновляем доступность пункта "Свернуть окно" в меню Инструменты
        if hasattr(self, 'minimize_to_tray_action') and self.minimize_to_tray_action:
            has_tray = bool(self.settings.get('show_in_tray', True) and hasattr(self, 'tray') and self.tray)
            self.minimize_to_tray_action.setEnabled(has_tray)

    def toggle_close_winws(self):
        """Переключает настройку закрытия winws при выходе"""
        value = self.close_winws_action.isChecked()
        if not self._persist_setting(
            'close_winws_on_exit',
            value,
            revert_callback=lambda v: self.close_winws_action.setChecked(v if v is not None else True),
        ):
            return

    def toggle_start_minimized(self):
        """Переключает настройку запуска свернутым"""
        value = self.start_minimized_action.isChecked()
        if not self._persist_setting(
            'start_minimized',
            value,
            revert_callback=lambda v: self.start_minimized_action.setChecked(bool(v)),
        ):
            return

    def toggle_auto_start(self):
        """Переключает автозапуск последней стратегии"""
        value = self.auto_start_action.isChecked()
        if not self._persist_setting(
            'auto_start_last_strategy',
            value,
            revert_callback=lambda v: self.auto_start_action.setChecked(bool(v)),
        ):
            return

    def toggle_auto_restart(self):
        """Переключает автоперезапуск стратегии"""
        value = self.auto_restart_action.isChecked()
        if not self._persist_setting(
            'auto_restart_strategy',
            value,
            revert_callback=lambda v: self.auto_restart_action.setChecked(bool(v)),
        ):
            return

    def toggle_autostart(self):
        """Переключает автозапуск приложения с Windows"""
        if self.autostart_action.isChecked():
            if self.autostart_manager.enable():
                if not self._persist_setting('autostart_enabled', True):
                    self.autostart_action.setChecked(False)
            else:
                self.autostart_action.setChecked(False)
                lang = self.settings.get('language', 'ru')
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_error', lang))
                msg.setText(tr('msg_autostart_enable_failed', lang))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
        else:
            if self.autostart_manager.disable():
                if not self._persist_setting('autostart_enabled', False):
                    self.autostart_action.setChecked(True)
            else:
                self.autostart_action.setChecked(True)

    def show_settings_dialog(self):
        """Открывает диалоговое окно с настройками (отложено для корректного закрытия меню)"""
        # Если диалог уже открыт — просто активируем его
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        # Если открытие уже запланировано/идёт — не дублируем
        if self._settings_dialog_opening:
            return
        self._settings_dialog_opening = True
        QTimer.singleShot(100, self._show_settings_dialog_impl)

    def _show_settings_dialog_impl(self):
        """Реализация открытия диалога настроек"""
        dialog = SettingsDialog(
            parent=self,
            settings=self.settings,
            config=self.config,
            autostart_manager=self.autostart_manager,
            zapret_updater=self.zapret_updater,
            winws_manager=self.winws_manager
        )
        self._settings_dialog = dialog
        
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            changes = dialog.get_settings_changes()
            
            # Применяем изменения
            # Язык
            if 'language' in changes:
                self.set_language(changes['language'])
            
            # Отображать в трее
            if 'show_in_tray' in changes:
                show_tray_value = changes['show_in_tray']
                if not self._persist_setting('show_in_tray', show_tray_value):
                    return
                if show_tray_value:
                    if hasattr(self, 'tray') and self.tray:
                        self.tray.show()
                else:
                    if hasattr(self, 'tray') and self.tray:
                        self.tray.hide()
                # Обновляем доступность пункта "Свернуть окно" в меню Инструменты,
                # если настройки менялись через диалог
                if hasattr(self, 'minimize_to_tray_action') and self.minimize_to_tray_action:
                    has_tray = bool(show_tray_value and hasattr(self, 'tray') and self.tray)
                    self.minimize_to_tray_action.setEnabled(has_tray)
            
            # Запускать свернутым
            if 'start_minimized' in changes:
                if not self._persist_setting('start_minimized', changes['start_minimized']):
                    return
            
            # Закрывать winws при выходе
            if 'close_winws_on_exit' in changes:
                if not self._persist_setting('close_winws_on_exit', changes['close_winws_on_exit']):
                    return
            
            # Автозапуск с Windows
            if 'autostart_enabled' in changes:
                autostart_value = changes['autostart_enabled']
                if autostart_value != self.autostart_manager.is_enabled():
                    if autostart_value:
                        if not self.autostart_manager.enable():
                            lang = self.settings.get('language', 'ru')
                            msg = configure_message_box(QMessageBox(self))
                            msg.setWindowTitle(tr('msg_error', lang))
                            msg.setText(tr('msg_autostart_enable_failed', lang))
                            msg.setIcon(QMessageBox.Icon.Warning)
                            msg.exec()
                        else:
                            if not self._persist_setting('autostart_enabled', True):
                                return
                    else:
                        if not self.autostart_manager.disable():
                            lang = self.settings.get('language', 'ru')
                            msg = configure_message_box(QMessageBox(self))
                            msg.setWindowTitle(tr('msg_error', lang))
                            msg.setText(tr('msg_autostart_disable_failed', lang))
                            msg.setIcon(QMessageBox.Icon.Warning)
                            msg.exec()
                        else:
                            if not self._persist_setting('autostart_enabled', False):
                                return

            # Автозапуск последней стратегии
            if 'auto_start_last_strategy' in changes:
                if not self._persist_setting('auto_start_last_strategy', changes['auto_start_last_strategy']):
                    return
            
            # Автоперезапуск стратегии
            if 'auto_restart_strategy' in changes:
                if not self._persist_setting('auto_restart_strategy', changes['auto_restart_strategy']):
                    return
            
            # Добавлять /B при обновлении
            if 'add_b_flag_on_update' in changes:
                if not self._persist_setting('add_b_flag_on_update', changes['add_b_flag_on_update']):
                    return
            
            # Проверка обновлений zapret
            if 'remove_check_updates' in changes:
                if not self._persist_setting('remove_check_updates', changes['remove_check_updates']):
                    return
            
            # Game Filter
            if 'game_filter_enabled' in changes:
                if not self._persist_setting('game_filter_enabled', changes['game_filter_enabled']):
                    return
                try:
                    if changes['game_filter_enabled']:
                        self.winws_manager.enable_game_filter()
                    else:
                        self.winws_manager.disable_game_filter()
                except Exception as e:
                    lang = self.settings.get('language', 'ru')
                    msg = configure_message_box(QMessageBox(self))
                    msg.setWindowTitle(tr('msg_error', lang))
                    msg.setText(str(e))
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.exec()
            
            # IPSet Filter
            if 'ipset_filter_mode' in changes:
                if not self._persist_setting('ipset_filter_mode', changes['ipset_filter_mode']):
                    return
                from src.platform import is_linux
                if not is_linux():
                    try:
                        self.winws_manager.set_ipset_mode(changes['ipset_filter_mode'])
                    except Exception as e:
                        lang = self.settings.get('language', 'ru')
                        msg = configure_message_box(QMessageBox(self))
                        msg.setWindowTitle(tr('msg_error', lang))
                        err = str(e)
                        if 'Backup' in err or 'backup' in err:
                            err = tr('msg_backup_not_found', lang)
                        msg.setText(err)
                        msg.setIcon(QMessageBox.Icon.Warning)
                        msg.exec()

            # Путь к папке winws
            if 'winws_path' in changes:
                if not self._persist_setting('winws_path', changes['winws_path']):
                    return
                from src.entities.zapret.zapret_updater import ZapretUpdater
                self.zapret_updater = ZapretUpdater()
                self.load_bat_files()

            # Linux: каталог zapret-linux (service.sh)
            if 'runtime_path' in changes:
                if not self._persist_setting('runtime_path', changes['runtime_path']):
                    return
                from src.entities.zapret.zapret_updater import ZapretUpdater
                from src.platform import is_linux

                if is_linux():
                    from src.platform.linux.linux_runtime_manager import LinuxRuntimeManager

                    self.winws_manager = LinuxRuntimeManager()
                self.zapret_updater = ZapretUpdater()
                if hasattr(self, '_init_winws_watcher'):
                    self._init_winws_watcher()
                self.load_bat_files()
                if hasattr(self, '_update_strategy_detail_panel'):
                    self._update_strategy_detail_panel()

            # Автоперезапуск приложений
            if 'auto_restart_apps' in changes:
                if not self._persist_setting('auto_restart_apps', changes['auto_restart_apps']):
                    return
            if 'auto_restart_apps_enabled' in changes:
                if not self._persist_setting('auto_restart_apps_enabled', changes['auto_restart_apps_enabled']):
                    return
            
            # Игнорируемые подпапки winws при обновлении
            if 'update_ignore_folders' in changes:
                if not self._persist_setting('update_ignore_folders', changes['update_ignore_folders']):
                    return

            if 'auto_update_mode' in changes:
                if not self._persist_setting('auto_update_mode', changes['auto_update_mode']):
                    return

            if 'app_repo' in changes:
                if not self._persist_setting('app_repo', changes['app_repo']):
                    return
                from src.features.updates.app_updater import AppUpdater
                self.app_updater = AppUpdater()
                if hasattr(self, 'load_footer_info'):
                    self.load_footer_info()
                elif hasattr(self, 'load_version_info'):
                    self.load_version_info()

            if 'zapret_repo' in changes:
                if not self._persist_setting('zapret_repo', changes['zapret_repo']):
                    return
                from src.entities.zapret.zapret_updater import ZapretUpdater
                self.zapret_updater = ZapretUpdater()
                if hasattr(self, 'load_footer_info'):
                    self.load_footer_info()
                elif hasattr(self, 'load_zapret_provider_info'):
                    self.load_zapret_provider_info()
        finally:
            self._settings_dialog = None
            self._settings_dialog_opening = False

