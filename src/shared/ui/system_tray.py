from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QObject, QTimer
from src.shared.i18n.translator import tr, tr_platform
from src.shared.lib.path_utils import get_winws_path
from src.shared.lib.open_path import open_path
from src.shared.ui.assets.embedded_assets import get_app_icon
from src.widgets.style_menu import StyleMenu
import os


class SystemTray(QSystemTrayIcon):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.init_ui()
    
    def init_ui(self):
        # Сначала пытаемся получить иконку из главного окна (она уже установлена там)


        icon = None
        if self.parent_window:
            icon = self.parent_window.windowIcon()
        
        if not icon or icon.isNull():
            icon = get_app_icon()
        
        # Если все еще пустая, используем системную
        if icon.isNull():
            icon = QIcon.fromTheme('application-x-executable')
            if icon.isNull():
                icon = QIcon()
        
        self.setIcon(icon)
        # Заголовок при наведении курсора на иконку в трее
        self.setToolTip("ZapretDesktop")
        
        # Создаем контекстное меню
        self.menu = StyleMenu()
        
        # Действие для показа/скрытия окна (будет обновляться динамически)
        self.toggle_window_action = QAction('', self)
        self.toggle_window_action.triggered.connect(self.toggle_window)
        self.menu.addAction(self.toggle_window_action)
        
        self.menu.addSeparator()
        
        # Подменю "Изменить стратегию"
        change_strategy_submenu = StyleMenu()
        self.change_strategy_menu = change_strategy_submenu
        change_strategy_action = QAction('', self)
        change_strategy_action.setMenu(change_strategy_submenu)
        self.menu.addAction(change_strategy_action)
        
        # Подменю "Перезапуск"
        restart_submenu = StyleMenu()
        self.restart_menu = restart_submenu
        restart_action = QAction('', self)
        restart_action.setMenu(restart_submenu)
        self.menu.addAction(restart_action)
        
        self.restart_strategy_action = QAction('', self)
        self.restart_strategy_action.triggered.connect(self.restart_strategy_manual)
        self.restart_menu.addAction(self.restart_strategy_action)
        
        self.menu.addSeparator()
        
        # Действие "Выход"
        self.quit_action = QAction('', self)
        self.quit_action.triggered.connect(self.quit_application)
        self.menu.addAction(self.quit_action)
        
        self.setContextMenu(self.menu)
        
        # Обработка клика по иконке
        self.activated.connect(self.tray_icon_activated)
        
        # Применяем переводы и обновляем меню
        lang = 'ru'
        if self.parent_window and hasattr(self.parent_window, 'settings'):
            lang = self.parent_window.settings.get('language', 'ru')
        self.update_menu()
    
    def tray_icon_activated(self, reason):
        """Обработка активации иконки в трее"""
        # Обрабатываем как одиночный клик, так и двойной клик
        if reason == QSystemTrayIcon.ActivationReason.Trigger or reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_window()
    
    def toggle_window(self):
        """Переключает видимость окна"""
        if self.parent_window:
            if self.parent_window.isVisible():
                self.hide_window()
            else:
                self.show_window()
            # Обновляем меню после изменения состояния
            self.update_menu()
    
    def show_window(self):
        """Показывает главное окно"""
        if self.parent_window:
            self.parent_window.show()
            self.parent_window.raise_()
            self.parent_window.activateWindow()
            # Обновляем меню после показа
            self.update_menu()
    
    def hide_window(self):
        """Скрывает главное окно"""
        if self.parent_window:
            self.parent_window.hide()
            # Обновляем меню после скрытия
            self.update_menu()
    
    def open_winws_folder(self):
        """Открывает папку runtime в файловом менеджере."""
        winws_folder = get_winws_path()
        if os.path.exists(winws_folder):
            try:
                open_path(winws_folder)
            except Exception as e:
                lang = 'ru'
                if self.parent_window and hasattr(self.parent_window, 'settings'):
                    lang = self.parent_window.settings.get('language', 'ru')
                from PyQt6.QtWidgets import QMessageBox
                msg = QMessageBox()
                if self.parent_window:
                    msg.setParent(self.parent_window)
                msg.setWindowTitle(tr('msg_error', lang))
                msg.setText(str(e))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
        else:
            lang = 'ru'
            if self.parent_window and hasattr(self.parent_window, 'settings'):
                lang = self.parent_window.settings.get('language', 'ru')
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox()
            if self.parent_window:
                msg.setParent(self.parent_window)
            msg.setWindowTitle(tr('msg_winws_not_found', lang))
            msg.setText(tr('msg_winws_not_found', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
    
    def update_change_strategy_menu(self):
        """Обновляет подменю 'Изменить стратегию' со списком стратегий"""
        if not hasattr(self, 'change_strategy_menu'):
            return
        
        self.change_strategy_menu.clear()
        lang = 'ru'
        if self.parent_window and hasattr(self.parent_window, 'settings'):
            lang = self.parent_window.settings.get('language', 'ru')
        
        winws_folder = get_winws_path()
        
        # Добавляем пункт "Открыть папку zapret (winws)"
        open_folder_action = QAction(tr_platform('strategies_open_winws_folder', lang), self)
        open_folder_action.triggered.connect(self.open_winws_folder)
        self.change_strategy_menu.addAction(open_folder_action)
        
        # Добавляем пункт "Текущая стратегия: {название}"
        current_strategy_text = tr('tray_current_strategy', lang)
        if self.parent_window and hasattr(self.parent_window, '_get_selected_strategy_name'):
            current_strategy = self.parent_window._get_selected_strategy_name()
            item = None
            if hasattr(self.parent_window, 'strategy_list'):
                item = self.parent_window.strategy_list.currentItem()
            display = item.text() if item else current_strategy
            if display and display not in [tr('msg_no_bat_files', lang), tr('msg_winws_not_found', lang)]:
                current_strategy_text += f' {display}'
            else:
                current_strategy_text += ' -'
        else:
            current_strategy_text += ' -'
         
        
        current_strategy_action = QAction(current_strategy_text, self)
        current_strategy_action.setEnabled(False)
        self.change_strategy_menu.addAction(current_strategy_action)
        
        # Добавляем разделитель
        self.change_strategy_menu.addSeparator()
        
        if os.path.exists(winws_folder):
            bat_files = []
            for filename in os.listdir(winws_folder):
                if filename.endswith('.bat') and os.path.isfile(os.path.join(winws_folder, filename)):
                    name_without_ext = filename[:-4]
                    bat_files.append((name_without_ext, filename))
            
            bat_files.sort(key=lambda x: x[0])
            
            for name, filename in bat_files:
                action = QAction(name, self)
                action.triggered.connect(lambda checked, f=filename: self.select_strategy(f))
                self.change_strategy_menu.addAction(action)
        else:
            action = QAction(tr('msg_winws_not_found', lang), self)
            action.setEnabled(False)
            self.change_strategy_menu.addAction(action)
    
    def select_strategy(self, filename):
        """Выбирает стратегию из меню"""
        if self.parent_window and hasattr(self.parent_window, '_select_strategy_by_data'):
            name_without_ext = filename[:-4]
            if self.parent_window._select_strategy_by_data(name_without_ext):
                if hasattr(self.parent_window, 'config'):
                    self.parent_window.config.set_setting('last_strategy', name_without_ext)
                if hasattr(self.parent_window, 'settings'):
                    self.parent_window.settings['last_strategy'] = name_without_ext
    
    def restart_strategy_manual(self):
        """Перезапускает стратегию вручную"""
        if self.parent_window and hasattr(self.parent_window, 'restart_running_strategy'):
            self.parent_window.restart_running_strategy()
    
    def quit_application(self):
        """Закрывает приложение"""
        if self.parent_window:
            # Вызываем метод quit_application из главного окна,
            # который проверяет настройку close_winws_on_exit
            self.parent_window.quit_application()
        else:
            QApplication.quit()
    
    def show_message(self, title, message, duration=2000):
        """Показывает уведомление в трее"""
        self.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, duration)
    
    def update_menu(self):
        """Обновляет меню в зависимости от состояния окна"""
        lang = 'ru'
        if self.parent_window and hasattr(self.parent_window, 'settings'):
            lang = self.parent_window.settings.get('language', 'ru')
        
        if self.parent_window and self.parent_window.isVisible():
            # Если окно видимо, показываем "Свернуть"
            if hasattr(self, 'toggle_window_action'):
                self.toggle_window_action.setText(tr('tray_minimize', lang))
        else:
            # Если окно скрыто, показываем "Показать"
            if hasattr(self, 'toggle_window_action'):
                self.toggle_window_action.setText(tr('tray_show', lang))
        
        if hasattr(self, 'change_strategy_menu'):
            # Обновляем список стратегий
            self.update_change_strategy_menu()
            # Находим action для подменю и обновляем его текст
            for action in self.menu.actions():
                if action.menu() == self.change_strategy_menu:
                    action.setText(tr('tray_change_strategy', lang))
                    break
        
        if hasattr(self, 'restart_menu'):
            # Находим action для подменю и обновляем его текст
            for action in self.menu.actions():
                if action.menu() == self.restart_menu:
                    action.setText(tr('tray_restart_menu', lang))
                    break
        if hasattr(self, 'restart_strategy_action'):
            self.restart_strategy_action.setText(tr('tray_restart_strategy', lang))
        
        if hasattr(self, 'quit_action'):
            self.quit_action.setText(tr('tray_quit', lang))
    
    def retranslate_ui(self, lang='ru'):
        """Обновляет тексты меню трея в соответствии с языком"""
        self.update_menu()

