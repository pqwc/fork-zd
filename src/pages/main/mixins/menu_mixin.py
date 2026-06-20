"""menu_mixin methods for MainWindow."""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from src.shared.i18n.translator import tr, tr_platform
from src.platform import is_linux
from src.entities.zapret.zapret_updater import ZapretUpdater
from src.shared.lib.path_utils import get_winws_path
from src.widgets.style_menu import StyleMenu
from src.shared.ui import theme
import os


class MenuMixin:
    def init_menu_bar(self):
        """Создает меню бар"""
        self.menubar = QMenuBar()
        self.setMenuBar(self.menubar)
      
        
        lang = self.settings.get('language', 'ru')
        
        # Меню "Tools"
        self.tools_menu = StyleMenu(self.menubar)
        
        # Запуск теста
        self.run_test_action = QAction('', self)
        self.run_test_action.setShortcut(QKeySequence("Ctrl+Shift+T"))
        self.run_test_action.triggered.connect(self.show_test_window)
        self.tools_menu.addAction(self.run_test_action)
        
        # Run Diagnostics
        self.run_diagnostics_action = QAction('', self)
        self.run_diagnostics_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        self.run_diagnostics_action.triggered.connect(self.run_diagnostics)
        self.tools_menu.addAction(self.run_diagnostics_action)
        
        self.tools_menu.addSeparator()

        # Редактор (списки + drivers\etc)
        self.editor_action = QAction('', self)
        self.editor_action.setShortcut(QKeySequence("Ctrl+E"))
        self.editor_action.triggered.connect(self.show_editor)
        self.tools_menu.addAction(self.editor_action)

        self.tools_menu.addSeparator()

        # Экспорт данных в zip
        self.export_bundle_action = QAction(tr("export_bundle_menu", lang), self)
        self.export_bundle_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.export_bundle_action.triggered.connect(self.show_export_bundle_dialog)
        self.tools_menu.addAction(self.export_bundle_action)

        self.tools_menu.addSeparator()

        # Создание стратегий
        self.create_strategy_action = QAction(tr('menu_create_strategy', lang), self)
        self.create_strategy_action.setShortcut(QKeySequence("Ctrl+N"))
        self.create_strategy_action.triggered.connect(self.show_strategy_creator)
        self.tools_menu.addAction(self.create_strategy_action)

        # Создание bin
        self.create_bin_action = QAction('', self)
        self.create_bin_action.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self.create_bin_action.triggered.connect(self.show_bin_creator)
        self.tools_menu.addAction(self.create_bin_action)

        self.tools_menu.addSeparator()

        # Открыть папку...
        self.open_folder_menu = StyleMenu(self.tools_menu)
        self.open_folder_menu.setTitle('')
        self.open_winws_folder_action = QAction('', self)
        self.open_winws_folder_action.setShortcut(QKeySequence("Ctrl+Shift+W"))
        self.open_winws_folder_action.triggered.connect(self.open_winws_folder)
        self.open_folder_menu.addAction(self.open_winws_folder_action)
        self.open_config_folder_action = QAction('', self)
        self.open_config_folder_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.open_config_folder_action.triggered.connect(self.open_config_folder)
        self.open_folder_menu.addAction(self.open_config_folder_action)
        self.tools_menu.addMenu(self.open_folder_menu)

        self.tools_menu.addSeparator()

        # Свернуть окно (если активный трей)
        self.minimize_to_tray_action = QAction('', self)
        self.minimize_to_tray_action.setShortcut(QKeySequence("Ctrl+M"))
        self.minimize_to_tray_action.triggered.connect(self.minimize_to_tray)
        self.tools_menu.addAction(self.minimize_to_tray_action)

        # Закрыть программу
        self.quit_app_action = QAction('', self)
        self.quit_app_action.setShortcut(QKeySequence("Ctrl+Q"))
        self.quit_app_action.triggered.connect(self.quit_application)
        self.tools_menu.addAction(self.quit_app_action)
        
        # Добавляем меню Tools в менюбар
        self.tools_menu_action = self.menubar.addAction('')
        self.tools_menu_action.setMenu(self.tools_menu)
        
        # Меню "Настройки"
        self.settings_menu = StyleMenu(self.menubar)
        
        # Параметры программы
        self.open_settings_action = QAction('', self)
        self.open_settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self.open_settings_action.triggered.connect(self.show_settings_dialog)
        self.settings_menu.addAction(self.open_settings_action)

        # Цветовая тема (Dark / Light)
        self.theme_submenu = StyleMenu(self.settings_menu)
        self.theme_submenu.setTitle(tr('settings_theme', lang))
        self.theme_dark_action = QAction(tr('settings_theme_dark', lang), self)
        self.theme_dark_action.setCheckable(True)
        self.theme_dark_action.triggered.connect(lambda: self._apply_theme('dark'))
        self.theme_light_action = QAction(tr('settings_theme_light', lang), self)
        self.theme_light_action.setCheckable(True)
        self.theme_light_action.triggered.connect(lambda: self._apply_theme('light'))
        self.theme_submenu.addAction(self.theme_dark_action)
        self.theme_submenu.addAction(self.theme_light_action)
        self.settings_menu.addMenu(self.theme_submenu)
        self._update_theme_menu_checked()

        # Добавляем меню Settings в менюбар
        self.settings_menu_action = self.menubar.addAction('')
        self.settings_menu_action.setMenu(self.settings_menu)
        
        # Сохраняем ссылки на действия для обновления в диалоге настроек
        # (они больше не в меню, но нужны для синхронизации)
        self.show_tray_action = None
        self.start_minimized_action = None
        self.close_winws_action = None
        self.autostart_action = None
        self.auto_start_action = None
        self.auto_restart_action = None
        self.language_menu = None
        
        # Меню "Дополнения"
        self.addons_menu = StyleMenu(self.menubar)
        self.addons_action = QAction('', self)
        self.addons_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        self.addons_action.triggered.connect(self._show_addons_dialog)
        self.addons_menu.addAction(self.addons_action)
        self.addons_menu_action = self.menubar.addAction('')
        self.addons_menu_action.setMenu(self.addons_menu)
        
        # Меню "Обновление"
        self.update_menu = StyleMenu(self.menubar)
        
        # Проверить наличие обновлений программы ZapretDesktop
        self.check_app_updates_action = QAction('', self)
        self.check_app_updates_action.setShortcut(QKeySequence("Ctrl+F5"))
        self.check_app_updates_action.triggered.connect(self.check_app_updates)
        self.update_menu.addAction(self.check_app_updates_action)
        
        self.update_menu.addSeparator()
        
        # Проверить наличие обновление стратегий zapret
        self.check_updates_action = QAction('', self)
        self.check_updates_action.setShortcut(QKeySequence("F5"))
        self.check_updates_action.triggered.connect(self.check_zapret_updates)
        self.update_menu.addAction(self.check_updates_action)
        
        # Обновить стратегии в ручную
        self.manual_update_action = QAction('', self)
        self.manual_update_action.setShortcut(QKeySequence("Ctrl+Shift+U"))
        self.manual_update_action.triggered.connect(self.manual_update_strategies)
        self.update_menu.addAction(self.manual_update_action)
        
        self.update_menu.addSeparator()
        
        # Update IPSet List
        self.update_ipset_action = QAction('', self)
        self.update_ipset_action.triggered.connect(self.update_ipset_list)
        self.update_menu.addAction(self.update_ipset_action)
        
        # Update Hosts File — перенесено в редактор etc (hosts + zapret_hosts.txt)
        
        # Добавляем меню Update в менюбар
        self.update_menu_action = self.menubar.addAction('')
        self.update_menu_action.setMenu(self.update_menu)
        
        # Меню "Справка"
        self.help_menu = StyleMenu(self.menubar)
        
        # Открыть страницу Github
        self.open_github_action = QAction('', self)
        self.open_github_action.setShortcut(QKeySequence("F1"))
        self.open_github_action.triggered.connect(self.open_github)
        self.help_menu.addAction(self.open_github_action)
        
        # Открыть Github Flowseal zapret
        self.open_github_zapret_action = QAction('', self)
        self.open_github_zapret_action.setShortcut(QKeySequence("Shift+F1"))
        self.open_github_zapret_action.triggered.connect(self.open_github_zapret)
        self.help_menu.addAction(self.open_github_zapret_action)
        
        # Добавляем меню Help в менюбар
        self.help_menu_action = self.menubar.addAction('')
        self.help_menu_action.setMenu(self.help_menu)

    def update_strategies_menu(self, menu):
        """Обновляет меню со списком стратегий"""
        menu.clear()
        winws_folder = get_winws_path()
        
        # Добавляем пункт "Открыть папку winws"
        lang = self.settings.get('language', 'ru')
        open_folder_action = QAction(tr_platform('strategies_open_winws_folder', lang), self)
        open_folder_action.triggered.connect(self.open_winws_folder)
        menu.addAction(open_folder_action)
        
        # Добавляем разделитель
        menu.addSeparator()
        
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
                menu.addAction(action)
        else:
            action = QAction(tr('msg_winws_not_found', lang), self)
            action.setEnabled(False)
            menu.addAction(action)

    def select_strategy(self, filename):
        """Выбирает стратегию из меню"""
        name_without_ext = filename[:-4]
        if self._select_strategy_by_data(name_without_ext):
            self._persist_setting('last_strategy', name_without_ext, silent=True)

    def retranslate_ui(self):
        """Обновляет все тексты интерфейса в соответствии с текущим языком"""
        lang = self.settings.get('language', 'ru')
        
        # Обновляем меню
        if hasattr(self, 'tools_menu_action') and self.tools_menu_action:
            self.tools_menu_action.setText(tr('menu_tools', lang))
        if hasattr(self, 'run_test_action') and self.run_test_action:
            self.run_test_action.setText(tr('menu_run_test', lang))
        if hasattr(self, 'run_diagnostics_action') and self.run_diagnostics_action:
            self.run_diagnostics_action.setText(tr('menu_run_diagnostics', lang))
        if hasattr(self, 'editor_action') and self.editor_action:
            self.editor_action.setText(tr('menu_editor', lang))
        if hasattr(self, 'create_strategy_action') and self.create_strategy_action:
            self.create_strategy_action.setText(tr('menu_create_strategy', lang))
        if hasattr(self, 'export_bundle_action') and self.export_bundle_action:
            self.export_bundle_action.setText(tr('export_bundle_menu', lang))
        if hasattr(self, 'create_bin_action') and self.create_bin_action:
            self.create_bin_action.setText(tr('menu_create_bin', lang))
        if hasattr(self, 'open_folder_menu') and self.open_folder_menu:
            self.open_folder_menu.setTitle(tr('menu_open_folder', lang))
        if hasattr(self, 'open_winws_folder_action') and self.open_winws_folder_action:
            self.open_winws_folder_action.setText(tr_platform('menu_open_winws_folder', lang))
        if hasattr(self, 'open_config_folder_action') and self.open_config_folder_action:
            self.open_config_folder_action.setText(tr('menu_open_config_folder', lang))
        if hasattr(self, 'minimize_to_tray_action') and self.minimize_to_tray_action:
            self.minimize_to_tray_action.setText(tr('menu_minimize_to_tray', lang))
            # Активна только когда трей включён
            has_tray = bool(self.settings.get('show_in_tray', True) and hasattr(self, 'tray') and self.tray)
            self.minimize_to_tray_action.setEnabled(has_tray)
        if hasattr(self, 'quit_app_action') and self.quit_app_action:
            self.quit_app_action.setText(tr('menu_quit_app', lang))
        
        if hasattr(self, 'settings_menu_action') and self.settings_menu_action:
            self.settings_menu_action.setText(tr('menu_settings', lang))
        if hasattr(self, 'open_settings_action') and self.open_settings_action:
            self.open_settings_action.setText(tr('tray_program_parameters', lang))
        if hasattr(self, 'theme_submenu') and self.theme_submenu:
            self.theme_submenu.setTitle(tr('settings_theme', lang))
        if hasattr(self, 'theme_dark_action') and self.theme_dark_action:
            self.theme_dark_action.setText(tr('settings_theme_dark', lang))
        if hasattr(self, 'theme_light_action') and self.theme_light_action:
            self.theme_light_action.setText(tr('settings_theme_light', lang))
        if hasattr(self, 'update_menu_action') and self.update_menu_action:
            self.update_menu_action.setText(tr('menu_update', lang))
        if hasattr(self, 'check_app_updates_action') and self.check_app_updates_action:
            self.check_app_updates_action.setText(tr('update_check_app', lang))
        if self.check_updates_action:
            self.check_updates_action.setText(tr('update_check_zapret', lang))
        if self.manual_update_action:
            self.manual_update_action.setText(tr('update_manual', lang))
        if hasattr(self, 'update_ipset_action') and self.update_ipset_action:
            self.update_ipset_action.setText(tr('update_ipset_list', lang))
        if hasattr(self, 'addons_menu_action') and self.addons_menu_action:
            self.addons_menu_action.setText(tr('menu_addons', lang))
        if hasattr(self, 'addons_action') and self.addons_action:
            self.addons_action.setText(tr('addons_title', lang))
        # Пункт Update Hosts File теперь отсутствует (функциональность перенесена в редактор)
        
        # Обновляем меню "Справка"
        if hasattr(self, 'help_menu_action') and self.help_menu_action:
            self.help_menu_action.setText(tr('menu_help', lang))
        if hasattr(self, 'open_github_action') and self.open_github_action:
            self.open_github_action.setText(tr('help_open_github', lang))
        if hasattr(self, 'open_github_zapret_action') and self.open_github_zapret_action:
            # Имя пользователя берём из настроек zapret_repo (owner/repo или URL)
            slug = getattr(self.zapret_updater, "github_repo", ZapretUpdater.GITHUB_REPO)
            slug = (slug or "").strip().strip("/")
            owner = "Flowseal"
            if slug:
                if slug.lower().startswith("http://") or slug.lower().startswith("https://"):
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(slug)
                        path = (parsed.path or "").strip("/ ")
                        parts = path.split("/")
                        if len(parts) >= 1 and parts[0]:
                            owner = parts[0]
                    except Exception:
                        owner = "Flowseal"
                else:
                    parts = slug.split("/", 1)
                    if parts and parts[0]:
                        owner = parts[0]
            self.open_github_zapret_action.setText(
                tr('help_open_github_zapret', lang).format(owner=owner)
            )
        
        # Синхронизируем кнопку и список стратегий с текущим состоянием запуска
        self._sync_run_state_ui()

        if hasattr(self, '_retranslate_home_panel'):
            self._retranslate_home_panel()
        
        # Обновляем трей меню
        if hasattr(self, 'tray') and self.tray:
            self.tray.update_menu()

    def set_language(self, lang):
        """Устанавливает язык и обновляет интерфейс"""
        if not self._persist_setting('language', lang):
            return
        self.retranslate_ui()

    def _update_theme_menu_checked(self):
        """Отмечает активную тему (dark/light) в подменю."""
        if not hasattr(self, 'theme_dark_action') or not hasattr(self, 'theme_light_action'):
            return
        is_light = theme.is_light()
        self.theme_light_action.setChecked(is_light)
        self.theme_dark_action.setChecked(not is_light)

    def _apply_theme(self, theme_name: str):
        """Применяет тему, сохраняет её в настройки и обновляет стили."""
        theme.set_theme(theme_name)
        if not self._persist_setting('color_theme', theme_name):
            return
        from PyQt6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance()
        if app:
            theme.apply_application_theme(app)
        if hasattr(self, 'refresh_theme'):
            self.refresh_theme()
        self._update_theme_menu_checked()
        lang = self.settings.get('language', 'ru')
        QMessageBox.information(
            self,
            tr('settings_theme', lang),
            tr('theme_restart_required', lang),
        )

