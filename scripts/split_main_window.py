"""Split main_window source into package with mixins."""
import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'scripts', 'main_window_source.py')
OUT_PKG = os.path.join(ROOT, 'src', 'ui', 'main_window')

WORKER_CLASSES = {'_StartWorker', '_StopWorker'}

MIXIN_METHODS = {
    'ui_mixin': ['init_ui'],
    'menu_mixin': [
        'init_menu_bar', 'update_strategies_menu', 'select_strategy', 'retranslate_ui',
        'set_language', '_update_theme_menu_checked', '_apply_theme',
    ],
    'settings_mixin': [
        'toggle_show_in_tray', 'toggle_close_winws', 'toggle_start_minimized',
        'toggle_auto_start', 'toggle_auto_restart', 'toggle_autostart',
        'show_settings_dialog', '_show_settings_dialog_impl',
    ],
    'updates_mixin': [
        'check_app_updates', 'download_and_install_app_update',
        'check_zapret_updates', 'download_and_install_update',
        '_show_addons_dialog', '_parse_github_repo', 'on_addon_download',
        '_download_addon_from_github', '_download_and_install_zapret_direct',
        '_merge_list_content', '_install_lists_from_zip', '_install_bin_from_zip',
        '_install_strategies_from_zip', 'manual_update_strategies', 'extract_archive_to_winws',
        'update_ipset_list', 'update_hosts_file',
    ],
    'strategy_flags_mixin': [
        'toggle_add_b_flag_on_update', 'add_b_flag_to_all_strategies',
        'remove_b_flag_from_all_strategies', 'remove_check_updates_from_all_strategies',
        'toggle_remove_check_updates',
    ],
    'tools_mixin': [
        'show_test_window', 'on_test_strategy_changed', 'show_editor',
        'show_bin_creator', 'show_strategy_creator',
    ],
    'diagnostics_mixin': [
        'run_diagnostics', '_export_diagnostics_text', '_export_diagnostics_csv',
        '_export_diagnostics_json',
    ],
    'filters_mixin': ['update_filter_statuses', 'toggle_game_filter', 'toggle_ipset_filter'],
    'version_mixin': [
        'load_version_info', '_show_version_context_menu', '_show_contact_context_menu',
    ],
    'strategy_list_mixin': [
        'load_bat_files', '_init_winws_watcher', '_on_winws_dir_changed',
        '_get_selected_strategy_name', '_find_combo_index_by_data', '_set_combo_item_text',
        '_get_running_winws_process', '_guess_winws_root_from_process',
        '_get_running_winws_version_and_pid', '_refresh_strategy_display', '_detect_running_strategy',
    ],
    'strategy_run_mixin': [
        'restore_last_strategy', 'auto_start_strategy', 'auto_start_last_strategy',
        'restart_strategy', 'on_strategy_changed', 'toggle_action', 'start_bat_file',
        '_on_start_worker_done', '_prepare_auto_restart_apps', '_launch_pending_auto_restart_apps',
        '_handle_auto_restart_apps', '_do_stop_winws_process', 'stop_winws_process',
        '_on_stop_worker_done', 'check_winws_process',
        '_update_window_title_with_strategy', '_sync_run_state_ui',
        '_show_menu_progress_bar', '_hide_menu_progress_bar',
    ],
    'lifecycle_mixin': [
        '_is_autostart', 'minimize_to_tray', 'quit_application',
        'open_github', 'open_github_zapret', 'open_winws_folder', 'open_config_folder',
        'init_tray', 'center_window', 'showEvent', 'hideEvent', 'closeEvent',
        '_run_startup_update_check', '_on_background_update_found',
    ],
}

