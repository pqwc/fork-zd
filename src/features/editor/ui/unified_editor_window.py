"""
Объединённое окно редакторов: списки winws/lists, файлы drivers\\etc и стратегии (.bat).
QTabWidget, в каждой вкладке: QLineEdit (поиск), QListWidget, QSplitter, QPlainTextEdit.
"""

import os
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import QFont, QAction, QKeySequence, QShortcut, QTextCursor, QTextDocument
from src.shared.i18n.translator import tr
from src.shared.lib.path_utils import get_winws_path
from src.features.editor.lib.editor_paths import (
    bat_run_terminal_command,
    get_editor_bat_setup,
    get_editor_lists_folder,
    resolve_editor_file_path,
)
from src.features.editor.lib.embedded_terminal import EmbeddedTerminal
from src.shared.lib.open_path import open_path, reveal_path_in_file_manager
from src.shared.lib.shell_launcher import launch_file_in_shell, launch_shell_in_directory
from src.shared.lib.text_encoding import read_text_file
from src.features.editor.lib.editor_prompts import prompt_unsaved_file_action
from src.shared.ui.standard_dialog import StandardDialog
from src.features.editor.ui.find_replace_dialog import FindReplaceDialog
from src.features.editor.ui.find_in_files_dialog import FindInFilesDialog
from src.features.editor.ui.country_blocklist_dialog import CountryBlocklistDialog
from src.features.editor.ui.domain_variants_dialog import DomainVariantsDialog
from src.features.editor.lib.line_number_editor import LineNumberPlainTextEdit
from src.widgets.style_menu import StyleMenu
from src.widgets.custom_context_widgets import ContextLineEdit
from src.widgets.label_menu_widget import LabelMenuWidget
from src.widgets.breadcrumb_widget import BreadcrumbWidget
from src.features.editor.lib.editor_highlighters import ListHighlighter, EtcHighlighter, BatHighlighter
from src.features.editor.lib.editor_autocomplete import EditorAutocomplete
from src.shared.ui import theme

_EDITOR_TAB_ICONS = ("list-tree", "file-code", "terminal")


class _EditorTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setExpanding(False)
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


def get_etcdrivers_folder():
    from src.platform import is_linux

    if is_linux():
        return "/etc"
    system_root = os.environ.get('SystemRoot', 'C:\\Windows')
    return os.path.join(system_root, 'System32', 'drivers', 'etc')


def get_etc_file_names():
    from src.platform import is_linux

    if is_linux():
        return ['hosts']
    return ['hosts', 'lmhosts', 'networks', 'protocol', 'services']


LIST_FILES = ['list-general.txt', 'list-exclude.txt', 'list-google.txt', 'ipset-all.txt', 'ipset-exclude.txt']
ETC_FILES = ['hosts', 'lmhosts', 'networks', 'protocol', 'services']


def get_bat_files(winws_folder):
    _cwd, names, _paths = get_editor_bat_setup()
    return names


