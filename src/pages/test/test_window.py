from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from src.shared.i18n.translator import tr, tr_platform
from src.platform import is_linux
from src.shared.lib.path_utils import get_base_path, get_winws_path
from src.shared.ui.standard_dialog import StandardDialog
from src.shared.ui import theme
from src.widgets.style_menu import StyleMenu
from src.features.editor.lib.line_number_editor import LineNumberPlainTextEdit
from src.features.editor.lib.editor_highlighters import TargetsTxtHighlighter
from src.widgets.animated_progressbar import AnimatedProgressBar
from src.widgets.codicon_button import CodiconButton
from src.widgets.tab_toolbar_host import TabToolbarHost
from src.widgets.unified_toolbar import UnifiedToolbar
from src.widgets.custom_combobox import CustomComboBox
from src.widgets.fake_header_table import FakeHeaderTable
from src.shared.ui.assets.codicon_utils import codicon_tab_icon
import os
import subprocess
import threading
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import csv
from datetime import datetime

# Профиль быстрого тестирования (таймауты и параллелизм)
_CURL_MAX_TIME = 3
_CURL_SUBPROC_TIMEOUT = 5
_PING_COUNT = 1
_PING_TIMEOUT = 4
_WINWS_START_TIMEOUT = 8.0
_LINUX_RUNTIME_START_TIMEOUT = 18.0
_WINWS_START_POLL = 0.15
_WINWS_STOP_SETTLE = 0.25
_HTTP_TLS_MAX_WORKERS = 24
_PING_MAX_WORKERS = 32

_TAB_ICONS = ("output", "star-full", "file-code")


