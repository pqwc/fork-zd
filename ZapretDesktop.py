import sys

if __name__ == "__main__":
    from src.app.deps_install import early_bootstrap

    early_bootstrap()

import os
import traceback
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from src.pages.main import MainWindow
from src.shared.lib.path_utils import (
    get_config_path,
    get_winws_path,
    has_runtime_installation,
    validate_linux_runtime_folder,
)
from src.shared.i18n.translator import tr
from src.entities.config.config_manager import ConfigManager
from src.shared.ui.assets.embedded_assets import get_app_icon
from src.shared.ui.assets.embedded_style import EmbeddedStyle
from src.shared.lib.app_logging import setup_logging
from src.shared.ui import theme
from src.platform import get_privilege_backend, is_linux, is_windows


_SINGLE_INSTANCE_KEY = "ZapretDesktop_SingleInstance"
_SINGLE_INSTANCE_SERVER = "ZapretDesktop_Show"


def _ping_primary_instance(server_name: str = _SINGLE_INSTANCE_SERVER) -> bool:
    """Проверяет, отвечает ли уже запущенный экземпляр приложения."""
    sock = QLocalSocket()
    sock.connectToServer(server_name, QLocalSocket.OpenModeFlag.ReadWrite)
    if not sock.waitForConnected(800):
        return False
    sock.write(b"show")
    sock.flush()
    sock.waitForBytesWritten(500)
    sock.disconnectFromServer()
    if sock.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        sock.waitForDisconnected(500)
    return True


def _check_single_instance(*, force_reset: bool = False):
    """Проверка одного экземпляра. Возвращает (exit_this_process, shared_memory_to_keep)."""
    from PyQt6.QtCore import QSharedMemory

    if force_reset:
        QLocalServer.removeServer(_SINGLE_INSTANCE_SERVER)
        stale = QSharedMemory(_SINGLE_INSTANCE_KEY)
        if stale.attach():
            stale.detach()

    shared = QSharedMemory(_SINGLE_INSTANCE_KEY)
    if shared.create(1):
        return (False, shared)

    if shared.attach():
        if _ping_primary_instance():
            return (True, None)
        shared.detach()
        if shared.create(1):
            return (False, shared)

    if shared.create(1):
        return (False, shared)

    stale = QSharedMemory(_SINGLE_INSTANCE_KEY)
    if stale.attach():
        stale.detach()
    shared = QSharedMemory(_SINGLE_INSTANCE_KEY)
    if shared.create(1):
        return (False, shared)

    return (False, None)


def run_as_admin():
    """Перезапускает программу с правами администратора (Windows)."""
    priv = get_privilege_backend()
    if priv.is_elevated():
        return True
    if priv.request_elevation():
        # Elevated-процесс запущен — текущий экземпляр завершается без ошибки.
        return False
    try:
        app = QApplication(sys.argv)

        config = ConfigManager()
        settings = config.load_settings()
        lang = settings.get('language', 'ru')

        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_app_icon())
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(tr('admin_error_title', lang))
        msg_box.setText(tr('admin_error_text', lang).format("elevation failed"))
        msg_box.exec()
    except Exception:
        pass
    return False
 

