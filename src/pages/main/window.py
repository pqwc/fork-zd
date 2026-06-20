"""Main window — assembly of feature mixins."""
from PyQt6.QtCore import QTimer, pyqtSignal, QFileSystemWatcher

from src.entities.config.config_manager import ConfigManager
from src.features.autostart.autostart_manager import AutostartManager
from src.platform import is_linux
from src.entities.zapret.zapret_updater import ZapretUpdater
from src.features.updates.app_updater import AppUpdater
from src.entities.winws.winws_manager import WinwsManager
from src.shared.ui.assets.embedded_assets import get_app_icon
from src.shared.ui.standard_window import StandardMainWindow
from src.app.launch_options import get_launch_options

from .mixins.lifecycle_mixin import LifecycleMixin
from .mixins.strategy_run_mixin import StrategyRunMixin
from .mixins.strategy_list_mixin import StrategyListMixin
from .mixins.updates_mixin import UpdatesMixin
from .mixins.settings_mixin import SettingsMixin
from .mixins.menu_mixin import MenuMixin
from .mixins.ui_mixin import UiMixin
from .mixins.tools_mixin import ToolsMixin
from .mixins.diagnostics_mixin import DiagnosticsMixin
from .mixins.strategy_flags_mixin import StrategyFlagsMixin
from .mixins.filters_mixin import FiltersMixin
from .mixins.version_mixin import VersionMixin
from .mixins.network_mixin import NetworkMixin


class MainWindow(
    LifecycleMixin,
    StrategyRunMixin,
    StrategyListMixin,
    UpdatesMixin,
    SettingsMixin,
    MenuMixin,
    UiMixin,
    ToolsMixin,
    DiagnosticsMixin,
    StrategyFlagsMixin,
    FiltersMixin,
    VersionMixin,
    NetworkMixin,
    StandardMainWindow
):
    update_found_signal = pyqtSignal(str)
    startup_zapret_check_done = pyqtSignal(object)
    startup_app_check_done = pyqtSignal(object)
    linux_deps_install_done = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__(title="ZapretDesktop", width=980, height=640, icon=get_app_icon(), theme="dark")
        self.setMinimumSize(780, 520)
        self.setMaximumSize(16777215, 16777215)
        self.resize(980, 640)
        self.is_running = False
        self.bat_process = None  # Процесс запущенного .bat файла
        self.running_strategy = None  # Название запущенной стратегии для перезапуска
        # True если winws был запущен из этой сессии ZapretDesktop (для отличия от "внешнего" запуска)
        self._started_winws_this_session = False
        self.is_restarting = False  # Флаг для предотвращения множественных перезапусков
        self.user_stopped = False  # Флаг явной остановки пользователем (чтобы не запускать автоперезапуск)
        self._strategy_test_active = False  # Окно тестирования стратегий открыто
        self._test_winws_live = False  # winws запущен окном тестирования (только UI)
        self._is_auto_start = False  # True при автозапуске стратегии — не показываем прогресс-бар
        self.bat_start_time = None  # Время запуска .bat файла (для проверки появления winws.exe)
        self.process_monitor_timer = QTimer(self)  # Таймер для отслеживания процесса
        self.process_monitor_timer.timeout.connect(self.check_winws_process)
        self._start_worker = None  # фоновый запуск стратегии
        self._stop_worker = None   # фоновая остановка
        self._pending_stop_after_start = False
        self._pending_app_restarts = []  # exe-пути приложений для перезапуска после старта winws
        # Отслеживание появления/изменения папки winws
        self.winws_watcher = QFileSystemWatcher(self)
        self.winws_watcher.directoryChanged.connect(self._on_winws_dir_changed)
        self._init_winws_watcher()
        # Инициализация менеджера конфигурации
        self.config = ConfigManager()
        # Загружаем настройки из файла
        self.settings = self.config.load_settings()
        # Инициализация менеджера автозапуска
        if is_linux():
            from src.features.autostart.autostart_linux import LinuxAutostartManager

            self.autostart_manager = LinuxAutostartManager()
        else:
            self.autostart_manager = AutostartManager()
        # Инициализация менеджера обновлений zapret
        self.zapret_updater = ZapretUpdater()
        # Инициализация менеджера обновлений программы
        self.app_updater = AppUpdater()
        self.latest_available_version = None   
        self.update_found_signal.connect(self._on_background_update_found)
        self.startup_zapret_check_done.connect(self._on_startup_zapret_check_done)
        self.startup_app_check_done.connect(self._on_startup_app_check_done)
        self.linux_deps_install_done.connect(self._on_linux_deps_install_done)
        # Инициализация менеджера runtime (winws / nfqws)
        if is_linux():
            from src.platform.linux.linux_runtime_manager import LinuxRuntimeManager

            self.winws_manager = LinuxRuntimeManager()
        else:
            self.winws_manager = WinwsManager()
        # Защита от повторного открытия окна настроек
        self._settings_dialog = None
        self._settings_dialog_opening = False
        self._external_winws_logged = False
        self._last_shown_winws_pid = None
        self._startup_update_in_progress = False
        self._is_shutting_down = False
        self._winws_watcher_paused = False
        self._linux_deps_worker = None
        self._on_stopped_callback = None
        self._init_network_status_monitor()
        self.init_ui()
        self.init_menu_bar()
        self.init_tray()
        self.show_first_run_if_needed()
        # Применяем переводы после инициализации всех компонентов
        self.retranslate_ui()
        
        # Синхронизируем настройки фильтров с файлами winws
        self.update_filter_statuses()
        # Обновляем заголовок окна с учётом текущей стратегии (если уже запущена)
        self._update_window_title_with_strategy()
        
        launch = get_launch_options()

        # Если включена настройка start_minimized, сворачиваем в трей при запуске
        if self.settings.get('start_minimized', False) or launch.start_minimized:
            # Скрываем окно в трей, если включена настройка
            self.hide()
        else:
            # Показываем окно, если настройка выключена
            self.show()
        
        # Запускаем мониторинг процесса (проверка каждые 1 секунду)
        self.process_monitor_timer.start(1000)
        
        # Если включен автозапуск последней стратегии, запускаем её
        if self.settings.get('auto_start_last_strategy', False) and not launch.no_auto_start_strategy:
            # Небольшая задержка, чтобы окно успело полностью инициализироваться
            QTimer.singleShot(1000, lambda: self.auto_start_last_strategy())
