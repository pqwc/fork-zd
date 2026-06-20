"""tools_mixin methods for MainWindow."""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import pyqtSlot, QTimer
from src.pages.test.test_window import TestWindow
from src.features.editor.ui.unified_editor_window import get_unified_editor_window
from src.features.tools.ui.bin_creator_window import get_bin_creator_window
from src.shared.i18n.translator import tr


class ToolsMixin:
    def _capture_pre_test_strategy_state(self) -> dict:
        """Сохраняет состояние стратегии до открытия окна тестирования."""
        was_own = True
        if hasattr(self, "_is_own_winws_session"):
            was_own = self._is_own_winws_session()
        return {
            'running_strategy': self.running_strategy,
            'is_running': self.is_running,
            'user_stopped': getattr(self, 'user_stopped', False),
            '_started_winws_this_session': getattr(self, '_started_winws_this_session', False),
            'was_own_session': was_own,
            'selected_strategy': self._get_selected_strategy_name(),
            'last_strategy': self.settings.get('last_strategy', ''),
        }

    def _finalize_after_strategy_test(self) -> None:
        """Синхронизация UI после закрытия окна тестирования (progress bar и winws)."""
        if self._is_winws_process_running():
            self.bat_start_time = None
            self.is_restarting = False
            self._hide_menu_progress_bar()
        elif not getattr(self, "is_running", False):
            self._hide_menu_progress_bar()
        self._sync_run_state_ui()
        QTimer.singleShot(150, self.check_winws_process)

    def _restore_after_strategy_test(self, snapshot: dict) -> None:
        """Возвращает стратегию и состояние winws, которые были до тестирования."""
        if getattr(self, '_test_restore_applied', False):
            return
        self._test_restore_applied = True

        self._hide_menu_progress_bar()
        self.bat_start_time = None
        self.bat_process = None
        self.is_restarting = False

        pre_last = snapshot.get('last_strategy', '')
        if pre_last != self.settings.get('last_strategy'):
            self._persist_setting('last_strategy', pre_last, silent=True)

        pre_running = snapshot.get('running_strategy')
        pre_selected = snapshot.get('selected_strategy') or pre_last or pre_running
        was_running = bool(snapshot.get('is_running')) and bool(pre_running)
        was_own = snapshot.get('was_own_session', snapshot.get('_started_winws_this_session', False))
        restore_selection = pre_running if was_running and pre_running else pre_selected

        self.stop_winws_process(silent=True)

        if restore_selection:
            self.strategy_list.blockSignals(True)
            try:
                self._select_strategy_by_data(restore_selection)
            finally:
                self.strategy_list.blockSignals(False)

        if was_running and was_own:
            self.running_strategy = pre_running
            self.user_stopped = False
            self._started_winws_this_session = snapshot.get('_started_winws_this_session', False)
            self.is_running = False
            self._sync_run_state_ui()
            self._refresh_strategy_display()
            self._update_window_title_with_strategy()
            if hasattr(self, '_update_strategy_detail_panel'):
                self._update_strategy_detail_panel()

            def _restart_pre_test_strategy(attempt: int = 0) -> None:
                if self._is_winws_process_running():
                    if attempt < 30:
                        QTimer.singleShot(300, lambda: _restart_pre_test_strategy(attempt + 1))
                    else:
                        lang = self.settings.get('language', 'ru')
                        if hasattr(self, '_append_strategy_console'):
                            self._append_strategy_console(
                                tr('home_console_error', lang).format(
                                    tr('strategy_test_restore_failed', lang)
                                ),
                                kind='error',
                            )
                    return
                if pre_running:
                    self.strategy_list.blockSignals(True)
                    try:
                        self._select_strategy_by_data(pre_running)
                    finally:
                        self.strategy_list.blockSignals(False)
                self._is_auto_start = True
                self.start_bat_file()

            QTimer.singleShot(500, lambda: _restart_pre_test_strategy(0))
            return

        if was_running and not was_own:
            self.running_strategy = pre_running
            self.is_running = False
            self.user_stopped = False
            self._started_winws_this_session = False
            self._sync_run_state_ui()
            self._refresh_strategy_display()
            self._update_window_title_with_strategy()
            if hasattr(self, '_update_strategy_detail_panel'):
                self._update_strategy_detail_panel()
            QTimer.singleShot(300, self.check_winws_process)
            return

        self.running_strategy = None
        self.is_running = False
        self.user_stopped = snapshot.get('user_stopped', False)
        self._started_winws_this_session = False
        self._clear_persisted_running_winws()
        self._sync_run_state_ui()
        self._refresh_strategy_display()
        self._update_window_title_with_strategy()
        if hasattr(self, '_update_strategy_detail_panel'):
            self._update_strategy_detail_panel()

    def _on_test_winws_state_changed(self, running: bool) -> None:
        """Синхронизация UI при смене winws во время окна тестирования."""
        if not getattr(self, '_strategy_test_active', False):
            return
        if hasattr(self, '_sync_winws_during_strategy_test'):
            self._sync_winws_during_strategy_test(running)

    def show_test_window(self):
        """Открывает окно тестирования стратегий"""
        snapshot = self._capture_pre_test_strategy_state()
        self._test_restore_applied = False
        self._strategy_test_active = True
        self._test_winws_live = self._is_winws_process_running()
        self._sync_run_state_ui()

        test_window = TestWindow(self, winws_folder=None)
        test_window.strategy_changed.connect(self._on_test_strategy_display_update)
        try:
            test_window.exec()
        finally:
            self._strategy_test_active = False
            self._test_winws_live = False
            if hasattr(self, 'action_button') and self.action_button:
                self.action_button.setToolTip('')
            if getattr(test_window, 'tests_session_started', False):
                self._restore_after_strategy_test(snapshot)
            self._finalize_after_strategy_test()

    @pyqtSlot(str)
    def _on_test_strategy_display_update(self, strategy_name: str):
        """Показывает текущую тестируемую стратегию без смены running_strategy и last_strategy."""
        if not strategy_name or not getattr(self, '_strategy_test_active', False):
            return
        self.strategy_list.blockSignals(True)
        try:
            self._select_strategy_by_data(strategy_name)
        finally:
            self.strategy_list.blockSignals(False)
        self._refresh_strategy_display()

    def show_editor(self):
        """Открывает объединённый редактор (списки, drivers\\etc, стратегии)"""
        w = get_unified_editor_window(self, initial_tab=0)
        w.show()
        w.raise_()
        w.activateWindow()

    def show_bin_creator(self):
        """Открывает окно редактора bin-файлов (winws/bin/*.bin)."""
        lang = self.settings.get("language", "ru")
        w = get_bin_creator_window(self, language=lang)
        w.show()
        w.raise_()
        w.activateWindow()

    def show_strategy_creator(self):
        """Открывает окно создания стратегий"""
        from src.features.strategy.ui.strategy_creator_window import RuleDialog
        dialog = RuleDialog(self)
        if dialog.exec():
            self.load_bat_files()

    def show_export_bundle_dialog(self):
        """Экспорт стратегий, lists, bin, config и zapret в zip."""
        from src.features.export.ui.export_bundle_dialog import ExportBundleDialog
        lang = self.settings.get("language", "ru")
        dlg = ExportBundleDialog(self, language=lang)
        dlg.exec()