def main():
    from src.app.launch_options import get_launch_options, parse_launch_options

    if is_linux():
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication

        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    launch = parse_launch_options()

    if launch.full_reset:
        from src.app.launch_recovery import perform_full_reset
        from src.app.launch_options import mark_full_reset_consumed

        perform_full_reset()
        mark_full_reset_consumed()
        launch = get_launch_options()

    priv = get_privilege_backend()
    if priv.requires_elevation_for_gui() and not priv.is_elevated():
        app = QApplication(sys.argv)
        
        config = ConfigManager()
        settings = config.load_settings()
        lang = settings.get('language', 'ru')
        
        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_app_icon())
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle(tr('admin_required_title', lang))
        msg_box.setText(tr('admin_required_text', lang))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        reply = msg_box.exec()
        
        if reply == QMessageBox.StandardButton.Yes:
            if not run_as_admin():
                sys.exit(0)
            else:
                sys.exit(0)
        else:
            sys.exit(0)
    
    app = QApplication(sys.argv)
    if is_linux():
        from src.shared.lib.qt_platform import configure_qt_desktop_file_name

        configure_qt_desktop_file_name()
    setup_logging()

    from src.shared.ui.assets.codicons_manager import ensure_codicons

    ensure_codicons(blocking=True)

    app.setStyle(EmbeddedStyle('Fusion'))
    app.setApplicationName('ZapretDesktop')
    app.setOrganizationName('ZapretDesktop')

    # Тема из настроек (до создания окна)
    config = ConfigManager()
    settings = config.load_settings()
    theme_value = settings.get('color_theme', 'dark')
    theme.set_theme(theme_value)
    theme.apply_application_theme(app)

    from src.widgets.custom_scrollbar import ScrollbarStyler
    ScrollbarStyler.apply_scrollbar_style(app, fade_timeout=1000)
    app.setQuitOnLastWindowClosed(False)
    font_family = get_privilege_backend().get_ui_font_family()
    app.setFont(QFont(font_family, 9))

    # Один экземпляр: при повторном запуске поднимаем существующее окно и выходим
    exit_process, single_instance_shared = _check_single_instance(
        force_reset=launch.reset_single_instance,
    )
    if exit_process:
        sys.exit(0)
    # single_instance_shared держим до конца работы приложения

    runtime_path = get_winws_path()
    if is_linux():
        if not validate_linux_runtime_folder(runtime_path)[0] and not launch.skip_winws_setup:
            from src.features.linux_runtime.ui.linux_runtime_setup_dialog import LinuxRuntimeSetupDialog

            setup_dialog = LinuxRuntimeSetupDialog(None, config)
            if setup_dialog.exec() != QDialog.DialogCode.Accepted:
                pass  # можно продолжить без runtime — функции будут заглушены
    elif not has_runtime_installation() and not launch.skip_winws_setup:
        from src.features.winws_setup.ui.winws_setup_dialog import WinwsSetupDialog

        setup_dialog = WinwsSetupDialog(None, config)
        if setup_dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)

    window = MainWindow()

    # Локальный сервер: второй экземпляр подключается и просит показать окно
    single_instance_server = QLocalServer()
    def on_show_request():
        conn = single_instance_server.nextPendingConnection()
        if conn:
            conn.disconnectFromServer()
            if conn.state() != QLocalSocket.LocalSocketState.UnconnectedState:
                conn.waitForDisconnected(300)
        if window.isMinimized() or not window.isVisible():
            window.show()
            window.raise_()
            window.activateWindow()
        else:
            window.raise_()
            window.activateWindow()
    single_instance_server.newConnection.connect(on_show_request)
    QLocalServer.removeServer(_SINGLE_INSTANCE_SERVER)
    single_instance_server.listen(_SINGLE_INSTANCE_SERVER)

    _install_runtime_crash_handler()
    sys.exit(app.exec())


def _prepare_crash_ui(app: QApplication) -> str:
    """Тема и язык для окна критической ошибки."""
    lang = "ru"
    try:
        config = ConfigManager()
        settings = config.load_settings()
        lang = settings.get("language", "ru")
        theme_value = settings.get("color_theme", "dark")
        theme.set_theme(theme_value)
        theme.apply_application_theme(app)
        app.setStyle(EmbeddedStyle("Fusion"))
        font_family = get_privilege_backend().get_ui_font_family()
        app.setFont(QFont(font_family, 9))
    except Exception:
        theme.set_theme("dark")
        theme.apply_application_theme(app)
    return lang


def _install_runtime_crash_handler() -> None:
    """Ловит необработанные исключения во время Qt event loop (app.exec)."""
    if getattr(_install_runtime_crash_handler, "_installed", False):
        return
    _install_runtime_crash_handler._installed = True
    previous_hook = sys.excepthook

    def runtime_excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            previous_hook(exc_type, exc_value, exc_tb)
            return
        try:
            error_traceback = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            show_critical_error(None, exc_value, error_traceback)
        except Exception:
            previous_hook(exc_type, exc_value, exc_tb)
        else:
            previous_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = runtime_excepthook


def show_critical_error(parent, error_msg, detailed_text):
    """Показывает окно критической ошибки в стиле редактора."""
    from src.app.critical_error_dialog import CriticalErrorDialog

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    lang = _prepare_crash_ui(app)
    dialog = CriticalErrorDialog(
        parent,
        lang=lang,
        summary=str(error_msg),
        traceback_text=detailed_text or "",
    )
    dialog.exec()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        error_traceback = traceback.format_exc()
        show_critical_error(None, error, error_traceback)
        sys.exit(1)