class EditorTabContent(QWidget):
    """Одна вкладка: фильтр (QLineEdit), список файлов (QListWidget), редактор (QPlainTextEdit) в QSplitter."""
    
    def __init__(
        self,
        parent,
        folder,
        file_names,
        language='ru',
        is_lists_tab=False,
        tab_kind='lists',
        file_paths=None,
    ):
        super().__init__(parent)
        self.folder = folder
        self.file_names = list(file_names)
        self.file_paths = dict(file_paths or {})
        self.language = language
        self.is_lists_tab = is_lists_tab
        self.tab_kind = tab_kind
        self._current_file = self.file_names[0] if self.file_names else ''
        self.is_saving = False
        self.file_watcher = QFileSystemWatcher(self)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.auto_save_file)

        self._build_ui()

        self._last_status = ''
        self._last_line = 1
        self._last_col = 1
        
        if self.file_names:
            self.file_list.setCurrentRow(0)
        
        for f in self.file_names:
            path = resolve_editor_file_path(self.folder, f, self.file_paths)
            if os.path.exists(path):
                try:
                    self.file_watcher.addPath(path)
                except Exception:
                    pass
        self.file_watcher.fileChanged.connect(self.on_file_changed_externally)
        # Отслеживание добавления/удаления файлов в папке.
        # Для вкладки lists не вешаем watcher на саму папку, чтобы избежать
        # ошибок FindNextChangeNotification/Access Denied на winws\\lists.
        if os.path.isdir(self.folder) and self.tab_kind != 'lists':
            try:
                self.file_watcher.addPath(self.folder)
                self.file_watcher.directoryChanged.connect(self._on_directory_changed)
            except Exception:
                pass
        self._dir_refresh_timer = QTimer(self)
        self._dir_refresh_timer.setSingleShot(True)
        self._dir_refresh_timer.timeout.connect(self._refresh_file_list_from_disk)

    @staticmethod
    def _make_block(object_name: str) -> QFrame:
        return theme.create_editor_block(object_name)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 12)
        root.setSpacing(0)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        theme.configure_invisible_splitter(main_splitter)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([248, 620])

        root.addWidget(main_splitter, 1)

    def _build_left_panel(self) -> QWidget:
        container = QWidget()
        container.setMinimumWidth(200)
        container.setMaximumWidth(360)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.filter_edit = ContextLineEdit()
        self.filter_edit.setFixedHeight(26)
        self.filter_edit.setStyleSheet(theme.editor_search_field_style())
        self.filter_edit.setPlaceholderText(tr("editor_list_search_placeholder", self.language))
        self.filter_edit.textChanged.connect(self.apply_filter)
        layout.addWidget(self.filter_edit)

        list_block = self._make_block("EditorListBlock")
        list_layout = QVBoxLayout(list_block)
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(0)

        self.file_list = QListWidget()
        self.file_list.setStyleSheet(theme.editor_file_list_style())
        self.file_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.file_list.setSpacing(0)
        self.file_list.setAlternatingRowColors(False)
        self.file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._on_file_list_context_menu)
        for name in self.file_names:
            self.file_list.addItem(name)
        self.file_list.currentItemChanged.connect(self._on_file_list_item_changed)

        self._left_list_stack = QStackedWidget()
        self._left_list_stack.addWidget(self.file_list)

        nothing_widget = QWidget()
        nothing_layout = QVBoxLayout(nothing_widget)
        nothing_layout.setContentsMargins(0, 0, 0, 0)
        nothing_label = QLabel(tr("settings_nothing_found", self.language))
        nothing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nothing_label.setStyleSheet(theme.nothing_found_style())
        nothing_layout.addWidget(nothing_label)
        self._left_list_stack.addWidget(nothing_widget)
        self._left_list_stack.setCurrentIndex(0)

        list_layout.addWidget(self._left_list_stack, 1)

        layout.addWidget(list_block, 1)
        return container

    def _build_editor_widget(self) -> LineNumberPlainTextEdit:
        editor = LineNumberPlainTextEdit()
        editor.setFrameShape(QFrame.Shape.NoFrame)
        editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        theme.apply_editor_text_widget(editor)
        editor.setFont(QFont("Consolas", 10))
        font_metrics = editor.fontMetrics()
        editor.setTabStopDistance(4 * font_metrics.horizontalAdvance(" "))
        self.tab_size = 4
        self.encoding = "UTF-8"
        self.line_ending = "CRLF"
        if self.tab_kind == "lists":
            self._highlighter = ListHighlighter(editor.document())
        elif self.tab_kind == "etc":
            self._highlighter = EtcHighlighter(editor.document())
        else:
            self._highlighter = BatHighlighter(editor.document())
        self._autocomplete = EditorAutocomplete(editor, tab_kind=self.tab_kind)
        editor.textChanged.connect(self.on_text_changed)
        editor.cursorPositionChanged.connect(self.on_cursor_position_changed)
        editor.cursorPositionChanged.connect(self._on_editor_cursor_changed)
        editor.installEventFilter(self)
        return editor

    def _build_right_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.editor = self._build_editor_widget()

        if self.tab_kind == "bat":
            layout.addWidget(self._build_bat_workspace(), 1)
        elif self.tab_kind == "etc":
            layout.addWidget(self._build_etc_workspace(), 1)
        else:
            code_block = self._make_block("EditorCodeBlock")
            code_layout = QVBoxLayout(code_block)
            code_layout.setContentsMargins(0, 0, 0, 0)
            code_layout.setSpacing(0)
            code_layout.addWidget(self.editor, 1)
            layout.addWidget(code_block, 1)

        return container

    def _build_bat_workspace(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Vertical)
        theme.configure_invisible_splitter(splitter)

        code_block = self._make_block("EditorCodeBlock")
        code_layout = QVBoxLayout(code_block)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_layout.setSpacing(0)
        code_layout.addWidget(self.editor, 1)
        splitter.addWidget(code_block)

        terminal = self._make_block("EditorTerminalPanel")
        terminal_layout = QVBoxLayout(terminal)
        terminal_layout.setContentsMargins(0, 0, 0, 0)
        terminal_layout.setSpacing(0)

        def _register_pid(pid: int) -> None:
            win = self.window()
            if hasattr(win, "_register_terminal_pid"):
                win._register_terminal_pid(pid)

        self._terminal = EmbeddedTerminal(
            self,
            working_directory=self.folder,
            language=self.language,
            register_pid=_register_pid,
        )
        self._terminal.start()
        self._terminal.output_appended.connect(
            lambda: setattr(self, '_cmd_input_start', self._terminal.input_start)
        )
        self.command_console = self._terminal.console
        self.cmd_label = self._terminal._header
        self.cmd_process = self._terminal._process
        self._cmd_input_start = 0
        self._cmd_cursor_fixing = False
        self.command_console.installEventFilter(self)
        self.command_console.cursorPositionChanged.connect(self._on_cmd_cursor_changed)
        self.command_console.cursorPositionChanged.connect(self._on_cmd_status_update)
        terminal_layout.addWidget(self._terminal, 1)

        splitter.addWidget(terminal)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 180])
        return splitter

    def _build_etc_workspace(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        theme.configure_invisible_splitter(splitter)

        code_block = self._make_block("EditorCodeBlock")
        code_layout = QVBoxLayout(code_block)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_layout.setSpacing(0)
        code_layout.addWidget(self.editor, 1)
        splitter.addWidget(code_block)

        hosts_panel = self._make_block("EditorHostsBlock")
        hosts_layout = QVBoxLayout(hosts_panel)
        hosts_layout.setContentsMargins(0, 0, 0, 0)
        hosts_layout.setSpacing(0)

        self.zapret_hosts_label = QLabel("zapret_hosts.txt")
        self.zapret_hosts_label.setStyleSheet(theme.editor_terminal_header_style())
        hosts_layout.addWidget(self.zapret_hosts_label)

        self.zapret_hosts_view = QPlainTextEdit()
        self.zapret_hosts_view.setReadOnly(True)
        self.zapret_hosts_view.setFrameShape(QFrame.Shape.NoFrame)
        theme.apply_editor_text_widget(self.zapret_hosts_view)
        self.zapret_hosts_view.setFont(QFont("Consolas", 9))
        hosts_layout.addWidget(self.zapret_hosts_view, 1)

        splitter.addWidget(hosts_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([480, 280])
        return splitter
    
    def refresh_theme(self):
        """Обновляет inline-стили вкладки после смены темы."""
        theme.refresh_editor_blocks(self)
        if hasattr(self, "filter_edit"):
            self.filter_edit.setStyleSheet(theme.editor_search_field_style())
        if hasattr(self, "file_list"):
            self.file_list.setStyleSheet(theme.editor_file_list_style())
        if hasattr(self, "editor"):
            theme.apply_editor_text_widget(self.editor)
            self.editor.refresh_editor_colors()
        if hasattr(self, "_highlighter") and hasattr(self._highlighter, "refresh_theme"):
            self._highlighter.refresh_theme()
        if hasattr(self, "_terminal"):
            self._terminal.refresh_theme()
        elif hasattr(self, "cmd_label"):
            self.cmd_label.setStyleSheet(theme.editor_terminal_header_style())
        if hasattr(self, "command_console") and not hasattr(self, "_terminal"):
            if not getattr(self.command_console, "_line_number_bg_override", None):
                theme.apply_editor_text_widget(self.command_console)
            self.command_console.refresh_editor_colors()
        if hasattr(self, "zapret_hosts_view"):
            theme.apply_editor_text_widget(self.zapret_hosts_view)
        if hasattr(self, "zapret_hosts_label"):
            self.zapret_hosts_label.setStyleSheet(theme.editor_terminal_header_style())

    def _on_directory_changed(self):
        """Папка изменилась — обновляем список файлов с небольшой задержкой (debounce)."""
        self._dir_refresh_timer.stop()
        self._dir_refresh_timer.start(300)

    def _get_files_from_disk(self):
        """Возвращает актуальный список файлов из папки в зависимости от вкладки."""
        if self.tab_kind == 'bat':
            cwd, names, paths = get_editor_bat_setup()
            self.folder = cwd
            self.file_paths = paths
            return names
        if not os.path.isdir(self.folder):
            return []
        if self.tab_kind == 'lists':
            try:
                files = [f for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f))]
                ordered = [f for f in LIST_FILES if f in files]
                others = sorted(f for f in files if f not in LIST_FILES)
                return ordered + others
            except OSError:
                return list(self.file_names)
        if self.tab_kind == 'etc':
            return [f for f in get_etc_file_names() if os.path.isfile(os.path.join(self.folder, f))]
        return list(self.file_names)

    def _refresh_file_list_from_disk(self):
        """Обновляет QListWidget и file_names по содержимому папки."""
        new_names = self._get_files_from_disk()
        if new_names == self.file_names:
            return
        current = self.file_list.currentItem()
        current_name = current.text() if current else self._current_file
        filter_text = self.filter_edit.text() if hasattr(self, 'filter_edit') else ''

        # Обновляем file_watcher: убираем старые пути к файлам
        for p in self.file_watcher.files():
            try:
                self.file_watcher.removePath(p)
            except Exception:
                pass

        self.file_names = new_names
        self.file_list.blockSignals(True)
        try:
            self.file_list.clear()
            for name in self.file_names:
                self.file_list.addItem(name)

            # Восстанавливаем выбор
            idx = -1
            for i, name in enumerate(self.file_names):
                if name == current_name:
                    idx = i
                    break
            if idx >= 0:
                self.file_list.setCurrentRow(idx)
                self._current_file = current_name
            elif self.file_names:
                self.file_list.setCurrentRow(0)
                self._current_file = self.file_names[0]
        finally:
            self.file_list.blockSignals(False)

        # Добавляем пути к файлам в watcher
        for f in self.file_names:
            path = resolve_editor_file_path(self.folder, f, self.file_paths)
            if os.path.exists(path):
                try:
                    self.file_watcher.addPath(path)
                except Exception:
                    pass

        self.apply_filter(filter_text)
        # Не перезагружаем текущий файл — список обновился, редактор остаётся без изменений

    def apply_filter(self, text):
        text = text.strip().lower()
        visible_count = 0
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            name = item.text().lower()
            visible = not text or text in name
            item.setHidden(not visible)
            if visible:
                visible_count += 1

        # Переключаемся на виджет «Ничего не найдено», если фильтр есть и видимых элементов нет
        if hasattr(self, '_left_list_stack'):
            if text and visible_count == 0:
                self._left_list_stack.setCurrentIndex(1)
                self.file_list.setCurrentRow(-1)
            else:
                self._left_list_stack.setCurrentIndex(0)
                # Если есть фильтр и текущий элемент не выбран, выбираем первый видимый
                if text and self.file_list.currentRow() < 0:
                    for i in range(self.file_list.count()):
                        if not self.file_list.item(i).isHidden():
                            self.file_list.setCurrentRow(i)
                            break

    def _on_file_list_context_menu(self, pos):
        """Контекстное меню по списку файлов слева."""
        item = self.file_list.itemAt(pos)
        menu = StyleMenu(self.file_list)

        action_open_folder = menu.addAction(tr('lists_editor_open_folder', self.language))

        # Создать файл через родительское окно, если есть такой метод
        win = self.window()
        can_create = hasattr(win, 'create_new_file')
        if can_create:
            action_create = menu.addAction(tr('editor_create_file', self.language))
        else:
            action_create = None

        # Удаление файла разрешаем только для списков и bat
        can_delete = bool(item) and getattr(self, 'tab_kind', '') in ('lists', 'bat')
        if can_delete:
            menu.addSeparator()
            action_delete = menu.addAction(tr('editor_delete_file', self.language))
        else:
            action_delete = None

        global_pos = self.file_list.mapToGlobal(pos)
        chosen = menu.exec(global_pos)
        if not chosen:
            return

        if chosen is action_open_folder:
            self.open_folder()
            return

        if chosen is action_create and can_create:
            win.create_new_file()
            return

        if chosen is action_delete and can_delete:
            filename = item.text()
            path = resolve_editor_file_path(self.folder, filename, self.file_paths)
            reply = QMessageBox.question(
                self,
                tr('msg_confirm', self.language),
                tr('editor_delete_file_confirm', self.language).format(filename),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            try:
                if os.path.exists(path):
                    try:
                        self.file_watcher.removePath(path)
                    except Exception:
                        pass
                    os.remove(path)
                row = self.file_list.row(item)
                self.file_list.takeItem(row)
                if self.file_list.count() > 0:
                    self.file_list.setCurrentRow(max(0, row - 1))
                else:
                    self._current_file = ''
                    self.editor.clear()
            except Exception as e:
                QMessageBox.warning(self, tr('msg_error', self.language), str(e))
    
    def get_current_file_path(self):
        cur = self.file_list.currentItem()
        if not cur:
            return resolve_editor_file_path(self.folder, self._current_file, self.file_paths) if self._current_file else ''
        return resolve_editor_file_path(self.folder, cur.text(), self.file_paths)
    
    def get_current_editor(self):
        """Возвращает активный редактор: при фокусе на CMD-консоли — консоль, иначе основной редактор."""
        if getattr(self, 'tab_kind', '') == 'bat' and hasattr(self, 'command_console') and self.command_console.hasFocus():
            return self.command_console
        return self.editor
    
    def load_current_file(self):
        path = self.get_current_file_path()
        if not path or not os.path.basename(path):
            return
        try:
            if os.path.exists(path):
                encoding_map = {'UTF-8': 'utf-8', 'UTF-8 BOM': 'utf-8-sig', 'Windows-1251': 'windows-1251'}
                preferred = encoding_map.get(self.encoding, 'utf-8')
                content, _, decode_issues = read_text_file(
                    path,
                    encoding=preferred,
                )
                if decode_issues:
                    QMessageBox.warning(
                        self.window() if self.window() else self,
                        tr('msg_error', self.language),
                        tr('editor_encoding_loss_warning', self.language),
                    )
            else:
                content = ''
                if self.is_lists_tab:
                    os.makedirs(self.folder, exist_ok=True)
            self.editor.blockSignals(True)
            self.editor.setPlainText(content)
            self.editor.blockSignals(False)
            self.editor.document().setModified(False)
            self.editor.refresh_line_number_area()
            self.save_timer.stop()
            self._last_status = tr('targets_saved', self.language)
            self._push_status()
            self.on_cursor_position_changed()
            # Обновляем подсветку текущей строки сразу после загрузки файла
            if hasattr(self.editor, "_on_cursor_position_changed"):
                self.editor._on_cursor_position_changed()
            self._on_editor_cursor_changed()
            # Обновляем заголовок окна после загрузки файла
            win = self.window()
            if win is not self and hasattr(win, '_update_window_title'):
                win._update_window_title()

            # Если это вкладка etc — обновляем просмотр zapret_hosts.txt при открытом hosts
            if getattr(self, 'tab_kind', '') == 'etc' and hasattr(self, 'zapret_hosts_view'):
                self._update_zapret_hosts_view()
        except Exception as e:
            QMessageBox.warning(self, tr('test_error_title', self.language),
                f"{tr('targets_error_loading', self.language)}: {str(e)}")
    
    def save_current_file(self):
        path = self.get_current_file_path()
        if not path:
            return
        try:
            self.is_saving = True
            content = self.editor.toPlainText()
            # Конвертируем окончания строк в выбранный формат
            if self.line_ending == 'CRLF':
                content = content.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
            elif self.line_ending == 'LF':
                content = content.replace('\r\n', '\n').replace('\r', '\n')
            elif self.line_ending == 'CR':
                content = content.replace('\r\n', '\n').replace('\n', '\r')
            if os.path.exists(path):
                try:
                    self.file_watcher.removePath(path)
                except Exception:
                    pass
            if self.is_lists_tab:
                os.makedirs(self.folder, exist_ok=True)
            # Используем выбранную кодировку
            encoding_map = {'UTF-8': 'utf-8', 'UTF-8 BOM': 'utf-8-sig', 'Windows-1251': 'windows-1251'}
            encoding = encoding_map.get(self.encoding, 'utf-8')
            with open(path, 'w', encoding=encoding, newline='') as f:
                if self.encoding == 'UTF-8 BOM':
                    f.write('\ufeff')
                f.write(content)
            if os.path.exists(path):
                try:
                    self.file_watcher.addPath(path)
                except Exception:
                    pass
            self.editor.document().setModified(False)
            self.save_timer.stop()
            self._last_status = tr('targets_saved', self.language)
            self._push_status()
            self._on_editor_cursor_changed()
            # При сохранении hosts можно тоже обновить просмотр zapret_hosts.txt (если нужно)
            if getattr(self, 'tab_kind', '') == 'etc' and hasattr(self, 'zapret_hosts_view'):
                self._update_zapret_hosts_view()
            # Обновляем заголовок окна после сохранения файла
            win = self.window()
            if win is not self and hasattr(win, '_update_window_title'):
                win._update_window_title()
        except PermissionError:
            QMessageBox.warning(self, tr('msg_error', self.language),
                tr('etcdrivers_save_admin_required', self.language))
        except Exception as e:
            QMessageBox.warning(self, tr('test_error_title', self.language),
                f"{tr('targets_error_saving', self.language)}: {str(e)}")
        finally:
            self.is_saving = False
    
    def set_tab_size(self, size):
        """Устанавливает размер табуляции (в пробелах)."""
        self.tab_size = size
        font_metrics = self.editor.fontMetrics()
        self.editor.setTabStopDistance(size * font_metrics.horizontalAdvance(' '))
    
    def set_encoding(self, encoding):
        """Устанавливает кодировку файла."""
        self.encoding = encoding
    
    def set_line_ending(self, line_ending):
        """Устанавливает окончания строк."""
        self.line_ending = line_ending
    
    def auto_save_file(self):
        if self.is_saving:
            return
        self.save_current_file()
    
    def _on_file_list_item_changed(self, current, previous):
        filename = current.text() if current else ''
        self.on_file_selected(filename)
    
    def on_file_selected(self, filename):
        if not filename:
            return
        if self.editor.document().isModified():
            action = prompt_unsaved_file_action(
                self.window() if self.window() else self,
                self.language,
                filename=self._current_file or filename,
            )
            if action == "cancel":
                for i in range(self.file_list.count()):
                    if self.file_list.item(i).text() == self._current_file:
                        self.file_list.blockSignals(True)
                        self.file_list.setCurrentRow(i)
                        self.file_list.blockSignals(False)
                        break
                return
            if action == "save":
                self.save_current_file()
        self._current_file = filename
        self.load_current_file()
    
    def on_text_changed(self):
        self.save_timer.stop()
        self.save_timer.start(1000)
        self._on_editor_cursor_changed()
    
    def on_file_changed_externally(self, path):
        if self.is_saving:
            return
        if path == self.get_current_file_path():
            if self.save_timer.isActive():
                self.save_timer.stop()
                self.auto_save_file()
                return
            if self.editor.document().isModified():
                reply = QMessageBox.question(
                    self, tr('test_error_title', self.language),
                    tr('targets_unsaved_changes', self.language),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            self.load_current_file()
        if os.path.exists(path) and path not in self.file_watcher.files():
            try:
                self.file_watcher.addPath(path)
            except Exception:
                pass

    
    def on_cursor_position_changed(self):
        line, col = self.editor.get_cursor_position()
        self._last_line, self._last_col = line, col
        self._push_status()
    
    def _on_editor_cursor_changed(self):
        """Обновляет состояние действий меню при изменении курсора."""
        win = self.window()
        if win is not self and hasattr(win, '_update_actions_state'):
            win._update_actions_state()
    
    def _push_status(self):
        """Обновляет статус-бар родительского окна."""
        win = self.window()
        if win is not self and hasattr(win, 'update_editor_status'):
            win.update_editor_status(self._last_status, self._last_line, self._last_col)

    def _download_zapret_hosts(self, zapret_path: str) -> bool:
        """Скачивает zapret hosts в указанный путь. Возвращает True при успехе."""
        import shutil

        hosts_url = 'https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/refs/heads/main/.service/hosts'
        try:
            if os.name != 'nt':
                curl = shutil.which('curl') or 'curl'
                r = subprocess.run(
                    [curl, '-L', '-s', '-o', zapret_path, hosts_url],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if r.returncode == 0 and os.path.exists(zapret_path):
                    return True
                try:
                    import requests

                    resp = requests.get(hosts_url, timeout=30)
                    resp.raise_for_status()
                    with open(zapret_path, 'w', encoding='utf-8') as f:
                        f.write(resp.text)
                    return True
                except Exception:
                    return False
            curl_path = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'curl.exe')
            if os.path.exists(curl_path):
                r = subprocess.run([curl_path, '-L', '-s', '-o', zapret_path, hosts_url], capture_output=True, text=True, timeout=30)
                if r.returncode == 0 and os.path.exists(zapret_path):
                    return True
            ps = f"Invoke-WebRequest -Uri '{hosts_url}' -TimeoutSec 15 -UseBasicParsing | Select-Object -ExpandProperty Content | Out-File -FilePath '{zapret_path}' -Encoding UTF8"
            r = subprocess.run(['powershell', '-Command', ps], capture_output=True, text=True, timeout=30)
            return r.returncode == 0 and os.path.exists(zapret_path)
        except Exception:
            return False

    def _update_zapret_hosts_view(self):
        """Обновляет нижний просмотр zapret_hosts.txt для вкладки etc и файла hosts."""
        if getattr(self, 'tab_kind', '') != 'etc' or not hasattr(self, 'zapret_hosts_view'):
            return
        current_name = self.file_list.currentItem().text() if self.file_list.currentItem() else self._current_file
        if not current_name or current_name.lower() != 'hosts':
            self.zapret_hosts_view.clear()
            return
        import tempfile

        temp_dir = tempfile.gettempdir()
        zapret_path = os.path.join(temp_dir, 'zapret_hosts.txt')
        if not os.path.exists(zapret_path) and not self._download_zapret_hosts(zapret_path):
            self.zapret_hosts_view.setPlainText(tr('msg_zapret_hosts_not_found', self.language))
            return
        try:
            with open(zapret_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            self.zapret_hosts_view.setPlainText(content)
            self.zapret_hosts_view.moveCursor(self.zapret_hosts_view.textCursor().MoveOperation.Start)
        except Exception as e:
            self.zapret_hosts_view.setPlainText(f"Ошибка чтения zapret_hosts.txt:\n{e}")

    def _on_cmd_status_update(self):
        """Обновляет статус-бар при движении курсора в CMD-консоли (строка, столбец)."""
        if getattr(self, 'tab_kind', '') != 'bat' or not hasattr(self, 'command_console') or not self.command_console.hasFocus():
            return
        line, col = self.command_console.get_cursor_position()
        self._last_line, self._last_col = line, col
        self._push_status()

    def _on_cmd_cursor_changed(self):
        """Ограничивает курсор терминала областью ввода."""
        if getattr(self, 'tab_kind', '') != 'bat' or not hasattr(self, '_terminal'):
            return
        self._terminal.on_cursor_changed()
        self._cmd_input_start = self._terminal.input_start

    def eventFilter(self, obj, event):
        """Обработка ввода в консоль команд и обновление статуса при смене фокуса."""
        from PyQt6.QtCore import QEvent

        if obj is self.editor and event.type() == QEvent.Type.FocusIn:
            self.on_cursor_position_changed()
            return False
        if getattr(self, 'tab_kind', '') == 'bat' and hasattr(self, '_terminal') and obj is self.command_console:
            if event.type() == QEvent.Type.FocusIn:
                self._on_cmd_status_update()
                return False
            if event.type() == QEvent.Type.KeyPress:
                self._cmd_input_start = self._terminal.input_start
                if self._terminal.handle_key_press(event):
                    self._cmd_input_start = self._terminal.input_start
                    return True
                self._cmd_input_start = self._terminal.input_start
            return False

        return super().eventFilter(obj, event)

    def _stop_cmd_process(self) -> None:
        """Завершает встроенный терминал этой вкладки."""
        if getattr(self, "tab_kind", "") != "bat":
            return
        if not hasattr(self, "_terminal"):
            return
        pid = int(self._terminal._process.processId()) if self._terminal._process.processId() else 0
        self._terminal.stop()
        if pid > 0:
            win = self.window()
            if isinstance(win, UnifiedEditorWindow):
                win._owned_terminal_pids.discard(pid)

    def run_command_from_input(self, cmd_text: str, allow_empty: bool = False):
        """Отправляет команду во встроенный терминал (вкладка стратегий)."""
        if getattr(self, 'tab_kind', '') != 'bat' or not hasattr(self, '_terminal'):
            return
        try:
            self._terminal.run_command(cmd_text, allow_empty=allow_empty)
            self._cmd_input_start = self._terminal.input_start
        except Exception as e:
            QMessageBox.warning(self, tr('msg_error', self.language), str(e))

    def open_folder(self):
        try:
            target = self.folder
            if not target or not os.path.exists(target):
                QMessageBox.warning(self, tr('msg_error', self.language),
                    tr('msg_winws_not_found', self.language) if self.is_lists_tab else tr('etcdrivers_folder_not_found', self.language))
                return
            open_path(target)
        except Exception as e:
            QMessageBox.warning(self, tr('msg_error', self.language), str(e))
    
    def add_file_to_list(self, filename):
        if filename and self.file_list.findItems(filename, Qt.MatchFlag.MatchExactly):
            return
        self.file_names.append(filename)
        self.file_list.addItem(filename)
        self.file_list.setCurrentRow(self.file_list.count() - 1)


class UnifiedEditorWindow(StandardDialog):
    """Окно с двумя вкладками: Редактор списков и Редактор drivers\\etc."""
    
    def __init__(self, parent=None, initial_tab=0):
        self.language = 'ru'
        if parent:
            if hasattr(parent, 'settings'):
                self.language = parent.settings.get('language', 'ru')
            elif hasattr(parent, 'config'):
                try:
                    self.language = parent.config.load_settings().get('language', 'ru')
                except Exception:
                    pass
        
        lists_folder = get_editor_lists_folder()
        etc_folder = get_etcdrivers_folder()
        bat_cwd, bat_files, bat_paths = get_editor_bat_setup()
        
        from src.shared.ui.assets.embedded_assets import get_app_icon
        super().__init__(
            parent=parent,
            title=tr('editor_window_title', self.language),
            width=980,
            height=640,
            icon=get_app_icon(),
            theme="dark"
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        
        self._find_replace_dialog = None
        self._find_in_files_dialog = None
        self._owned_terminal_pids: set[int] = set()
        
        content = self.getContentLayout()
        content.setContentsMargins(12, 12, 12, 12)
        content.setSpacing(0)
        
        self.status_bar = self.addStatusBar()
        p = theme.palette()
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                {theme.muted_label_style()}
                background-color: transparent;
                border: none;
                padding: 2px 8px;
            }}
        """)
        
        # Хлебные крошки слева (вместо сообщения "Файл сохранен")
        self._breadcrumb_widget = BreadcrumbWidget()
        self._breadcrumb_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._breadcrumb_widget.setMinimumWidth(200)
        self._breadcrumb_widget.partClicked.connect(self._on_breadcrumb_part_clicked)
        self.status_bar.addWidget(self._breadcrumb_widget, 1)
        
        # Добавляем виджеты в статус-бар справа: Строка столбец Spaces UTF-8 CRLF
        # Сначала создаём виджет позиции (будет обновляться в update_editor_status)
        self._position_widget = QLabel("")
        self._position_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        p = theme.palette()
        self._position_widget.setStyleSheet(f"""
            QLabel {{ color: {p.fg_muted}; }}
            QLabel:hover {{ color: {p.fg_text}; text-decoration: underline; }}
        """)
        self._position_widget.mousePressEvent = lambda e: self.go_to_line()  # type: ignore[method-assign]
        self.status_bar.addPermanentWidget(self._position_widget)
        
        # Затем добавляем LabelMenuWidget для настроек
        self.tab_size_combo = LabelMenuWidget()
        self.tab_size_combo.addItems(['Spaces: 2', 'Spaces: 4', 'Spaces: 8', 'Tabs'])
        self.tab_size_combo.setCurrentText('Spaces: 4')
        self.tab_size_combo.currentTextChanged.connect(self._on_tab_size_changed)
        self.status_bar.addPermanentWidget(self.tab_size_combo)
        
        self.encoding_combo = LabelMenuWidget()
        self.encoding_combo.addItems(['UTF-8', 'UTF-8 BOM', 'Windows-1251'])
        self.encoding_combo.setCurrentText('UTF-8')
        self.encoding_combo.currentTextChanged.connect(self._on_encoding_changed)
        self.status_bar.addPermanentWidget(self.encoding_combo)
        
        self.line_ending_combo = LabelMenuWidget()
        self.line_ending_combo.addItems(['CRLF', 'LF', 'CR'])
        self.line_ending_combo.setCurrentText('CRLF')
        self.line_ending_combo.currentTextChanged.connect(self._on_line_ending_changed)
        self.status_bar.addPermanentWidget(self.line_ending_combo)
        
        self.tabs = QTabWidget()
        self.tabs.setObjectName("EditorTabWidget")
        self.tabs.setTabBar(_EditorTabBar(self.tabs))
        self.tabs.setDocumentMode(False)
        self.tabs.setIconSize(QSize(14, 16))
        self.tabs.setStyleSheet(
            theme.detached_tab_widget_stylesheet(widget_id="EditorTabWidget")
        )

        self.tab_lists = EditorTabContent(self, lists_folder, LIST_FILES, self.language, is_lists_tab=True, tab_kind='lists')
       
        self.tab_etc = EditorTabContent(self, etc_folder, get_etc_file_names(), self.language, is_lists_tab=False, tab_kind='etc')
        self.tab_bat = EditorTabContent(
            self, bat_cwd, bat_files, self.language, is_lists_tab=False, tab_kind='bat', file_paths=bat_paths,
        )
        self.tabs.addTab(self.tab_lists, tr('editor_tab_lists', self.language))
        self.tabs.addTab(self.tab_etc, tr('editor_tab_etc', self.language))
        self.tabs.addTab(self.tab_bat, tr('editor_tab_bat', self.language))
        self._update_editor_tab_icons()
        self.tabs.setCurrentIndex(min(max(0, initial_tab), 2))
        self.tabs.currentChanged.connect(self._on_tab_changed)
        content.addWidget(self.tabs)
        
        # Применяем настройки по умолчанию ко всем вкладкам
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab:
                self._sync_settings_to_tab(tab)
        
        # Подключаем обновление хлебных крошек и заголовка окна
        self.tabs.currentChanged.connect(self._update_breadcrumb)
        self.tabs.currentChanged.connect(self._update_window_title)
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab:
                tab.file_list.currentItemChanged.connect(lambda *a: self._update_breadcrumb())
                tab.file_list.currentItemChanged.connect(lambda *a: self._update_window_title())
                tab.editor.document().modificationChanged.connect(self._update_breadcrumb)
                tab.editor.document().modificationChanged.connect(self._update_window_title)
        
        self._update_breadcrumb()
        self._update_window_title()

        self._list_filter_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self._list_filter_shortcut.activated.connect(self._focus_current_tab_filter)
        
        self.menu_bar = QMenuBar()
        
        # Файл
        file_menu = StyleMenu(self.menu_bar)
        file_menu.setTitle(tr('editor_menu_file', self.language))
        self.menu_bar.addMenu(file_menu)
        
        self.action_create_file = QAction(tr('editor_create_file', self.language), self)
        self.action_create_file.setShortcut(QKeySequence("Ctrl+N"))
        self.action_create_file.triggered.connect(self.create_new_file)
        file_menu.addAction(self.action_create_file)
        
        self.action_save = QAction(tr('editor_save', self.language), self)
        self.action_save.setShortcut(QKeySequence("Ctrl+S"))
        self.action_save.triggered.connect(self.save_current_file)
        file_menu.addAction(self.action_save)
        
        self.action_save_as = QAction(tr('editor_save_as', self.language), self)
        self.action_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.action_save_as.triggered.connect(self.save_as)
        file_menu.addAction(self.action_save_as)
        
        file_menu.addSeparator()
        
        open_folder_sub = StyleMenu(file_menu)
        open_folder_sub.setTitle(tr('editor_open_folder', self.language))
        from src.platform import is_linux

        if is_linux():
            self.action_open_folder_cmd = QAction(tr('editor_open_folder_terminal', self.language), self)
            self.action_open_folder_cmd.triggered.connect(lambda: self.open_folder_in_terminal('bash'))
            open_folder_sub.addAction(self.action_open_folder_cmd)
            self.action_open_folder_ps = QAction(tr('editor_open_folder_filemanager', self.language), self)
            self.action_open_folder_ps.triggered.connect(self.open_current_folder)
            open_folder_sub.addAction(self.action_open_folder_ps)
        else:
            self.action_open_folder_cmd = QAction(tr('editor_open_folder_cmd', self.language), self)
            self.action_open_folder_cmd.triggered.connect(lambda: self.open_folder_in_terminal('cmd'))
            open_folder_sub.addAction(self.action_open_folder_cmd)
            self.action_open_folder_ps = QAction(tr('editor_open_folder_ps', self.language), self)
            self.action_open_folder_ps.triggered.connect(lambda: self.open_folder_in_terminal('powershell'))
            open_folder_sub.addAction(self.action_open_folder_ps)
        file_menu.addMenu(open_folder_sub)

        open_file_sub = StyleMenu(file_menu)
        open_file_sub.setTitle(tr('editor_open_file_folder', self.language))
        if is_linux():
            self.action_open_file_cmd = QAction(tr('editor_open_folder_terminal', self.language), self)
            self.action_open_file_cmd.triggered.connect(lambda: self.open_file_folder_in_terminal('bash'))
            open_file_sub.addAction(self.action_open_file_cmd)
            self.action_open_file_ps = QAction(tr('editor_open_folder_filemanager', self.language), self)
            self.action_open_file_ps.triggered.connect(self._open_current_file_in_file_manager)
            open_file_sub.addAction(self.action_open_file_ps)
        else:
            self.action_open_file_cmd = QAction(tr('editor_open_folder_cmd', self.language), self)
            self.action_open_file_cmd.triggered.connect(lambda: self.open_file_folder_in_terminal('cmd'))
            open_file_sub.addAction(self.action_open_file_cmd)
            self.action_open_file_ps = QAction(tr('editor_open_folder_ps', self.language), self)
            self.action_open_file_ps.triggered.connect(lambda: self.open_file_folder_in_terminal('powershell'))
            open_file_sub.addAction(self.action_open_file_ps)
        file_menu.addMenu(open_file_sub)
        
        file_menu.addSeparator()
        
        self.action_close = QAction(tr('editor_close', self.language), self)
        self.action_close.setShortcut(QKeySequence("Ctrl+W"))
        self.action_close.triggered.connect(self.close)
        file_menu.addAction(self.action_close)
        
        # Правка
        edit_menu = StyleMenu(self.menu_bar)
        edit_menu.setTitle(tr('lists_editor_menu_edit', self.language))
        self.menu_bar.addMenu(edit_menu)
        
        self.action_undo = QAction(tr('editor_undo', self.language), self)
        self.action_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self.action_undo.triggered.connect(self.undo_action)
        edit_menu.addAction(self.action_undo)
        
        self.action_redo = QAction(tr('editor_redo', self.language), self)
        self.action_redo.setShortcut(QKeySequence("Ctrl+Y"))
        self.action_redo.triggered.connect(self.redo_action)
        edit_menu.addAction(self.action_redo)
        
        edit_menu.addSeparator()
        
        self.action_cut = QAction(tr('editor_cut', self.language), self)
        self.action_cut.setShortcut(QKeySequence("Ctrl+X"))
        self.action_cut.triggered.connect(self.cut_action)
        edit_menu.addAction(self.action_cut)
        
        self.action_copy = QAction(tr('editor_copy', self.language), self)
        self.action_copy.setShortcut(QKeySequence("Ctrl+C"))
        self.action_copy.triggered.connect(self.copy_action)
        edit_menu.addAction(self.action_copy)
        
        self.action_paste = QAction(tr('editor_paste', self.language), self)
        self.action_paste.setShortcut(QKeySequence("Ctrl+V"))
        self.action_paste.triggered.connect(self.paste_action)
        edit_menu.addAction(self.action_paste)
        
        self.action_delete = QAction(tr('editor_delete', self.language), self)
        self.action_delete.setShortcut(QKeySequence("Delete"))
        self.action_delete.triggered.connect(self.delete_action)
        edit_menu.addAction(self.action_delete)
        
        edit_menu.addSeparator()
        
        self.action_find = QAction(tr('editor_find', self.language), self)
        self.action_find.setShortcut(QKeySequence("Ctrl+F"))
        self.action_find.triggered.connect(self.show_find_replace)
        edit_menu.addAction(self.action_find)
        
        self.action_find_next = QAction(tr('editor_find_next', self.language), self)
        self.action_find_next.setShortcut(QKeySequence("F3"))
        self.action_find_next.triggered.connect(lambda: self.show_find_replace(go_next=True))
        edit_menu.addAction(self.action_find_next)
        
        self.action_find_prev = QAction(tr('editor_find_prev', self.language), self)
        self.action_find_prev.setShortcut(QKeySequence("Shift+F3"))
        self.action_find_prev.triggered.connect(lambda: self.show_find_replace(go_prev=True))
        edit_menu.addAction(self.action_find_prev)
        
        self.action_replace = QAction(tr('editor_replace', self.language), self)
        self.action_replace.setShortcut(QKeySequence("Ctrl+H"))
        self.action_replace.triggered.connect(self.show_find_replace)
        edit_menu.addAction(self.action_replace)

        self.action_find_in_files = QAction(tr('find_in_files_title', self.language), self)
        self.action_find_in_files.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.action_find_in_files.triggered.connect(self.show_find_in_files)
        edit_menu.addAction(self.action_find_in_files)
        
        self.action_go_to_line = QAction(tr('editor_go_to', self.language), self)
        self.action_go_to_line.setShortcut(QKeySequence("Ctrl+G"))
        self.action_go_to_line.triggered.connect(self.go_to_line)
        edit_menu.addAction(self.action_go_to_line)

        edit_menu.addSeparator()

        self.action_comment = QAction(tr('editor_comment', self.language), self)
        self.action_comment.setShortcut(QKeySequence("Ctrl+/"))
        self.action_comment.triggered.connect(self.comment_action)
        edit_menu.addAction(self.action_comment)

        self.action_uncomment = QAction(tr('editor_uncomment', self.language), self)
        self.action_uncomment.setShortcut(QKeySequence("Ctrl+Shift+/"))
        self.action_uncomment.triggered.connect(self.uncomment_action)
        edit_menu.addAction(self.action_uncomment)
        
        # Selection menu
        selection_menu = StyleMenu(self.menu_bar)
        selection_menu.setTitle(tr('editor_menu_selection', self.language))
        self.menu_bar.addMenu(selection_menu)
        
        self.action_select_all = QAction(tr('editor_select_all', self.language), self)
        self.action_select_all.setShortcut(QKeySequence("Ctrl+A"))
        self.action_select_all.triggered.connect(self.select_all_action)
        selection_menu.addAction(self.action_select_all)
        
        self.action_expand_selection = QAction(tr('editor_expand_selection', self.language), self)
        self.action_expand_selection.setShortcut(QKeySequence("Shift+Alt+Right"))
        self.action_expand_selection.triggered.connect(self.expand_selection_action)
        selection_menu.addAction(self.action_expand_selection)
        
        self.action_shrink_selection = QAction(tr('editor_shrink_selection', self.language), self)
        self.action_shrink_selection.setShortcut(QKeySequence("Shift+Alt+Left"))
        self.action_shrink_selection.triggered.connect(self.shrink_selection_action)
        selection_menu.addAction(self.action_shrink_selection)
        
        selection_menu.addSeparator()
        
        self.action_copy_line_up = QAction(tr('editor_copy_line_up', self.language), self)
        self.action_copy_line_up.setShortcut(QKeySequence("Shift+Alt+Up"))
        self.action_copy_line_up.triggered.connect(self.copy_line_up_action)
        selection_menu.addAction(self.action_copy_line_up)
        
        self.action_copy_line_down = QAction(tr('editor_copy_line_down', self.language), self)
        self.action_copy_line_down.setShortcut(QKeySequence("Shift+Alt+Down"))
        self.action_copy_line_down.triggered.connect(self.copy_line_down_action)
        selection_menu.addAction(self.action_copy_line_down)
        
        self.action_move_line_up = QAction(tr('editor_move_line_up', self.language), self)
        self.action_move_line_up.setShortcut(QKeySequence("Alt+Up"))
        self.action_move_line_up.triggered.connect(self.move_line_up_action)
        selection_menu.addAction(self.action_move_line_up)
        
        self.action_move_line_down = QAction(tr('editor_move_line_down', self.language), self)
        self.action_move_line_down.setShortcut(QKeySequence("Alt+Down"))
        self.action_move_line_down.triggered.connect(self.move_line_down_action)
        selection_menu.addAction(self.action_move_line_down)
        
        self.action_duplicate_selection = QAction(tr('editor_duplicate_selection', self.language), self)
        self.action_duplicate_selection.setShortcut(QKeySequence("Shift+Alt+D"))
        self.action_duplicate_selection.triggered.connect(self.duplicate_selection_action)
        selection_menu.addAction(self.action_duplicate_selection)
        
        selection_menu.addSeparator()
        
        self.action_add_next_occurrence = QAction(tr('editor_add_next_occurrence', self.language), self)
        self.action_add_next_occurrence.setShortcut(QKeySequence("Ctrl+D"))
        self.action_add_next_occurrence.triggered.connect(self.add_next_occurrence_action)
        selection_menu.addAction(self.action_add_next_occurrence)
        
        self.action_add_prev_occurrence = QAction(tr('editor_add_prev_occurrence', self.language), self)
        self.action_add_prev_occurrence.setShortcut(QKeySequence("Ctrl+Shift+D"))
        self.action_add_prev_occurrence.triggered.connect(self.add_prev_occurrence_action)
        selection_menu.addAction(self.action_add_prev_occurrence)
        
        self.action_select_all_occurrences = QAction(tr('editor_select_all_occurrences', self.language), self)
        self.action_select_all_occurrences.setShortcut(QKeySequence("Ctrl+Shift+L"))
        self.action_select_all_occurrences.triggered.connect(self.select_all_occurrences_action)
        selection_menu.addAction(self.action_select_all_occurrences)
        
        # View menu
        view_menu = StyleMenu(self.menu_bar)
        view_menu.setTitle(tr('menu_view', self.language))
        self.menu_bar.addMenu(view_menu)
        
        self.action_fullscreen = QAction(tr('editor_fullscreen', self.language), self)
        self.action_fullscreen.setShortcut(QKeySequence("F11"))
        self.action_fullscreen.setCheckable(True)
        self.action_fullscreen.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(self.action_fullscreen)
        
        zoom_sub = StyleMenu(view_menu)
        zoom_sub.setTitle(tr('editor_zoom_menu', self.language))
        self.action_zoom_in = QAction(tr('editor_zoom_in', self.language), self)
        self.action_zoom_in.setShortcut(QKeySequence("Ctrl+="))
        self.action_zoom_in.triggered.connect(self.zoom_in_action)
        zoom_sub.addAction(self.action_zoom_in)
        self.action_zoom_out = QAction(tr('editor_zoom_out', self.language), self)
        self.action_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        self.action_zoom_out.triggered.connect(self.zoom_out_action)
        zoom_sub.addAction(self.action_zoom_out)
        self.action_zoom_reset = QAction(tr('editor_zoom_reset_default', self.language), self)
        self.action_zoom_reset.setShortcut(QKeySequence("Ctrl+0"))
        self.action_zoom_reset.triggered.connect(self.zoom_reset_action)
        zoom_sub.addAction(self.action_zoom_reset)
        view_menu.addMenu(zoom_sub)
        
        self.action_word_wrap = QAction(tr('editor_word_wrap', self.language), self)
        self.action_word_wrap.setCheckable(True)
        self.action_word_wrap.setChecked(False)
        # Горячая клавиша для переноса по словам (оставляем Ctrl+Z для Undo)
        self.action_word_wrap.setShortcut(QKeySequence("Alt+Z"))
        self.action_word_wrap.triggered.connect(self.toggle_word_wrap)
        view_menu.addAction(self.action_word_wrap)

        # Terminal menu
        terminal_menu = StyleMenu(self.menu_bar)
        terminal_menu.setTitle(tr('editor_menu_terminal', self.language))
        self.menu_bar.addMenu(terminal_menu)

        self.action_run_current_file = QAction(tr('editor_terminal_run_file', self.language), self)
        self.action_run_current_file.setShortcut(QKeySequence("F5"))
        self.action_run_current_file.triggered.connect(self.run_current_file_in_terminal)
        terminal_menu.addAction(self.action_run_current_file)

        self.action_run_selection = QAction(tr('editor_terminal_run_selection', self.language), self)
        self.action_run_selection.setShortcut(QKeySequence("F6"))
        self.action_run_selection.triggered.connect(self.run_selection_in_terminal)
        terminal_menu.addAction(self.action_run_selection)
        
        # Tools menu
        tools_menu = StyleMenu(self.menu_bar)
        tools_menu.setTitle(tr('menu_tools', self.language))
        self.menu_bar.addMenu(tools_menu)
        
        self.action_country_blocklist = QAction(tr('country_blocklist_btn', self.language), self)
        self.action_country_blocklist.triggered.connect(self.show_country_blocklist)
        tools_menu.addAction(self.action_country_blocklist)

        self.action_domain_variants = QAction(tr('domain_variants_btn', self.language), self)
        self.action_domain_variants.triggered.connect(self.show_domain_variants)
        tools_menu.addAction(self.action_domain_variants)
        
        self.action_format_document = QAction(tr('editor_format_document', self.language), self)
        self.action_format_document.setShortcut(QKeySequence("Shift+Alt+F"))
        self.action_format_document.triggered.connect(self.format_document_action)
        tools_menu.addAction(self.action_format_document)
        
        tools_menu.addSeparator()
        
        convert_sub = StyleMenu(tools_menu)
        convert_sub.setTitle(tr('editor_convert_menu', self.language))
        self.action_convert_line_endings = QAction(tr('editor_convert_line_endings_short', self.language), self)
        self.action_convert_line_endings.triggered.connect(self.convert_line_endings_action)
        convert_sub.addAction(self.action_convert_line_endings)
        self.action_convert_encoding = QAction(tr('editor_convert_encoding_short', self.language), self)
        self.action_convert_encoding.triggered.connect(self.convert_encoding_action)
        convert_sub.addAction(self.action_convert_encoding)
        tools_menu.addMenu(convert_sub)
        
        self.title_bar.addLeftWidget(self.menu_bar)
        
        # Обновляем состояние действий при изменении курсора / смене вкладки
        self.tabs.currentChanged.connect(self._update_actions_state)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._update_actions_state()
        
        self._refresh_status_from_current_tab()
        self._sync_word_wrap_action_state()

    def refresh_theme(self):
        """Переприменяет inline-стили после смены темы."""
        p = theme.palette()
        self.tabs.setStyleSheet(
            theme.detached_tab_widget_stylesheet(widget_id="EditorTabWidget")
        )
        self._update_editor_tab_icons()
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                {theme.muted_label_style()}
                background-color: transparent;
                border: none;
                padding: 2px 8px;
            }}
        """)
        self._position_widget.setStyleSheet(f"""
            QLabel {{ color: {p.fg_muted}; }}
            QLabel:hover {{ color: {p.fg_text}; text-decoration: underline; }}
        """)
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab and hasattr(tab, "refresh_theme"):
                tab.refresh_theme()
        self._apply_theme()
    
    def _on_tab_changed(self, index):
        self._refresh_status_from_current_tab()
        self._update_breadcrumb()
        # При смене вкладки синхронизируем настройки
        tab = self.current_tab_content()
        if tab:
            self._sync_settings_to_tab(tab)
        self._sync_word_wrap_action_state()
        self._update_window_title()
    
    def _update_breadcrumb(self):
        """Обновляет хлебные крошки: Folder [chevron] Folder [chevron] File.txt [ (изменен) ]"""
        tab = self.current_tab_content()
        if not tab or not hasattr(self, '_breadcrumb_widget'):
            return
        path = tab.get_current_file_path()
        if not path:
            self._breadcrumb_widget.set_path([])
            return
        # Разбиваем путь на части (используем pathlib для корректной обработки диска на Windows)
        p = Path(path)
        parts = list(p.parts)
        if not parts:
            self._breadcrumb_widget.set_path([])
            return
        # Формируем подписи: для первого элемента убираем конечный слэш, чтобы было "C:" вместо "C:\"
        labels = []
        for i, part in enumerate(parts):
            if i == 0 and part.endswith(os.sep):
                labels.append(part.rstrip(os.sep))
            else:
                labels.append(part)
        # Текст о модификации
        modified_text = ""
        if tab.editor.document().isModified():
            modified_text = tr('editor_file_modified', self.language)
        self._breadcrumb_widget.set_path(labels, modified_text)
    
    def _sync_word_wrap_action_state(self):
        """Делает пункт 'Перенос текста' согласованным с режимом переноса в текущем редакторе."""
        tab = self.current_tab_content()
        if not tab:
            return
        editor = tab.get_current_editor()
        self.action_word_wrap.setChecked(
            editor.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
        )

    def _on_breadcrumb_part_clicked(self, index: int):
        """Обработчик клика по части хлебных крошек.

        Клик по папке — открыть папку в проводнике.
        Клик по файлу — открыть файл в системном файловом менеджере.
        """
        tab = self.current_tab_content()
        if not tab:
            return
        path = tab.get_current_file_path()
        if not path:
            return
        try:
            p = Path(path)
            parts = list(p.parts)
            if index < 0 or index >= len(parts):
                return
            target = Path(*parts[: index + 1])
            if target.is_dir():
                try:
                    open_path(str(target))
                except Exception as e:
                    QMessageBox.warning(self, tr('msg_error', self.language), str(e))
            elif target.is_file():
                try:
                    reveal_path_in_file_manager(str(target))
                except Exception as e:
                    QMessageBox.warning(self, tr('msg_error', self.language), str(e))
        except Exception:
            # В случае неожиданных проблем просто ничего не делаем
            return
    
    def _refresh_status_from_current_tab(self):
        tab = self.current_tab_content()
        if tab and hasattr(tab, '_last_status'):
            self.update_editor_status(tab._last_status, tab._last_line, tab._last_col)
        # Синхронизируем настройки с текущей вкладкой
        if tab:
            self._sync_settings_to_tab(tab)
        self._update_window_title()

    def _update_editor_tab_icons(self):
        from src.shared.ui.assets.codicon_utils import codicon_tab_icon

        titles = (
            tr("editor_tab_lists", self.language),
            tr("editor_tab_etc", self.language),
            tr("editor_tab_bat", self.language),
        )
        for index, icon_name in enumerate(_EDITOR_TAB_ICONS):
            if index >= self.tabs.count():
                break
            self.tabs.setTabText(index, titles[index])
            icon = codicon_tab_icon(icon_name, 14)
            if not icon.isNull():
                self.tabs.setTabIcon(index, icon)

    def _update_window_title(self):
        """Обновляет заголовок окна: 'Редактор — путь к файлу •' (если изменен)."""
        base = tr('editor_window_title', self.language)
        tab = self.current_tab_content()
        if not tab:
            self.setWindowTitle(base)
            return
        path = tab.get_current_file_path()
        if not path:
            self.setWindowTitle(base)
            return
        display_path = os.path.normpath(path)
        title = f"{base} — {display_path}"
        if tab.editor.document().isModified():
            title += " •"
        self.setWindowTitle(title)
    
    def _sync_settings_to_tab(self, tab):
        """Синхронизирует настройки из комбобоксов с текущей вкладкой."""
        tab_size_text = self.tab_size_combo.currentText()
        if tab_size_text == 'Tabs':
            tab.set_tab_size(8)  # Для табов используем стандартный размер
        else:
            size = int(tab_size_text.split(':')[1].strip())
            tab.set_tab_size(size)
        tab.set_encoding(self.encoding_combo.currentText())
        tab.set_line_ending(self.line_ending_combo.currentText())
    
    def _on_tab_size_changed(self, text):
        """Обработчик изменения размера табуляции."""
        tab = self.current_tab_content()
        if tab:
            if text == 'Tabs':
                tab.set_tab_size(8)
            else:
                size = int(text.split(':')[1].strip())
                tab.set_tab_size(size)
    
    def _on_encoding_changed(self, text):
        """Обработчик изменения кодировки."""
        tab = self.current_tab_content()
        if tab:
            tab.set_encoding(text)
    
    def _on_line_ending_changed(self, text):
        """Обработчик изменения окончаний строк."""
        tab = self.current_tab_content()
        if tab:
            tab.set_line_ending(text)

    # --- Терминал (меню "Терминал") ---

    def _ensure_cmd_console_focus(self, tab):
        if getattr(tab, 'tab_kind', '') == 'bat' and hasattr(tab, 'command_console'):
            tab.command_console.setFocus()

    def run_current_file_in_terminal(self):
        """Запускает текущий файл во встроенном терминале текущей вкладки стратегий."""
        tab = self.current_tab_content()
        if not tab or getattr(tab, 'tab_kind', '') != 'bat':
            return
        path = tab.get_current_file_path()
        if not path:
            return
        self._ensure_cmd_console_focus(tab)
        cmd = bat_run_terminal_command(path, get_winws_path())
        tab.run_command_from_input(cmd, allow_empty=False)

    def run_selection_in_terminal(self):
        """Отправляет выделенный в редакторе текст в терминал как команду."""
        tab = self.current_tab_content()
        if not tab or getattr(tab, 'tab_kind', '') != 'bat':
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        text = cursor.selectedText().replace('\u2029', '\n').strip()
        if not text:
            return
        self._ensure_cmd_console_focus(tab)
        if hasattr(tab, 'run_command_from_input'):
            tab.run_command_from_input(text, allow_empty=False)
    
    def update_editor_status(self, message, line=1, col=1):
        if self.status_bar is None:
            return
        # Хлебные крошки уже в статус-баре — не показываем сообщение "Файл сохранен"
        self.status_bar.clearMessage()
        pos_text = tr('editor_line_column', self.language).format(line, col)
        if hasattr(self, '_position_widget'):
            self._position_widget.setText(pos_text)

    def _show_goto_line_column_dialog(self):
        """Совместимость: старый хелпер, теперь вызывает go_to_line()."""
        self.go_to_line()
    
    def current_tab_content(self):
        return self.tabs.currentWidget()

    def _focus_current_tab_filter(self):
        tab = self.current_tab_content()
        if tab is not None and hasattr(tab, "filter_edit"):
            tab.filter_edit.setFocus()
            tab.filter_edit.selectAll()
    
    def _update_actions_state(self):
        """Обновляет состояние действий меню в зависимости от текущего редактора."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        has_selection = cursor.hasSelection()
        
        self.action_undo.setEnabled(editor.document().isUndoAvailable())
        self.action_redo.setEnabled(editor.document().isRedoAvailable())
        self.action_cut.setEnabled(has_selection)
        self.action_copy.setEnabled(has_selection)
        self.action_delete.setEnabled(has_selection or bool(editor.toPlainText()))
        self.action_save.setEnabled(editor.document().isModified())

        # Раскомментировать — enabled только если есть хотя бы одна закомментированная строка
        # Закомментировать — enabled только если есть хотя бы одна не закомментированная строка
        can_uncomment = False
        can_comment = False
        doc = editor.document()
        if not cursor.hasSelection():
            start_block = cursor.block()
            end_block = start_block
        else:
            start = min(cursor.selectionStart(), cursor.selectionEnd())
            end = max(cursor.selectionStart(), cursor.selectionEnd())
            if end > start and end > 0:
                end -= 1
            start_block = doc.findBlock(start)
            end_block = doc.findBlock(end)
        block = start_block
        while block.isValid() and block.blockNumber() <= end_block.blockNumber():
            text = block.text()
            stripped = text.lstrip()
            if tab.tab_kind == 'bat':
                if stripped.startswith('rem ') or stripped.rstrip() == 'rem' or stripped.startswith('::'):
                    can_uncomment = True
                elif stripped:  # не пустая строка
                    can_comment = True
            else:
                if stripped.startswith('#'):
                    can_uncomment = True
                elif stripped:  # не пустая строка
                    can_comment = True
            block = block.next()
        if hasattr(self, 'action_comment'):
            self.action_comment.setEnabled(can_comment)
        if hasattr(self, 'action_uncomment'):
            self.action_uncomment.setEnabled(can_uncomment)
        if hasattr(self, 'action_run_current_file'):
            can_run_file = getattr(tab, 'tab_kind', '') == 'bat' and bool(tab.get_current_file_path())
            self.action_run_current_file.setEnabled(can_run_file)
        if hasattr(self, 'action_run_selection'):
            can_run_sel = getattr(tab, 'tab_kind', '') == 'bat' and editor.textCursor().hasSelection()
            self.action_run_selection.setEnabled(can_run_sel)
    
    def save_current_file(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.save_current_file()
        self._update_actions_state()

    def save_as(self):
        """Сохранить текущий файл как... (в пределах текущей папки вкладки)."""
        tab = self.current_tab_content()
        if tab is None:
            return

        current_path = tab.get_current_file_path()
        current_name = os.path.basename(current_path) if current_path else ''
        initial_dir = tab.folder if hasattr(tab, 'folder') else os.getcwd()
        initial_path = os.path.join(initial_dir, current_name) if current_name else initial_dir

        fname, _ = QFileDialog.getSaveFileName(
            self,
            tr('editor_save_as', self.language),
            initial_path,
            "All Files (*.*)"
        )
        if not fname:
            return

        fname = os.path.normpath(fname)
        target_dir = os.path.dirname(fname)

        # Ограничиваемся текущей папкой вкладки, чтобы модель EditorTabContent оставалась согласованной
        if hasattr(tab, 'folder') and os.path.normcase(target_dir) != os.path.normcase(tab.folder):
            QMessageBox.warning(
                self,
                tr('editor_save_as', self.language),
                tr('editor_save_as_outside_folder', self.language).format(tab.folder),
            )
            return

        try:
            content = tab.editor.toPlainText()
            # Применяем выбранные окончания строк
            if tab.line_ending == 'CRLF':
                content = content.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
            elif tab.line_ending == 'LF':
                content = content.replace('\r\n', '\n').replace('\r', '\n')
            elif tab.line_ending == 'CR':
                content = content.replace('\r\n', '\n').replace('\n', '\r')

            if os.path.exists(fname):
                try:
                    tab.file_watcher.removePath(fname)
                except Exception:
                    pass

            if getattr(tab, 'is_lists_tab', False):
                os.makedirs(tab.folder, exist_ok=True)

            encoding_map = {'UTF-8': 'utf-8', 'UTF-8 BOM': 'utf-8-sig', 'Windows-1251': 'windows-1251'}
            encoding = encoding_map.get(getattr(tab, 'encoding', 'UTF-8'), 'utf-8')
            with open(fname, 'w', encoding=encoding, newline='') as f:
                if getattr(tab, 'encoding', 'UTF-8') == 'UTF-8 BOM':
                    f.write('\ufeff')
                f.write(content)

            if os.path.exists(fname):
                try:
                    tab.file_watcher.addPath(fname)
                except Exception:
                    pass

            tab.editor.document().setModified(False)
            tab.save_timer.stop()
            tab._last_status = tr('targets_saved', self.language)
            tab._push_status()
            tab._on_editor_cursor_changed()

            new_name = os.path.basename(fname)
            # Обновляем текущий файл и список файлов
            from PyQt6.QtCore import Qt as _QtAlias  # локальный импорт, чтобы использовать MatchExactly
            existing_items = tab.file_list.findItems(new_name, _QtAlias.MatchFlag.MatchExactly)
            if not existing_items:
                tab.add_file_to_list(new_name)
            else:
                tab._current_file = new_name
                for i in range(tab.file_list.count()):
                    if tab.file_list.item(i).text() == new_name:
                        tab.file_list.setCurrentRow(i)
                        break

            self._update_actions_state()
            self._update_breadcrumb()
            self._update_window_title()
        except Exception as e:
            QMessageBox.warning(
                self,
                tr('test_error_title', self.language),
                f"{tr('targets_error_saving', self.language)}: {str(e)}"
            )
    
    def reload_current_file(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        if tab.editor.document().isModified():
            action = prompt_unsaved_file_action(
                self,
                self.language,
                filename=os.path.basename(tab.get_current_file_path() or ""),
            )
            if action == "cancel":
                return
            if action == "save":
                tab.save_current_file()
        tab.load_current_file()
        self._update_actions_state()
    
    def undo_action(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.get_current_editor().undo()
        self._update_actions_state()
    
    def redo_action(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.get_current_editor().redo()
        self._update_actions_state()
    
    def cut_action(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.get_current_editor().cut()
        self._update_actions_state()
    
    def copy_action(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.get_current_editor().copy()
    
    def paste_action(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.get_current_editor().paste()
        self._update_actions_state()
    
    def select_all_action(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.get_current_editor().selectAll()
        self._update_actions_state()
    
    def go_to_line(self):
        """Переход к строке/столбцу (диалог). Поддерживает '234' и '234,11'."""
        from PyQt6.QtWidgets import QInputDialog
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        current_line, current_col = editor.get_cursor_position()

        hint = (
            f"{tr('editor_go_to_line', self.language)} ({current_line},{current_col})"
        )
        text, ok = QInputDialog.getText(
            self,
            tr('editor_go_to', self.language),
            hint + ":",
            QLineEdit.EchoMode.Normal,
            f"{current_line},{current_col}"
        )
        if not ok:
            return
        raw = (text or "").strip()
        if not raw:
            return

        import re
        nums = re.findall(r"\d+", raw)
        if not nums:
            return
        try:
            line = int(nums[0])
        except Exception:
            return
        col = 1
        if len(nums) >= 2:
            try:
                col = int(nums[1])
            except Exception:
                col = 1

        if line < 1:
            line = 1
        if col < 1:
            col = 1

        doc = editor.document()
        block = doc.findBlockByNumber(line - 1)
        if not block.isValid():
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            editor.setTextCursor(cursor)
            editor.setFocus()
            return

        line_text = block.text()
        max_col = max(1, len(line_text) + 1)
        if col > max_col:
            col = max_col
        pos = block.position() + (col - 1)

        cursor = editor.textCursor()
        cursor.setPosition(pos)
        editor.setTextCursor(cursor)
        editor.setFocus()

    def create_new_file(self):
        """Создать новый файл в текущей открытой папке вкладки."""
        from PyQt6.QtWidgets import QInputDialog
        tab = self.current_tab_content()
        if tab is None or not hasattr(tab, 'folder'):
            return

        if getattr(tab, 'tab_kind', '') == 'lists':
            default_name = 'new-list.txt'
        elif getattr(tab, 'tab_kind', '') == 'etc':
            default_name = 'new-file.txt'
        elif getattr(tab, 'tab_kind', '') == 'bat':
            default_name = 'new.bat'
        else:
            default_name = 'new.txt'

        name, ok = QInputDialog.getText(
            self,
            tr('editor_create_file', self.language),
            tr('editor_create_file', self.language) + ':',
            text=default_name
        )
        if not ok:
            return
        name = os.path.basename(name.strip())
        if not name:
            return

        # Если файл уже есть в списке — просто переключаемся на него
        from PyQt6.QtCore import Qt as _QtAlias  # локальный импорт, чтобы использовать MatchExactly
        existing = tab.file_list.findItems(name, _QtAlias.MatchFlag.MatchExactly)
        if existing:
            for i in range(tab.file_list.count()):
                if tab.file_list.item(i).text() == name:
                    tab.file_list.setCurrentRow(i)
                    break
            return

        try:
            os.makedirs(tab.folder, exist_ok=True)
            path = os.path.join(tab.folder, name)
            if not os.path.exists(path):
                # Создаём пустой файл; содержимое заполнится при первом сохранении
                with open(path, 'w', encoding='utf-8') as f:
                    f.write('')
        except Exception:
            # Если не удалось создать файл на диске, всё равно добавим его в список,
            # чтобы пользователь мог работать с ним как с новым.
            pass

        tab.add_file_to_list(name)
        self._update_actions_state()
    
    def expand_selection_action(self):
        """Расширяет выделение до следующего уровня: слово -> строка -> блок -> документ."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        else:
            doc = editor.document()
            sel_start = min(cursor.selectionStart(), cursor.selectionEnd())
            block = doc.findBlock(sel_start)
            block_start = block.position()
            block_end = block.position() + len(block.text())
            line_start = block_start
            line_end = block_end
            cur_start = min(cursor.selectionStart(), cursor.selectionEnd())
            cur_end = max(cursor.selectionStart(), cursor.selectionEnd())
            doc_len = doc.characterCount()
            if cur_start >= line_start and cur_end <= line_end and (cur_end - cur_start) < (line_end - line_start):
                cursor.movePosition(QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            elif cur_start >= block_start and cur_end <= block_end:
                cursor.setPosition(block_start)
                cursor.setPosition(block_end, QTextCursor.MoveMode.KeepAnchor)
            elif cur_end - cur_start < doc_len:
                cursor.movePosition(QTextCursor.MoveOperation.Start, QTextCursor.MoveMode.KeepAnchor)
                cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def shrink_selection_action(self):
        """Сужает выделение: документ -> блок -> строка -> слово."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            return
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        if start > end:
            start, end = end, start
        doc = editor.document()
        block_start = doc.findBlock(start)
        block_end = doc.findBlock(end)
        if block_start.blockNumber() == block_end.blockNumber():
            line_start = block_start.position()
            line_end = block_start.position() + len(block_start.text())
            if start == line_start and end == line_end:
                cursor.setPosition(start)
                cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            else:
                cursor.setPosition(start)
                cursor.setPosition(line_end, QTextCursor.MoveMode.KeepAnchor)
        else:
            cursor.setPosition(start)
            cursor.setPosition(block_start.position() + len(block_start.text()), QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def copy_line_up_action(self):
        """Копирует текущую строку вверх."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        text = cursor.selectedText().replace('\u2029', '\n')
        cursor.clearSelection()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.insertText(text + '\n')
        cursor.movePosition(QTextCursor.MoveOperation.Up)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def copy_line_down_action(self):
        """Копирует текущую строку вниз."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        text = cursor.selectedText().replace('\u2029', '\n')
        cursor.clearSelection()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
        cursor.insertText('\n' + text)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def move_line_up_action(self):
        """Перемещает текущую строку вверх."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        block = cursor.block()
        if block.blockNumber() == 0:
            return
        line_text = block.text()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.movePosition(QTextCursor.MoveOperation.Up)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.insertText(line_text + '\n')
        cursor.movePosition(QTextCursor.MoveOperation.Up)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def move_line_down_action(self):
        """Перемещает текущую строку вниз."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        block = cursor.block()
        if block.blockNumber() >= editor.blockCount() - 1:
            return
        line_text = block.text()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.movePosition(QTextCursor.MoveOperation.Down)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.insertText(line_text + '\n')
        cursor.movePosition(QTextCursor.MoveOperation.Up)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def duplicate_selection_action(self):
        """Дублирует выделение или текущую строку."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText().replace('\u2029', '\n')
            end_pos = cursor.selectionEnd()
            cursor.setPosition(end_pos)
            cursor.insertText(text)
            cursor.setPosition(end_pos)
            cursor.setPosition(end_pos + len(text), QTextCursor.MoveMode.KeepAnchor)
        else:
            block = cursor.block()
            text = block.text() + '\n'
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
            cursor.insertText('\n' + block.text())
            cursor.movePosition(QTextCursor.MoveOperation.Down)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def add_next_occurrence_action(self):
        """Добавляет следующее вхождение выделенного текста к выделению."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        search_text = cursor.selectedText().replace('\u2029', '\n') if cursor.hasSelection() else None
        if not search_text:
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            search_text = cursor.selectedText().replace('\u2029', '\n')
        if not search_text:
            return
        doc = editor.document()
        start_from = cursor.selectionEnd()
        found = doc.find(search_text, start_from, QTextDocument.FindFlag.FindCaseSensitively)
        if found.isNull():
            found = doc.find(search_text, 0, QTextDocument.FindFlag.FindCaseSensitively)
        if not found.isNull():
            cursor.setPosition(found.selectionStart())
            cursor.setPosition(found.selectionEnd(), QTextCursor.MoveMode.KeepAnchor)
            editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def add_prev_occurrence_action(self):
        """Добавляет предыдущее вхождение выделенного текста к выделению."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        search_text = cursor.selectedText().replace('\u2029', '\n') if cursor.hasSelection() else None
        if not search_text:
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            search_text = cursor.selectedText().replace('\u2029', '\n')
        if not search_text:
            return
        doc = editor.document()
        start_from = cursor.selectionStart() - 1
        flags = QTextDocument.FindFlag.FindCaseSensitively | QTextDocument.FindFlag.FindBackward
        found = doc.find(search_text, start_from, flags)
        if found.isNull():
            found = doc.find(search_text, doc.characterCount(), flags)
        if not found.isNull():
            cursor.setPosition(found.selectionStart())
            cursor.setPosition(found.selectionEnd(), QTextCursor.MoveMode.KeepAnchor)
            editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def select_all_occurrences_action(self):
        """Выделяет все вхождения выделенного текста."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        search_text = cursor.selectedText().replace('\u2029', '\n') if cursor.hasSelection() else None
        if not search_text:
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            search_text = cursor.selectedText().replace('\u2029', '\n')
        if not search_text:
            return
        doc = editor.document()
        pos = 0
        first_start = -1
        last_end = -1
        found_cursor = doc.find(search_text, pos, QTextDocument.FindFlag.FindCaseSensitively)
        while not found_cursor.isNull():
            if first_start < 0:
                first_start = found_cursor.selectionStart()
            last_end = found_cursor.selectionEnd()
            pos = found_cursor.selectionEnd()
            found_cursor = doc.find(search_text, pos, QTextDocument.FindFlag.FindCaseSensitively)
        if first_start < 0 or last_end < 0:
            return
        cursor.setPosition(first_start)
        cursor.setPosition(last_end, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def toggle_fullscreen(self):
        """Переключает полноэкранный режим."""
        if self.isFullScreen():
            self.showNormal()
            self.action_fullscreen.setChecked(False)
        else:
            self.showFullScreen()
            self.action_fullscreen.setChecked(True)
    
    def open_current_folder(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.open_folder()

    def _open_current_file_in_file_manager(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        path = tab.get_current_file_path()
        if not path:
            return
        try:
            reveal_path_in_file_manager(path)
        except Exception as e:
            QMessageBox.warning(self, tr('msg_error', self.language), str(e))

    def _register_terminal_pid(self, pid: int) -> None:
        if pid > 0:
            self._owned_terminal_pids.add(pid)

    def _stop_all_terminals(self) -> None:
        """Завершает только терминалы, запущенные этим окном редактора."""
        from src.shared.lib.process_utils import terminate_process_tree

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, EditorTabContent):
                tab._stop_cmd_process()

        for pid in list(self._owned_terminal_pids):
            terminate_process_tree(pid)
        self._owned_terminal_pids.clear()

    def open_folder_in_terminal(self, shell: str):
        """Открыть текущую папку вкладки во внешнем терминале или файловом менеджере."""
        from src.platform import is_linux

        tab = self.current_tab_content()
        if tab is None or not hasattr(tab, 'folder'):
            return
        folder = tab.folder
        if not folder or not os.path.isdir(folder):
            return
        try:
            if is_linux() and shell != 'bash':
                open_path(folder)
                return
            proc = launch_shell_in_directory(folder, shell=shell if shell in ('cmd', 'powershell', 'bash') else 'default')
            if proc and proc.pid:
                self._register_terminal_pid(proc.pid)
        except Exception as e:
            QMessageBox.warning(self, tr('msg_error', self.language), str(e))

    def open_file_folder_in_terminal(self, shell: str):
        """Запустить текущий файл во внешнем терминале."""
        from src.platform import is_linux

        tab = self.current_tab_content()
        if tab is None:
            return
        path = tab.get_current_file_path()
        if not path:
            return
        try:
            if is_linux() and shell != 'bash':
                reveal_path_in_file_manager(path)
                return
            proc = launch_file_in_shell(path, shell=shell if shell in ('cmd', 'powershell', 'bash') else 'default')
            if proc and proc.pid:
                self._register_terminal_pid(proc.pid)
        except Exception as e:
            QMessageBox.warning(self, tr('msg_error', self.language), str(e))
    
    def show_find_replace(self, go_next=False, go_prev=False):
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        if self._find_replace_dialog is None:
            self._find_replace_dialog = FindReplaceDialog(
                parent=self,
                editor=editor,
                language=self.language
            )
        self._find_replace_dialog.set_editor(editor)
        self._find_replace_dialog.show()
        self._find_replace_dialog.raise_()
        self._find_replace_dialog.activateWindow()
        if go_next and self._find_replace_dialog.search_edit.text():
            self._find_replace_dialog._find_next()
        elif go_prev and self._find_replace_dialog.search_edit.text():
            self._find_replace_dialog._find_prev()

    def show_find_in_files(self):
        """Открыть диалог поиска по файлам."""
        if self._find_in_files_dialog is None:
            self._find_in_files_dialog = FindInFilesDialog(parent=self, language=self.language)
        self._find_in_files_dialog.show()
        self._find_in_files_dialog.raise_()
        self._find_in_files_dialog.activateWindow()
        self._find_in_files_dialog.search_edit.setFocus()

    def open_file_at_line(self, tab_index, filename, line_num):
        """Открыть файл в указанной вкладке и перейти к строке."""
        if tab_index < 0 or tab_index >= self.tabs.count():
            return
        self.tabs.setCurrentIndex(tab_index)
        tab = self.tabs.widget(tab_index)
        if tab is None:
            return
        for i in range(tab.file_list.count()):
            if tab.file_list.item(i).text() == filename:
                tab.file_list.blockSignals(True)
                tab.file_list.setCurrentRow(i)
                tab.file_list.blockSignals(False)
                tab._current_file = filename
                tab.load_current_file()
                editor = tab.get_current_editor()
                block = editor.document().findBlockByLineNumber(line_num - 1)
                cursor = editor.textCursor()
                cursor.setPosition(block.position())
                editor.setTextCursor(cursor)
                editor.setFocus()
                return
        # Файла нет в списке — добавляем
        tab.add_file_to_list(filename)
        tab.load_current_file()
        editor = tab.get_current_editor()
        block = editor.document().findBlockByLineNumber(line_num - 1)
        cursor = editor.textCursor()
        cursor.setPosition(block.position())
        editor.setTextCursor(cursor)
        editor.setFocus()
    
    def show_autocomplete(self):
        """Показать автодополнение (Ctrl+Space)."""
        tab = self.current_tab_content()
        if tab is None:
            return
        if hasattr(tab, '_autocomplete'):
            tab._autocomplete.show()
    
    def show_country_blocklist(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        if not getattr(tab, 'is_lists_tab', False):
            self.tabs.setCurrentIndex(0)
            tab = self.tab_lists
        dlg = CountryBlocklistDialog(
            parent=self,
            lists_folder=tab.folder,
            language=self.language
        )
        dlg.exec()
        if getattr(dlg, 'created_filename', None):
            tab.add_file_to_list(dlg.created_filename)

    def show_domain_variants(self):
        tab = self.current_tab_content()
        initial = ""
        if tab and getattr(tab, "is_lists_tab", False):
            cursor = tab.editor.textCursor()
            if cursor.hasSelection():
                initial = cursor.selectedText().replace("\u2029", "\n").split("\n")[0].strip()
        dlg = DomainVariantsDialog(parent=self, language=self.language, initial_domain=initial)
        dlg.exec()

    def insert_text_to_current_editor(self, text: str):
        tab = self.current_tab_content()
        if not tab:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        if cursor.hasSelection():
            cursor.insertText(text)
        else:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            editor.setTextCursor(cursor)
            editor.insertPlainText(text)
        editor.setFocus()
    
    def delete_action(self):
        """Удаляет выделенный текст или символ под курсором."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        else:
            cursor.deleteChar()
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def duplicate_line_action(self):
        """Дублирует текущую строку."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        block = cursor.block()
        text = block.text()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
        cursor.insertText('\n' + text)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def comment_action(self):
        """Закомментировать выделенные строки."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        doc = editor.document()
        if not cursor.hasSelection():
            # Без выделения — только текущая строка (блок курсора)
            start_block = cursor.block()
            end_block = start_block
        else:
            start = min(cursor.selectionStart(), cursor.selectionEnd())
            end = max(cursor.selectionStart(), cursor.selectionEnd())
            if end > start and end > 0:
                end -= 1
            start_block = doc.findBlock(start)
            end_block = doc.findBlock(end)
        # Собираем (block_number, leading) и обрабатываем снизу вверх, чтобы вставка не сдвигала позиции
        comment_ops = []
        block = start_block
        while block.isValid() and block.blockNumber() <= end_block.blockNumber():
            text = block.text()
            stripped = text.lstrip()
            if tab.tab_kind == 'bat':
                if stripped and not stripped.startswith('rem ') and stripped.rstrip() != 'rem' and not stripped.startswith('::'):
                    leading = len(text) - len(stripped)
                    comment_ops.append((block.blockNumber(), leading))
            else:
                if stripped and not stripped.startswith('#'):
                    leading = len(text) - len(stripped)
                    comment_ops.append((block.blockNumber(), leading))
            block = block.next()
        cursor.beginEditBlock()
        for blk_num, leading in reversed(comment_ops):
            block = doc.findBlockByNumber(blk_num)
            if not block.isValid():
                continue
            insert_pos = block.position() + leading
            cursor.setPosition(insert_pos)
            cursor.insertText('rem ' if tab.tab_kind == 'bat' else '#')
        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def uncomment_action(self):
        """Раскомментировать выделенные строки."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        doc = editor.document()
        if not cursor.hasSelection():
            start_block = cursor.block()
            end_block = start_block
        else:
            start = min(cursor.selectionStart(), cursor.selectionEnd())
            end = max(cursor.selectionStart(), cursor.selectionEnd())
            if end > start and end > 0:
                end -= 1
            start_block = doc.findBlock(start)
            end_block = doc.findBlock(end)

        # Собираем строки для раскомментирования и обрабатываем снизу вверх, чтобы вставка не сдвигала позиции
        uncomment_ops = []
        block = start_block
        while block.isValid() and block.blockNumber() <= end_block.blockNumber():
            text = block.text()
            stripped = text.lstrip()
            leading = len(text) - len(stripped)
            if tab.tab_kind == 'bat':
                if stripped.startswith('rem '):
                    uncomment_ops.append((block.blockNumber(), leading, 4))
                elif stripped.rstrip() == 'rem':
                    uncomment_ops.append((block.blockNumber(), leading, 3))
                elif stripped.startswith('::'):
                    uncomment_ops.append((block.blockNumber(), leading, 2))
            else:
                if stripped.startswith('#'):
                    uncomment_ops.append((block.blockNumber(), leading, 1))
            block = block.next()

        cursor.beginEditBlock()
        for blk_num, leading, remove_len in reversed(uncomment_ops):
            block = doc.findBlockByNumber(blk_num)
            if not block.isValid():
                continue
            pos = block.position() + leading
            cursor.setPosition(pos)
            cursor.setPosition(pos + remove_len, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def toggle_word_wrap(self, checked):
        """Переключает перенос строк."""
        tab = self.current_tab_content()
        if tab:
            tab.get_current_editor().setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if checked else QPlainTextEdit.LineWrapMode.NoWrap)
    
    def zoom_in_action(self):
        """Увеличивает масштаб шрифта."""
        tab = self.current_tab_content()
        if tab:
            editor = tab.get_current_editor()
            font = editor.font()
            font.setPointSize(font.pointSize() + 1)
            editor.setFont(font)
            tab._autocomplete.on_editor_font_changed()

    def zoom_out_action(self):
        """Уменьшает масштаб шрифта."""
        tab = self.current_tab_content()
        if tab:
            editor = tab.get_current_editor()
            font = editor.font()
            if font.pointSize() > 6:
                font.setPointSize(font.pointSize() - 1)
                editor.setFont(font)
            tab._autocomplete.on_editor_font_changed()

    def zoom_reset_action(self):
        """Сбрасывает масштаб шрифта на значение по умолчанию."""
        tab = self.current_tab_content()
        if tab:
            editor = tab.get_current_editor()
            font = QFont("Consolas", 10)
            editor.setFont(font)
            tab._autocomplete.on_editor_font_changed()
    
    def format_document_action(self):
        """Форматирует документ (удаляет лишние пробелы в конце строк)."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        text = editor.toPlainText()
        lines = text.split('\n')
        formatted_lines = [line.rstrip() for line in lines]
        formatted_text = '\n'.join(formatted_lines)
        if formatted_text != text:
            cursor = editor.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.insertText(formatted_text)
            self._update_actions_state()
    
    def convert_line_endings_action(self):
        """Конвертирует окончания строк в выбранный формат."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        text = editor.toPlainText()
        # Нормализуем к LF
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # Конвертируем в выбранный формат
        if tab.line_ending == 'CRLF':
            text = text.replace('\n', '\r\n')
        elif tab.line_ending == 'CR':
            text = text.replace('\n', '\r')
        # Применяем изменения
        cursor = editor.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(text)
        self._update_actions_state()
    
    def convert_encoding_action(self):
        """Конвертирует кодировку: перечитывает байты файла в выбранной кодировке."""
        tab = self.current_tab_content()
        if tab is None:
            return
        path = tab.get_current_file_path()
        if not path or not os.path.isfile(path):
            return
        if tab.editor.document().isModified():
            reply = QMessageBox.question(
                self,
                tr('editor_convert_encoding', self.language),
                tr('targets_unsaved_changes', self.language),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Yes:
                tab.save_current_file()
        encoding_map = {
            'UTF-8': 'utf-8',
            'UTF-8 BOM': 'utf-8-sig',
            'Windows-1251': 'windows-1251',
        }
        enc = encoding_map.get(self.encoding_combo.currentText(), 'utf-8')
        try:
            with open(path, 'rb') as f:
                raw = f.read()
            text = raw.decode(enc)
            if '\ufffd' in text:
                QMessageBox.warning(
                    self,
                    tr('editor_convert_encoding', self.language),
                    tr('editor_encoding_loss_warning', self.language),
                )
        except UnicodeDecodeError:
            QMessageBox.warning(
                self,
                tr('editor_convert_encoding', self.language),
                tr('editor_encoding_decode_error', self.language),
            )
            return
        except OSError as exc:
            QMessageBox.warning(self, tr('msg_error', self.language), str(exc))
            return
        tab.editor.blockSignals(True)
        tab.editor.setPlainText(text)
        tab.editor.blockSignals(False)
        tab.editor.document().setModified(True)
        tab.set_encoding(self.encoding_combo.currentText())
        self._update_actions_state()
    
    def show_about(self):
        """Показывает диалог 'О программе'."""
        from src.shared.ui.assets.embedded_assets import get_app_icon
        QMessageBox.about(
            self,
            tr('editor_about', self.language),
            f"ZapretDesktop Editor\n\n{tr('editor_window_title', self.language)}"
        )

    def _flush_all_tabs_before_close(self) -> None:
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab is None or not isinstance(tab, EditorTabContent):
                continue
            if tab.save_timer.isActive():
                tab.save_timer.stop()
            if tab.editor.document().isModified():
                tab.save_current_file()

    def closeEvent(self, event):
        """При закрытии окна сбрасываем singleton, чтобы следующий запуск создавал новое окно
        с корректным состоянием (размер/кнопка разворота)."""
        self._flush_all_tabs_before_close()
        self._stop_all_terminals()
        super().closeEvent(event)
        # Сбрасываем кешированный экземпляр, если он указывает на это окно
        global get_unified_editor_window
        if 'get_unified_editor_window' in globals():
            if getattr(get_unified_editor_window, "_instance", None) is self:
                get_unified_editor_window._instance = None


def get_unified_editor_window(parent=None, initial_tab=0):
    """Возвращает единственный экземпляр окна (или создаёт новый)."""
    if not hasattr(get_unified_editor_window, '_instance') or get_unified_editor_window._instance is None:
        get_unified_editor_window._instance = UnifiedEditorWindow(parent, initial_tab=initial_tab)
    else:
        get_unified_editor_window._instance.tabs.setCurrentIndex(min(max(0, initial_tab), 2))
    return get_unified_editor_window._instance
