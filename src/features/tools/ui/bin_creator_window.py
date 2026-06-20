"""Окно редактора bin-файлов winws/bin (как редактор списков)."""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QTimer, QFileSystemWatcher
from PyQt6.QtGui import QAction, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QInputDialog,
    QSizePolicy,
)

from src.features.editor.lib.line_number_editor import LineNumberPlainTextEdit
from src.features.tools.lib import bin_utils
from src.shared.i18n.translator import tr
from src.shared.lib.path_utils import get_winws_path, has_runtime_installation
from src.shared.lib.open_path import open_path
from src.shared.ui import theme
from src.shared.ui.assets.embedded_assets import get_app_icon
from src.shared.ui.message_box_utils import configure_message_box
from src.shared.ui.standard_dialog import StandardDialog
from src.widgets.codicon_button import CodiconButton
from src.widgets.custom_context_widgets import ContextLineEdit
from src.widgets.style_menu import StyleMenu
from src.widgets.unified_toolbar import UnifiedToolbar


class BinCreatorWindow(StandardDialog):
    """Редактор bin: список файлов, hex-редактор, справка по типам fake-пакетов zapret."""

    def __init__(self, parent=None, language: str = "ru"):
        self.language = language
        self.winws_folder = get_winws_path()
        self.bin_folder = bin_utils.get_bin_folder()
        self._current_file = ""
        self._loading = False
        self._pending_new_name: str | None = None

        super().__init__(
            parent=parent,
            title=tr("bin_window_title", language),
            width=980,
            height=640,
            icon=get_app_icon(),
            theme="dark",
            resizable=True,
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        self._build_ui()
        self._wire_watcher()
        self.refresh_theme()
        self._reload_file_list()
        QTimer.singleShot(0, self._select_first_file)

    def _build_ui(self) -> None:
        layout = self.getContentLayout()
        theme.apply_editor_tab_content_layout(layout)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        theme.configure_invisible_splitter(self._splitter)
        self._splitter.addWidget(self._build_left_panel())
        self._splitter.addWidget(self._build_right_panel())
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([248, 620])
        layout.addWidget(self._splitter, 1)

        self.status_bar = self.addStatusBar()
        self.status_bar.setStyleSheet(
            f"QStatusBar {{ {theme.muted_label_style()} background: transparent; border: none; padding: 2px 8px; }}"
        )
        self._status_label = QLabel("")
        self.status_bar.addWidget(self._status_label, 1)

        self._build_menu()

        save_sc = QShortcut(QKeySequence("Ctrl+S"), self)
        save_sc.activated.connect(self.save_current_file)
        new_sc = QShortcut(QKeySequence("Ctrl+N"), self)
        new_sc.activated.connect(self.create_new_file)
        find_sc = QShortcut(QKeySequence("Ctrl+K"), self)
        find_sc.activated.connect(lambda: self._filter_edit.setFocus())

    def _build_menu(self) -> None:
        lang = self.language
        from PyQt6.QtWidgets import QMenuBar

        self.menu_bar = QMenuBar()

        file_menu = StyleMenu(self.menu_bar)
        file_menu.setTitle(tr("editor_menu_file", lang))
        self.menu_bar.addMenu(file_menu)

        self._action_new = QAction(tr("bin_action_new", lang), self)
        self._action_new.setShortcut(QKeySequence("Ctrl+N"))
        self._action_new.triggered.connect(self.create_new_file)
        file_menu.addAction(self._action_new)

        self._action_save = QAction(tr("editor_save", lang), self)
        self._action_save.setShortcut(QKeySequence("Ctrl+S"))
        self._action_save.triggered.connect(self.save_current_file)
        file_menu.addAction(self._action_save)

        self._action_save_as = QAction(tr("editor_save_as", lang), self)
        self._action_save_as.triggered.connect(self.save_file_as)
        file_menu.addAction(self._action_save_as)

        file_menu.addSeparator()

        self._action_import = QAction(tr("bin_action_import", lang), self)
        self._action_import.triggered.connect(self.import_external_bin)
        file_menu.addAction(self._action_import)

        self._action_delete = QAction(tr("bin_action_delete", lang), self)
        self._action_delete.triggered.connect(self.delete_current_file)
        file_menu.addAction(self._action_delete)

        file_menu.addSeparator()

        tpl_menu = StyleMenu(file_menu)
        tpl_menu.setTitle(tr("bin_menu_templates", lang))
        for group_key, names in bin_utils.iter_template_groups():
            sub = StyleMenu(tpl_menu)
            sub.setTitle(tr(group_key, lang))
            for name in names:
                act = QAction(name, self)
                act.triggered.connect(lambda _checked=False, n=name: self.download_template(n))
                sub.addAction(act)
            tpl_menu.addMenu(sub)
        file_menu.addMenu(tpl_menu)

        file_menu.addSeparator()

        self._action_open_folder = QAction(tr("bin_action_open_folder", lang), self)
        self._action_open_folder.triggered.connect(self.open_bin_folder)
        file_menu.addAction(self._action_open_folder)

        edit_menu = StyleMenu(self.menu_bar)
        edit_menu.setTitle(tr("lists_editor_menu_edit", lang))
        self.menu_bar.addMenu(edit_menu)

        self._action_format = QAction(tr("bin_action_format_hex", lang), self)
        self._action_format.triggered.connect(self.format_hex_view)
        edit_menu.addAction(self._action_format)

        self._action_copy_hex = QAction(tr("bin_action_copy_hex", lang), self)
        self._action_copy_hex.triggered.connect(self.copy_hex_to_clipboard)
        edit_menu.addAction(self._action_copy_hex)

        self.title_bar.addLeftWidget(self.menu_bar)

    def _build_left_panel(self) -> QWidget:
        container = QWidget()
        container.setMinimumWidth(200)
        container.setMaximumWidth(360)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._filter_edit = ContextLineEdit()
        self._filter_edit.setFixedHeight(theme.EDITOR_FIELD_HEIGHT)
        self._filter_edit.setStyleSheet(theme.editor_search_field_style())
        self._filter_edit.setPlaceholderText(tr("editor_list_search_placeholder", self.language))
        self._filter_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter_edit)

        toolbar = UnifiedToolbar()
        self._btn_new = CodiconButton("add", tooltip=tr("bin_action_new", self.language))
        self._btn_new.clicked.connect(self.create_new_file)
        toolbar.add_button(self._btn_new)
        self._btn_save = CodiconButton("save", tooltip=tr("editor_save", self.language))
        self._btn_save.clicked.connect(self.save_current_file)
        toolbar.add_button(self._btn_save)
        self._btn_refresh = CodiconButton("refresh", tooltip=tr("bin_action_refresh", self.language))
        self._btn_refresh.clicked.connect(self._reload_file_list)
        toolbar.add_button(self._btn_refresh)
        self._btn_delete = CodiconButton("trash", tooltip=tr("bin_action_delete", self.language))
        self._btn_delete.clicked.connect(self.delete_current_file)
        toolbar.add_button(self._btn_delete)
        layout.addWidget(toolbar)

        list_block = theme.create_editor_block("BinListBlock")
        list_layout = QVBoxLayout(list_block)
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(0)

        self.file_list = QListWidget()
        self.file_list.setStyleSheet(theme.editor_file_list_style())
        self.file_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.file_list.currentItemChanged.connect(self._on_file_changed)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._file_list_context_menu)

        self._list_stack = QStackedWidget()
        self._list_stack.addWidget(self.file_list)
        nothing = QWidget()
        nl = QVBoxLayout(nothing)
        nl.setContentsMargins(0, 0, 0, 0)
        self._nothing_label = QLabel(tr("settings_nothing_found", self.language))
        self._nothing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._nothing_label.setStyleSheet(theme.nothing_found_style())
        nl.addWidget(self._nothing_label)
        self._list_stack.addWidget(nothing)
        list_layout.addWidget(self._list_stack, 1)
        layout.addWidget(list_block, 1)
        return container

    def _build_right_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        right_split = QSplitter(Qt.Orientation.Vertical)
        theme.configure_invisible_splitter(right_split)

        hex_block = theme.create_editor_block("BinHexBlock")
        hex_layout = QVBoxLayout(hex_block)
        hex_layout.setContentsMargins(0, 0, 0, 0)
        hex_layout.setSpacing(0)

        self.hex_edit = LineNumberPlainTextEdit()
        self.hex_edit.setFrameShape(QFrame.Shape.NoFrame)
        theme.apply_editor_text_widget(self.hex_edit)
        self.hex_edit.setFont(QFont("Consolas", 10))
        self.hex_edit.setPlaceholderText(tr("bin_creator_hex_placeholder", self.language))
        self.hex_edit.textChanged.connect(self._on_hex_changed)
        hex_layout.addWidget(self.hex_edit, 1)
        right_split.addWidget(hex_block)

        info_block = theme.create_editor_block("BinInfoBlock")
        info_layout = QVBoxLayout(info_block)
        info_layout.setContentsMargins(10, 8, 10, 8)
        info_layout.setSpacing(4)

        self._info_title = QLabel(tr("bin_info_title", self.language))
        p = theme.palette()
        self._info_title.setStyleSheet(f"color: {p.fg_text}; font-weight: 600; font-size: 12px;")
        info_layout.addWidget(self._info_title)

        self._info_meta = QLabel("—")
        self._info_meta.setWordWrap(True)
        self._info_meta.setStyleSheet(theme.muted_label_style())
        info_layout.addWidget(self._info_meta)

        self._info_usage = QPlainTextEdit()
        self._info_usage.setReadOnly(True)
        self._info_usage.setMaximumHeight(88)
        self._info_usage.setFrameShape(QFrame.Shape.NoFrame)
        theme.apply_editor_text_widget(self._info_usage)
        self._info_usage.setFont(QFont("Consolas", 9))
        info_layout.addWidget(self._info_usage)

        self._info_help = QPlainTextEdit()
        self._info_help.setReadOnly(True)
        self._info_help.setFrameShape(QFrame.Shape.NoFrame)
        theme.apply_editor_text_widget(self._info_help)
        self._info_help.setFont(QFont("Consolas", 9))
        self._info_help.setPlainText(tr("bin_help_zapret", self.language))
        info_layout.addWidget(self._info_help, 1)

        right_split.addWidget(info_block)
        right_split.setStretchFactor(0, 4)
        right_split.setStretchFactor(1, 1)
        right_split.setSizes([420, 180])
        layout.addWidget(right_split, 1)
        return container

    def _wire_watcher(self) -> None:
        self._watcher = QFileSystemWatcher(self)
        if os.path.isdir(self.bin_folder):
            try:
                self._watcher.addPath(self.bin_folder)
            except Exception:
                pass
        self._watcher.directoryChanged.connect(lambda *_: self._schedule_reload())
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._reload_file_list)

    def _schedule_reload(self) -> None:
        self._reload_timer.start(300)

    def refresh_theme(self) -> None:
        super().refresh_theme()
        theme.refresh_editor_blocks(self)
        if hasattr(self, "_nothing_label"):
            self._nothing_label.setStyleSheet(theme.nothing_found_style())
        if hasattr(self, "_filter_edit"):
            self._filter_edit.setStyleSheet(theme.editor_search_field_style())
        if hasattr(self, "hex_edit"):
            theme.apply_editor_text_widget(self.hex_edit)
        for w in (getattr(self, "_info_usage", None), getattr(self, "_info_help", None)):
            if w is not None:
                theme.apply_editor_text_widget(w)

    def _reload_file_list(self) -> None:
        self._refresh_bin_folder()
        current = self._current_file
        names = bin_utils.list_bin_files(self.bin_folder)
        self.file_list.blockSignals(True)
        self.file_list.clear()
        for name in names:
            self.file_list.addItem(name)
        self.file_list.blockSignals(False)
        self._apply_filter(self._filter_edit.text())
        if current and self._find_row(current) >= 0:
            self.file_list.setCurrentRow(self._find_row(current))
        elif self._pending_new_name and self._find_row(self._pending_new_name) >= 0:
            self.file_list.setCurrentRow(self._find_row(self._pending_new_name))
            self._pending_new_name = None
        elif self.file_list.count():
            self.file_list.setCurrentRow(0)

    def _find_row(self, name: str) -> int:
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item and item.text() == name:
                return i
        return -1

    def _select_first_file(self) -> None:
        if self.file_list.count() and not self._current_file:
            self.file_list.setCurrentRow(0)

    def _apply_filter(self, text: str) -> None:
        query = text.strip().lower()
        visible = 0
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item is None:
                continue
            match = query in item.text().lower()
            item.setHidden(not match)
            if match:
                visible += 1
        self._list_stack.setCurrentIndex(0 if visible else 1)

    def _on_file_changed(self, current, previous) -> None:
        if current is None:
            self._current_file = ""
            self._loading = True
            self.hex_edit.clear()
            self._loading = False
            self._update_info_panel(None, b"")
            self._update_status()
            return
        if not self._confirm_discard():
            self.file_list.blockSignals(True)
            if previous is not None:
                self.file_list.setCurrentItem(previous)
            self.file_list.blockSignals(False)
            return
        self._load_file(current.text())

    def _load_file(self, name: str) -> None:
        path = os.path.join(self.bin_folder, name)
        if not os.path.isfile(path):
            return
        try:
            data = bin_utils.read_bin_file(path)
        except OSError:
            return
        self._current_file = name
        self._loading = True
        self.hex_edit.setPlainText(bin_utils.format_bytes_as_hex(data))
        self.hex_edit.document().setModified(False)
        self._loading = False
        self._update_info_panel(name, data)
        self._update_status(data)

    def _on_hex_changed(self) -> None:
        if self._loading:
            return
        self._update_info_from_editor()
        self._update_status()

    def _update_info_from_editor(self) -> None:
        try:
            data = bin_utils.parse_hex_text(self.hex_edit.toPlainText())
        except ValueError:
            data = b""
        self._update_info_panel(self._current_file or tr("bin_unsaved_draft", self.language), data)

    def _update_info_panel(self, name: str | None, data: bytes) -> None:
        display_name = name or "—"
        info = bin_utils.analyze_bin_file(display_name, data)
        lang = self.language
        self._info_meta.setText(
            tr("bin_info_meta", lang).format(
                name=display_name,
                size=len(data),
                kind=tr(info.category_key, lang),
            )
        )
        if data and display_name != "—":
            self._info_usage.setPlainText(bin_utils.winws_arg_example(display_name, info))
        else:
            self._info_usage.clear()
        self._info_help.setPlainText(tr(info.description_key, lang))

    def _update_status(self, data: bytes | None = None) -> None:
        lang = self.language
        if data is None:
            try:
                data = bin_utils.parse_hex_text(self.hex_edit.toPlainText())
            except ValueError:
                data = b""
        modified = self.hex_edit.document().isModified()
        mod = tr("bin_status_modified", lang) if modified else tr("bin_status_saved", lang)
        path = os.path.join(self.bin_folder, self._current_file) if self._current_file else "—"
        self._status_label.setText(f"{mod} · {len(data)} B · {path}")
        self.setWindowTitle(
            tr("bin_window_title_modified", lang).format(self._current_file or tr("bin_unsaved_draft", lang))
            if modified
            else tr("bin_window_title", lang)
        )

    def _confirm_discard(self) -> bool:
        if not self.hex_edit.document().isModified():
            return True
        msg = configure_message_box(QMessageBox(self))
        msg.setWindowTitle(tr("msg_confirm", self.language))
        msg.setText(tr("bin_discard_changes", self.language))
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return msg.exec() == QMessageBox.StandardButton.Yes

    def create_new_file(self) -> None:
        if not self._confirm_discard():
            return
        self._refresh_bin_folder()
        lang = self.language
        name, ok = QInputDialog.getText(
            self,
            tr("bin_action_new", lang),
            tr("bin_creator_dst_label", lang),
            text="custom.bin",
        )
        if not ok:
            return
        filename = bin_utils.normalize_bin_name(name)
        path = os.path.join(self.bin_folder, filename)
        if os.path.exists(path):
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr("msg_error", lang))
            msg.setText(tr("bin_file_exists", lang).format(filename))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        try:
            os.makedirs(self.bin_folder, exist_ok=True)
            bin_utils.write_bin_file(path, b"")
        except OSError as e:
            self._show_error(tr("bin_creator_write_error", lang), str(e))
            return
        self._pending_new_name = filename
        self._reload_file_list()

    def _refresh_bin_folder(self) -> None:
        self.winws_folder = get_winws_path()
        self.bin_folder = bin_utils.get_bin_folder()

    def save_current_file(self) -> bool:
        lang = self.language
        self._refresh_bin_folder()
        if not has_runtime_installation():
            self._show_error(tr("msg_error", lang), tr("msg_winws_not_found", lang))
            return False
        try:
            data = bin_utils.parse_hex_text(self.hex_edit.toPlainText())
        except ValueError as e:
            key = "bin_creator_hex_odd" if str(e) == "odd" else "bin_creator_invalid_hex"
            self._show_error(tr("msg_error", lang), tr(key, lang))
            return False

        if not self._current_file:
            return self.save_file_as(data=data)

        path = os.path.join(self.bin_folder, self._current_file)
        try:
            os.makedirs(self.bin_folder, exist_ok=True)
            bin_utils.write_bin_file(path, data)
        except OSError as e:
            self._show_error(tr("bin_creator_write_error", lang), str(e))
            return False

        self.hex_edit.document().setModified(False)
        self._update_info_panel(self._current_file, data)
        self._update_status(data)
        return True

    def save_file_as(self, data: bytes | None = None) -> bool:
        lang = self.language
        if data is None:
            try:
                data = bin_utils.parse_hex_text(self.hex_edit.toPlainText())
            except ValueError as e:
                key = "bin_creator_hex_odd" if str(e) == "odd" else "bin_creator_invalid_hex"
                self._show_error(tr("msg_error", lang), tr(key, lang))
                return False
        name, ok = QInputDialog.getText(
            self,
            tr("editor_save_as", lang),
            tr("bin_creator_dst_label", lang),
            text=self._current_file or "custom.bin",
        )
        if not ok:
            return False
        filename = bin_utils.normalize_bin_name(name)
        self._current_file = filename
        row = self._find_row(filename)
        if row < 0:
            self.file_list.addItem(filename)
            self.file_list.setCurrentRow(self.file_list.count() - 1)
        else:
            self.file_list.setCurrentRow(row)
        return self.save_current_file()

    def delete_current_file(self) -> None:
        lang = self.language
        if not self._current_file:
            return
        msg = configure_message_box(QMessageBox(self))
        msg.setWindowTitle(tr("msg_confirm", lang))
        msg.setText(tr("bin_confirm_delete", lang).format(self._current_file))
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if msg.exec() != QMessageBox.StandardButton.Yes:
            return
        path = os.path.join(self.bin_folder, self._current_file)
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError as e:
            self._show_error(tr("msg_error", lang), str(e))
            return
        self._current_file = ""
        self._loading = True
        self.hex_edit.clear()
        self.hex_edit.document().setModified(False)
        self._loading = False
        self._reload_file_list()

    def import_external_bin(self) -> None:
        lang = self.language
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("bin_action_import", lang),
            self.bin_folder if os.path.isdir(self.bin_folder) else "",
            tr("bin_import_filter", lang),
        )
        if not path:
            return
        try:
            data = bin_utils.read_bin_file(path)
        except OSError as e:
            self._show_error(tr("msg_error", lang), str(e))
            return
        dest_name = bin_utils.normalize_bin_name(os.path.basename(path))
        dest_path = os.path.join(self.bin_folder, dest_name)
        try:
            os.makedirs(self.bin_folder, exist_ok=True)
            bin_utils.write_bin_file(dest_path, data)
        except OSError as e:
            self._show_error(tr("bin_creator_write_error", lang), str(e))
            return
        self._pending_new_name = dest_name
        self._reload_file_list()

    def download_template(self, template_name: str) -> None:
        lang = self.language
        self._refresh_bin_folder()
        if not has_runtime_installation():
            self._show_error(tr("msg_error", lang), tr("msg_winws_not_found", lang))
            return
        try:
            os.makedirs(self.bin_folder, exist_ok=True)
            bin_utils.download_zapret_template(template_name, self.bin_folder)
        except OSError as e:
            self._show_error(tr("bin_template_download_error", lang), str(e))
            return
        self._pending_new_name = template_name
        self._reload_file_list()

    def format_hex_view(self) -> None:
        try:
            data = bin_utils.parse_hex_text(self.hex_edit.toPlainText())
        except ValueError:
            return
        self._loading = True
        self.hex_edit.setPlainText(bin_utils.format_bytes_as_hex(data))
        self._loading = False
        self.hex_edit.document().setModified(True)

    def copy_hex_to_clipboard(self) -> None:
        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.hex_edit.toPlainText())

    def open_bin_folder(self) -> None:
        folder = self.bin_folder
        if not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        open_path(folder)

    def _file_list_context_menu(self, pos) -> None:
        lang = self.language
        menu = StyleMenu(self)
        menu.addAction(tr("bin_action_open_folder", lang), self.open_bin_folder)
        if self._current_file:
            menu.addAction(tr("bin_action_delete", lang), self.delete_current_file)
        menu.exec(self.file_list.mapToGlobal(pos))

    def _show_error(self, title: str, text: str) -> None:
        msg = configure_message_box(QMessageBox(self))
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.exec()

    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            global get_bin_creator_window
            if getattr(get_bin_creator_window, "_instance", None) is self:
                get_bin_creator_window._instance = None
            event.accept()
        else:
            event.ignore()


def get_bin_creator_window(parent=None, language: str = "ru") -> BinCreatorWindow:
    if not hasattr(get_bin_creator_window, "_instance") or get_bin_creator_window._instance is None:
        get_bin_creator_window._instance = BinCreatorWindow(parent, language=language)
    else:
        win = get_bin_creator_window._instance
        if language and getattr(win, "language", None) != language:
            win.language = language
    return get_bin_creator_window._instance