MIXIN_IMPORTS = {
    'ui_mixin': '''from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from src.widgets.custom_combobox import CustomComboBox
from src.shared.ui import theme
''',
    'menu_mixin': '''from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from src.shared.i18n.translator import tr
from src.entities.zapret.zapret_updater import ZapretUpdater
from src.shared.lib.path_utils import get_winws_path
from src.widgets.style_menu import StyleMenu
from src.shared.ui import theme
from src.shared.ui.window_styles import apply_window_style
import os
''',
    'settings_mixin': '''from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from src.shared.i18n.translator import tr
from src.features.settings.ui.settings_dialog import SettingsDialog
from src.shared.ui.message_box_utils import configure_message_box
''',
    'updates_mixin': '''from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from src.shared.i18n.translator import tr
from src.entities.zapret.zapret_updater import ZapretUpdater
from src.shared.lib.path_utils import get_winws_path, get_config_path
from src.features.updates.ui.vs_update_dialog import VSUpdateDialog
from src.features.winws_setup.ui.winws_setup_dialog import WinwsSetupDialog
from src.features.updates.ui.addons_dialog import AddonsDialog
from src.shared.ui.message_box_utils import configure_message_box
import os
import re
import requests
import psutil
from datetime import datetime
''',
    'strategy_flags_mixin': '''from PyQt6.QtWidgets import *
from src.shared.i18n.translator import tr
from src.shared.lib.path_utils import get_winws_path
from src.shared.ui.message_box_utils import configure_message_box
import os
''',
    'tools_mixin': '''from PyQt6.QtWidgets import *
from PyQt6.QtCore import pyqtSlot
from src.pages.test.test_window import TestWindow
from src.features.editor.ui.unified_editor_window import get_unified_editor_window
from src.features.tools.ui.bin_creator_dialog import BinCreatorDialog
''',
    'diagnostics_mixin': '''from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from src.shared.i18n.translator import tr
from src.shared.lib.path_utils import get_winws_path
from src.shared.ui.assets.embedded_assets import get_app_icon
from src.shared.ui.standard_dialog import StandardDialog
from src.widgets.custom_context_widgets import ContextTextEdit
from src.widgets.style_menu import StyleMenu
from src.shared.ui import theme
import os
import subprocess
import psutil
import winreg
import json
import csv
from datetime import datetime
''',
    'filters_mixin': '''from PyQt6.QtWidgets import *
from src.shared.i18n.translator import tr
from src.shared.ui.message_box_utils import configure_message_box
''',
    'version_mixin': '''from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from src.entities.config.config_manager import VERSION
from src.shared.i18n.translator import tr
from src.shared.ui import theme
from src.widgets.style_menu import StyleMenu
''',
    'strategy_list_mixin': '''from PyQt6.QtCore import QFileSystemWatcher
from src.shared.i18n.translator import tr
from src.shared.lib.path_utils import get_base_path, get_winws_path
import os
import psutil
''',
    'strategy_run_mixin': '''from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from src.shared.i18n.translator import tr
from src.shared.lib.path_utils import get_winws_path
from ..workers import StartWorker, StopWorker
import os
import subprocess
import psutil
import time
''',
    'lifecycle_mixin': '''from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from src.shared.i18n.translator import tr
from src.shared.lib.path_utils import get_winws_path, get_config_path
from src.entities.zapret.zapret_updater import ZapretUpdater
from src.shared.ui.system_tray import SystemTray
import os
import sys
import psutil
import threading
''',
}

METHOD_TO_MIXIN = {}
for mixin, methods in MIXIN_METHODS.items():
    for m in methods:
        METHOD_TO_MIXIN[m] = mixin


def _postprocess_strategy_run(content: str) -> str:
    return (
        content.replace('_StartWorker(', 'StartWorker(')
        .replace('_StopWorker(', 'StopWorker(')
    )


