"""updates_mixin methods for MainWindow."""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from src.shared.i18n.translator import tr
from src.entities.zapret.zapret_updater import ZapretUpdater
from src.shared.lib.path_utils import get_winws_path, get_config_path, has_runtime_installation
from src.platform import is_linux
from src.features.updates.ui.vs_update_dialog import VSUpdateDialog
from src.shared.ui.update_progress import create_update_progress
from src.features.winws_setup.ui.winws_setup_dialog import WinwsSetupDialog
from src.features.updates.ui.addons_dialog import AddonsDialog
from src.shared.ui.message_box_utils import configure_message_box
import os
import re
import subprocess
import requests
import psutil
from datetime import datetime


class UpdatesMixin:
    def _has_winws(self) -> bool:
        return has_runtime_installation()

    def _set_watcher_paused(self, paused: bool) -> None:
        self._winws_watcher_paused = paused

    def _should_emit_update_signal(self) -> bool:
        return not getattr(self, "_is_shutting_down", False)

    def _clear_startup_update_block(self) -> None:
        self._startup_update_in_progress = False
        if hasattr(self, "_hide_menu_progress_bar"):
            self._hide_menu_progress_bar()

    def _keep_startup_update_block_for_app_phase(self) -> None:
        mode = getattr(self, "_startup_update_mode", "none")
        if mode == "all":
            self._startup_update_in_progress = True

    def _finish_startup_update_block_if_done(self, *, auto: bool) -> None:
        if not auto:
            return
        mode = getattr(self, "_startup_update_mode", "none")
        if mode != "all":
            self._clear_startup_update_block()

    def _background_app_update_check(self):
        """Фоновая проверка обновлений программы (только индикатор в UI)."""
        def check():
            try:
                info = self.app_updater.check_for_updates()
                if not info.get('error') and info.get('has_update'):
                    if self._should_emit_update_signal():
                        self.update_found_signal.emit(info['latest_version'])
            except Exception:
                pass
        import threading
        threading.Thread(target=check, daemon=True).start()

    def _get_update_progress(self, auto: bool, lang: str):
        return create_update_progress(self, auto=auto, language=lang)

    def _show_auto_update_status(self, text: str) -> None:
        """Краткий статус автообновления в футере и indeterminate-полоска."""
        footer = getattr(self, "footer_label", None)
        if footer is not None:
            from src.shared.ui import theme as ui_theme
            p = ui_theme.palette()
            footer.setText(f'<span style="color:{p.fg_muted};">{text}</span>')
        if hasattr(self, "_append_strategy_console"):
            self._append_strategy_console(text)
        if hasattr(self, "_show_menu_progress_bar"):
            self._show_menu_progress_bar()
        QApplication.processEvents()

    def _finish_auto_update_status(self, text: str, *, is_error: bool = False, delay_ms: int = 5000) -> None:
        """Показывает итог автообновления в футере, затем восстанавливает обычный футер."""
        if hasattr(self, "_hide_menu_progress_bar"):
            self._hide_menu_progress_bar()
        footer = getattr(self, "footer_label", None)
        if footer is not None:
            from src.shared.ui import theme as ui_theme
            p = ui_theme.palette()
            color = "#e06060" if is_error else p.accent
            footer.setText(f'<span style="color:{color};">{text}</span>')
        if hasattr(self, "_append_strategy_console"):
            self._append_strategy_console(text)
        if hasattr(self, "load_footer_info"):
            QTimer.singleShot(delay_ms, self.load_footer_info)

    def run_startup_updates(self):
        """Проверка/установка обновлений при запуске согласно настройкам или CLI."""
        from src.app.launch_options import forced_update_mode, should_skip_updates

        if should_skip_updates():
            return

        forced = forced_update_mode()
        lang = self.settings.get('language', 'ru')

        if forced == 'app':
            self._startup_update_mode = 'app'
            self._startup_update_lang = lang
            self._startup_update_in_progress = True
            self._show_auto_update_status(tr('update_checking_app', lang))
            self._run_startup_app_check_async()
            return

        if forced == 'strategies':
            if not self._has_winws():
                return
            self._startup_update_mode = 'strategies'
            self._startup_update_lang = lang
            self._startup_update_in_progress = True
            self._show_auto_update_status(tr('update_checking', lang))
            self._run_startup_zapret_check_async()
            return

        if forced == 'all':
            self._startup_update_mode = 'all'
            self._startup_update_lang = lang
            if self._has_winws():
                self._startup_update_in_progress = True
                self._show_auto_update_status(tr('update_checking', lang))
                self._run_startup_zapret_check_async()
            else:
                self._startup_update_in_progress = True
                self._show_auto_update_status(tr('update_checking_app', lang))
                self._run_startup_app_check_async()
            return

        mode = self.settings.get('auto_update_mode', 'none')
        if mode == 'none':
            self._background_app_update_check()
            return

        self._startup_update_mode = mode
        self._startup_update_lang = self.settings.get('language', 'ru')
        if mode == 'app':
            self._startup_update_in_progress = True
            self._show_auto_update_status(tr('update_checking_app', self._startup_update_lang))
            self._run_startup_app_check_async()
            return
        if mode in ('strategies', 'all') and self._has_winws():
            self._startup_update_in_progress = True
            self._show_auto_update_status(tr('update_checking', self._startup_update_lang))
            self._run_startup_zapret_check_async()
            return
        if mode == 'all':
            self._startup_update_in_progress = True
            self._show_auto_update_status(tr('update_checking_app', self._startup_update_lang))
            self._run_startup_app_check_async()

    def _run_startup_zapret_check_async(self) -> None:
        mode = getattr(self, '_startup_update_mode', 'none')
        if mode not in ('strategies', 'all') or not self._has_winws():
            if mode in ('app', 'all'):
                self._startup_update_in_progress = True
                self._run_startup_app_check_async()
            else:
                self._clear_startup_update_block()
                self.load_footer_info()
            return

        self._startup_update_in_progress = True
        lang = self._startup_update_lang
        self._show_auto_update_status(tr('update_checking', lang))

        def worker():
            try:
                info = self.zapret_updater.check_for_updates()
            except Exception as exc:
                info = {'error': str(exc), 'has_update': False}
            if self._should_emit_update_signal():
                self.startup_zapret_check_done.emit(info)

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _on_startup_zapret_check_done(self, zapret_info: dict) -> None:
        mode = getattr(self, '_startup_update_mode', 'none')
        had_zapret_update = zapret_info.get('has_update') and not zapret_info.get('error')
        if had_zapret_update:
            self.download_and_install_update(zapret_info, auto=True)
            if mode == 'all':
                return
        elif mode != 'all':
            self._clear_startup_update_block()
            self.load_footer_info()
        if mode in ('app', 'all'):
            self._keep_startup_update_block_for_app_phase()
            self._run_startup_app_check_async()

    def _run_startup_app_check_async(self) -> None:
        mode = getattr(self, '_startup_update_mode', 'none')
        if mode not in ('app', 'all'):
            return

        lang = self._startup_update_lang
        self._startup_update_in_progress = True
        self._show_auto_update_status(tr('update_checking_app', lang))

        def worker():
            try:
                info = self.app_updater.check_for_updates()
            except Exception as exc:
                info = {'error': str(exc), 'has_update': False}
            if self._should_emit_update_signal():
                self.startup_app_check_done.emit(info)

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _on_startup_app_check_done(self, app_info: dict) -> None:
        if app_info.get('has_update') and not app_info.get('error'):
            self.latest_available_version = app_info['latest_version']
            self.load_version_info()
            self.download_and_install_app_update(app_info, auto=True)
            return
        if not app_info.get('error'):
            self.latest_available_version = None
            self.load_version_info()
        else:
            self.load_footer_info()
        self._clear_startup_update_block()

    def _runtime_process_label(self) -> str:
        return "nfqws" if is_linux() else "winws.exe"

    def _strategies_install_folder(self) -> str:
        """Каталог для .bat стратегий: winws (Windows) или zapret-latest (Linux)."""
        runtime = get_winws_path()
        if is_linux():
            return os.path.join(runtime, "zapret-latest")
        return runtime

    def _lists_install_folder(self) -> str:
        """Каталог lists: winws/lists (Windows) или zapret-latest/lists (Linux)."""
        if is_linux():
            from src.features.editor.lib.editor_paths import get_editor_lists_folder

            return get_editor_lists_folder()
        return os.path.join(get_winws_path(), "lists")

    def _update_runtime_running_text(self, lang: str) -> str:
        if is_linux():
            return tr("update_runtime_running", lang).format(self._runtime_process_label())
        return tr("update_winws_running", lang)

    def _is_runtime_process_running(self) -> bool:
        mgr = getattr(self, "winws_manager", None)
        if mgr is not None:
            stored = None
            if hasattr(self, "_get_stored_winws_pid"):
                stored = self._get_stored_winws_pid()
            if hasattr(mgr, "is_running"):
                return bool(mgr.is_running(stored))
        process_name = self._runtime_process_label()
        try:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if proc.info.get("name", "").lower() == process_name:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception:
            pass
        return False

    def _stop_winws_for_update(self, auto: bool = False) -> bool:
        """Останавливает runtime перед обновлением. False — пользователь отменил."""
        lang = self.settings.get('language', 'ru')
        winws_running = self._is_runtime_process_running()

        if not winws_running:
            return True

        if auto:
            self.stop_winws_process(silent=True)
            QApplication.processEvents()
            import time
            time.sleep(2)
            return True

        stop_dialog = QMessageBox(self)
        stop_dialog.setWindowTitle(tr('update_stopping_winws', lang))
        stop_dialog.setText(self._update_runtime_running_text(lang))
        stop_dialog.setInformativeText(tr('update_winws_stop_required', lang))
        stop_dialog.setIcon(QMessageBox.Icon.Question)
        stop_dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        stop_dialog.setDefaultButton(QMessageBox.StandardButton.Yes)
        if stop_dialog.exec() != QMessageBox.StandardButton.Yes:
            return False

        self.stop_winws_process(silent=True)
        QApplication.processEvents()
        import time
        time.sleep(3)
        process_name = self._runtime_process_label()
        for _ in range(10):
            still_running = False
            try:
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if proc.info['name'] and proc.info['name'].lower() == process_name:
                            still_running = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
            except Exception:
                pass
            if not still_running:
                break
            time.sleep(0.5)
            QApplication.processEvents()
        return True

    def check_app_updates(self):
        """Проверяет наличие обновлений программы ZapretDesktop"""
        lang = self.settings.get('language', 'ru')
        
        # Показываем окно проверки в стиле VS
        update_dialog = VSUpdateDialog(self, lang)
        update_dialog.set_status(tr('update_checking_app', lang))
        update_dialog.show()
        QApplication.processEvents()
        
        # Проверяем обновления
        update_info = self.app_updater.check_for_updates()
        update_dialog.close()

        if 'error' in update_info:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(update_info['error'])
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        if not update_info['has_update']:
            self.latest_available_version = None
            self.load_version_info()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_check_updates_title', lang))
            msg.setText(tr('update_not_found', lang))
            msg.setInformativeText(tr('update_current_version', lang).format(update_info["current_version"]))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            return

        self.latest_available_version = update_info['latest_version']
        self.load_version_info()
        # Есть обновление - спрашиваем пользователя
        reply = QMessageBox.question(
            self,
            tr('update_available_title', lang),
            tr('update_available_text_app', lang).format(update_info["latest_version"], update_info["current_version"]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.download_and_install_app_update(update_info)

    def download_and_install_app_update(self, update_info, auto: bool = False):
        """Скачивает и устанавливает обновление программы"""
        lang = self.settings.get('language', 'ru')
        progress = None

        if auto:
            self._startup_update_in_progress = True

        try:
            if is_linux() and not update_info.get('download_url'):
                release_url = update_info.get('release_url', '')
                if release_url:
                    from PyQt6.QtCore import QUrl
                    from PyQt6.QtGui import QDesktopServices

                    QDesktopServices.openUrl(QUrl(release_url))
                if not auto:
                    msg = configure_message_box(QMessageBox(self))
                    msg.setWindowTitle(tr('update_app_title', lang))
                    msg.setText(tr('linux_app_update_manual', lang))
                    msg.setIcon(QMessageBox.Icon.Information)
                    msg.exec()
                elif hasattr(self, "_finish_auto_update_status"):
                    self._finish_auto_update_status(tr('linux_app_update_manual', lang), delay_ms=4000)
                return

            if not update_info.get('download_url'):
                if not auto:
                    msg = configure_message_box(QMessageBox(self))
                    msg.setWindowTitle(tr('update_error_title', lang))
                    msg.setText(tr('update_error_url_not_found', lang))
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.exec()
                elif hasattr(self, "_finish_auto_update_status"):
                    self._finish_auto_update_status(
                        tr('update_error_url_not_found', lang),
                        is_error=True,
                    )
                return

            progress = self._get_update_progress(auto, lang)
            progress.set_status(tr('update_downloading', lang))
            progress.show_cancel(False)
            progress.show()
            QApplication.processEvents()

            last_progress_update = [0]

            def update_progress(value):
                progress.set_progress(value)
                if value - last_progress_update[0] >= 5 or value >= 100:
                    progress.add_detail(f"{tr('update_downloading', lang)}: {value:.0f}%")
                    last_progress_update[0] = value
                QApplication.processEvents()
                if progress.is_cancelled():
                    raise Exception("Обновление отменено пользователем")

            progress.set_status(tr('update_downloading', lang))
            progress.add_detail(
                f"{tr('update_downloading', lang)} {update_info['latest_version']}..."
            )
            downloaded_path = self.app_updater.download_update(
                update_info['download_url'],
                progress_callback=update_progress,
            )

            if is_linux():
                progress.set_progress(100)
                progress.set_status(tr('update_completed', lang))
                progress.add_detail(tr('linux_app_update_manual', lang))
                QApplication.processEvents()
                progress.close()
                from src.shared.lib.open_path import open_path

                open_path(downloaded_path)
                if auto:
                    self._finish_auto_update_status(tr('linux_app_update_manual', lang), delay_ms=4000)
                else:
                    msg = configure_message_box(QMessageBox(self))
                    msg.setWindowTitle(tr('update_completed', lang))
                    msg.setText(tr('linux_app_update_manual', lang))
                    msg.setIcon(QMessageBox.Icon.Information)
                    msg.exec()
                return

            progress.set_status(tr('update_installing', lang))
            progress.set_progress(90)
            progress.add_detail(tr('update_installing', lang) + "...")
            QApplication.processEvents()

            self.app_updater.install_update(downloaded_path, update_info['latest_version'])

            progress.set_progress(100)
            progress.set_status(tr('update_completed', lang))
            progress.add_detail(
                tr('update_completed_text_app', lang).format(update_info["latest_version"])
            )
            QApplication.processEvents()

            import time
            start_time = time.time()
            while time.time() - start_time < (0.4 if auto else 1.0):
                QApplication.processEvents()
                time.sleep(0.05)
            progress.close()

            if auto:
                self._finish_auto_update_status(
                    tr('update_completed_text_app', lang).format(update_info["latest_version"]),
                    delay_ms=1500,
                )
            else:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('update_completed', lang))
                msg.setText(tr('update_completed_text_app', lang).format(update_info["latest_version"]))
                msg.setInformativeText(tr('update_restart_required', lang))
                msg.setIcon(QMessageBox.Icon.Information)
                msg.exec()

            QTimer.singleShot(300, QApplication.instance().quit)

        except Exception as e:
            if progress is not None:
                progress.close()
            if auto:
                self._finish_auto_update_status(
                    tr('update_error_text', lang).format(str(e)),
                    is_error=True,
                )
            else:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('update_error_title', lang))
                msg.setText(tr('update_error_text', lang).format(str(e)))
                msg.setIcon(QMessageBox.Icon.Critical)
                msg.exec()
        finally:
            if auto:
                self._clear_startup_update_block()

    def check_zapret_updates(self):
        """Проверяет наличие обновлений стратегий zapret"""
        lang = self.settings.get('language', 'ru')

        if not has_runtime_installation():
            if is_linux():
                from src.features.linux_runtime.ui.linux_runtime_setup_dialog import LinuxRuntimeSetupDialog

                dlg = LinuxRuntimeSetupDialog(self, self.config)
                dlg.exec()
            else:
                dlg = WinwsSetupDialog(self, self.config)
                dlg.exec()
            self.settings = self.config.load_settings()
            self.zapret_updater = ZapretUpdater()
            if not has_runtime_installation():
                return

        # Показываем окно проверки в стиле VS
        update_dialog = VSUpdateDialog(self, lang)
        update_dialog.set_status(tr('update_checking', lang))
        update_dialog.show()
        QApplication.processEvents()
        
        # Проверяем обновления
        update_info = self.zapret_updater.check_for_updates()
        update_dialog.close()
        
        if 'error' in update_info:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(update_info['error'])
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        if not update_info['has_update']:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_check_updates_title', lang))
            msg.setText(tr('update_not_found', lang))
            msg.setInformativeText(tr('update_current_version', lang).format(update_info["current_version"]))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            return
        
        # Есть обновление - спрашиваем пользователя
        reply = QMessageBox.question(
            self,
            tr('update_available_title', lang),
            tr('update_available_text', lang).format(update_info["latest_version"], update_info["current_version"]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.download_and_install_update(update_info)

    def _download_and_install_update_linux(self, update_info, auto: bool = False):
        """Обновление стратегий на Linux через service.sh download-deps (фоновый поток)."""
        from src.features.updates.update_workers import LinuxDepsWorker

        lang = self.settings.get('language', 'ru')
        if auto:
            self._startup_update_in_progress = True

        if not self._stop_winws_for_update(auto=auto):
            self._finish_startup_update_block_if_done(auto=auto)
            return

        progress = self._get_update_progress(auto, lang)
        progress.set_status(tr('update_downloading', lang))
        progress.show_cancel(False)
        progress.show()
        progress.add_detail(tr('linux_update_download_deps', lang))
        QApplication.processEvents()

        self._linux_update_ctx = {
            "update_info": update_info,
            "auto": auto,
            "lang": lang,
            "progress": progress,
        }
        self._set_watcher_paused(True)

        worker = LinuxDepsWorker(self)
        self._linux_deps_worker = worker
        worker.finished.connect(self._on_linux_deps_worker_finished)
        worker.start()

    def _on_linux_deps_worker_finished(self, ok: bool, detail: str) -> None:
        ctx = getattr(self, "_linux_update_ctx", None) or {}
        self._linux_update_ctx = None
        self._linux_deps_worker = None
        self._set_watcher_paused(False)

        lang = ctx.get("lang", "ru")
        auto = bool(ctx.get("auto"))
        progress = ctx.get("progress")

        try:
            if not ok:
                raise Exception(detail or "download-deps failed")

            update_info = ctx.get("update_info") or {}
            target_version = (update_info.get("latest_version") or "").strip()
            self.zapret_updater._sync_zapret_version_with_service()
            version = self.zapret_updater.get_current_version()
            if target_version:
                if version != target_version:
                    self.zapret_updater._apply_version_after_update(target_version)
                    version = target_version
                else:
                    self.zapret_updater.save_version(target_version)
                    self.zapret_updater.current_version = target_version

            if hasattr(self, "sync_linux_conf_env_from_settings"):
                self.sync_linux_conf_env_from_settings(silent=True)

            if progress is not None:
                progress.set_progress(100)
                progress.set_status(tr('update_completed', lang))
                progress.add_detail(tr('update_completed_text', lang).format(version))
                QApplication.processEvents()
                progress.close()

            current_strategy = self._get_selected_strategy_name()
            self.load_bat_files()
            self._select_strategy_by_data(current_strategy)

            if auto:
                self._finish_auto_update_status(
                    tr('update_completed_text', lang).format(version),
                    delay_ms=4000,
                )
            else:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('update_completed', lang))
                msg.setText(tr('update_completed_text', lang).format(version))
                msg.setIcon(QMessageBox.Icon.Information)
                msg.exec()
        except Exception as e:
            if progress is not None:
                progress.close()
            if auto:
                self._finish_auto_update_status(
                    tr('update_error_text', lang).format(str(e)),
                    is_error=True,
                )
            else:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('update_error_title', lang))
                msg.setText(tr('update_error_text', lang).format(str(e)))
                msg.setIcon(QMessageBox.Icon.Critical)
                msg.exec()
        finally:
            auto = bool(ctx.get("auto"))
            mode = getattr(self, "_startup_update_mode", "none")
            if auto and mode == "all":
                self._keep_startup_update_block_for_app_phase()
                self._run_startup_app_check_async()
            else:
                self._finish_startup_update_block_if_done(auto=auto)

    def _on_linux_deps_install_done(self, ok: bool, detail: str) -> None:
        """Alias для совместимости с сигналом окна (не используется напрямую)."""
        self._on_linux_deps_worker_finished(ok, detail)

    def download_and_install_update(self, update_info, auto: bool = False):
        """Скачивает и устанавливает обновление"""
        lang = self.settings.get('language', 'ru')

        if is_linux() and not update_info.get('download_url'):
            self._download_and_install_update_linux(update_info, auto=auto)
            return

        if auto:
            self._startup_update_in_progress = True
        
        if not update_info.get('download_url'):
            if not auto:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('update_error_title', lang))
                msg.setText(tr('update_error_url_not_found', lang))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
            return

        if not self._stop_winws_for_update(auto=auto):
            self._finish_startup_update_block_if_done(auto=auto)
            return
        
        progress = self._get_update_progress(auto, lang)
        progress.set_status(tr('update_downloading', lang))
        progress.show_cancel(False)
        progress.show()
        QApplication.processEvents()

        last_progress_update = [0]
        def update_progress(value):
            progress.set_progress(value)
            if value - last_progress_update[0] >= 5 or value >= 100:
                progress.add_detail(f"{tr('update_downloading', lang)}: {value:.0f}%")
                last_progress_update[0] = value
            QApplication.processEvents()
            if progress.is_cancelled():
                raise Exception("Обновление отменено пользователем")

        try:
            progress.set_status(tr('update_downloading', lang))
            progress.add_detail(
                f"{tr('update_downloading', lang)} {update_info['latest_version']}..."
            )
            zip_path = self.zapret_updater.download_update(
                update_info['download_url'],
                progress_callback=update_progress
            )

            progress.set_status(tr('update_installing', lang))
            progress.set_progress(90)
            progress.add_detail(tr('update_installing', lang) + "...")
            QApplication.processEvents()

            self.zapret_updater.extract_and_update(zip_path, update_info['latest_version'])

            if hasattr(self, 'load_footer_info'):
                self.load_footer_info()
            elif hasattr(self, 'load_zapret_provider_info'):
                self.load_zapret_provider_info()

            progress.set_progress(100)
            progress.set_status(tr('update_completed', lang))
            progress.add_detail(
                tr('update_completed_text', lang).format(update_info["latest_version"])
            )
            QApplication.processEvents()

            import time
            start_time = time.time()
            while time.time() - start_time < (0.4 if auto else 1.0):
                QApplication.processEvents()
                time.sleep(0.05)
            progress.close()

            current_strategy = self._get_selected_strategy_name()
            self.load_bat_files()
            self._select_strategy_by_data(current_strategy)

            if self.settings.get('add_b_flag_on_update', False) and not is_linux():
                self.add_b_flag_to_all_strategies(silent=True)

            if self.settings.get('remove_check_updates', False):
                self.remove_check_updates_from_all_strategies(silent=True)

            if auto:
                self._finish_auto_update_status(
                    tr('update_completed_text', lang).format(update_info["latest_version"]),
                    delay_ms=4000,
                )
            else:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('update_completed', lang))
                msg.setText(tr('update_completed_text', lang).format(update_info["latest_version"]))
                msg.setIcon(QMessageBox.Icon.Information)
                msg.exec()

        except Exception as e:
            progress.close()
            if auto:
                self._finish_auto_update_status(
                    tr('update_error_text', lang).format(str(e)),
                    is_error=True,
                )
            else:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('update_error_title', lang))
                msg.setText(tr('update_error_text', lang).format(str(e)))
                msg.setIcon(QMessageBox.Icon.Critical)
                msg.exec()
        finally:
            self._finish_startup_update_block_if_done(auto=auto)
            mode = getattr(self, "_startup_update_mode", "none")
            if auto and mode == "all":
                self._keep_startup_update_block_for_app_phase()
                self._run_startup_app_check_async()

    def _show_addons_dialog(self):
        """Открывает окно «Дополнения»."""
        d = AddonsDialog(self, self.settings)
        d.exec()

    def _parse_github_repo(self, url):
        """Из URL вида https://github.com/owner/repo или https://github.com/owner/repo/ извлекает (owner, repo)."""
        if not url:
            return None, None
        url = url.strip().rstrip('/')
        m = re.match(r'https?://(?:www\.)?github\.com/([^/]+)/([^/#?]+)', url, re.IGNORECASE)
        if m:
            return m.group(1), m.group(2)
        return None, None

    def on_addon_download(self, name, url, mode="full"):
        """Скачивает дополнение: для основного репозитория запрашивает обновление zapret,
        для остальных — скачивает релиз GitHub в winws.

        mode: 'full' | 'lists' | 'strategies' | 'bin' (зарезервировано под будущие режимы установки).
        """
        lang = self.settings.get('language', 'ru')
        owner, repo = self._parse_github_repo(url)
        if not owner or not repo:
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('addons_error_download', lang).format('Некорректная ссылка на GitHub'))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        repo_slug = f"{owner}/{repo}"
        # Если это тот же репозиторий, что используется для zapret‑обновлений
        if repo_slug.lower() == getattr(self.zapret_updater, "github_repo", ZapretUpdater.GITHUB_REPO).lower():
            if has_runtime_installation():
                self.check_zapret_updates()
                return
            return self._download_and_install_zapret_direct(lang, owner, repo)
        self._download_addon_from_github(lang, name, owner, repo, mode)

    def _download_addon_from_github(self, lang, name, owner, repo, mode="full"):
        """Скачивает последний релиз/архив GitHub и распаковывает его в winws.

        mode:
          - full/strategies/bin: передаётся в zapret_updater (пока обрабатывается как полная установка)
          - lists: обновляет только winws\\lists (list-*.txt, ipset-*.txt и т.п.)
        """
        # Проверяем наличие runtime перед скачиванием (только если не списки)
        if not has_runtime_installation() and mode != "lists":
            return self._download_and_install_zapret_direct(lang, owner, repo)

        winws_running = self._is_runtime_process_running()
        if winws_running:
            reply = QMessageBox.question(
                self,
                tr('update_stopping_winws', lang),
                self._update_runtime_running_text(lang) + '\n' + tr('update_winws_stop_required', lang),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_winws_process(silent=True)
                QApplication.processEvents()
                import time
                time.sleep(3)
            else:
                return
        update_dialog = VSUpdateDialog(self, lang)
        update_dialog.set_status(tr('update_downloading', lang))
        update_dialog.show_cancel(False)
        update_dialog.show()
        QApplication.processEvents()
        try:
            download_url = None
            # Сначала пытаемся взять последний релиз
            api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
            r = requests.get(api_url, timeout=15)
            if r.status_code == 404:
                # У репозитория нет релизов — падаем обратно на архив ветки по умолчанию
                repo_api = f"https://api.github.com/repos/{owner}/{repo}"
                r_repo = requests.get(repo_api, timeout=15)
                r_repo.raise_for_status()
                repo_data = r_repo.json()
                default_branch = (repo_data.get("default_branch") or "main").strip()
                if not default_branch:
                    default_branch = "main"
                download_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{default_branch}.zip"
            else:
                r.raise_for_status()
                data = r.json()
                for asset in data.get('assets', []):
                    if asset.get('name', '').endswith('.zip'):
                        download_url = asset.get('browser_download_url')
                        break
                # Если в релизе нет zip‑ассетов, тоже пробуем архив ветки по умолчанию
                if not download_url:
                    repo_api = f"https://api.github.com/repos/{owner}/{repo}"
                    r_repo = requests.get(repo_api, timeout=15)
                    r_repo.raise_for_status()
                    repo_data = r_repo.json()
                    default_branch = (repo_data.get("default_branch") or "main").strip()
                    if not default_branch:
                        default_branch = "main"
                    download_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{default_branch}.zip"

            if not download_url:
                update_dialog.close()
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('update_error_title', lang))
                msg.setText(tr('addons_error_no_zip', lang))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
                return
            last_progress = [0]
            def progress_cb(value):
                update_dialog.set_progress(value)
                QApplication.processEvents()
            zip_path = self.zapret_updater.download_update(download_url, progress_callback=progress_cb)
            update_dialog.set_status(tr('update_installing', lang))
            QApplication.processEvents()

            # Режимы установки дополнений:
            # - lists: только winws\lists (txt-списки), без требований к .bat и игнор-листов
            # - bin: только winws\bin (бинарники), без требований к .bat и игнор-листов
            # - strategies: только .bat-стратегии в корень winws
            # - full/прочее: полное обновление через ZapretUpdater (с учётом ignore_folders)
            if mode == "lists":
                self._install_lists_from_zip(zip_path, lang, ignore_settings=False)
            elif mode == "bin":
                self._install_bin_from_zip(zip_path, lang)
            elif mode == "strategies":
                self._install_strategies_from_zip(zip_path, lang)
            else:
                # Полное обновление winws (zapret, бинарники, списки и т.д.)
                self.zapret_updater.extract_zip_to_winws(zip_path)
            update_dialog.close()
            current_strategy = self._get_selected_strategy_name()
            self.load_bat_files()
            self._select_strategy_by_data(current_strategy)
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_completed', lang))
            msg.setText(tr('addons_success', lang))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
        except Exception as e:
            update_dialog.close()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('addons_error_download', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()

    def _download_and_install_zapret_direct(self, lang, owner, repo):
        """Скачивает и устанавливает zapret напрямую (без окна настройки и проверки версии)."""
        update_dialog = VSUpdateDialog(self, lang)
        update_dialog.set_status(tr('update_downloading', lang))
        update_dialog.show_cancel(False)
        update_dialog.show()
        QApplication.processEvents()

        try:
            download_url = None
            # Сначала пытаемся взять последний релиз
            api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
            r = requests.get(api_url, timeout=15)
            if r.status_code == 404:
                # У репозитория нет релизов — падаем обратно на архив ветки по умолчанию
                repo_api = f"https://api.github.com/repos/{owner}/{repo}"
                r_repo = requests.get(repo_api, timeout=15)
                r_repo.raise_for_status()
                repo_data = r_repo.json()
                default_branch = (repo_data.get("default_branch") or "main").strip()
                if not default_branch:
                    default_branch = "main"
                download_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{default_branch}.zip"
            else:
                r.raise_for_status()
                data = r.json()
                for asset in data.get('assets', []):
                    if asset.get('name', '').endswith('.zip'):
                        download_url = asset.get('browser_download_url')
                        break
                if not download_url:
                    repo_api = f"https://api.github.com/repos/{owner}/{repo}"
                    r_repo = requests.get(repo_api, timeout=15)
                    r_repo.raise_for_status()
                    repo_data = r_repo.json()
                    default_branch = (repo_data.get("default_branch") or "main").strip()
                    if not default_branch:
                        default_branch = "main"
                    download_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{default_branch}.zip"

            if not download_url:
                update_dialog.close()
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('update_error_title', lang))
                msg.setText(tr('addons_error_no_zip', lang))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
                return

            def progress_cb(value):
                update_dialog.set_progress(value)
                QApplication.processEvents()

            zip_path = self.zapret_updater.download_update(download_url, progress_callback=progress_cb)
            update_dialog.set_status(tr('update_installing', lang))
            update_dialog.set_progress(90)
            QApplication.processEvents()

            # Используем extract_zip_to_winws (не extract_and_update, чтобы не записывать версию)
            self.zapret_updater.extract_zip_to_winws(zip_path)

            # Применяем автоматические правки (если включены)
            settings = self.config.load_settings()
            winws_folder = get_winws_path()

            # Авто-добавление /B
            if settings.get("add_b_flag_on_update", False) and os.path.isdir(winws_folder):
                try:
                    bat_files = [
                        f for f in os.listdir(winws_folder)
                        if f.lower().endswith(".bat") and os.path.isfile(os.path.join(winws_folder, f))
                    ]
                    old_string = 'start "zapret: %~n0" /min'
                    new_string = 'start "zapret: %~n0" /B /min'
                    for filename in bat_files:
                        file_path = os.path.join(winws_folder, filename)
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                            if old_string in content:
                                new_content = content.replace(old_string, new_string)
                                with open(file_path, "w", encoding="utf-8") as f:
                                    f.write(new_content)
                        except Exception:
                            continue
                except Exception:
                    pass

            # Авто-удаление check_updates
            if settings.get("remove_check_updates", False) and os.path.isdir(winws_folder):
                try:
                    bat_files = [
                        f for f in os.listdir(winws_folder)
                        if f.lower().endswith(".bat") and os.path.isfile(os.path.join(winws_folder, f))
                    ]
                    for filename in bat_files:
                        file_path = os.path.join(winws_folder, filename)
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                lines = f.readlines()
                            new_lines = []
                            modified = False
                            for line in lines:
                                stripped = line.strip().lower()
                                if (
                                    stripped == "call service.bat check_updates"
                                    or "call service.bat check_updates" in stripped
                                ):
                                    modified = True
                                    continue
                                new_lines.append(line)
                            if modified:
                                with open(file_path, "w", encoding="utf-8") as f:
                                    f.writelines(new_lines)
                        except Exception:
                            continue
                except Exception:
                    pass

            update_dialog.set_progress(100)
            update_dialog.set_status(tr('update_completed', lang))
            QApplication.processEvents()

            # Обновляем список стратегий
            current_strategy = self._get_selected_strategy_name()
            self.load_bat_files()
            self._select_strategy_by_data(current_strategy)

            update_dialog.close()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_completed', lang))
            msg.setText(tr('addons_success', lang))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
        except Exception as e:
            update_dialog.close()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('addons_error_download', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()

    def _merge_list_content(self, update_content: str, current_content: str) -> str:
        """
        Объединяет содержимое обновления с пользовательскими дополнениями.
        Строки из current, которых нет в update (по регистронезависимому сравнению),
        добавляются в конец. Дубликаты не создаются.
        """
        def _normalize(s: str) -> str:
            return s.strip().lower()

        update_lines = [line.rstrip('\r\n') for line in update_content.splitlines()]
        current_lines = [line.rstrip('\r\n') for line in current_content.splitlines()]

        update_set = set()
        for line in update_lines:
            n = _normalize(line)
            if n:
                update_set.add(n)

        user_additions = []
        seen = set(update_set)
        for line in current_lines:
            n = _normalize(line)
            if n and n not in seen:
                seen.add(n)
                user_additions.append(line)

        result_lines = update_lines
        if user_additions:
            result_lines = update_lines + [''] + user_additions
        return '\n'.join(result_lines) + ('\n' if result_lines else '')

    def _install_lists_from_zip(self, zip_path, lang, ignore_settings: bool = True):
        """Устанавливает только списки (txt-файлы) из архива в winws\\lists.
        Делает бэкап .txt в lists, скачивает обновления и объединяет с пользовательскими доменами
        без дубликатов (строки из обновления заменяют совпадающие; добавленные пользователем сохраняются).

        ignore_settings:
          - True  — обычное обновление через меню (учитывать настройки/игнорирование папок).
          - False — установка списков из дополнений (addons), всегда писать в lists,
                    даже если она есть в update_ignore_folders.
        """
        import zipfile
        import shutil

        lists_folder = self._lists_install_folder()
        os.makedirs(lists_folder, exist_ok=True)

        # При установке списков из дополнений нам не нужно отключать watcher/игнор,
        # так как операция работает только с .txt в lists.

        try:
            # 1. Бэкап существующих .txt в папке lists
            backup_folder = os.path.join(
                os.path.dirname(lists_folder),
                f"lists_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            if os.path.isdir(lists_folder):
                txt_files = [f for f in os.listdir(lists_folder) if f.lower().endswith('.txt')]
                if txt_files:
                    os.makedirs(backup_folder, exist_ok=True)
                    for f in txt_files:
                        src = os.path.join(lists_folder, f)
                        if os.path.isfile(src):
                            shutil.copy2(src, os.path.join(backup_folder, f))

            # 2. Читаем содержимое из архива и объединяем с текущими файлами
            with zipfile.ZipFile(zip_path, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    name = info.filename.replace("\\", "/")
                    if not name.lower().endswith(".txt"):
                        continue
                    base = name.split("/")[-1]
                    dest_path = os.path.join(lists_folder, base)
                    try:
                        with zf.open(info, "r") as src:
                            update_bytes = src.read()
                        update_content = update_bytes.decode("utf-8", errors="replace")

                        if os.path.isfile(dest_path):
                            with open(dest_path, "r", encoding="utf-8", errors="replace") as f:
                                current_content = f.read()
                            merged = self._merge_list_content(update_content, current_content)
                            with open(dest_path, "w", encoding="utf-8") as f:
                                f.write(merged)
                        else:
                            with open(dest_path, "w", encoding="utf-8") as f:
                                f.write(update_content)
                    except Exception:
                        continue
        except Exception as e:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('addons_error_download', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()

    def _install_bin_from_zip(self, zip_path, lang):
        """Устанавливает бинарники из архива в каталог bin."""
        import zipfile

        from src.features.tools.lib.bin_utils import get_bin_folder

        bin_folder = get_bin_folder()
        os.makedirs(bin_folder, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    name = info.filename.replace("\\", "/")
                    if not name:
                        continue
                    # Сохраняем относительную структуру из архива внутри winws\bin.
                    # Если в архиве уже есть префикс bin/, отбрасываем его.
                    parts = name.split("/", 1)
                    if parts[0].lower() == "bin" and len(parts) > 1:
                        rel_path = parts[1]
                    else:
                        rel_path = name
                    if not rel_path:
                        continue
                    dest_path = os.path.join(bin_folder, rel_path)
                    # Если файл уже существует, не трогаем его — только добавляем новые файлы «рядом».
                    if os.path.exists(dest_path):
                        continue
                    try:
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        with zf.open(info, "r") as src:
                            data = src.read()
                        with open(dest_path, "wb") as f:
                            f.write(data)
                    except Exception:
                        continue
        except Exception as e:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('addons_error_download', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()

    def _install_strategies_from_zip(self, zip_path, lang):
        """Устанавливает .bat-стратегии из архива в корень winws.
        Не требует наличия service.bat и не затрагивает другие файлы.
        """
        import zipfile
        import shutil

        winws_folder = self._strategies_install_folder()
        os.makedirs(winws_folder, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    name = info.filename.replace("\\", "/")
                    base = name.split("/")[-1]
                    if not base.lower().endswith(".bat"):
                        continue
                    dest_path = os.path.join(winws_folder, base)
                    try:
                        with zf.open(info, "r") as src:
                            data = src.read()
                        with open(dest_path, "wb") as f:
                            f.write(data)
                    except Exception:
                        continue
        except Exception as e:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('addons_error_download', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()

    def manual_update_strategies(self):
        """Обновляет стратегии вручную из выбранного архива"""
        lang = self.settings.get('language', 'ru')
        winws_folder = self._strategies_install_folder()

        # Проверяем, запущен ли runtime
        winws_running = self._is_runtime_process_running()
        
        if winws_running:
            reply = QMessageBox.question(
                self,
                tr('update_stopping_winws', lang),
                self._update_runtime_running_text(lang) + '\n' + tr('update_winws_stop_required', lang),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_winws_process(silent=True)
                import time
                time.sleep(2)
            else:
                return
        
        # Открываем диалог выбора файла
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle(tr('update_manual_select_archive', lang))
        file_dialog.setNameFilter('ZIP файлы (*.zip);;Все файлы (*.*)')
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        
        if not file_dialog.exec():
            return
        
        selected_files = file_dialog.selectedFiles()
        if not selected_files:
            return
        
        archive_path = selected_files[0]
        
        # Показываем прогресс
        progress_dialog = QProgressDialog(self)
        progress_dialog.setWindowTitle(tr('update_manual_title', lang))
        progress_dialog.setLabelText(tr('update_manual_extracting', lang))
        progress_dialog.setRange(0, 0)
        progress_dialog.setCancelButton(None)
        progress_dialog.show()
        QApplication.processEvents()
        
        try:
            # Распаковываем архив
            self.extract_archive_to_winws(archive_path, winws_folder)
            
            progress_dialog.close()
            
            # Обновляем список стратегий в ComboBox
            current_strategy = self._get_selected_strategy_name()
            self.load_bat_files()
            self._select_strategy_by_data(current_strategy)
            
            # Если включена настройка "Добавлять /B при обновлении", добавляем /B флаг
            if self.settings.get('add_b_flag_on_update', False) and not is_linux():
                self.add_b_flag_to_all_strategies(silent=True)
            
            # Если включена настройка "Удалять проверку обновлений", удаляем строку check_updates
            if self.settings.get('remove_check_updates', False):
                self.remove_check_updates_from_all_strategies(silent=True)
            
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_completed', lang))
            msg.setText(tr('update_manual_completed', lang))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            
        except Exception as e:
            progress_dialog.close()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('update_error_text', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()

    def extract_archive_to_winws(self, archive_path, winws_folder):
        """Распаковывает архив (ZIP или RAR) в папку winws"""
        import time
        import zipfile
        import shutil
        
        # Нормализуем пути до абсолютных
        winws_folder = os.path.abspath(winws_folder)
        archive_path = os.path.abspath(archive_path)
        
        # Создаем резервную копию
        backup_folder = f"{winws_folder}_backup"
        if os.path.exists(winws_folder):
            if os.path.exists(backup_folder):
                shutil.rmtree(backup_folder)
            shutil.copytree(winws_folder, backup_folder)
        
        # Ждем немного для освобождения файлов
        time.sleep(1)
        
        # Определяем тип архива
        archive_ext = os.path.splitext(archive_path)[1].lower()
        
        # Создаем временную папку для распаковки
        winws_parent = os.path.dirname(winws_folder) or os.getcwd()
        temp_extract = os.path.join(winws_parent, 'temp_manual_extract')
        if os.path.exists(temp_extract):
            shutil.rmtree(temp_extract)
        os.makedirs(temp_extract, exist_ok=True)
        
        try:
            if archive_ext == '.zip':
                # Распаковываем ZIP
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    from src.shared.lib.safe_zip import safe_extractall

                    safe_extractall(zip_ref, temp_extract)
            else:
                raise Exception(f'Неподдерживаемый формат архива: {archive_ext}. Поддерживается только ZIP формат.')
            
            # Ищем папку winws или .bat файлы в распакованном архиве
            winws_source = None
            
            # Сначала ищем папку winws или zapret-latest (Linux)
            for root, dirs, files in os.walk(temp_extract):
                if 'winws' in dirs:
                    winws_source = os.path.join(root, 'winws')
                    break
                if is_linux() and 'zapret-latest' in dirs:
                    winws_source = os.path.join(root, 'zapret-latest')
                    break
            
            # Если папки winws нет, ищем .bat файлы
            if not winws_source:
                bat_files_found = []
                for root, dirs, files in os.walk(temp_extract):
                    for file in files:
                        if file.endswith('.bat'):
                            bat_files_found.append((root, file))
                
                if bat_files_found:
                    # Определяем общую папку для всех .bat файлов
                    first_bat_dir = bat_files_found[0][0]
                    all_same_dir = all(dir_path == first_bat_dir for dir_path, _ in bat_files_found)
                    if all_same_dir:
                        winws_source = first_bat_dir
                    else:
                        winws_source = temp_extract
            
            if not winws_source:
                raise Exception('Не найдены .bat файлы или папка winws в архиве')
            
            # Обновляем файлы по одному
            if os.path.isdir(winws_source):
                # Нормализуем путь источника до абсолютного
                winws_source = os.path.abspath(winws_source)
                
                # Создаем папку winws если её нет
                if not os.path.exists(winws_folder):
                    os.makedirs(winws_folder, exist_ok=True)
                
                # Рекурсивно копируем все файлы и папки из winws_source в winws_folder
                def copy_tree(src, dst):
                    """Рекурсивно копирует дерево файлов и папок в winws, не перезатирая существующие."""
                    src = os.path.abspath(src)
                    dst = os.path.abspath(dst)
                    
                    if os.path.isdir(src):
                        # Создаём папку назначения при необходимости, но не удаляем существующую
                        os.makedirs(dst, exist_ok=True)
                        # Копируем содержимое папки, не трогая уже существующие элементы
                        for item in os.listdir(src):
                            src_item = os.path.join(src, item)
                            dst_item = os.path.join(dst, item)
                            copy_tree(src_item, dst_item)
                    else:
                        # Копируем файл только если его ещё нет в целевой winws
                        parent_dir = os.path.dirname(dst)
                        if parent_dir:
                            os.makedirs(parent_dir, exist_ok=True)
                        if os.path.exists(dst):
                            return
                        shutil.copy2(src, dst)
                
                # Копируем все содержимое
                for item in os.listdir(winws_source):
                    src_item = os.path.join(winws_source, item)
                    dst_item = os.path.join(winws_folder, item)
                    copy_tree(src_item, dst_item)
            
            # Очищаем временные файлы
            try:
                shutil.rmtree(temp_extract)
            except Exception:
                pass
                
        except Exception as e:
            # Восстанавливаем из резервной копии при ошибке
            if os.path.exists(backup_folder):
                if os.path.exists(winws_folder):
                    try:
                        shutil.rmtree(winws_folder)
                    except Exception:
                        pass
                # Используем рекурсивное копирование вместо copytree
                os.makedirs(winws_folder, exist_ok=True)
                for item in os.listdir(backup_folder):
                    src_item = os.path.join(backup_folder, item)
                    dst_item = os.path.join(winws_folder, item)
                    if os.path.isdir(src_item):
                        shutil.copytree(src_item, dst_item)
                    else:
                        shutil.copy2(src_item, dst_item)
            raise

    def update_ipset_list(self):
        """Обновляет список IPSet из репозитория"""
        import shutil

        lang = self.settings.get('language', 'ru')
        list_file = os.path.join(self._lists_install_folder(), 'ipset-all.txt')
        url = 'https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/refs/heads/main/.service/ipset-service.txt'
        
        # Показываем прогресс
        progress_dialog = QProgressDialog(self)
        progress_dialog.setWindowTitle(tr('update_ipset_list', lang))
        progress_dialog.setLabelText(tr('update_ipset_progress', lang))
        progress_dialog.setRange(0, 0)
        progress_dialog.setCancelButton(None)
        progress_dialog.show()
        QApplication.processEvents()
        
        try:
            # Создаем директорию если не существует
            os.makedirs(os.path.dirname(list_file), exist_ok=True)

            if os.name != 'nt':
                curl = shutil.which('curl') or 'curl'
                result = subprocess.run(
                    [curl, '-L', '-s', '-o', list_file, url],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    try:
                        resp = requests.get(url, timeout=30)
                        resp.raise_for_status()
                        with open(list_file, 'w', encoding='utf-8') as f:
                            f.write(resp.text)
                    except Exception as exc:
                        raise Exception(f'curl failed: {result.stderr or exc}')
            else:
                # Пробуем использовать curl
                curl_path = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'curl.exe')
                if os.path.exists(curl_path):
                    result = subprocess.run(
                        [curl_path, '-L', '-o', list_file, url],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode != 0:
                        raise Exception(f'curl failed: {result.stderr}')
                else:
                    # Используем PowerShell
                    ps_command = f'''
$url = '{url}';
$out = '{list_file}';
$dir = Split-Path -Parent $out;
if (-not (Test-Path $dir)) {{ New-Item -ItemType Directory -Path $dir | Out-Null }};
$res = Invoke-WebRequest -Uri $url -TimeoutSec 10 -UseBasicParsing;
if ($res.StatusCode -eq 200) {{ $res.Content | Out-File -FilePath $out -Encoding UTF8 }} else {{ exit 1 }}
'''
                    result = subprocess.run(
                        ['powershell', '-Command', ps_command],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode != 0:
                        raise Exception(f'PowerShell failed: {result.stderr}')
            
            progress_dialog.close()
            
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_ipset_list', lang))
            msg.setText(tr('update_ipset_success', lang))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
        except Exception as e:
            progress_dialog.close()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('update_ipset_error', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()

    def update_hosts_file(self):
        """Обновляет hosts файл из репозитория"""
        import shutil
        import tempfile

        from src.shared.lib.open_path import open_path, reveal_path_in_file_manager

        lang = self.settings.get('language', 'ru')
        if is_linux():
            hosts_file = "/etc/hosts"
        else:
            hosts_file = os.path.join(
                os.environ.get('SystemRoot', 'C:\\Windows'),
                'System32', 'drivers', 'etc', 'hosts',
            )
        hosts_url = 'https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/refs/heads/main/.service/hosts'
        temp_file = os.path.join(tempfile.gettempdir(), 'zapret_hosts.txt')
        
        # Показываем прогресс
        progress_dialog = QProgressDialog(self)
        progress_dialog.setWindowTitle(tr('update_hosts_file', lang))
        progress_dialog.setLabelText(tr('update_hosts_progress', lang))
        progress_dialog.setRange(0, 0)
        progress_dialog.setCancelButton(None)
        progress_dialog.show()
        QApplication.processEvents()
        
        try:
            if os.name != 'nt':
                curl = shutil.which('curl') or 'curl'
                result = subprocess.run(
                    [curl, '-L', '-s', '-o', temp_file, hosts_url],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    try:
                        import requests

                        resp = requests.get(hosts_url, timeout=30)
                        resp.raise_for_status()
                        with open(temp_file, 'w', encoding='utf-8') as f:
                            f.write(resp.text)
                    except Exception as exc:
                        raise Exception(f'curl failed: {result.stderr or exc}')
            else:
                curl_path = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'curl.exe')
                if os.path.exists(curl_path):
                    result = subprocess.run(
                        [curl_path, '-L', '-s', '-o', temp_file, hosts_url],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode != 0:
                        raise Exception(f'curl failed: {result.stderr}')
                else:
                    # Используем PowerShell
                    ps_command = f'''
$url = '{hosts_url}';
$out = '{temp_file}';
$res = Invoke-WebRequest -Uri $url -TimeoutSec 10 -UseBasicParsing;
if ($res.StatusCode -eq 200) {{ $res.Content | Out-File -FilePath $out -Encoding UTF8 }} else {{ exit 1 }}
'''
                    result = subprocess.run(
                        ['powershell', '-Command', ps_command],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode != 0:
                        raise Exception(f'PowerShell failed: {result.stderr}')
            
            if not os.path.exists(temp_file):
                raise Exception(tr('update_hosts_download_failed', lang))
            
            # Читаем первую и последнюю строки из скачанного файла
            with open(temp_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            
            if not lines:
                raise Exception(tr('update_hosts_file_empty', lang))
            
            first_line = lines[0]
            last_line = lines[-1]
            
            # Проверяем, нужно ли обновление
            needs_update = False
            if os.path.exists(hosts_file):
                with open(hosts_file, 'r', encoding='utf-8') as f:
                    hosts_content = f.read()
                    if first_line not in hosts_content or last_line not in hosts_content:
                        needs_update = True
            else:
                needs_update = True
            
            progress_dialog.close()
            
            if needs_update:
                msg = QMessageBox(self)
                msg.setWindowTitle(tr('update_hosts_file', lang))
                msg.setText(tr('update_hosts_needs_update', lang))
                msg.setIcon(QMessageBox.Icon.Information)
                msg.exec()

                open_path(temp_file)
                try:
                    reveal_path_in_file_manager(hosts_file)
                except Exception:
                    open_path(os.path.dirname(hosts_file))
            else:
                # Удаляем временный файл
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
                
                msg = QMessageBox(self)
                msg.setWindowTitle(tr('update_hosts_file', lang))
                msg.setText(tr('update_hosts_up_to_date', lang))
                msg.setIcon(QMessageBox.Icon.Information)
                msg.exec()
        except Exception as e:
            progress_dialog.close()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('update_hosts_error', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()

