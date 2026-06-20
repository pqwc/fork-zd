"""strategy_run_mixin methods for MainWindow."""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from src.shared.i18n.translator import tr, tr_platform
from src.shared.lib.path_utils import get_winws_path
from src.shared.lib.open_path import open_path
from src.shared.ui.message_box_utils import configure_message_box
from src.platform import is_linux, linux_runtime_configured, get_runtime_backend
from ..workers import StartWorker, StopWorker, LinuxStartWorker, LinuxStopWorker
import os
import subprocess
import psutil
import time


class StrategyRunMixin:
    def _runtime_process_name(self) -> str:
        return "nfqws" if is_linux() else "winws.exe"

    def _get_winws_start_timeout(self) -> float:
        try:
            timeout = int(self.settings.get('winws_start_timeout_sec', 15) or 15)
        except (TypeError, ValueError):
            timeout = 15
        return float(max(5, min(timeout, 120)))

    def _is_winws_process_running(self) -> bool:
        return self._runtime_process_active()

    def _runtime_process_active(self) -> bool:
        """Фактическое наличие nfqws/winws в процессах (без systemd-only «active»)."""
        stored = self._get_stored_winws_pid()
        mgr = getattr(self, "winws_manager", None)
        if mgr is not None and hasattr(mgr, "is_running"):
            return bool(mgr.is_running(stored))
        return self._get_running_winws_process() is not None

    def _stop_worker_active(self) -> bool:
        worker = getattr(self, "_stop_worker", None)
        return worker is not None and worker.isRunning()

    def _start_worker_active(self) -> bool:
        worker = getattr(self, "_start_worker", None)
        return worker is not None and worker.isRunning()

    def _may_sync_runtime_from_process(self) -> bool:
        if self.user_stopped:
            return False
        if self._stop_worker_active():
            return False
        return True

    def _ui_shows_running(self) -> bool:
        """UI «запущено»: процесс жив или идёт stop worker."""
        if self._stop_worker_active():
            return True
        return self.is_running or self._runtime_process_active()

    def _action_should_stop(self) -> bool:
        """Действие кнопки — остановить (не во время start worker)."""
        if self._stop_worker_active():
            return True
        if self._start_worker_active():
            return False
        return self.is_running or self._runtime_process_active()

    def _runtime_locks_strategy_list(self) -> bool:
        return (
            self._action_should_stop()
            or self._start_worker_active()
            or self._stop_worker_active()
        )

    def _is_strategy_runtime_active(self, strategy_name: str | None) -> bool:
        if not strategy_name:
            return False
        if not self._runtime_process_active():
            return False
        if self.is_running and self.running_strategy == strategy_name:
            return True
        detected = self._detect_running_strategy()
        if detected == strategy_name:
            return True
        if is_linux():
            mgr = getattr(self, "winws_manager", None)
            if mgr is not None and hasattr(mgr, "get_configured_strategy"):
                configured = mgr.get_configured_strategy()
                if configured == strategy_name:
                    return True
        return False

    def _sync_runtime_state_from_process(self) -> None:
        """Подтягивает is_running/running_strategy по фактическому состоянию runtime."""
        if not self._may_sync_runtime_from_process():
            return
        if not self._runtime_process_active():
            return
        detected = self._detect_running_strategy()
        if detected:
            self.running_strategy = detected
        elif not self.running_strategy:
            last = self.settings.get("last_strategy", "")
            if last:
                self.running_strategy = last
        self.is_running = True
        self.bat_start_time = None
        self._capture_running_winws_pid()
        if detected:
            index = self._find_strategy_index_by_data(detected)
            if index >= 0:
                self.strategy_list.setCurrentRow(index)

    def _get_stored_winws_pid(self) -> int | None:
        try:
            pid = self.settings.get("running_winws_pid")
            if pid is None:
                pid = self.config.get_setting("running_winws_pid", 0)
            pid = int(pid or 0)
            return pid if pid > 0 else None
        except (TypeError, ValueError):
            return None

    def _persist_running_winws_pid(self, pid: int | None) -> None:
        value = int(pid) if pid else 0
        self._persist_setting('running_winws_pid', value, silent=True)

    def _clear_persisted_running_winws(self) -> None:
        self._persist_running_winws_pid(None)
        self._last_shown_winws_pid = None

    def _is_own_winws_session(self) -> bool:
        if getattr(self, "_started_winws_this_session", False):
            return True
        stored = self._get_stored_winws_pid()
        if not stored:
            return False
        proc = self._get_running_winws_process()
        return proc is not None and proc.pid == stored

    def _capture_running_winws_pid(self) -> int | None:
        proc = self._get_running_winws_process()
        if proc is None:
            return None
        try:
            pid = proc.pid
        except Exception:
            return None
        if pid:
            self._persist_running_winws_pid(pid)
        return pid

    def _process_matches_runtime(self, proc) -> bool:
        mgr = getattr(self, "winws_manager", None)
        if mgr is not None and hasattr(mgr, "_is_nfqws_process"):
            return bool(mgr._is_nfqws_process(proc))
        try:
            return (proc.name() or "").lower() == self._runtime_process_name().lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False

    def _get_display_winws_pid(self) -> int | None:
        _v, live_pid, _root = self._get_running_winws_version_and_pid()
        if live_pid:
            return live_pid
        if getattr(self, "is_running", False):
            stored = self._get_stored_winws_pid()
            if stored:
                try:
                    proc = psutil.Process(stored)
                    if proc.is_running() and self._process_matches_runtime(proc):
                        return stored
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        return None

    def _sync_winws_pid_ui(self) -> None:
        if not getattr(self, "is_running", False):
            return
        pid = self._capture_running_winws_pid()
        if not pid or pid == getattr(self, "_last_shown_winws_pid", None):
            return
        self._last_shown_winws_pid = pid
        if hasattr(self, "_refresh_strategy_display"):
            self._refresh_strategy_display()
        if hasattr(self, "_update_strategy_detail_panel"):
            self._update_strategy_detail_panel()

    def _update_window_title_with_strategy(self):
        """Обновляет заголовок окна вида 'ZapretDesktop — <стратегия>' если стратегия запущена."""
        base_title = "ZapretDesktop"
        if self.is_running and self.running_strategy:
            # Пытаемся вытащить текст из ComboBox (там уже есть версия и pid)
            idx = self._find_strategy_index_by_data(self.running_strategy)
            if idx >= 0:
                item = self.strategy_list.item(idx)
                text = item.text() if item else self.running_strategy
                self.setWindowTitle(f"{base_title} — {text}")
                return
            # Fallback: только имя стратегии
            self.setWindowTitle(f"{base_title} — {self.running_strategy}")
        else:
            self.setWindowTitle(base_title)

    def _sync_run_state_ui(self):
        """Синхронизирует кнопку «Запустить/Остановить» и ComboBox с is_running и состоянием воркеров."""
        lang = self.settings.get('language', 'ru')
        start_busy = getattr(self, '_start_worker', None) and self._start_worker.isRunning()
        stop_busy = getattr(self, '_stop_worker', None) and self._stop_worker.isRunning()
        busy = start_busy or stop_busy
        test_active = getattr(self, '_strategy_test_active', False)
        if test_active:
            test_live = getattr(self, '_test_winws_live', False)
            if hasattr(self, 'action_button') and self.action_button:
                self.action_button.setText(
                    tr('button_stop', lang) if test_live else tr('button_start', lang)
                )
                self.action_button.setEnabled(False)
                self.action_button.setToolTip(tr('home_strategy_test_active', lang))
            if hasattr(self, 'strategy_list') and self.strategy_list:
                self.strategy_list.setEnabled(False)
            if hasattr(self, 'strategy_search') and self.strategy_search:
                self.strategy_search.setEnabled(False)
            if hasattr(self, '_refresh_primary_action_style'):
                self._refresh_primary_action_style()
            if hasattr(self, '_apply_strategy_list_visual_state'):
                self._apply_strategy_list_visual_state()
            if hasattr(self, '_apply_home_action_icons'):
                self._apply_home_action_icons()
            return
        if hasattr(self, 'action_button') and self.action_button:
            self.action_button.setToolTip('')
            if start_busy:
                self.action_button.setText(tr('button_starting', lang))
                self.action_button.setEnabled(False)
            elif stop_busy or self._action_should_stop():
                self.action_button.setText(tr('button_stop', lang))
                self.action_button.setEnabled(not stop_busy)
            else:
                self.action_button.setText(tr('button_start', lang))
                self.action_button.setEnabled(True)
        if hasattr(self, '_refresh_primary_action_style'):
            self._refresh_primary_action_style()
        if hasattr(self, 'strategy_list') and self.strategy_list:
            from PyQt6.QtWidgets import QAbstractItemView

            running_ui = self._ui_shows_running()
            if running_ui:
                self.strategy_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
            else:
                self.strategy_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            self.strategy_list.setEnabled(not busy)
        if hasattr(self, 'strategy_search') and self.strategy_search:
            running_ui = self._ui_shows_running()
            self.strategy_search.setEnabled(not running_ui and not busy)
        if hasattr(self, '_apply_strategy_list_visual_state'):
            self._apply_strategy_list_visual_state()
        if self._ui_shows_running():
            self._lock_strategy_list_to_running()
        if hasattr(self, '_apply_home_action_icons'):
            self._apply_home_action_icons()

    def _show_menu_progress_bar(self):
        """Показывает анимированную полоску прогресса под меню, не сдвигая остальные виджеты."""
        if hasattr(self, 'menu_progress_bar') and self.menu_progress_bar:
            if hasattr(self.menu_progress_bar, 'setProgressHidden'):
                self.menu_progress_bar.setProgressHidden(False)
            if hasattr(self.menu_progress_bar, 'setIndeterminate'):
                self.menu_progress_bar.setIndeterminate(True)
            elif hasattr(self.menu_progress_bar, 'setMaximum'):
                self.menu_progress_bar.setMaximum(0)
            self.menu_progress_bar.show()
            self.menu_progress_bar.update()
            QApplication.processEvents()

    def _hide_menu_progress_bar(self):
        """Скрывает полоску прогресса без сдвига layout."""
        if hasattr(self, 'menu_progress_bar') and self.menu_progress_bar:
            if hasattr(self.menu_progress_bar, 'setIndeterminate'):
                self.menu_progress_bar.setIndeterminate(False)
            if hasattr(self.menu_progress_bar, 'setProgressHidden'):
                self.menu_progress_bar.setProgressHidden(True)
            elif hasattr(self.menu_progress_bar, 'setMaximum'):
                self.menu_progress_bar.setMaximum(100)
                self.menu_progress_bar.setValue(0)
            self.menu_progress_bar.update()

    def restore_last_strategy(self):
        """Восстанавливает последнюю выбранную стратегию.
        Если winws.exe уже запущен (программа перезапущена), пытается определить
        запущенную стратегию и выбрать её в ComboBox."""
        strategy_to_select = None
        winws_running = self._runtime_process_active()
        if winws_running:
            proc = self._get_running_winws_process()
            detected = self._detect_running_strategy(proc)
            stored = self._get_stored_winws_pid()
            if proc and stored and proc.pid == stored:
                self.is_running = True
                self._started_winws_this_session = True
                strategy_to_select = detected or self.settings.get("last_strategy", "")
                if strategy_to_select:
                    self.running_strategy = strategy_to_select
            elif detected:
                strategy_to_select = detected
                self.is_running = True
                self.running_strategy = detected
                self._started_winws_this_session = False
            else:
                self.is_running = True
                self._started_winws_this_session = False
                strategy_to_select = self.settings.get("last_strategy", "")
                if strategy_to_select:
                    self.running_strategy = strategy_to_select
            self._hide_menu_progress_bar()
        if not strategy_to_select:
            strategy_to_select = self.settings.get('last_strategy', '')
        if strategy_to_select:
            index = self._find_strategy_index_by_data(strategy_to_select)
            if index >= 0:
                self.strategy_list.setCurrentRow(index)
                if winws_running:
                    # Если стратегия уже запущена при старте приложения — обновляем combo (в т.ч. pid) и заголовок
                    self._refresh_strategy_display()
                    self._update_window_title_with_strategy()
                    if hasattr(self, "_sync_external_winws_console"):
                        self._sync_external_winws_console()
                    if hasattr(self, "_update_strategy_detail_panel"):
                        self._update_strategy_detail_panel()
                # Автозапуск стратегии — только через window.auto_start_last_strategy() (+1 с)
        # Всегда синхронизируем кнопку и ComboBox с is_running после восстановления
        self._sync_run_state_ui()

    def auto_start_last_strategy(self):
        """Автоматически запускает последнюю сохраненную стратегию при запуске программы
        Запускает стратегию только если last_strategy явно указан в конфиге и найден в списке.
        Полоска прогресса при автозапуске не показывается (скрыта по завершении в _on_start_worker_done)."""
        if getattr(self, "_startup_update_in_progress", False) or getattr(self, "_linux_deps_worker", None):
            retries = getattr(self, "_auto_start_update_wait_count", 0)
            if retries >= 120:
                return
            self._auto_start_update_wait_count = retries + 1
            QTimer.singleShot(500, self.auto_start_last_strategy)
            return
        self._auto_start_update_wait_count = 0
        if self.is_running or self._is_winws_process_running():
            return

        last_strategy = self.settings.get('last_strategy', '')
        
        # Если last_strategy не указан (пустой), не запускаем ничего
        # Пользователь должен сам выбрать стратегию при первом запуске
        if not last_strategy:
            return
        
        # Пытаемся найти указанную стратегию в списке
        index = self._find_strategy_index_by_data(last_strategy)
        if index < 0:
            return

        self.strategy_list.setCurrentRow(index)
        self._is_auto_start = True  # start_bat_file не покажет прогресс; _on_start_worker_done скроет и сбросит флаг
        if not self.is_running:
            self.start_bat_file()

    def restart_strategy(self):
        """Перезапускает стратегию, которая была запущена ранее"""
        # ВАЖНО: Проверяем настройку автоперезапуска ПЕРВЫМ делом
        # Если настройка выключена, не перезапускаем
        if not self.settings.get('auto_restart_strategy', False):
            return
        
        # Не перезапускаем, если пользователь явно остановил процесс или уже идет перезапуск
        if not self.running_strategy or self.is_restarting or self.user_stopped:
            return
        
        # Устанавливаем флаг перезапуска
        self.is_restarting = True
        
        # Проверяем, что стратегия все еще существует
        index = self._find_strategy_index_by_data(self.running_strategy)
        if index < 0:
            # Стратегия больше не существует
            self.running_strategy = None
            self.is_restarting = False
            return
        
        # Проверяем еще раз перед запуском (на случай, если пользователь нажал Stop во время задержки)
        if self.user_stopped:
            self.is_restarting = False
            return
        
        # Выбираем стратегию в ComboBox
        self.strategy_list.setCurrentRow(index)
        
        # Запускаем стратегию
        if not self.is_running:
            self.start_bat_file()
        
        # Сбрасываем флаг перезапуска через небольшую задержку
        QTimer.singleShot(2000, lambda: setattr(self, 'is_restarting', False))

    def on_strategy_changed(self, strategy_name):
        """Обработчик изменения выбранной стратегии."""
        if not isinstance(strategy_name, str) or not strategy_name or strategy_name == "__external_winws__":
            return
        self._persist_setting('last_strategy', strategy_name, silent=True)

    def toggle_action(self):
        """Переключает состояние между Запустить и Остановить"""
        if getattr(self, '_strategy_test_active', False):
            return
        lang = self.settings.get('language', 'ru')
        if self._start_worker_active():
            return
        if not self._action_should_stop():
            self.user_stopped = False  # Сбрасываем флаг при запуске
            self._pending_stop_after_start = False
            self.start_bat_file()  # асинхронно, заголовок обновится в _on_start_worker_done
        else:
            # Останавливаем процесс winws.exe
            # Показываем полоску прогресса до исчезновения winws.exe
            self._show_menu_progress_bar()
            # ВАЖНО: Устанавливаем флаги ДО остановки процесса, чтобы check_winws_process() их увидел
            self.user_stopped = True  # Устанавливаем флаг явной остановки пользователем
            self.running_strategy = None  # Очищаем название стратегии при явной остановке
            self.is_running = False
            self._external_winws_logged = False
            self._stop_incomplete_logged = False
            if hasattr(self, '_append_strategy_console'):
                self._append_strategy_console(tr_platform('home_console_stop', lang))
            if hasattr(self, '_stop_bat_output_reader'):
                self._stop_bat_output_reader()
            self._pending_app_restarts = []
            self.is_restarting = False  # Сбрасываем флаг перезапуска
            self._started_winws_this_session = False
            self._clear_persisted_running_winws()
            # Останавливаем процесс в фоне (обновление UI в _on_stop_worker_done)
            self.stop_winws_process()

    def _start_linux_strategy(self, current_strategy: str, lang: str) -> None:
        """Запуск стратегии через service.sh (Linux)."""
        if not linux_runtime_configured():
            self._is_auto_start = False
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('linux_runtime_not_configured', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return

        if not current_strategy or current_strategy in (
            tr('msg_no_bat_files', lang),
            tr('msg_winws_not_found', lang),
            tr('linux_runtime_not_configured', lang),
        ):
            self._is_auto_start = False
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_no_strategy_selected', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return

        from src.platform import get_runtime_backend

        allowed = {s.name for s in get_runtime_backend().list_strategies()}
        if current_strategy not in allowed:
            self._is_auto_start = False
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_bat_not_in_list', lang).format(current_strategy))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return

        bat_filename = f"{current_strategy}.bat"
        if not getattr(self, '_is_auto_start', False):
            self._show_menu_progress_bar()

        if hasattr(self, '_clear_strategy_console'):
            self._clear_strategy_console()
        if hasattr(self, '_append_strategy_console'):
            self._append_strategy_console(tr('home_console_start', lang).format(current_strategy))

        if self._start_worker is not None and self._start_worker.isRunning():
            self._is_auto_start = False
            return

        if self._is_winws_process_running():
            detected = self._detect_running_strategy()
            if detected == current_strategy:
                self.is_running = True
                self.running_strategy = current_strategy
                self._started_winws_this_session = True
                self.user_stopped = False
                self.bat_start_time = None
                self._capture_running_winws_pid()
                self._is_auto_start = False
                self._hide_menu_progress_bar()
                self._sync_run_state_ui()
                self._refresh_strategy_display()
                self._update_strategy_detail_panel()
                self._update_window_title_with_strategy()
                if hasattr(self, "_append_strategy_console"):
                    pid = self._get_display_winws_pid() or "—"
                    self._append_strategy_console(
                        tr("home_console_already_running", lang).format(
                            current_strategy,
                            self._runtime_process_name(),
                            pid,
                        )
                    )
                return

        self._start_worker = LinuxStartWorker(self, current_strategy)
        self._start_worker.output_signal.connect(
            lambda text: self._append_strategy_console(text, kind="output")
            if hasattr(self, "_append_strategy_console")
            else None
        )
        self._start_worker.done_signal.connect(
            lambda ok, proc, err: self._on_start_worker_done(ok, proc, err, current_strategy, bat_filename)
        )

        def _on_start_worker_finished():
            self._start_worker = None
            self._sync_run_state_ui()

        self._start_worker.finished.connect(_on_start_worker_finished)
        self._start_worker.start()
        self._sync_run_state_ui()

    def start_bat_file(self):
        """Запускает выбранный .bat файл"""
        lang = self.settings.get('language', 'ru')
        if getattr(self, "_startup_update_in_progress", False) or getattr(self, "_linux_deps_worker", None):
            if hasattr(self, "_append_strategy_console"):
                self._append_strategy_console(
                    tr("home_console_update_in_progress", lang),
                    kind="warning",
                )
            return
        current_strategy = self._get_selected_strategy_name()

        if is_linux():
            self._start_linux_strategy(current_strategy, lang)
            return
        
        # Проверяем, что стратегия выбрана
        if not current_strategy or current_strategy in [tr('msg_no_bat_files', lang), tr('msg_winws_not_found', lang)]:
            self._is_auto_start = False
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_no_strategy_selected', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        # Формируем путь к .bat файлу
        bat_filename = f"{current_strategy}.bat"
        winws_folder = get_winws_path()
        bat_path = os.path.join(winws_folder, bat_filename)
        
        # Контроль запуска: только .bat из папки winws, без path traversal
        try:
            bat_path_real = os.path.realpath(bat_path)
            winws_folder_real = os.path.realpath(winws_folder)
            if not bat_path_real.startswith(winws_folder_real + os.sep) and bat_path_real != winws_folder_real:
                self._is_auto_start = False
                msg = QMessageBox(self)
                msg.setWindowTitle(tr('msg_error', lang))
                msg.setText(tr('msg_bat_path_not_allowed', lang))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
                return
        except (OSError, ValueError):
            pass  # дальше сработает проверка exists
        
        # Разрешены только файлы из списка загруженных стратегий (исключая service.bat)
        allowed = set()
        if os.path.exists(winws_folder):
            for f in os.listdir(winws_folder):
                if f.endswith('.bat') and f != 'service.bat' and os.path.isfile(os.path.join(winws_folder, f)):
                    allowed.add(f[:-4])
        if current_strategy not in allowed:
            self._is_auto_start = False
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_bat_not_in_list', lang).format(current_strategy))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        if not os.path.exists(bat_path):
            self._is_auto_start = False
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_file_not_found', lang).format(bat_filename, bat_path))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        bat_path_abs = os.path.abspath(bat_path)
        bat_dir = os.path.dirname(bat_path_abs)
        is_service_file = bat_filename.lower().startswith('service')

        # Показываем полоску прогресса только при ручном запуске (не при автозапуске стратегии)
        if not is_service_file and not getattr(self, '_is_auto_start', False):
            self._show_menu_progress_bar()

        if hasattr(self, '_clear_strategy_console'):
            self._clear_strategy_console()
        if hasattr(self, '_append_strategy_console'):
            self._append_strategy_console(
                tr('home_console_start', lang).format(current_strategy)
            )

        # Запуск в фоне: UI не замирает
        if self._start_worker is not None and self._start_worker.isRunning():
            self._is_auto_start = False
            return

        if self._is_winws_process_running():
            detected = self._detect_running_strategy()
            if detected == current_strategy:
                self.is_running = True
                self.running_strategy = current_strategy
                self._started_winws_this_session = True
                self.user_stopped = False
                self.bat_start_time = None
                self._capture_running_winws_pid()
                self._is_auto_start = False
                self._hide_menu_progress_bar()
                self._sync_run_state_ui()
                self._refresh_strategy_display()
                self._update_strategy_detail_panel()
                self._update_window_title_with_strategy()
                if hasattr(self, "_append_strategy_console"):
                    pid = self._get_display_winws_pid() or "—"
                    self._append_strategy_console(
                        tr("home_console_already_running", lang).format(
                            current_strategy,
                            self._runtime_process_name(),
                            pid,
                        )
                    )
                return

        self._start_worker = StartWorker(self, bat_path_abs, bat_dir, os.name == 'nt')
        self._start_worker.done_signal.connect(
            lambda ok, proc, err: self._on_start_worker_done(ok, proc, err, current_strategy, bat_filename)
        )
        def _on_start_worker_finished():
            self._start_worker = None
            self._sync_run_state_ui()
        self._start_worker.finished.connect(_on_start_worker_finished)
        self._start_worker.start()
        self._sync_run_state_ui()  # кнопка/комбо disabled пока воркер запуска

    def _on_start_worker_done(self, success, process, error_message, current_strategy, bat_filename):
        """Вызывается в главном потоке после завершения _StartWorker."""
        lang = self.settings.get('language', 'ru')
        is_service_file = bat_filename.lower().startswith('service')
        if getattr(self, "_pending_stop_after_start", False):
            self._pending_stop_after_start = False
            self._is_auto_start = False
            self.bat_process = process
            self._hide_menu_progress_bar()
            self.stop_winws_process()
            return
        if not success:
            self.is_running = False
            self._is_auto_start = False
            self._pending_app_restarts = []
            self._hide_menu_progress_bar()
            self._sync_run_state_ui()
            if hasattr(self, '_append_strategy_console'):
                self._append_strategy_console(
                    tr('home_console_error', lang).format(error_message or ''),
                    kind='error',
                )
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_error_on_start', lang).format(error_message or ''))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()
            return
        import time
        self.bat_process = process
        self.is_running = True
        self.running_strategy = current_strategy
        self._started_winws_this_session = True
        self.user_stopped = False
        self._stop_incomplete_logged = False
        self.is_restarting = False
        if not is_service_file:
            if self._runtime_process_active():
                self.bat_start_time = None
            else:
                self.bat_start_time = time.time()
        else:
            self.bat_start_time = None
        self._sync_run_state_ui()
        self._refresh_strategy_display()
        self._update_strategy_detail_panel()
        self._update_window_title_with_strategy()
        if hasattr(self, '_start_bat_output_reader'):
            self._start_bat_output_reader(process)
        if not is_service_file:
            self._persist_setting('last_strategy', current_strategy, silent=True)
        else:
            self.running_strategy = None
        self._sync_winws_pid_ui()
        # При автозапуске прогресс не показывали — убедимся, что полоска скрыта и флаг сброшен
        if getattr(self, '_is_auto_start', False):
            self._is_auto_start = False
            self._hide_menu_progress_bar()

    def _normalize_restart_process_name(name: str) -> str:
        n = (name or "").strip()
        if not n:
            return ""
        return n if n.lower().endswith(".exe") else f"{n}.exe"

    def _prepare_auto_restart_apps(self):
        """Завершает указанные приложения перед запуском стратегии и запоминает пути для перезапуска."""
        self._pending_app_restarts = []
        if not self.settings.get('auto_restart_apps_enabled', False):
            return
        apps = self.settings.get('auto_restart_apps', [])
        if not apps:
            return

        targets = {
            self._normalize_restart_process_name(name).lower()
            for name in apps
            if name
        }
        targets.discard("")
        if not targets:
            return

        restart_specs: dict[str, dict] = {}
        procs_to_stop = []
        for proc in psutil.process_iter(['name', 'exe', 'pid']):
            try:
                proc_name = self._normalize_restart_process_name(proc.info.get('name') or '').lower()
                if proc_name not in targets:
                    continue
                try:
                    exe_path = proc.info.get('exe') or proc.exe()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    exe_path = None
                if not exe_path or not os.path.isfile(exe_path):
                    continue
                exe_key = os.path.normcase(os.path.abspath(exe_path))
                if exe_key not in restart_specs:
                    try:
                        cwd = proc.cwd()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        cwd = os.path.dirname(exe_path)
                    restart_specs[exe_key] = {
                        'exe': exe_path,
                        'cwd': cwd or os.path.dirname(exe_path),
                        'name': proc.info.get('name') or os.path.basename(exe_path),
                    }
                procs_to_stop.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if not restart_specs:
            return

        for proc in procs_to_stop:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        if procs_to_stop:
            gone, alive = psutil.wait_procs(procs_to_stop, timeout=5)
            for proc in alive:
                try:
                    proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass

        self._pending_app_restarts = list(restart_specs.values())

    def _launch_pending_auto_restart_apps(self):
        """Перезапускает приложения после появления winws.exe."""
        if not self._pending_app_restarts:
            return

        lang = self.settings.get('language', 'ru')
        pending = self._pending_app_restarts
        self._pending_app_restarts = []

        for spec in pending:
            if isinstance(spec, str):
                spec = {'exe': spec, 'cwd': os.path.dirname(spec), 'name': os.path.basename(spec)}
            exe_path = spec.get('exe')
            if not exe_path or not os.path.isfile(exe_path):
                continue
            cwd = spec.get('cwd') or os.path.dirname(exe_path)
            display_name = spec.get('name') or os.path.basename(exe_path)
            launched = False
            try:
                if os.name == 'nt':
                    subprocess.Popen(
                        [exe_path],
                        cwd=cwd if cwd and os.path.isdir(cwd) else None,
                        creationflags=(
                            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                        ),
                        close_fds=True,
                    )
                else:
                    subprocess.Popen(
                        [exe_path],
                        cwd=cwd if cwd and os.path.isdir(cwd) else None,
                        start_new_session=True,
                    )
                launched = True
            except Exception:
                try:
                    open_path(exe_path)
                    launched = True
                except Exception:
                    pass
            if launched and hasattr(self, '_append_strategy_console'):
                self._append_strategy_console(
                    tr('home_console_app_restarted', lang).format(display_name),
                )

    def _handle_auto_restart_apps(self):
        """Совместимость: завершить и сразу перезапустить (используется там, где winws уже активен)."""
        self._prepare_auto_restart_apps()
        self._launch_pending_auto_restart_apps()

    def _do_stop_winws_process(self):
        """Синхронно завершает runtime (winws.exe / nfqws)."""
        if is_linux() and self.bat_process is not None:
            try:
                self.bat_process.terminate()
                try:
                    self.bat_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.bat_process.kill()
            except Exception:
                pass
            self.bat_process = None

        if getattr(self, "winws_manager", None):
            self.winws_manager.stop_all()
            return
        import time
        processes_to_kill = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info.get('name', '').lower() == 'winws.exe':
                    processes_to_kill.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        for proc in processes_to_kill:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        if processes_to_kill:
            time.sleep(0.5)
        remaining = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info.get('name', '').lower() == 'winws.exe':
                    remaining.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        for proc in remaining:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

    def stop_winws_process(self, silent=False, for_restart=False, on_stopped=None):
        """Останавливает процесс winws.exe. При silent=False — в фоне (UI не замирает).
        Args:
            silent: Если True, выполняется синхронно (для выхода/обновлений); иначе в фоне.
            for_restart: Не сбрасывать running_strategy и user_stopped (перезапуск из трея).
            on_stopped: Колбэк после завершения фоновой остановки.
        """
        if not silent:
            self.process_monitor_timer.stop()
            if for_restart:
                saved = self.running_strategy or self._get_selected_strategy_name()
                if saved and saved != "__external_winws__":
                    self.running_strategy = saved
                self.user_stopped = False
                self.is_restarting = True
            else:
                self.user_stopped = True
                self.running_strategy = None
                self.is_restarting = False
                self.is_running = False
            self._on_stopped_callback = on_stopped

        if silent:
            self._on_stopped_callback = None
            self._do_stop_winws_process()
            # Чтобы UI не показывал «Остановить» до следующего тика таймера
            self.is_running = False
            self.bat_start_time = None
            self.bat_process = None
            self._clear_persisted_running_winws()
            self._hide_menu_progress_bar()
            self._sync_run_state_ui()
            return
        if self._start_worker_active():
            self._pending_stop_after_start = True
            if not for_restart:
                self.user_stopped = True
                self.running_strategy = None
                self.is_restarting = False
                self.is_running = False
            if self.bat_process is not None:
                try:
                    self.bat_process.terminate()
                except Exception:
                    pass
            self._show_menu_progress_bar()
            self._sync_run_state_ui()
            return
        if self._stop_worker is not None and self._stop_worker.isRunning():
            return
        worker_cls = LinuxStopWorker if is_linux() else StopWorker
        self._stop_worker = worker_cls(self)
        self._stop_worker.done_signal.connect(
            lambda: self._on_stop_worker_done(False)
        )
        def _on_stop_worker_finished():
            self._stop_worker = None
            self._sync_run_state_ui()
        self._stop_worker.finished.connect(_on_stop_worker_finished)
        self._stop_worker.start()
        self._sync_run_state_ui()  # кнопка/комбо disabled пока воркер останавливает

    def _on_stop_worker_done(self, silent):
        """Вызывается в главном потоке после завершения _StopWorker."""
        if hasattr(self, '_stop_bat_output_reader'):
            self._stop_bat_output_reader()
        callback = getattr(self, '_on_stopped_callback', None)
        self._on_stopped_callback = None
        if not silent:
            self.is_running = False
            self.bat_start_time = None
            self.bat_process = None
            self._clear_persisted_running_winws()
            self._sync_run_state_ui()
            self._update_window_title_with_strategy()
            self._refresh_strategy_display()
            if hasattr(self, '_update_strategy_detail_panel'):
                self._update_strategy_detail_panel()
            if self.user_stopped and self._runtime_process_active():
                if not getattr(self, "_stop_incomplete_logged", False):
                    self._stop_incomplete_logged = True
                    lang = self.settings.get("language", "ru")
                    if hasattr(self, "_append_strategy_console"):
                        self._append_strategy_console(
                            tr_platform("home_console_stop_incomplete", lang).format(
                                self._runtime_process_name()
                            ),
                            kind="warning",
                        )
            else:
                self._stop_incomplete_logged = False
            if callback:
                try:
                    callback()
                except Exception:
                    pass
            QTimer.singleShot(2000, lambda: self.process_monitor_timer.start(1000))

    def restart_running_strategy(self, *, delay_ms: int = 500) -> None:
        """Перезапуск текущей или выбранной стратегии без потери имени (трей и др.)."""
        lang = self.settings.get('language', 'ru')
        invalid = (
            tr('msg_no_bat_files', lang),
            tr('msg_winws_not_found', lang),
        )
        strategy = self.running_strategy or self._get_selected_strategy_name()
        if strategy == "__external_winws__":
            strategy = self._detect_running_strategy() or self.settings.get('last_strategy', '')
        if not strategy or strategy in invalid:
            self.start_bat_file()
            return

        index = self._find_strategy_index_by_data(strategy)
        if index >= 0:
            self.strategy_list.setCurrentRow(index)

        def _start_after_stop():
            self.running_strategy = strategy
            self.user_stopped = False
            self.is_restarting = True
            self.start_bat_file()
            QTimer.singleShot(2000, lambda: setattr(self, 'is_restarting', False))

        if self.is_running or self._is_winws_process_running():
            self.stop_winws_process(
                for_restart=True,
                on_stopped=lambda: QTimer.singleShot(delay_ms, _start_after_stop),
            )
        else:
            _start_after_stop()

    def _sync_winws_during_strategy_test(self, winws_running: bool) -> None:
        """Лёгкая синхронизация UI главного окна пока открыто окно тестирования."""
        self._test_winws_live = winws_running
        self._sync_run_state_ui()
        if hasattr(self, '_refresh_strategy_display'):
            self._refresh_strategy_display()
        if hasattr(self, '_update_strategy_detail_panel'):
            self._update_strategy_detail_panel()

    def check_winws_process(self):
        """Проверяет наличие runtime-процесса и обновляет состояние кнопки.
        Также проверяет появление процесса в течение winws_start_timeout_sec после запуска."""
        winws_running = self._runtime_process_active()

        if getattr(self, '_strategy_test_active', False):
            self._sync_winws_during_strategy_test(winws_running)
            if not winws_running and not getattr(self, 'is_running', False):
                self._hide_menu_progress_bar()
            return

        lang = self.settings.get('language', 'ru')
        import time
        
        # Скрываем полоску прогресса только когда процесс исчез и мы не ждём его появления
        # (при ожидании старта bat_start_time не None и is_running True — не скрываем)
        if not winws_running and (self.bat_start_time is None or not self.is_running):
            self._hide_menu_progress_bar()

        starting = (
            getattr(self, "_start_worker", None) is not None
            and self._start_worker.isRunning()
        )
        stopping = (
            getattr(self, "_stop_worker", None) is not None
            and self._stop_worker.isRunning()
        )
        if (
            winws_running
            and self.bat_start_time is None
            and not starting
            and not stopping
        ):
            self._hide_menu_progress_bar()
        
        # Проверка запуска: если прошло более N секунд с момента запуска .bat файла
        # и процесс winws.exe не появился - останавливаем процесс запуска
        # ВАЖНО: Проверка выполняется только один раз, после чего bat_start_time сбрасывается
        if (self.bat_start_time is not None and 
            self.is_running and 
            not self.user_stopped):
            start_timeout = self._get_winws_start_timeout()
            elapsed_time = time.time() - self.bat_start_time
            if elapsed_time >= start_timeout:
                # Прошло N секунд - проверяем один раз и сбрасываем время запуска
                strategy_name = self.running_strategy if self.running_strategy else self._get_selected_strategy_name()
                self.bat_start_time = None  # Сбрасываем время запуска сразу, чтобы проверка не повторялась
                
                if not winws_running:
                    # Процесс не появился в течение таймаута — останавливаем запуск
                    if self.bat_process is not None:
                        try:
                            self.bat_process.terminate()
                            try:
                                self.bat_process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                self.bat_process.kill()
                        except Exception:
                            pass

                    # Обновляем состояние
                    self.is_running = False
                    self.running_strategy = None
                    self.bat_process = None
                    self._pending_app_restarts = []
                    self._hide_menu_progress_bar()
                    self.is_restarting = False
                    self._sync_run_state_ui()

                    if hasattr(self, '_append_strategy_console'):
                        self._append_strategy_console(
                            tr('home_console_critical_launch', lang).format(
                                strategy_name,
                                int(start_timeout),
                                self._runtime_process_name(),
                            ),
                            kind='critical',
                        )
                    msg = configure_message_box(QMessageBox(self))
                    msg.setWindowTitle(tr('msg_error_launch_title', lang))
                    msg.setText(tr('msg_winws_not_started_title', lang).format(strategy_name))
                    msg.setInformativeText(
                        tr('msg_winws_not_started_details', lang).format(
                            int(start_timeout),
                            self._runtime_process_name(),
                        )
                    )
                    msg.setIcon(QMessageBox.Icon.Critical)
                    msg.exec()
                    return
        
        # Если процесс winws.exe появился, сбрасываем время запуска и скрываем полоску прогресса
        if winws_running and self.bat_start_time is not None:
            self.bat_start_time = None
            self.is_restarting = False
            self._hide_menu_progress_bar()
            self._launch_pending_auto_restart_apps()
            self._sync_winws_pid_ui()

        if winws_running and self.is_running:
            self._sync_winws_pid_ui()

        if not winws_running:
            waiting_start = (
                getattr(self, "bat_start_time", None) is not None
                and getattr(self, "is_running", False)
            )
            if not waiting_start and self._get_stored_winws_pid() is not None:
                self._clear_persisted_running_winws()
        
        # Синхронизируем состояние кнопки с реальным состоянием процесса
        if winws_running and not self.is_running:
            if not self._may_sync_runtime_from_process():
                self._sync_run_state_ui()
                return
            if self._start_worker_active():
                return
            # Процесс запущен, но кнопка показывает "Запустить" (программа перезапущена)
            self._sync_runtime_state_from_process()
            self._sync_run_state_ui()
            # Обновляем заголовок окна с найденной стратегией
            self._update_window_title_with_strategy()
            self._refresh_strategy_display()
            if hasattr(self, "_sync_external_winws_console"):
                self._sync_external_winws_console()
            if hasattr(self, "_update_strategy_detail_panel"):
                self._update_strategy_detail_panel()
        elif not winws_running and self.is_running:
            # Не считаем процесс мёртвым, если мы ещё в периоде ожидания появления winws
            start_timeout = self._get_winws_start_timeout()
            if self.bat_start_time is not None and (time.time() - self.bat_start_time) < start_timeout:
                return
            # Процесс остановлен, но кнопка показывает "Остановить"
            self.is_running = False
            self._started_winws_this_session = False
            self._clear_persisted_running_winws()
            self.bat_process = None
            self._hide_menu_progress_bar()
            self._sync_run_state_ui()
            # Обновляем заголовок окна (стратегия больше не запущена)
            self._update_window_title_with_strategy()
            self._refresh_strategy_display()
            
            # ВАЖНО: Проверяем флаг user_stopped ПЕРВЫМ делом
            # Если пользователь явно остановил процесс, НЕ запускаем автоперезапуск
            if self.user_stopped:
                # Пользователь явно остановил процесс - не перезапускаем
                # Флаг будет сброшен при следующем запуске стратегии
                # Также очищаем running_strategy на всякий случай
                self.running_strategy = None
                self.is_restarting = False  # Сбрасываем флаг перезапуска
                return
            
            # ВАЖНО: Проверяем настройку автоперезапуска ВТОРЫМ делом
            # Если настройка выключена, НЕ делаем НИЧЕГО связанного с перезапуском
            auto_restart_enabled = self.settings.get('auto_restart_strategy', False)
            if not auto_restart_enabled:
                # Настройка выключена - полностью отключаем логику перезапуска
                # Очищаем все связанные флаги
                self.running_strategy = None
                self.is_restarting = False
                return
            
            # Только если настройка ВКЛЮЧЕНА и все остальные условия выполнены
            # Если включен автоперезапуск и была запущена стратегия, перезапускаем её
            # Проверяем, что мы не в процессе перезапуска, чтобы избежать множественных перезапусков
            if (self.running_strategy and 
                not self.is_restarting):
                # Небольшая задержка перед перезапуском
                QTimer.singleShot(1000, self.restart_strategy)

        if self.user_stopped and not winws_running and not self._stop_worker_active():
            self._hide_menu_progress_bar()
            self._sync_run_state_ui()
            self._refresh_strategy_display()
            if hasattr(self, "_update_strategy_detail_panel"):
                self._update_strategy_detail_panel()
            self._update_window_title_with_strategy()

