"""lifecycle_mixin methods for MainWindow."""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from src.shared.i18n.translator import tr
from src.shared.lib.path_utils import get_winws_path, get_config_path
from src.shared.lib.open_path import open_path
from src.entities.zapret.zapret_updater import ZapretUpdater
from src.shared.ui.system_tray import SystemTray
from src.shared.ui.message_box_utils import configure_message_box
import os
import sys
import psutil

class LifecycleMixin:
    def show_first_run_if_needed(self):
        """Показывает мастер первого запуска, если first_run_done=False."""
        if self.settings.get('first_run_done', False):
            return
        from src.features.setup.ui.first_run_window import FirstRunWindow

        dlg = FirstRunWindow(self, self.config)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.settings = self.config.load_settings()
        if dlg.enable_autostart:
            if self.autostart_manager.enable():
                self.config.set_setting('autostart_enabled', True)
                self.settings['autostart_enabled'] = True
        if hasattr(self, 'retranslate_ui'):
            self.retranslate_ui()

    def _is_autostart(self):
        """Проверяет, запущено ли приложение через автозапуск"""
        from src.app.launch_options import get_launch_options

        if get_launch_options().autostart:
            return True
        if '--autostart' in sys.argv:
            return True
        
        from src.platform import is_windows
        if not is_windows():
            return False

        # Проверяем, включен ли автозапуск (через Task Scheduler)
        if self.autostart_manager.is_enabled():
            # Дополнительная проверка: если родительский процесс - explorer.exe, winlogon.exe или userinit.exe,
            # и автозапуск включен, то вероятно это автозапуск
            try:
                current_process = psutil.Process()
                parent = current_process.parent()
                if parent:
                    parent_name = parent.name().lower()
                    # Если родитель - explorer.exe и автозапуск включен, это может быть автозапуск
                    # Но explorer.exe также может быть родителем при обычном запуске
                    # Поэтому проверяем только winlogon.exe и userinit.exe как более надежные индикаторы
                    if parent_name in ['winlogon.exe', 'userinit.exe']:
                        return True
                    # Для explorer.exe используем дополнительную проверку - время запуска
                    # При автозапуске процесс обычно запускается сразу после входа в систему
                    if parent_name == 'explorer.exe':
                        # Проверяем, что процесс запущен недавно (в течение последних 30 секунд)
                        # Это может указывать на автозапуск
                        import time
                        process_create_time = current_process.create_time()
                        current_time = time.time()
                        if current_time - process_create_time < 30:
                            return True
            except Exception:
                pass
        
        return False

    def minimize_to_tray(self):
        """Сворачивает окно в трей"""
        self.hide()

    def quit_application(self):
        """Полностью закрывает приложение"""
        self._is_shutting_down = True
        # Если нужно закрыть winws при выходе
        if self.settings.get('close_winws_on_exit', True):
            self.stop_winws_process(silent=True)
        
        QApplication.quit()

    def open_github(self):
        """Открывает страницу GitHub проекта"""
        if hasattr(self, "_app_repo_url"):
            url = QUrl(self._app_repo_url())
        else:
            from src.entities.config.config_manager import DEFAULT_APP_GITHUB_REPO
            url = QUrl(f"https://github.com/{DEFAULT_APP_GITHUB_REPO}")
        QDesktopServices.openUrl(url)

    def open_github_zapret(self):
        """Открывает страницу GitHub репозитория zapret из настроек."""
        slug = getattr(self.zapret_updater, "github_repo", ZapretUpdater.GITHUB_REPO)
        slug = (slug or "").strip().strip("/")
        # Если вдруг в github_repo уже попал полный URL — используем его как есть
        if slug.lower().startswith("http://") or slug.lower().startswith("https://"):
            url = QUrl(slug)
        else:
            url = QUrl(f'https://github.com/{slug}')
        QDesktopServices.openUrl(url)

    def open_winws_folder(self):
        """Открывает папку runtime (winws / zapret-linux) в файловом менеджере."""
        winws_folder = get_winws_path()
        if os.path.exists(winws_folder):
            try:
                open_path(winws_folder)
            except Exception as e:
                lang = self.settings.get('language', 'ru')
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_error', lang))
                msg.setText(str(e))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
        else:
            lang = self.settings.get('language', 'ru')
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_winws_not_found', lang))
            msg.setText(tr('msg_winws_not_found', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()

    def open_config_folder(self):
        """Открывает папку конфигурации программы в файловом менеджере."""
        try:
            config_path = get_config_path()
            config_dir = os.path.dirname(config_path)
            if config_dir and os.path.exists(config_dir):
                open_path(config_dir)
            else:
                lang = self.settings.get('language', 'ru')
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_error', lang))
                msg.setText(config_dir or "Config folder not found")
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
        except Exception as e:
            lang = self.settings.get('language', 'ru')
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(str(e))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()

    def init_tray(self):
        self.tray = SystemTray(self)
        # Применяем настройку show_in_tray при инициализации
        if self.settings.get('show_in_tray', True):
            self.tray.show()
        else:
            self.tray.hide()

    def center_window(self):
        """Центрирует окно на экране"""
        screen = QApplication.primaryScreen().geometry()
        window_geometry = self.frameGeometry()
        window_geometry.moveCenter(screen.center())
        self.move(window_geometry.topLeft())

    def showEvent(self, event):
        """Обработка показа окна - обновляет меню трея"""
        super().showEvent(event)
        self._is_shutting_down = False
        # Обновляем меню трея при показе окна
        if hasattr(self, 'tray') and self.tray:
            self.tray.update_menu()
        if hasattr(self, '_on_window_shown_refresh_network'):
            self._on_window_shown_refresh_network()

    def _run_startup_update_check(self):
        """Проверка/автоустановка обновлений при запуске (вызывается из main thread по таймеру)."""
        self.run_startup_updates()

    def _on_background_update_found(self, latest_version):
        """Вызывается из main thread когда проверка нашла обновление"""
        self.latest_available_version = latest_version
        self.load_version_info()

    def hideEvent(self, event):
        """Обработка скрытия окна - обновляет меню трея"""
        super().hideEvent(event)
        # Обновляем меню трея при скрытии окна
        if hasattr(self, 'tray') and self.tray:
            self.tray.update_menu()

    def closeEvent(self, event):
        """Обработка закрытия окна - скрывает в трей"""
        if self.settings.get('show_in_tray', True):
            event.ignore()
            self.hide()
            self.tray.update_menu()  # Обновляем меню трея
        else:
            # Если трей отключен, закрываем приложение
            self.quit_application()