class _TestTabBar(QTabBar):
    """Tab bar with hand cursor only over tab labels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseMoveEvent(self, event):
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self.tabAt(event.pos()) >= 0
            else Qt.CursorShape.ArrowCursor
        )
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)


class TestWindow(StandardDialog):
    """Окно тестирования стратегий."""
    strategy_changed = pyqtSignal(str)
    tests_completed = pyqtSignal()

    def __init__(self, parent=None, winws_folder=None):
        # Преобразуем путь к winws в абсолютный
        if winws_folder is None:
            # Если путь не передан, используем стандартный путь
            self.winws_folder = get_winws_path()
        elif not os.path.isabs(winws_folder):
            # Если путь относительный, используем базовую директорию приложения
            base_dir = get_base_path()
            self.winws_folder = os.path.join(base_dir, winws_folder)
        else:
            self.winws_folder = winws_folder
        self._linux_mode = is_linux()
        self._linux_manager = None
        self._linux_runtime = None
        self._linux_bg_proc = None
        if self._linux_mode:
            from src.platform.linux.linux_runtime_manager import LinuxRuntimeManager
            from src.platform.linux.runtime_service_sh import ServiceShRuntimeBackend

            self._linux_manager = LinuxRuntimeManager()
            self._linux_runtime = ServiceShRuntimeBackend()
        self.test_results = []
        self.is_running = False
        self.tests_session_started = False
        self._test_thread = None
        self._user_stopped_tests = False
        self.strategy_stats = {}  # Статистика по стратегиям: {strategy_name: {'http_ok': 0, 'tls_ok': 0, 'ping_ok': 0, 'total': 0}}
        # Получаем язык из родительского окна или используем русский по умолчанию
        self.language = 'ru'
        if parent:
            if hasattr(parent, 'settings'):
                self.language = parent.settings.get('language', 'ru')
            elif hasattr(parent, 'config'):
                # Если у родителя есть config, загружаем настройки
                try:
                    settings = parent.config.load_settings()
                    self.language = settings.get('language', 'ru')
                except:
                    pass
        
        from src.shared.ui.assets.embedded_assets import get_app_icon
        super().__init__(
            parent=parent,
            title=tr('test_window_title', self.language),
            width=900,
            height=520,
            icon=get_app_icon(),
            theme="dark",
            resizable=True,
        )
        self.setMinimumSize(820, 480)

        # Флаг автоскролла (для пункта меню "Вид -> Автоскролл")
        self.auto_scroll_enabled = True
        # Режим тестирования: 'standard' или 'dpi'
        self.test_mode = 'standard'
        # Флаг паузы
        self.is_paused = False

        # Данные по стратегиям для меню "Стратегии"
        self.strategy_items = []  # [{'text': str, 'data': Optional[bat_file]}]
        self.current_strategy_index = 0

        # Меню в titlebar
        self.menu_bar = QMenuBar()
        self.menu_bar.setNativeMenuBar(False)

        # Меню "Вид" с пунктом "Автоскролл" c кастомным StyleMenu
        self.view_menu = StyleMenu(self)
        self.view_menu.setTitle(tr('test_menu_view', self.language))
        self.auto_scroll_action = QAction(tr('test_auto_scroll', self.language), self)
        self.auto_scroll_action.setCheckable(True)
        self.auto_scroll_action.setChecked(True)
        self.auto_scroll_action.toggled.connect(self.on_auto_scroll_toggled)
        self.view_menu.addAction(self.auto_scroll_action)
        self.add_fullscreen_view_action(self.view_menu, self.language)

        # Меню "Экспорт" c кастомным StyleMenu
        self.export_menu = StyleMenu(self)
        self.export_menu.setTitle(tr('test_menu_export', self.language))
        
        # Подменю "Экспорт результатов тестирования"
        self.export_results_menu = StyleMenu(self)
        self.export_results_menu.setTitle(tr('tab_test_results', self.language))
        self.export_menu.addMenu(self.export_results_menu)
        
        # Действия для экспорта результатов
        self.export_results_csv = QAction(tr('export_csv', self.language), self)
        self.export_results_csv.triggered.connect(lambda: self.export_table_data(self.table, "results", "csv"))
        self.export_results_menu.addAction(self.export_results_csv)
        
        self.export_results_json = QAction(tr('export_json', self.language), self)
        self.export_results_json.triggered.connect(lambda: self.export_table_data(self.table, "results", "json"))
        self.export_results_menu.addAction(self.export_results_json)
        
        self.export_results_txt = QAction(tr('export_txt', self.language), self)
        self.export_results_txt.triggered.connect(lambda: self.export_table_data(self.table, "results", "txt"))
        self.export_results_menu.addAction(self.export_results_txt)
        
        self.export_menu.addSeparator()
        
        # Подменю "Экспорт лучших стратегий"
        self.export_best_menu = StyleMenu(self)
        self.export_best_menu.setTitle(tr('tab_best_strategies', self.language))
        self.export_menu.addMenu(self.export_best_menu)
        
        # Действия для экспорта лучших стратегий
        self.export_best_csv = QAction(tr('export_csv', self.language), self)
        self.export_best_csv.triggered.connect(lambda: self.export_table_data(self.best_table, "best_strategies", "csv"))
        self.export_best_menu.addAction(self.export_best_csv)
        
        self.export_best_json = QAction(tr('export_json', self.language), self)
        self.export_best_json.triggered.connect(lambda: self.export_table_data(self.best_table, "best_strategies", "json"))
        self.export_best_menu.addAction(self.export_best_json)
        
        self.export_best_txt = QAction(tr('export_txt', self.language), self)
        self.export_best_txt.triggered.connect(lambda: self.export_table_data(self.best_table, "best_strategies", "txt"))
        self.export_best_menu.addAction(self.export_best_txt)

        self.menu_bar.addMenu(self.view_menu)
        self.menu_bar.addMenu(self.export_menu)

        # Добавляем QMenuBar в левую часть кастомного title bar
        if hasattr(self, "title_bar"):
            self.title_bar.addLeftWidget(self.menu_bar)
        
        self.init_ui()
        self.retranslate_ui()
        if self._linux_mode and not self._list_strategy_files():
            QTimer.singleShot(0, self._warn_no_strategies_linux)
    
    def _warn_no_strategies_linux(self) -> None:
        if self._list_strategy_files():
            return
        QMessageBox.warning(
            self,
            tr("test_error_title", self.language),
            tr("test_error_no_bat_files", self.language),
        )

    def _sync_targets_file_path(self) -> None:
        utils = self._utils_folder()
        try:
            os.makedirs(utils, exist_ok=True)
        except OSError:
            pass
        self.targets_file_path = os.path.join(utils, "targets.txt")

    def _runtime_start_timeout(self) -> float:
        parent = self.parent()
        if parent is not None and hasattr(parent, "_get_winws_start_timeout"):
            try:
                return float(parent._get_winws_start_timeout())
            except (TypeError, ValueError):
                pass
        if parent is not None and hasattr(parent, "settings"):
            try:
                raw = int(parent.settings.get("winws_start_timeout_sec", 15) or 15)
                return float(max(5, min(raw, 120)))
            except (TypeError, ValueError):
                pass
        return _LINUX_RUNTIME_START_TIMEOUT if self._linux_mode else _WINWS_START_TIMEOUT
    
    def _style_table(self, table: QTableWidget):
        p = theme.palette()
        table.setCursor(Qt.CursorShape.ArrowCursor)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {p.bg_panel};
                color: {p.fg_text};
                border: none;
                outline: none;
                gridline-color: {p.border};
            }}
            QTableWidget::item:selected {{
                background-color: {p.accent};
                color: #ffffff;
            }}
        """)

    def _update_tabs_appearance(self):
        if not hasattr(self, "tabs"):
            return
        tab_texts = [
            tr('tab_test_results', self.language),
            tr('tab_best_strategies', self.language),
            tr('tab_targets', self.language),
        ]
        for index, text in enumerate(tab_texts):
            if index >= self.tabs.count():
                break
            self.tabs.setTabText(index, text)
            if index < len(_TAB_ICONS):
                icon = codicon_tab_icon(_TAB_ICONS[index], 14)
                if not icon.isNull():
                    self.tabs.setTabIcon(index, icon)

    def _apply_tabs_style(self):
        self.tabs.setDocumentMode(False)
        self.tabs.setIconSize(QSize(14, 16))
        tab_bar = self.tabs.tabBar()
        tab_bar.setUsesScrollButtons(True)
        tab_bar.setExpanding(False)
        tab_bar.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.apply_theme()

    def refresh_theme(self):
        self._apply_tabs_style()
        self._update_tabs_appearance()
        toolbar = getattr(self, "_transport_toolbar", None)
        if toolbar and hasattr(toolbar, "apply_theme"):
            toolbar.apply_theme()
        if hasattr(self, "targets_editor"):
            theme.apply_test_panel_text_widget(self.targets_editor)
            self.targets_editor.refresh_editor_colors()
        if hasattr(self, "_targets_highlighter") and hasattr(self._targets_highlighter, "refresh_theme"):
            self._targets_highlighter.refresh_theme()
        theme.refresh_round_clip_widgets(self)
        for combo_name in ("mode_combo", "strategy_combo"):
            combo = getattr(self, combo_name, None)
            if combo is not None and hasattr(combo, "apply_theme"):
                combo.apply_theme()
        self._apply_theme()

    def _create_toolbar(self) -> UnifiedToolbar:
        bar = UnifiedToolbar(self)
        self.btn_start = CodiconButton(
            "play", tr("test_start_button", self.language), self,
        )
        self.btn_stop = CodiconButton(
            "debug-stop", tr("test_stop_button", self.language), self,
        )
        self.btn_pause = CodiconButton(
            "debug-pause", tr("test_menu_pause", self.language), self,
        )
        self.btn_start.clicked.connect(self.start_tests)
        self.btn_stop.clicked.connect(self.stop_tests)
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        self.mode_combo = CustomComboBox(self)
        self.mode_combo.addItem(tr("test_mode_standard", self.language), "standard")
        self.mode_combo.addItem(tr("test_mode_dpi", self.language), "dpi")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_combo_changed)

        self.strategy_combo = CustomComboBox(self)
        self.strategy_combo.currentIndexChanged.connect(self._on_strategy_combo_changed)

        bar.add_button(self.btn_start)
        bar.add_button(self.btn_stop)
        bar.add_button(self.btn_pause)
        bar.add_separator()
        bar.add_combobox(self.mode_combo, 108, flat=True)
        bar.add_separator()
        bar.add_combobox(self.strategy_combo, 180 if self._linux_mode else 116, flat=True)
        self._update_transport_buttons()
        self._transport_toolbar = bar
        return bar

    def _update_transport_buttons(self):
        if getattr(self, "btn_start", None) is None:
            return
        if self.is_running:
            self.btn_start.hide()
            self.btn_stop.show()
            self.btn_pause.show()
            if self.is_paused:
                self.btn_pause.set_codicon("debug-continue")
                self.btn_pause.setToolTip(tr("test_menu_continue", self.language))
            else:
                self.btn_pause.set_codicon("debug-pause")
                self.btn_pause.setToolTip(tr("test_menu_pause", self.language))
        else:
            self.btn_start.show()
            self.btn_stop.hide()
            self.btn_pause.hide()
            self.is_paused = False
            self.btn_pause.set_codicon("debug-pause")

    def _on_pause_clicked(self):
        if not self.is_running:
            return
        self.is_paused = not self.is_paused
        self._update_transport_buttons()

    def _on_mode_combo_changed(self, index: int):
        mode = self.mode_combo.itemData(index)
        if mode:
            self.set_test_mode(mode)

    def _on_strategy_combo_changed(self, index: int):
        if index >= 0:
            self.current_strategy_index = index

    def init_ui(self):
        layout = self.getContentLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.tabs = TabToolbarHost(self)
        self.tabs.setTabBar(_TestTabBar(self.tabs))
        self._apply_tabs_style()
        self.tabs.set_toolbar(self._create_toolbar())

        self.results_view = FakeHeaderTable()
        self.table = self.results_view.table
        self.table.setColumnCount(4)
        self._style_table(self.table)
        self.tabs.addTab(self.results_view, "")

        self.best_view = FakeHeaderTable()
        self.best_table = self.best_view.table
        self.best_table.setColumnCount(4)
        self._style_table(self.best_table)
        self.tabs.addTab(self.best_view, "")

        self.targets_editor = LineNumberPlainTextEdit()
        try:
            from src.platform import get_privilege_backend

            mono = get_privilege_backend().get_ui_font_family()
        except Exception:
            mono = "Monospace" if self._linux_mode else "Consolas"
        self.targets_editor.setFont(QFont(mono, 10))
        self._targets_highlighter = TargetsTxtHighlighter(self.targets_editor.document())
        self.targets_editor.textChanged.connect(self.on_targets_text_changed)
        theme.apply_test_panel_text_widget(self.targets_editor)
        self.targets_panel = theme.wrap_tab_page_content(self.targets_editor)
        self.tabs.addTab(self.targets_panel, "")
        
        # Инициализируем путь к файлу targets.txt (zapret-latest/utils на Linux)
        self._sync_targets_file_path()
        
        # Отслеживание изменений файла извне через QFileSystemWatcher
        self.file_watcher = QFileSystemWatcher()
        if os.path.exists(self.targets_file_path):
            self.file_watcher.addPath(self.targets_file_path)
        self.file_watcher.fileChanged.connect(self.on_targets_file_changed_externally)
        
        # Таймер для отложенного автоматического сохранения
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.auto_save_targets_file)
        
        # Флаг для предотвращения циклических обновлений (когда мы сами сохраняем файл)
        self.is_saving = False
        
        # Загружаем файл при инициализации
        self.load_targets_file()
        
        layout.addWidget(self.tabs)
        
        # Словарь для хранения статистики по стратегиям
        self.strategy_stats = {}
        
        # Инициализируем список целей для тестирования (стандартный и для DPI)
        self.init_targets()
        
        # Прогресс бар в стиле VS Code с анимацией
        self.progress = AnimatedProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        # Изначально "прячем" прогрессбар через фон
        self._apply_progressbar_hidden_style()
        layout.addWidget(self.progress)
        
        # Статус - перемещен в заголовок окна
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p = theme.palette()
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {p.fg_text};
                font-size: 12px;
                background-color: transparent;
                border: none;
            }}
        """)
        # Добавляем статус в центр заголовка (title_bar создается в StandardDialog.__init__)
        if hasattr(self, "title_bar"):
            self.title_bar.addCenterWidget(self.status_label)

    def retranslate_ui(self):
        """Обновляет все тексты интерфейса в соответствии с выбранным языком"""
        # Обновляем язык из родительского окна, если оно доступно
        parent = self.parent()
        if parent:
            if hasattr(parent, 'settings'):
                self.language = parent.settings.get('language', 'ru')
            elif hasattr(parent, 'config'):
                # Если у родителя есть config, загружаем настройки
                try:
                    settings = parent.config.load_settings()
                    self.language = settings.get('language', 'ru')
                except:
                    pass
        
        self.setWindowTitle(tr('test_window_title', self.language))
        
        if hasattr(self, "btn_start"):
            self.btn_start.setToolTip(tr('test_start_button', self.language))
            self.btn_stop.setToolTip(tr('test_stop_button', self.language))
            self._update_transport_buttons()

        if hasattr(self, "results_view"):
            self.results_view.set_header_labels([
                tr('table_col_strategy', self.language),
                tr('table_col_target', self.language),
                tr('table_col_http_tls', self.language),
                tr('table_col_ping', self.language),
            ])

        if hasattr(self, "best_view"):
            self.best_view.set_header_labels([
                tr('best_strategies_col_strategy', self.language),
                tr('best_strategies_col_http_ok', self.language),
                tr('best_strategies_col_tls_ok', self.language),
                tr('best_strategies_col_ping_ok', self.language),
            ])

        self._update_tabs_appearance()

        if hasattr(self, "view_menu"):
            self.view_menu.setTitle(tr('test_menu_view', self.language))
        if hasattr(self, "auto_scroll_action"):
            self.auto_scroll_action.setText(tr('test_auto_scroll', self.language))
        if hasattr(self, "_fullscreen_action"):
            self._fullscreen_action.setText(tr('editor_fullscreen', self.language))
        if hasattr(self, "mode_combo"):
            mode = self.test_mode
            self.mode_combo.blockSignals(True)
            self.mode_combo.clear()
            self.mode_combo.addItem(tr('test_mode_standard', self.language), "standard")
            self.mode_combo.addItem(tr('test_mode_dpi', self.language), "dpi")
            self.mode_combo.setCurrentIndex(0 if mode == 'standard' else 1)
            self.mode_combo.blockSignals(False)
        if hasattr(self, "export_menu"):
            self.export_menu.setTitle(tr('test_menu_export', self.language))
        if hasattr(self, "export_results_menu"):
            self.export_results_menu.setTitle(tr('tab_test_results', self.language))
        if hasattr(self, "export_results_csv"):
            self.export_results_csv.setText(tr('export_csv', self.language))
        if hasattr(self, "export_results_json"):
            self.export_results_json.setText(tr('export_json', self.language))
        if hasattr(self, "export_results_txt"):
            self.export_results_txt.setText(tr('export_txt', self.language))
        if hasattr(self, "export_best_menu"):
            self.export_best_menu.setTitle(tr('tab_best_strategies', self.language))
        if hasattr(self, "export_best_csv"):
            self.export_best_csv.setText(tr('export_csv', self.language))
        if hasattr(self, "export_best_json"):
            self.export_best_json.setText(tr('export_json', self.language))
        if hasattr(self, "export_best_txt"):
            self.export_best_txt.setText(tr('export_txt', self.language))

        # Обновляем список стратегий в меню
        self.load_strategies()

    def load_strategies(self):
        """Загружает список стратегий и перестраивает меню 'Стратегии'."""
        # Запоминаем текущий выбранный .bat (если был)
        current_data = None
        if 0 <= self.current_strategy_index < len(self.strategy_items):
            current_data = self.strategy_items[self.current_strategy_index].get("data")

        self.strategy_items = []

        # Первый пункт: "Все стратегии"
        self.strategy_items.append({
            "text": tr('test_all_strategies', self.language),
            "data": None
        })

        # Получаем список .bat файлов
        bat_files = self._list_strategy_files()
        for bat_file in bat_files:
            strategy_name = os.path.splitext(bat_file)[0]
            self.strategy_items.append({
                "text": strategy_name,
                "data": bat_file
            })

        if hasattr(self, "strategy_combo"):
            self.strategy_combo.blockSignals(True)
            self.strategy_combo.clear()
            for item in self.strategy_items:
                self.strategy_combo.addItem(item["text"], item.get("data"))
            self.strategy_combo.blockSignals(False)

        # Восстанавливаем выбранный элемент, если он был
        if current_data:
            for i, item in enumerate(self.strategy_items):
                if item.get("data") == current_data:
                    self.current_strategy_index = i
                    break
        else:
            self.current_strategy_index = 0

        if hasattr(self, "strategy_combo"):
            self.strategy_combo.blockSignals(True)
            if 0 <= self.current_strategy_index < self.strategy_combo.count():
                self.strategy_combo.setCurrentIndex(self.current_strategy_index)
            self.strategy_combo.blockSignals(False)

    def set_test_mode(self, mode: str):
        """Устанавливает режим тестирования."""
        if mode not in ('standard', 'dpi'):
            return
        self.test_mode = mode
        if hasattr(self, "mode_combo"):
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(0 if mode == 'standard' else 1)
            self.mode_combo.blockSignals(False)

    def init_targets(self):
        """Инициализирует список целей для тестирования"""
        # Загружаем цели из файла targets.txt, если он существует
        targets_file = os.path.join(self._utils_folder(), 'targets.txt')
        self.targets = []
        
        if os.path.exists(targets_file):
            try:
                with open(targets_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and '=' in line:
                            match = re.match(r'^\s*(\w+(?:\s+\w+)*)\s*=\s*"(.+)"\s*$', line)
                            if match:
                                name = match.group(1)
                                value = match.group(2)
                                if value.startswith('PING:'):
                                    ping_target = value.replace('PING:', '').strip()
                                    self.targets.append({
                                        'name': name,
                                        'url': None,
                                        'ping_target': ping_target
                                    })
                                else:
                                    self.targets.append({
                                        'name': name,
                                        'url': value,
                                        'ping_target': None
                                    })
            except Exception:
                pass
        
        # Если файл не найден или пуст, используем значения по умолчанию
        if not self.targets:
            self.targets = [
                {'name': 'Discord Main', 'url': 'https://discord.com', 'ping_target': None},
                {'name': 'Discord Gateway', 'url': 'https://gateway.discord.gg', 'ping_target': None},
                {'name': 'Discord CDN', 'url': 'https://cdn.discordapp.com', 'ping_target': None},
                {'name': 'Discord Updates', 'url': 'https://updates.discord.com', 'ping_target': None},
                {'name': 'YouTube Web', 'url': 'https://www.youtube.com', 'ping_target': None},
                {'name': 'YouTube Short', 'url': 'https://youtu.be', 'ping_target': None},
                {'name': 'YouTube Image', 'url': 'https://i.ytimg.com', 'ping_target': None},
                {'name': 'YouTube Video Redirect', 'url': 'https://redirector.googlevideo.com', 'ping_target': None},
                {'name': 'Google Main', 'url': 'https://www.google.com', 'ping_target': None},
                {'name': 'Google Gstatic', 'url': 'https://www.gstatic.com', 'ping_target': None},
                {'name': 'Cloudflare Web', 'url': 'https://www.cloudflare.com', 'ping_target': None},
                {'name': 'Cloudflare CDN', 'url': 'https://cdnjs.cloudflare.com', 'ping_target': None},
                {'name': 'Cloudflare DNS 1.1.1.1', 'url': None, 'ping_target': '1.1.1.1'},
                {'name': 'Cloudflare DNS 1.0.0.1', 'url': None, 'ping_target': '1.0.0.1'},
                {'name': 'Google DNS 8.8.8.8', 'url': None, 'ping_target': '8.8.8.8'},
                {'name': 'Google DNS 8.8.4.4', 'url': None, 'ping_target': '8.8.4.4'},
                {'name': 'Quad9 DNS 9.9.9.9', 'url': None, 'ping_target': '9.9.9.9'},
            ]

        # Сохраняем стандартный список целей и отдельный набор для DPI‑тестов
        self.standard_targets = list(self.targets)
        # DPI checkers: небольшой фиксированный набор TCP/HTTPS целей
        self.dpi_targets = [
            {'name': 'Discord Main', 'url': 'https://discord.com', 'ping_target': None},
            {'name': 'YouTube Web', 'url': 'https://www.youtube.com', 'ping_target': None},
            {'name': 'Cloudflare Web', 'url': 'https://www.cloudflare.com', 'ping_target': None},
            {'name': 'Google Main', 'url': 'https://www.google.com', 'ping_target': None},
        ]
    
    def start_tests(self):
        if self.is_running:
            return

        # Перед запуском тестов проверяем, не запущен ли уже runtime (winws / nfqws)
        runtime_running = self._is_runtime_running()

        if runtime_running:
            from src.platform import is_linux

            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setWindowTitle(tr_platform('update_stopping_winws', self.language))
            if is_linux():
                runtime_text = tr('update_runtime_running', self.language).format('nfqws')
            else:
                runtime_text = tr('update_winws_running', self.language)
            msg_box.setText(runtime_text)
            msg_box.setInformativeText(tr_platform('update_winws_stop_required', self.language))
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
            reply = msg_box.exec()
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_winws()
            else:
                return

        # Получаем выбранную стратегию из меню
        selected_index = self.current_strategy_index
        
        # Если выбрано "Все стратегии" (индекс 0)
        if selected_index == 0:
            # Получаем список всех .bat файлов
            bat_files = self._list_strategy_files()
        else:
            # Получаем выбранный .bat файл из self.strategy_items
            if 0 <= selected_index < len(self.strategy_items):
                bat_file = self.strategy_items[selected_index].get("data")
            else:
                bat_file = None
            if bat_file:
                bat_files = [bat_file]
            else:
                QMessageBox.warning(self, tr('test_error_title', self.language), 
                                     tr('test_error_cannot_determine', self.language))
                return
        
        if not bat_files:
            QMessageBox.warning(self, tr('test_error_title', self.language), 
                             tr('test_error_no_bat_files', self.language))
            return

        self.tests_session_started = True
        self._user_stopped_tests = False
        if getattr(self, '_test_thread', None) is not None and self._test_thread.is_alive():
            QMessageBox.warning(
                self,
                tr('test_error_title', self.language),
                tr('test_error_already_running', self.language),
            )
            return
        self.is_running = True
        self.is_paused = False
        self._update_transport_buttons()
        self._apply_progressbar_visible_style()
        # Выбираем список целей в зависимости от режима
        if getattr(self, "test_mode", "standard") == "dpi":
            self.targets = getattr(self, "dpi_targets", self.targets)
        else:
            self.targets = getattr(self, "standard_targets", self.targets)

        # Прогресс = количество .bat файлов * количество целей
        total_tests = len(bat_files) * len(self.targets)
        self.progress.setRange(0, total_tests)
        self.progress.setValue(0)
        
        # Очищаем таблицы перед новым тестом
        self.table.setRowCount(0)
        self.best_table.setRowCount(0)
        self.strategy_stats = {}
        
        # Запускаем тесты в отдельном потоке
        self._test_thread = threading.Thread(target=self.run_tests, args=(bat_files,))
        self._test_thread.daemon = True
        self._test_thread.start()
    
    def stop_tests(self):
        self._user_stopped_tests = True
        self.is_running = False
        self.is_paused = False
        self._update_transport_buttons()
        self._apply_progressbar_hidden_style()
        # Обновляем заголовок окна
        try:
            title_base = tr('test_window_title', self.language)
        except Exception:
            title_base = 'Тестирование'
        status_text = tr('test_status_stopping', self.language)
        self.setWindowTitle(f"{title_base} — {status_text}")
        if hasattr(self, "status_label"):
            self.status_label.setText(status_text)
    
    def closeEvent(self, event):
        if self.is_running:
            self.stop_tests()
            thread = getattr(self, '_test_thread', None)
            if thread is not None and thread.is_alive():
                thread.join(timeout=4.0)
        super().closeEvent(event)
    
    def run_tests(self, bat_files):
        self.test_results = []
        test_count = 0
        total_files = len(bat_files)

        try:
            for file_index, bat_file in enumerate(bat_files, start=1):
                if not self.is_running:
                    break

                # Вычисляем процент обработки
                percent = int((file_index / total_files) * 100) if total_files > 0 else 0

                # Обновляем статус с информацией о файле (1/19) и проценте
                status_text = f"{bat_file} ({file_index}/{total_files} - {percent}%)"
                QMetaObject.invokeMethod(self, "update_status", Qt.ConnectionType.QueuedConnection,
                                        Q_ARG(str, status_text))

                # Добавляем заголовок стратегии в таблицу
                QMetaObject.invokeMethod(self, "add_strategy_header", Qt.ConnectionType.QueuedConnection,
                                        Q_ARG(str, bat_file))

                # Останавливаем runtime если запущен
                self.stop_winws()
                self._sleep_while_running(_WINWS_STOP_SETTLE)

                # Запускаем стратегию
                if not self._start_strategy_for_test(bat_file):
                    self._sleep_while_running(2.0)
                elif not self._wait_for_runtime_ready():
                    self._sleep_while_running(2.0)
                else:
                    self._notify_parent_winws_state(True)

                # Инициализируем статистику для этой стратегии
                strategy_name = os.path.splitext(bat_file)[0]
                self.strategy_changed.emit(strategy_name)
                strategy_stats = {
                    'http_ok': 0,
                    'tls12_ok': 0,
                    'tls13_ok': 0,
                    'ping_ok': 0,
                    'total_targets': 0
                }

                # HTTP/TLS и ping параллельно по всем целям
                results = {}
                ping_results = {}
                if self.is_running:
                    with ThreadPoolExecutor(max_workers=2) as phase_pool:
                        http_future = phase_pool.submit(self.test_targets_http_tls_parallel, self.targets)
                        ping_future = phase_pool.submit(self.test_targets_ping_parallel, self.targets)
                        http_map = http_future.result() if self.is_running else {}
                        ping_results = ping_future.result() if self.is_running else {}

                    for target in self.targets:
                        if not self.is_running:
                            break
                        target_name = target['name']
                        result = http_map.get(target_name, {
                            'http': 'N/A', 'tls12': 'N/A', 'tls13': 'N/A', 'ping': ''
                        })
                        ping_result = ping_results.get(target_name, 'N/A')
                        result['ping'] = ping_result
                        results[target_name] = {'target': target, 'result': result}

                        strategy_stats['total_targets'] += 1
                        if result.get('http') == 'OK':
                            strategy_stats['http_ok'] += 1
                        if result.get('tls12') == 'OK':
                            strategy_stats['tls12_ok'] += 1
                        if result.get('tls13') == 'OK':
                            strategy_stats['tls13_ok'] += 1
                        ping_val = ping_result
                        if ping_val not in ('N/A', 'ERROR', 'Timeout') and 'ms' in str(ping_val):
                            strategy_stats['ping_ok'] += 1

                        QMetaObject.invokeMethod(
                            self, "add_result_to_table", Qt.ConnectionType.QueuedConnection,
                            Q_ARG(str, target_name), Q_ARG(dict, result)
                        )
                        test_count += 1
                        QMetaObject.invokeMethod(
                            self, "update_progress", Qt.ConnectionType.QueuedConnection,
                            Q_ARG(int, test_count)
                        )

                # Обновляем статистику стратегии в главном потоке
                QMetaObject.invokeMethod(self, "update_strategy_stats", Qt.ConnectionType.QueuedConnection,
                                        Q_ARG(str, strategy_name),
                                        Q_ARG(int, strategy_stats['http_ok']),
                                        Q_ARG(int, strategy_stats['tls12_ok']),
                                        Q_ARG(int, strategy_stats['tls13_ok']),
                                        Q_ARG(int, strategy_stats['ping_ok']),
                                        Q_ARG(int, strategy_stats['total_targets']))

                # Обновляем таблицу лучших стратегий после тестирования стратегии
                QMetaObject.invokeMethod(self, "update_best_strategies", Qt.ConnectionType.QueuedConnection)

                # Останавливаем winws после тестирования всех целей для этого .bat файла
                self.stop_winws()

                # Добавляем пустую строку-разделитель между .bat файлами
                QMetaObject.invokeMethod(self, "add_separator", Qt.ConnectionType.QueuedConnection)

        except Exception:
            from src.shared.lib.app_logging import setup_logging
            setup_logging().exception("Test run failed")
        finally:
            QMetaObject.invokeMethod(self, "tests_finished", Qt.ConnectionType.QueuedConnection)
    
    def _sleep_while_running(self, seconds):
        """Пауза с учётом остановки тестов и режима паузы."""
        import time
        elapsed = 0.0
        while elapsed < seconds and self.is_running:
            while getattr(self, "is_paused", False) and self.is_running:
                time.sleep(0.05)
            time.sleep(0.05)
            elapsed += 0.05

    def _utils_folder(self) -> str:
        if self._linux_mode and self._linux_manager is not None:
            return self._linux_manager.utils_folder
        return os.path.join(self.winws_folder, 'utils')

    def _list_strategy_files(self) -> list[str]:
        if self._linux_mode and self._linux_manager is not None:
            return [
                filename
                for filename in self._linux_manager.list_strategy_files()
                if not filename.startswith('service')
            ]
        bat_files = []
        if os.path.exists(self.winws_folder):
            for file in os.listdir(self.winws_folder):
                if file.endswith('.bat') and not file.startswith('service'):
                    bat_files.append(file)
        bat_files.sort()
        return bat_files

    def _is_runtime_running(self) -> bool:
        if self._linux_mode and self._linux_manager is not None:
            return self._linux_manager.is_running()
        try:
            import psutil

            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info.get('name', '').lower() == 'winws.exe':
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            pass
        return False

    def _is_winws_running(self):
        return self._is_runtime_running()

    def _wait_for_runtime_ready(self):
        """Ждёт появления winws.exe / nfqws, выходя раньше при успехе."""
        import time

        elapsed = 0.0
        timeout = self._runtime_start_timeout()
        while elapsed < timeout and self.is_running:
            while getattr(self, "is_paused", False) and self.is_running:
                time.sleep(0.05)
            if self._is_runtime_running():
                return True
            time.sleep(_WINWS_START_POLL)
            elapsed += _WINWS_START_POLL
        return self._is_runtime_running()

    def _wait_for_winws_ready(self):
        return self._wait_for_runtime_ready()

    def _start_strategy_for_test(self, bat_file: str) -> bool:
        if self._linux_mode and self._linux_runtime is not None:
            status, self._linux_bg_proc = self._linux_runtime.start_background(
                bat_file,
                use_systemd=False,
            )
            if status.running:
                return True
            if self._linux_bg_proc is not None:
                return True
            detail = (status.detail or "").strip().lower()
            pending_ok = frozenset({"starting_via_service", "background_run", ""})
            if detail in pending_ok:
                return True
            if "fail" in detail or "error" in detail or "not_configured" in detail:
                return False
            return False
        bat_path = os.path.join(self.winws_folder, bat_file)
        subprocess.Popen(
            ['cmd.exe', '/c', bat_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=self.winws_folder,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True

    def _run_single_curl(self, test_name, args, url):
        try:
            curl_exe = 'curl' if self._linux_mode else 'curl.exe'
            curl_args = [
                curl_exe, '-I', '-s', '-m', str(_CURL_MAX_TIME),
                '--connect-timeout', '2', '-o', os.devnull,
            ] + args + [url]
            run_kwargs = {
                'capture_output': True,
                'timeout': _CURL_SUBPROC_TIMEOUT,
                'encoding': 'utf-8',
                'errors': 'replace',
            }
            if sys.platform == 'win32':
                run_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            curl_process = subprocess.run(curl_args, **run_kwargs)
            output = curl_process.stdout or ''
            stderr = curl_process.stderr or ''
            combined = output + stderr
            if (curl_process.returncode == 35 or
                    'not supported' in combined.lower() or
                    'unsupported' in combined.lower() or
                    ('protocol' in combined.lower() and 'not' in combined.lower())):
                return test_name, 'UNSUP'
            if curl_process.returncode == 0:
                return test_name, 'OK'
            return test_name, 'ERROR'
        except Exception:
            return test_name, 'ERROR'

    def test_targets_http_tls_parallel(self, targets):
        """HTTP/TLS для всех целей параллельно."""
        results = {}
        if not targets:
            return results
        max_workers = min(len(targets), _HTTP_TLS_MAX_WORKERS)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {}
            for target in targets:
                if not self.is_running:
                    break
                while getattr(self, "is_paused", False) and self.is_running:
                    self._sleep_while_running(0.05)
                future_to_name[executor.submit(self.test_target_http_tls, target)] = target['name']
            for future in as_completed(future_to_name):
                if not self.is_running:
                    break
                while getattr(self, "is_paused", False) and self.is_running:
                    self._sleep_while_running(0.05)
                name = future_to_name[future]
                try:
                    results[name] = future.result()
                except Exception:
                    results[name] = {'http': 'ERROR', 'tls12': 'ERROR', 'tls13': 'ERROR', 'ping': ''}
        return results

    def test_target_http_tls(self, target):
        """Тестирует HTTP/TLS для одной цели (без ping)."""
        result = {
            'http': 'N/A',
            'tls12': 'N/A',
            'tls13': 'N/A',
            'ping': ''
        }
        if not target.get('url'):
            return result
        url = target['url']
        test_configs = [
            ('http', ['--http1.1']),
            ('tls12', ['--tlsv1.2', '--tls-max', '1.2']),
            ('tls13', ['--tlsv1.3', '--tls-max', '1.3']),
        ]
        max_workers = min(len(test_configs), 3)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self._run_single_curl, test_name, args, url)
                for test_name, args in test_configs
            ]
            for future in as_completed(futures):
                try:
                    test_name, status = future.result()
                    result[test_name] = status
                except Exception:
                    pass
        return result
    
    def test_target_ping(self, target):
        """Тестирует ping для одной цели"""
        ping_target = target.get('ping_target')
        if not ping_target and target.get('url'):
            # Для URL целей используем хост из URL для ping
            try:
                from urllib.parse import urlparse
                parsed = urlparse(target['url'])
                ping_target = parsed.hostname
                # Если hostname не определен, пробуем извлечь из URL напрямую
                if not ping_target:
                    url = target['url']
                    # Убираем протокол
                    if '://' in url:
                        url = url.split('://')[1]
                    # Берем первую часть до / или :
                    ping_target = url.split('/')[0].split(':')[0]
            except Exception:
                ping_target = None
        
        if not ping_target:
            return 'N/A'

        ping_cmd = (
            ['ping', '-c', str(_PING_COUNT), '-W', '2', ping_target]
            if self._linux_mode
            else ['ping', '-n', str(_PING_COUNT), '-w', '2000', ping_target]
        )
        ping_kwargs = {
            'capture_output': True,
            'timeout': _PING_TIMEOUT,
            'errors': 'replace',
        }
        if self._linux_mode:
            ping_kwargs['encoding'] = 'utf-8'
        else:
            ping_kwargs['encoding'] = 'cp866'
            ping_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

        try:
            ping_process = subprocess.run(ping_cmd, **ping_kwargs)
        except Exception:
            if self._linux_mode:
                return 'ERROR'
            try:
                ping_kwargs['encoding'] = 'cp1251'
                ping_process = subprocess.run(ping_cmd, **ping_kwargs)
            except Exception:
                return 'ERROR'

        if ping_process.returncode == 0:
            try:
                output = ping_process.stdout if isinstance(ping_process.stdout, str) else ping_process.stdout.decode(
                    'utf-8' if self._linux_mode else 'cp866', errors='replace'
                )
            except Exception:
                try:
                    output = ping_process.stdout if isinstance(ping_process.stdout, str) else ping_process.stdout.decode(
                        'utf-8' if self._linux_mode else 'cp1251', errors='replace'
                    )
                except Exception:
                    return 'OK'

            match = (
                re.search(r'rtt min/avg/max/(?:mdev|stddev)\s*=\s*[\d.]+/([\d.]+)/', output)
                or re.search(r'Среднее\s*=\s*(\d+)', output, re.IGNORECASE)
                or re.search(r'Average\s*=\s*(\d+)', output, re.IGNORECASE)
                or re.search(r'Среднее\s*=\s*(\d+)\s*мс', output, re.IGNORECASE)
                or re.search(r'Average\s*=\s*(\d+)\s*ms', output, re.IGNORECASE)
                or re.search(r'(?:Среднее|Average)\s*=\s*(\d+)', output, re.IGNORECASE)
            )
            if match:
                return f"{match.group(1)} ms"
            else:
                # Если не нашли среднее, но ping успешен, ищем любое время ответа
                time_match = (
                    re.search(r'время[<>=]\s*(\d+)\s*мс', output, re.IGNORECASE) or
                    re.search(r'time[<>=]\s*(\d+)\s*ms', output, re.IGNORECASE) or
                    re.search(r'время[<>=]\s*(\d+)', output, re.IGNORECASE) or
                    re.search(r'time[<>=]\s*(\d+)', output, re.IGNORECASE) or
                    re.search(r'Минимальное\s*=\s*(\d+)', output, re.IGNORECASE) or
                    re.search(r'Minimum\s*=\s*(\d+)', output, re.IGNORECASE) or
                    re.search(r'Максимальное\s*=\s*(\d+)', output, re.IGNORECASE) or
                    re.search(r'Maximum\s*=\s*(\d+)', output, re.IGNORECASE)
                )
                if time_match:
                    return f"{time_match.group(1)} ms"
                else:
                    return 'OK'
        else:
            return 'Timeout'
    
    def test_targets_ping_parallel(self, targets):
        """Выполняет ping для всех таргетов параллельно"""
        ping_results = {}
        
        # Фильтруем таргеты, для которых нужен ping
        targets_to_ping = []
        for target in targets:
            ping_target = target.get('ping_target')
            if not ping_target and target.get('url'):
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(target['url'])
                    ping_target = parsed.hostname
                    if not ping_target:
                        url = target['url']
                        if '://' in url:
                            url = url.split('://')[1]
                        ping_target = url.split('/')[0].split(':')[0]
                except Exception:
                    ping_target = None
            
            if ping_target:
                targets_to_ping.append((target['name'], target))
            else:
                # Если у таргета нет ping_target, добавляем N/A
                ping_results[target['name']] = 'N/A'
        
        if not targets_to_ping:
            return ping_results
        
        # Выполняем ping параллельно
        max_workers = min(len(targets_to_ping), _PING_MAX_WORKERS)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Создаем словарь future -> target_name для отслеживания
            future_to_target = {}
            for target_name, target in targets_to_ping:
                if not self.is_running:
                    break
                # Пауза между задачами ping
                while getattr(self, "is_paused", False) and self.is_running:
                    time.sleep(0.05)
                future = executor.submit(self.test_target_ping, target)
                future_to_target[future] = target_name
            
            # Собираем результаты по мере их готовности и сразу обновляем UI
            for future in as_completed(future_to_target):
                if not self.is_running:
                    break
                while getattr(self, "is_paused", False) and self.is_running:
                    time.sleep(0.05)
                target_name = future_to_target[future]
                try:
                    ping_result = future.result()
                    ping_results[target_name] = ping_result
                except Exception:
                    ping_results[target_name] = 'ERROR'
        
        return ping_results
    
    def _notify_parent_winws_state(self, running: bool) -> None:
        parent = self.parent()
        if parent is not None and hasattr(parent, '_on_test_winws_state_changed'):
            try:
                parent._on_test_winws_state_changed(running)
            except Exception:
                pass

    def stop_winws(self):
        """Останавливает runtime (winws / nfqws)."""
        try:
            parent = self.parent()
            parent_mgr = getattr(parent, "winws_manager", None) if parent is not None else None
            if self._linux_mode and self._linux_manager is not None:
                self._linux_manager.stop_all()
                bg_proc = getattr(self, '_linux_bg_proc', None)
                if bg_proc is not None:
                    try:
                        bg_proc.terminate()
                    except Exception:
                        pass
                    self._linux_bg_proc = None
            elif parent_mgr is not None:
                parent_mgr.stop_all()
            else:
                import psutil

                target = "nfqws" if self._linux_mode else "winws.exe"
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        name = (proc.info.get('name') or '').lower()
                        if name == target or (
                            self._linux_mode
                            and name == "nfqws"
                        ):
                            proc.kill()
                            continue
                        if self._linux_mode:
                            cmdline = " ".join(proc.info.get('cmdline') or []).lower()
                            if "nfqws" in cmdline:
                                proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
        except Exception:
            pass
        self._notify_parent_winws_state(False)
    
    @pyqtSlot(str)
    def update_status(self, text):
        # Перемещаем статус в заголовок окна: "Тестирование — <состояние>"
        try:
            title_base = tr('test_window_title', self.language)
        except Exception:
            title_base = 'Тестирование'
        self.setWindowTitle(f"{title_base} — {text}")
        if hasattr(self, "status_label"):
            self.status_label.setText(text)
    
    def on_auto_scroll_changed(self, state):
        """Старый обработчик checkbox (оставлен для совместимости, не используется)."""
        self.auto_scroll_enabled = (state != 0)

    def on_auto_scroll_toggled(self, checked: bool):
        """Обработчик пункта меню 'Вид -> Автоскролл'."""
        self.auto_scroll_enabled = checked
    
    def scroll_if_enabled(self):
        """Выполняет скролл вниз только если автоскролл включен"""
        if getattr(self, "auto_scroll_enabled", True):
            self.table.scrollToBottom()

    def _apply_progressbar_hidden_style(self):
        """Скрывает прогрессбар без синей полосы внизу окна."""
        try:
            self.progress.setProgressHidden(True)
            self.progress.setStyleSheet("""
                QProgressBar {
                    background-color: transparent;
                    border: none;
                }
                QProgressBar::chunk {
                    background-color: transparent;
                }
            """)
        except Exception:
            pass

    def _apply_progressbar_visible_style(self):
        """Возвращает прогрессбар к видимому стилю."""
        try:
            self.progress.setProgressHidden(False)
            self.progress.setStyleSheet(theme.progress_bar_visible_style())
        except Exception:
            pass
    
    @pyqtSlot(str)
    def add_strategy_header(self, bat_file):
        """Добавляет заголовок стратегии в таблицу"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Заголовок стратегии (без расширения .bat)
        strategy_name = os.path.splitext(bat_file)[0]
        
        # Создаем элемент для названия стратегии в первой колонке
        header_item = QTableWidgetItem(strategy_name)
        font = header_item.font()
        font.setBold(True)
        header_item.setFont(font)
        self.table.setItem(row, 0, header_item)
        
        # Остальные колонки пустые для заголовка
        self.table.setItem(row, 1, QTableWidgetItem(''))
        self.table.setItem(row, 2, QTableWidgetItem(''))
        self.table.setItem(row, 3, QTableWidgetItem(''))
        
        # Автоскролл вниз (если включен)
        self.scroll_if_enabled()
    
    @pyqtSlot(str, dict)
    def add_result_to_table(self, target_name, result):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Форматируем имя цели (убираем пробелы для компактности, как в примере)
        # Пример: "Discord Gateway" -> "DiscordGateway", "Cloudflare DNS 1.1.1.1" -> "CloudflareDNS1111"
        display_name = target_name.replace(' ', '').replace('.', '')
        
        # Добавляем отступ для подчиненности под стратегией
        display_name = '  ' + display_name
        
        # Первая колонка пустая (название стратегии уже в заголовке)
        self.table.setItem(row, 0, QTableWidgetItem(''))
        # Вторая колонка - название цели
        self.table.setItem(row, 1, QTableWidgetItem(display_name))
        
        # Форматируем результаты: HTTP/TLS в отдельную колонку, Ping в отдельную
        http_val = result.get('http', 'N/A')
        tls12_val = result.get('tls12', 'N/A')
        tls13_val = result.get('tls13', 'N/A')
        ping_val = result.get('ping', 'N/A')
        
        # Формируем строку HTTP/TLS результатов
        http_tls_parts = []
        if http_val != 'N/A' or tls12_val != 'N/A' or tls13_val != 'N/A':
            # Форматируем с правильным выравниванием (как в примере: HTTP:OK    TLS1.2:OK    TLS1.3:OK)
            http_text = f"HTTP:{http_val}"
            tls12_text = f"TLS1.2:{tls12_val}"
            tls13_text = f"TLS1.3:{tls13_val}"
            # Добавляем пробелы для выравнивания
            http_tls_parts.append(f"{http_text:<12} {tls12_text:<12} {tls13_text:<12}")
        
        http_tls_text = ' '.join(http_tls_parts) if http_tls_parts else 'N/A'
        http_tls_item = QTableWidgetItem(http_tls_text)
        # Tooltip с подробной информацией
        http_tls_item.setToolTip(
            f"HTTP: {http_val}\nTLS 1.2: {tls12_val}\nTLS 1.3: {tls13_val}"
        )
        self.table.setItem(row, 2, http_tls_item)
        
        # Формируем строку Ping результатов
        ping_text = ping_val if ping_val != 'N/A' else 'N/A'
        if ping_text != 'N/A' and ping_text:
            ping_text = f"{ping_text}"
        ping_item = QTableWidgetItem(ping_text)
        ping_item.setToolTip(f"Ping: {ping_val}")
        self.table.setItem(row, 3, ping_item)
        
        # Цветовая индикация для HTTP/TLS колонки
        item = self.table.item(row, 2)
        if item:
            text = item.text()
            # Определяем общий статус по результатам
            has_error = 'ERROR' in text
            has_ok = 'OK' in text
            has_unsup = 'UNSUP' in text
            
            if has_error:
                item.setForeground(QColor(255, 0, 0))  # Красный
            elif has_ok and not has_error:
                item.setForeground(QColor(0, 128, 0))  # Зеленый
            elif has_unsup:
                item.setForeground(QColor(255, 165, 0))  # Оранжевый
            else:
                item.setForeground(QColor(128, 128, 128))  # Серый
        
        # Цветовая индикация для Ping колонки
        ping_item = self.table.item(row, 3)
        if ping_item:
            ping_text = ping_item.text()
            if ping_text == 'N/A' or ping_text == 'Timeout' or ping_text == 'ERROR':
                ping_item.setForeground(QColor(255, 0, 0))  # Красный
            elif 'ms' in ping_text:
                ping_item.setForeground(QColor(0, 128, 0))  # Зеленый
            else:
                ping_item.setForeground(QColor(128, 128, 128))  # Серый
        
        # Автоскролл вниз при добавлении новой строки (если включен)
        self.scroll_if_enabled()
    
    @pyqtSlot(str, str)
    def update_result_ping(self, target_name, ping_result):
        """Обновляет ping результат в таблице для указанного таргета"""
        # Форматируем имя цели так же, как в add_result_to_table
        display_name = target_name.replace(' ', '').replace('.', '')
        display_name = '  ' + display_name
        
        # Ищем все строки с этим таргетом (может быть несколько, если тестируется несколько стратегий)
        found = False
        for row in range(self.table.rowCount()):
            target_item = self.table.item(row, 1)  # Колонка Target
            if target_item:
                item_text = target_item.text().strip()
                # Сравниваем без учета отступа (может быть разное количество пробелов)
                if item_text == display_name.strip() or item_text == target_name.replace(' ', '').replace('.', ''):
                    # Обновляем колонку Ping (индекс 3)
                    ping_item = QTableWidgetItem(ping_result)
                    # Применяем цветовую индикацию для ping
                    if ping_result != 'N/A' and ping_result != 'ERROR' and ping_result != 'Timeout' and 'ms' in str(ping_result):
                        ping_item.setForeground(QColor(0, 128, 0))  # Зеленый для успешного ping
                    elif ping_result == 'ERROR' or ping_result == 'Timeout':
                        ping_item.setForeground(QColor(255, 0, 0))  # Красный для ошибки
                    else:
                        ping_item.setForeground(QColor(128, 128, 128))  # Серый
                    self.table.setItem(row, 3, ping_item)
                    found = True
                    # Принудительно обновляем таблицу
                    self.table.viewport().update()
                    # Автоскролл вниз (если включен)
                    self.scroll_if_enabled()
        
        # Если не нашли по отформатированному имени, пробуем найти по оригинальному имени
        if not found:
            for row in range(self.table.rowCount()):
                target_item = self.table.item(row, 1)  # Колонка Target
                if target_item:
                    item_text = target_item.text().strip()
                    # Пробуем найти по частичному совпадению (без учета форматирования)
                    if target_name.replace(' ', '').replace('.', '') in item_text.replace(' ', '').replace('.', ''):
                        ping_item = QTableWidgetItem(ping_result)
                        if ping_result != 'N/A' and ping_result != 'ERROR' and ping_result != 'Timeout' and 'ms' in str(ping_result):
                            ping_item.setForeground(QColor(0, 128, 0))
                        elif ping_result == 'ERROR' or ping_result == 'Timeout':
                            ping_item.setForeground(QColor(255, 0, 0))
                        else:
                            ping_item.setForeground(QColor(128, 128, 128))
                        self.table.setItem(row, 3, ping_item)
                        # Принудительно обновляем таблицу и обрабатываем события
                        self.table.viewport().update()
                        self.scroll_if_enabled()
                        QApplication.processEvents()
                        break
    
    @pyqtSlot()
    def add_separator(self):
        """Добавляет пустую строку-разделитель между группами тестов разных .bat файлов"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(''))
        self.table.setItem(row, 1, QTableWidgetItem(''))
        self.table.setItem(row, 2, QTableWidgetItem(''))
        self.table.setItem(row, 3, QTableWidgetItem(''))
        
        # Автоскролл вниз (если включен)
        self.scroll_if_enabled()
    
    @pyqtSlot(int)
    def update_progress(self, value):
        self.progress.setValue(value)
    
    @pyqtSlot(str, int, int, int, int, int)
    def update_strategy_stats(self, strategy_name, http_ok, tls12_ok, tls13_ok, ping_ok, total_targets):
        """Обновляет статистику стратегии из главного потока"""
        self.strategy_stats[strategy_name] = {
            'http_ok': http_ok,
            'tls12_ok': tls12_ok,
            'tls13_ok': tls13_ok,
            'ping_ok': ping_ok,
            'total_targets': total_targets
        }
    
    @pyqtSlot()
    def update_best_strategies(self):
        """Обновляет таблицу лучших стратегий на основе текущей статистики
        Классифицирует стратегии по качеству работы:
        - Зеленые: наилучшие (рабочие) стратегии (>70% успеха)
        - Желтые: средние стратегии (30-70% успеха)
        - Красные: нерабочие стратегии (<30% успеха)
        """
        # Очищаем таблицу
        self.best_table.setRowCount(0)
        
        # Подготавливаем данные стратегий с расчетом процента успеха
        strategies_data = []
        for strategy_name, stats in self.strategy_stats.items():
            total_targets = stats['total_targets']
            if total_targets == 0:
                continue
            
            # Считаем общее количество успешных тестов
            # HTTP OK + TLS1.2 OK + TLS1.3 OK + Ping OK
            total_tests = total_targets * 4  # HTTP + TLS1.2 + TLS1.3 + Ping для каждого таргета
            total_ok = stats['http_ok'] + stats['tls12_ok'] + stats['tls13_ok'] + stats['ping_ok']
            
            # Рассчитываем процент успеха
            success_percent = (total_ok / total_tests * 100) if total_tests > 0 else 0
            
            strategies_data.append({
                'name': strategy_name,
                'http_ok': stats['http_ok'],
                'tls_ok': stats['tls12_ok'] + stats['tls13_ok'],
                'ping_ok': stats['ping_ok'],
                'total': total_targets,
                'success_percent': success_percent
            })
        
        # Сортируем по проценту успеха (от лучших к худшим)
        strategies_data.sort(key=lambda x: x['success_percent'], reverse=True)
        
        # Добавляем все стратегии в таблицу с цветовой классификацией
        for strategy in strategies_data:
            row = self.best_table.rowCount()
            self.best_table.insertRow(row)
            
            # Название стратегии
            name_item = QTableWidgetItem(strategy['name'])
            self.best_table.setItem(row, 0, name_item)
            
            # HTTP OK
            http_item = QTableWidgetItem(f"{strategy['http_ok']}/{strategy['total']}")
            self.best_table.setItem(row, 1, http_item)
            
            # TLS OK (TLS1.2 + TLS1.3)
            tls_item = QTableWidgetItem(f"{strategy['tls_ok']}/{strategy['total'] * 2}")
            self.best_table.setItem(row, 2, tls_item)
            
            # Ping OK
            ping_item = QTableWidgetItem(f"{strategy['ping_ok']}/{strategy['total']}")
            self.best_table.setItem(row, 3, ping_item)
            
            # Цветовая классификация по проценту успеха
            success_percent = strategy['success_percent']
            if success_percent >= 70:
                # Зеленый - наилучшие (рабочие) стратегии
                color = QColor(0, 200, 0)  # Яркий зеленый
            elif success_percent >= 30:
                # Желтый - средние стратегии
                color = QColor(255, 200, 0)  # Желтый
            else:
                # Красный - нерабочие стратегии
                color = QColor(255, 0, 0)  # Красный
            
            # Применяем цвет ко всем ячейкам строки
            for col in range(4):
                item = self.best_table.item(row, col)
                if item:
                    item.setForeground(color)
        
        # Автоскролл вверх
        self.best_table.scrollToTop()
    
    @pyqtSlot()
    def tests_finished(self):
        self.is_running = False
        self.is_paused = False
        self._update_transport_buttons()
        self._apply_progressbar_hidden_style()
        # Восстанавливаем заголовок окна
        try:
            title_base = tr('test_window_title', self.language)
        except Exception:
            title_base = 'Тестирование'
        status_key = 'test_status_stopping' if getattr(self, '_user_stopped_tests', False) else 'test_status_finished'
        status_text = tr(status_key, self.language)
        self.setWindowTitle(f"{title_base} — {status_text}")
        if hasattr(self, "status_label"):
            self.status_label.setText(status_text)
        self.progress.setValue(self.progress.maximum())
        self.stop_winws()
        
        # Финальное обновление таблицы лучших стратегий
        self.update_best_strategies()
        self.tests_completed.emit()
    
    def load_targets_file(self):
        """Загружает содержимое файла targets.txt в редактор"""
        try:
            if os.path.exists(self.targets_file_path):
                with open(self.targets_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Блокируем сигнал textChanged, чтобы не устанавливать флаг изменений
                self.targets_editor.blockSignals(True)
                self.targets_editor.setPlainText(content)
                self.targets_editor.blockSignals(False)
                # Останавливаем таймер автосохранения при загрузке файла
                self.save_timer.stop()
            else:
                # Если файл не существует, создаем его с базовым содержимым
                default_content = """# targets.txt - endpoint list for zapret.ps1 tests