def main():
    with open(SRC, encoding='utf-8') as f:
        source = f.read()
        lines = source.splitlines(keepends=True)

    tree = ast.parse(source)
    module_items = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if node.name in WORKER_CLASSES:
                module_items.append(('workers', node.name, node.lineno, node.end_lineno))
            elif node.name == 'MainWindow':
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        name = item.name
                        mixin = METHOD_TO_MIXIN.get(name)
                        if mixin:
                            module_items.append((mixin, name, item.lineno, item.end_lineno))
                        elif name == '__init__':
                            module_items.append(('window', '__init__', item.lineno, item.end_lineno))
                    elif isinstance(item, ast.Assign):
                        module_items.append(('window', 'signal', item.lineno, item.end_lineno))

    os.makedirs(os.path.join(OUT_PKG, 'mixins'), exist_ok=True)

    with open(os.path.join(OUT_PKG, 'workers.py'), 'w', encoding='utf-8') as f:
        f.write('"""Background workers for strategy start/stop."""\n')
        f.write('from PyQt6.QtCore import QThread, pyqtSignal\nimport subprocess\nimport os\nimport time\n\n')
        w1 = ''.join(lines[40:76]).replace('class _StartWorker', 'class StartWorker')
        w2 = ''.join(lines[78:92]).replace('class _StopWorker', 'class StopWorker')
        f.write(w1)
        f.write('\n')
        f.write(w2)

    for mixin_name in MIXIN_METHODS:
        chunks = [(n, s, e) for m, n, s, e in module_items if m == mixin_name]
        if not chunks:
            continue
        class_name = ''.join(part.capitalize() for part in mixin_name.split('_'))
        body = ''
        for name, start, end in sorted(chunks, key=lambda x: x[1]):
            body += ''.join(lines[start - 1:end]) + '\n'
        if mixin_name == 'strategy_run_mixin':
            body = _postprocess_strategy_run(body)
        imports = MIXIN_IMPORTS.get(mixin_name, '')
        out = f'"""{mixin_name} methods for MainWindow."""\n{imports}\n\nclass {class_name}:\n{body}'
        with open(os.path.join(OUT_PKG, 'mixins', f'{mixin_name}.py'), 'w', encoding='utf-8') as f:
            f.write(out)

    window_chunks = [(n, s, e) for m, n, s, e in module_items if m == 'window']
    init_body = signal_body = ''
    for name, start, end in window_chunks:
        chunk = ''.join(lines[start - 1:end])
        if name == 'signal':
            signal_body = chunk
        else:
            init_body = chunk

    mro = [
        'LifecycleMixin', 'StrategyRunMixin', 'StrategyListMixin', 'UpdatesMixin',
        'SettingsMixin', 'MenuMixin', 'UiMixin', 'ToolsMixin', 'DiagnosticsMixin',
        'StrategyFlagsMixin', 'FiltersMixin', 'VersionMixin', 'StandardMainWindow',
    ]
    window_py = f'''"""Main window — assembly of feature mixins."""
from PyQt6.QtCore import QTimer, pyqtSignal, QFileSystemWatcher

from src.entities.config.config_manager import ConfigManager
from src.features.autostart.autostart_manager import AutostartManager
from src.entities.zapret.zapret_updater import ZapretUpdater
from src.features.updates.app_updater import AppUpdater
from src.entities.winws.winws_manager import WinwsManager
from src.shared.ui.assets.embedded_assets import get_app_icon
from src.shared.ui.standard_window import StandardMainWindow

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


class MainWindow(
    {",\n    ".join(mro)}
):
    {signal_body.strip()}

    {init_body.strip()}
'''
    with open(os.path.join(OUT_PKG, 'window.py'), 'w', encoding='utf-8') as f:
        f.write(window_py)

    with open(os.path.join(OUT_PKG, '__init__.py'), 'w', encoding='utf-8') as f:
        f.write('from .window import MainWindow\n\n__all__ = ["MainWindow"]\n')

    with open(os.path.join(OUT_PKG, 'mixins', '__init__.py'), 'w', encoding='utf-8') as f:
        f.write('"""Mixins for MainWindow."""\n')

    print('Generated', OUT_PKG)


if __name__ == '__main__':
    main()