#

# Format:

#   KeyName = "https://host..."   -> Runs HTTP/TLS checks + ping

#   KeyName = "PING:1.2.3.4"       -> Ping only

#

# Keys must be a single word (letters/digits/underscore), because the

# script parses them as simple identifiers. You can add or remove lines.

### Discord

DiscordMain           = "https://discord.com"

DiscordGateway        = "https://gateway.discord.gg"

DiscordCDN            = "https://cdn.discordapp.com"

DiscordUpdates        = "https://updates.discord.com"

### YouTube

YouTubeWeb            = "https://www.youtube.com"

YouTubeShort          = "https://youtu.be"

YouTubeImage          = "https://i.ytimg.com"

YouTubeVideoRedirect  = "https://redirector.googlevideo.com"

### Google

GoogleMain            = "https://www.google.com"

GoogleGstatic         = "https://www.gstatic.com"

### Cloudflare

CloudflareWeb         = "https://www.cloudflare.com"

CloudflareCDN         = "https://cdnjs.cloudflare.com"

### Public DNS (PING-only)

CloudflareDNS1111     = "PING:1.1.1.1"

CloudflareDNS1001     = "PING:1.0.0.1"

GoogleDNS8888         = "PING:8.8.8.8"

GoogleDNS8844         = "PING:8.8.4.4"

Quad9DNS9999          = "PING:9.9.9.9"
"""
                # Создаем директорию, если её нет
                os.makedirs(os.path.dirname(self.targets_file_path), exist_ok=True)
                with open(self.targets_file_path, 'w', encoding='utf-8') as f:
                    f.write(default_content)
                self.targets_editor.blockSignals(True)
                self.targets_editor.setPlainText(default_content)
                self.targets_editor.blockSignals(False)
                # Останавливаем таймер автосохранения при загрузке файла
                self.save_timer.stop()
                # Добавляем файл в watcher
                if os.path.exists(self.targets_file_path):
                    self.file_watcher.addPath(self.targets_file_path)
        except Exception as e:
            QMessageBox.warning(self, tr('test_error_title', self.language), 
                              f"{tr('targets_error_loading', self.language)}: {str(e)}")
    
    def auto_save_targets_file(self):
        """Автоматически сохраняет содержимое редактора в файл targets.txt"""
        if self.is_saving:
            return  # Предотвращаем рекурсивные вызовы
        
        try:
            self.is_saving = True
            content = self.targets_editor.toPlainText()
            
            # Временно отключаем watcher, чтобы не сработало событие изменения файла
            if os.path.exists(self.targets_file_path):
                self.file_watcher.removePath(self.targets_file_path)
            
            # Создаем директорию, если её нет
            os.makedirs(os.path.dirname(self.targets_file_path), exist_ok=True)
            
            # Сохраняем файл
            with open(self.targets_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Включаем watcher обратно
            if os.path.exists(self.targets_file_path):
                self.file_watcher.addPath(self.targets_file_path)
            
            # Перезагружаем цели для тестирования
            self.init_targets()
        except Exception as e:
            # В случае ошибки просто выводим в консоль (не показываем диалог, чтобы не мешать)
            print(f"Error auto-saving targets file: {e}")
            # Включаем watcher обратно в случае ошибки
            if os.path.exists(self.targets_file_path):
                self.file_watcher.addPath(self.targets_file_path)
        finally:
            self.is_saving = False
    
    def on_targets_text_changed(self):
        """Обработчик изменения текста в редакторе - запускает таймер для автоматического сохранения"""
        # Перезапускаем таймер при каждом изменении (debounce)
        # Сохранение произойдет через 1 секунду после последнего изменения
        self.save_timer.stop()
        self.save_timer.start(1000)  # 1 секунда задержки
    
    def on_targets_file_changed_externally(self, path):
        """Обработчик изменения файла targets.txt извне через QFileSystemWatcher"""
        if path == self.targets_file_path:
            # Если мы сами сохраняем файл, игнорируем событие
            if self.is_saving:
                return
            
            # Останавливаем таймер автосохранения, так как файл уже изменен извне
            self.save_timer.stop()
            
            # Автоматически перезагружаем файл из диска
            self.load_targets_file()
            # Перезагружаем цели для тестирования
            self.init_targets()
            
            # Переподключаем watcher (файл мог быть удален и создан заново)
            if os.path.exists(self.targets_file_path):
                if self.targets_file_path not in self.file_watcher.files():
                    self.file_watcher.addPath(self.targets_file_path)
    
    def export_table_data(self, table, table_name, format_type):
        """Экспортирует данные таблицы в указанном формате"""
        if table.rowCount() == 0:
            QMessageBox.information(self, tr('test_error_title', self.language), 
                                   tr('export_table_empty', self.language))
            return
        
        # Определяем расширение файла и фильтр
        if format_type == "csv":
            file_filter = "CSV Files (*.csv);;All Files (*)"
            default_ext = ".csv"
        elif format_type == "json":
            file_filter = "JSON Files (*.json);;All Files (*)"
            default_ext = ".json"
        else:  # txt
            file_filter = "Text Files (*.txt);;All Files (*)"
            default_ext = ".txt"
        
        # Получаем заголовки колонок
        headers = []
        for col in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(col)
            if header_item:
                headers.append(header_item.text())
            else:
                headers.append(tr('export_column', self.language).format(col + 1))
        
        # Получаем данные таблицы
        data = []
        for row in range(table.rowCount()):
            row_data = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item:
                    row_data.append(item.text())
                else:
                    row_data.append("")
            data.append(row_data)
        
        # Показываем диалог сохранения файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{table_name}_{timestamp}{default_ext}"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr('export_menu_title', self.language),
            default_filename,
            file_filter
        )
        
        if not file_path:
            return  # Пользователь отменил
        
        try:
            if format_type == "csv":
                self._export_to_csv(file_path, headers, data)
            elif format_type == "json":
                self._export_to_json(file_path, headers, data)
            else:  # txt
                self._export_to_txt(file_path, headers, data)
            
            QMessageBox.information(self, tr('export_menu_title', self.language), tr('export_success', self.language).format(file_path))
        except Exception as e:
            QMessageBox.critical(self, tr('export_error_title', self.language), tr('export_error', self.language).format(str(e)))
    
    def _export_to_csv(self, file_path, headers, data):
        """Экспортирует данные в CSV формат"""
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(headers)
            writer.writerows(data)
    
    def _export_to_json(self, file_path, headers, data):
        """Экспортирует данные в JSON формат"""
        json_data = {
            "export_date": datetime.now().isoformat(),
            "headers": headers,
            "rows": []
        }
        
        for row in data:
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ""
            json_data["rows"].append(row_dict)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    def _export_to_txt(self, file_path, headers, data):
        """Экспортирует данные в TXT формат (табличный)"""
        with open(file_path, 'w', encoding='utf-8') as f:
            # Записываем заголовки
            f.write(" | ".join(headers) + "\n")
            f.write("-" * (sum(len(h) for h in headers) + len(headers) * 3) + "\n")
            
            # Записываем данные
            for row in data:
                # Форматируем каждую ячейку с фиксированной шириной
                formatted_row = []
                for i, cell in enumerate(row):
                    # Обрезаем или дополняем до ширины заголовка
                    header_width = len(headers[i]) if i < len(headers) else 20
                    cell_str = str(cell)[:header_width].ljust(header_width)
                    formatted_row.append(cell_str)
                f.write(" | ".join(formatted_row) + "\n")

