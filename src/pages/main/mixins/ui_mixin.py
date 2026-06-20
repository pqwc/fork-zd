"""ui_mixin methods for MainWindow."""
from __future__ import annotations

import os
import subprocess

from PyQt6.QtCore import Qt, QTimer, QSize, QRectF
from PyQt6.QtGui import QFont, QKeySequence, QPixmap, QPainter, QShortcut, QIcon
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from src.widgets.animated_progressbar import AnimatedProgressBar
from src.features.editor.lib.line_number_editor import LineNumberPlainTextEdit
from src.features.editor.lib.editor_highlighters import DiagnosticsLogHighlighter

from src.shared.ui.assets.embedded_assets import get_svg_qbytearray
from src.shared.lib.path_utils import get_winws_path
from src.shared.i18n.translator import tr, tr_platform
from src.features.editor.ui.unified_editor_window import get_unified_editor_window
from src.shared.ui import theme
from src.widgets.custom_context_widgets import ContextLineEdit
from src.widgets.codicon_button import CodiconButton
from src.widgets.style_menu import StyleMenu

_HOME_CONSOLE_PREFIX = {
    "info": "[INFO]",
    "error": "[FAIL]",
    "critical": "[CRITICAL]",
    "warn": "[WARN]",
    "pass": "[OK]",
}


class UiMixin:
    def init_ui(self):
        central_widget = QWidget()
        self.setContentWidget(central_widget)

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        central_widget.setLayout(layout)

        progress_bar_container = QWidget()
        progress_bar_container.setFixedHeight(2)
        progress_bar_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        progress_bar_container_layout = QHBoxLayout(progress_bar_container)
        progress_bar_container_layout.setContentsMargins(0, 0, 0, 0)
        progress_bar_container_layout.setSpacing(0)
        self.menu_progress_bar = AnimatedProgressBar()
        self.menu_progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.menu_progress_bar.setProgressHidden(True)
        progress_bar_container_layout.addWidget(self.menu_progress_bar)
        layout.addWidget(progress_bar_container)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)
        layout.addWidget(content_widget, 1)

        self._home_splitter = QSplitter(Qt.Orientation.Horizontal)
        theme.configure_invisible_splitter(self._home_splitter)
        content_layout.addWidget(self._home_splitter, 1)

        self._home_splitter.addWidget(self._build_strategy_list_panel())
        self._home_splitter.addWidget(self._build_strategy_detail_panel())
        self._home_splitter.setStretchFactor(0, 0)
        self._home_splitter.setStretchFactor(1, 1)
        self._home_splitter.setSizes([280, 640])

        footer_row_widget = QWidget()
        footer_row = QHBoxLayout(footer_row_widget)
        footer_row.setContentsMargins(4, 0, 4, 0)
        footer_row.setSpacing(6)
        self.fork_icon_label = QLabel()
        self.fork_icon_label.setFixedSize(16, 16)
        self.fork_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_row.addWidget(self.fork_icon_label)
        self.footer_label = QLabel()
        self.footer_label.setTextFormat(Qt.TextFormat.RichText)
        self.footer_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.footer_label.setOpenExternalLinks(True)
        self.footer_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.footer_label.setWordWrap(False)
        self.footer_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.footer_label.customContextMenuRequested.connect(self._show_version_context_menu)
        footer_row.addWidget(self.footer_label, 1)
        self.launch_args_label = QLabel()
        self.launch_args_label.setWordWrap(False)
        self.launch_args_label.hide()
        footer_row.addWidget(self.launch_args_label)
        self.network_status_label = QLabel()
        self.network_status_label.setFixedSize(16, 16)
        self.network_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.network_status_label.setCursor(Qt.CursorShape.PointingHandCursor)
        footer_row.addWidget(self.network_status_label)
        content_layout.addWidget(footer_row_widget)

        self.load_bat_files()
        self.load_footer_info()
        self.restore_last_strategy()
        self._sync_external_winws_console()
        lang = self.settings.get("language", "ru")
        self._retranslate_home_panel()
        if hasattr(self, "strategy_console") and not self.strategy_console.toPlainText().strip():
            self.strategy_console.setPlainText(tr("home_console_empty", lang))
        self._update_strategy_detail_panel()

        QTimer.singleShot(0, self._run_startup_update_check)

        self.menubar = None
        self.settings_menu = None
        self.update_menu = None
        self.language_menu = None
        self.check_app_updates_action = None
        self.check_updates_action = None
        self.manual_update_action = None

    def _build_strategy_list_panel(self) -> QWidget:
        container = QWidget()
        container.setMinimumWidth(200)
        container.setMaximumWidth(360)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        search_row = QWidget()
        search_row_layout = QHBoxLayout(search_row)
        search_row_layout.setContentsMargins(0, 0, 0, 0)
        search_row_layout.setSpacing(4)

        self.strategy_search = ContextLineEdit()
        self.strategy_search.setFixedHeight(theme.EDITOR_FIELD_HEIGHT)
        self.strategy_search.setStyleSheet(theme.editor_search_field_style())
        self.strategy_search.textChanged.connect(self._apply_strategy_filter)
        search_row_layout.addWidget(self.strategy_search, 1)

        self.strategy_check_updates_btn = CodiconButton(
            "refresh",
            "",
            size=14,
            button_size=theme.EDITOR_FIELD_HEIGHT,
        )
        self.strategy_check_updates_btn.setObjectName("HomeCheckUpdatesBtn")
        self.strategy_check_updates_btn.clicked.connect(self.check_zapret_updates)
        search_row_layout.addWidget(self.strategy_check_updates_btn)
        layout.addWidget(search_row)

        self._home_search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self._home_search_shortcut.activated.connect(self._focus_strategy_search)

        list_block = theme.create_editor_block("HomeStrategyListBlock")
        list_layout = QVBoxLayout(list_block)
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(0)

        self.strategy_list = QListWidget()
        self.strategy_list.setStyleSheet(theme.home_strategy_list_style())
        self.strategy_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.strategy_list.customContextMenuRequested.connect(self._show_strategy_list_context_menu)
        self.strategy_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.strategy_list.setSpacing(0)
        self.strategy_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.strategy_list.currentItemChanged.connect(self._on_strategy_list_selection_changed)
        self.strategy_list.viewport().installEventFilter(self)

        self._strategy_list_stack = QStackedWidget()
        self._strategy_list_stack.addWidget(self.strategy_list)

        nothing_widget = QWidget()
        nothing_layout = QVBoxLayout(nothing_widget)
        nothing_layout.setContentsMargins(0, 0, 0, 0)
        self._strategy_nothing_label = QLabel()
        self._strategy_nothing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._strategy_nothing_label.setStyleSheet(theme.nothing_found_style())
        nothing_layout.addWidget(self._strategy_nothing_label)
        self._strategy_list_stack.addWidget(nothing_widget)
        self._strategy_list_stack.setCurrentIndex(0)

        list_layout.addWidget(self._strategy_list_stack, 1)
        layout.addWidget(list_block, 1)
        return container

    def _build_strategy_detail_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.strategy_empty_label = QLabel()
        self.strategy_empty_label.setWordWrap(True)
        self.strategy_empty_label.setObjectName("HomeStrategyEmptyHint")
        self.strategy_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.strategy_empty_label)

        self.strategy_detail_form = QWidget()
        form_layout = QVBoxLayout(self.strategy_detail_form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(6)

        info_block = theme.create_editor_block("HomeInfoBlock")
        info_outer = QVBoxLayout(info_block)
        info_outer.setContentsMargins(12, 10, 12, 10)
        info_outer.setSpacing(8)
        self._info_section_title = QLabel()
        self._info_section_title.setObjectName("HomeSectionTitle")
        info_outer.addWidget(self._info_section_title)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        self.strategy_detail_name = QLabel()
        self.strategy_detail_name.setObjectName("HomeStrategyName")
        self.strategy_detail_name.setWordWrap(True)
        header_row.addWidget(self.strategy_detail_name, 1)
        self.strategy_status_badge = QLabel()
        self.strategy_status_badge.setObjectName("HomeStrategyStatusBadge")
        self.strategy_status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_row.addWidget(self.strategy_status_badge, 0, Qt.AlignmentFlag.AlignTop)
        info_outer.addLayout(header_row)

        self.strategy_external_note = QLabel()
        self.strategy_external_note.setWordWrap(True)
        self.strategy_external_note.setObjectName("HomeExternalNote")
        self.strategy_external_note.hide()
        info_outer.addWidget(self.strategy_external_note)

        info_grid_host = QWidget()
        info_grid = QGridLayout(info_grid_host)
        info_grid.setContentsMargins(0, 0, 0, 0)
        info_grid.setHorizontalSpacing(12)
        info_grid.setVerticalSpacing(6)
        info_grid.setColumnStretch(0, 0)
        info_grid.setColumnStretch(1, 1)

        self._detail_labels: dict[str, QLabel] = {}
        self._detail_rows: dict[str, QLabel] = {}
        for row, key in enumerate(("zapret_version", "pid", "file")):
            caption = QLabel()
            caption.setObjectName("HomeInfoCaption")
            value = QLabel()
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setObjectName("HomeInfoValue")
            info_grid.addWidget(caption, row, 0)
            info_grid.addWidget(value, row, 1)
            self._detail_labels[key] = caption
            self._detail_rows[key] = value
        info_outer.addWidget(info_grid_host)
        form_layout.addWidget(info_block)

        actions_block = theme.create_editor_block("HomeActionsBlock")
        actions_outer = QVBoxLayout(actions_block)
        actions_outer.setContentsMargins(12, 10, 12, 10)
        actions_outer.setSpacing(8)
        self._actions_section_title = QLabel()
        self._actions_section_title.setObjectName("HomeSectionTitle")
        actions_outer.addWidget(self._actions_section_title)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(6)
        actions_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.action_button = QPushButton("")
        self.action_button.setObjectName("HomePrimaryAction")
        self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_button.setFixedHeight(28)
        self.action_button.setMinimumWidth(110)
        self.action_button.setMaximumWidth(160)
        self.action_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.action_button.clicked.connect(self.toggle_action)
        actions_row.addWidget(self.action_button)

        for attr, handler in (
            ("strategy_edit_btn", self._open_strategy_in_editor),
            ("strategy_open_file_btn", self._open_strategy_file_location),
            ("strategy_open_winws_btn", self.open_winws_folder),
        ):
            btn = QPushButton("")
            btn.setObjectName("HomeSecondaryAction")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(handler)
            setattr(self, attr, btn)
            actions_row.addWidget(btn)

        self.strategy_favorite_btn = QPushButton("")
        self.strategy_favorite_btn.setObjectName("HomeSecondaryAction")
        self.strategy_favorite_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.strategy_favorite_btn.setFixedHeight(28)
        self.strategy_favorite_btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.strategy_favorite_btn.clicked.connect(self._toggle_selected_strategy_favorite)
        actions_row.addWidget(self.strategy_favorite_btn)

        actions_row.addStretch(1)
        actions_outer.addLayout(actions_row)
        form_layout.addWidget(actions_block)

        layout.addWidget(self.strategy_detail_form)

        console_wrapper = QWidget()
        console_wrap_layout = QVBoxLayout(console_wrapper)
        console_wrap_layout.setContentsMargins(0, 6, 0, 0)
        console_wrap_layout.setSpacing(0)

        console_block = theme.create_editor_block("HomeConsoleBlock")
        console_outer = QVBoxLayout(console_block)
        console_outer.setContentsMargins(0, 0, 0, 0)
        console_outer.setSpacing(0)

        self._output_section_title = QLabel()
        self._output_section_title.setObjectName("HomeConsoleHeader")
        self._output_section_title.setStyleSheet(theme.editor_terminal_header_style())
        console_outer.addWidget(self._output_section_title)

        self.strategy_console = LineNumberPlainTextEdit()
        self.strategy_console.setObjectName("HomeStrategyConsole")
        self.strategy_console.setReadOnly(True)
        self.strategy_console.setFrameShape(QFrame.Shape.NoFrame)
        self.strategy_console.setFont(QFont("Consolas", 10))
        self.strategy_console.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        if hasattr(self.strategy_console, "set_highlight_current_line_enabled"):
            self.strategy_console.set_highlight_current_line_enabled(False)
        from PyQt6.QtWidgets import QPlainTextEdit

        self.strategy_console.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        theme.apply_home_console_text_widget(self.strategy_console)
        self._strategy_console_highlighter = DiagnosticsLogHighlighter(
            self.strategy_console.document()
        )
        console_outer.addWidget(self.strategy_console, 1)

        bottom_pad = QWidget()
        bottom_pad.setFixedHeight(6)
        console_outer.addWidget(bottom_pad)

        console_wrap_layout.addWidget(console_block, 1)

        layout.addWidget(console_wrapper, 1)
        return container

    def _focus_strategy_search(self) -> None:
        if hasattr(self, "strategy_search"):
            self.strategy_search.setFocus()
            self.strategy_search.selectAll()

    def _is_external_winws(self) -> bool:
        runtime_active = (
            self._runtime_process_active()
            if hasattr(self, "_runtime_process_active")
            else getattr(self, "is_running", False)
        )
        return bool(
            runtime_active
            and hasattr(self, "_is_own_winws_session")
            and not self._is_own_winws_session()
        )

    def _sync_external_winws_console(self) -> None:
        if not self._is_external_winws():
            self._external_winws_logged = False
            return
        if getattr(self, "_external_winws_logged", False):
            return
        lang = self.settings.get("language", "ru")
        _v, pid_proc, _root = self._get_running_winws_version_and_pid()
        strategy = self.running_strategy or "—"
        from src.platform import is_linux

        process_name = "nfqws" if is_linux() else "winws.exe"
        if hasattr(self, "_append_strategy_console"):
            if hasattr(self, "strategy_console"):
                current = self.strategy_console.toPlainText().strip()
                empty_hint = tr("home_console_empty", lang).strip()
                if not current or current == empty_hint:
                    self.strategy_console.clear()
            self._append_strategy_console(
                tr("home_console_external", lang).format(pid_proc or "—", strategy, process_name)
            )
            self._append_strategy_console(tr("home_console_external_no_output", lang))
        self._external_winws_logged = True

    def _append_strategy_console(self, text: str, *, kind: str = "info") -> None:
        if not hasattr(self, "strategy_console") or self.strategy_console is None:
            return
        if not text:
            return

        if kind == "output":
            for part in text.splitlines():
                if part:
                    self.strategy_console.appendPlainText(f"    {part}")
            self._scroll_strategy_console()
            return

        message = text.rstrip("\n")
        if message.startswith("==="):
            self.strategy_console.appendPlainText(message)
            self._scroll_strategy_console()
            return

        if "\n" in message:
            parts = message.split("\n")
            for index, part in enumerate(parts):
                if index == 0:
                    self._append_strategy_console_timestamped(kind, part)
                elif part:
                    self._append_strategy_console(part, kind="output")
            self._scroll_strategy_console()
            return

        self._append_strategy_console_timestamped(kind, message)
        self._scroll_strategy_console()

    def _append_strategy_console_timestamped(self, kind: str, message: str) -> None:
        from datetime import datetime

        prefix = _HOME_CONSOLE_PREFIX.get(kind, "[INFO]")
        ts = datetime.now().strftime("%H:%M:%S")
        self.strategy_console.appendPlainText(f"[{ts}] {prefix} {message}")

    def _scroll_strategy_console(self) -> None:
        cursor = self.strategy_console.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.strategy_console.setTextCursor(cursor)

    def _clear_strategy_console(self) -> None:
        if hasattr(self, "strategy_console") and self.strategy_console is not None:
            self.strategy_console.clear()

    def _stop_bat_output_reader(self) -> None:
        reader = getattr(self, "_bat_output_reader", None)
        if reader is None:
            return
        try:
            if reader.isRunning():
                reader.wait(300)
        except Exception:
            pass
        self._bat_output_reader = None

    def _start_bat_output_reader(self, process) -> None:
        from ..workers import BatOutputReader

        self._stop_bat_output_reader()
        if process is None or getattr(process, "stdout", None) is None:
            return
        self._bat_output_reader = BatOutputReader(process)
        self._bat_output_reader.output.connect(
            lambda text: self._append_strategy_console(text, kind="output")
        )
        self._bat_output_reader.start()

    def _refresh_primary_action_style(self) -> None:
        if not hasattr(self, "action_button"):
            return
        p = theme.palette()
        self.action_button.setStyleSheet(
            f"""
            QPushButton#HomePrimaryAction {{
                background-color: {p.accent};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: 600;
            }}
            QPushButton#HomePrimaryAction:hover {{
                background-color: {p.accent_hover};
            }}
            QPushButton#HomePrimaryAction:pressed {{
                background-color: {p.accent_hover};
            }}
            QPushButton#HomePrimaryAction:disabled {{
                background-color: {p.bg_item};
                color: {p.fg_muted};
                border: 1px solid {p.border};
            }}
            """
        )

    def _apply_strategy_filter(self, text: str) -> None:
        query = text.strip().lower()
        visible_count = 0
        first_visible = -1
        for i in range(self.strategy_list.count()):
            item = self.strategy_list.item(i)
            if item is None:
                continue
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, str) and data and data.startswith("__header_"):
                item.setHidden(bool(query))
                continue
            if not isinstance(data, str) or not data:
                item.setHidden(bool(query))
                continue
            hay = f"{data} {item.text()}".lower()
            visible = not query or query in hay
            item.setHidden(not visible)
            if visible:
                visible_count += 1
                if first_visible < 0:
                    first_visible = i
        if query and visible_count == 0:
            self._strategy_list_stack.setCurrentIndex(1)
        else:
            self._strategy_list_stack.setCurrentIndex(0)
            if query and first_visible >= 0 and not getattr(self, "is_running", False):
                self.strategy_list.setCurrentRow(first_visible)

    def _on_strategy_list_selection_changed(self, current, _previous) -> None:
        if getattr(self, "is_running", False):
            self._lock_strategy_list_to_running()
            current = self.strategy_list.currentItem()
        if current is not None:
            data = current.data(Qt.ItemDataRole.UserRole)
            if (
                isinstance(data, str)
                and data
                and data != "__external_winws__"
                and not data.startswith("__header_")
            ):
                self.on_strategy_changed(data)
        self._update_strategy_detail_panel()

    def _set_status_badge(self, running: bool) -> None:
        lang = self.settings.get("language", "ru")
        p = theme.palette()
        if running:
            text = tr("home_status_running_badge", lang)
            color = p.accent
            bg = p.accent_subtle
        else:
            text = tr("home_status_stopped_badge", lang)
            color = p.fg_muted
            bg = p.bg_item
        self.strategy_status_badge.setText(text)
        self.strategy_status_badge.setStyleSheet(
            f"QLabel#HomeStrategyStatusBadge {{"
            f" color: {color}; background-color: {bg};"
            f" border: none;"
            f" border-radius: 10px;"
            f" padding: 3px 10px; font-size: 11px; font-weight: 600;"
            f"}}"
        )

    def _update_strategy_detail_panel(self) -> None:
        from src.platform import is_linux

        lang = self.settings.get("language", "ru")
        name = self._get_selected_strategy_name()
        ext_key = "__external_winws__"
        is_ext_item = name == ext_key
        invalid = (
            not name
            or name in (tr("msg_no_bat_files", lang), tr_platform("msg_winws_not_found", lang))
        ) and not is_ext_item

        _v, pid_proc, _root = self._get_running_winws_version_and_pid()
        if hasattr(self, "_get_display_winws_pid"):
            pid_proc = self._get_display_winws_pid()
        if getattr(self, "is_running", False) and pid_proc is None:
            pid_text = tr("home_pid_pending", lang)
        else:
            pid_text = str(pid_proc) if pid_proc else "—"
        external = self._is_external_winws()

        if invalid:
            self.strategy_detail_form.hide()
            self.strategy_empty_label.show()
            self.strategy_detail_name.hide()
            self.strategy_status_badge.hide()
            if hasattr(self, "strategy_external_note"):
                self.strategy_external_note.hide()
            self._update_favorite_button(None, False)
            self.strategy_empty_label.setText(tr("home_strategy_select_hint", lang))
            self.action_button.setEnabled(False)
            self.strategy_edit_btn.setEnabled(False)
            self.strategy_open_file_btn.setEnabled(False)
            self.strategy_open_winws_btn.setEnabled(os.path.isdir(get_winws_path()))
            self._refresh_primary_action_style()
            return

        self.strategy_empty_label.hide()
        self.strategy_detail_form.show()
        self.strategy_detail_name.show()
        self.strategy_status_badge.show()

        if is_ext_item:
            proc_name = self._runtime_process_name()
            if is_linux():
                self.strategy_detail_name.setText(
                    tr("home_external_runtime_title", lang).format(proc_name)
                )
            else:
                self.strategy_detail_name.setText(tr_platform("home_external_winws_title", lang))
            self._detail_rows["file"].setText("—")
            self._detail_rows["file"].setToolTip("")
            version_text = _v or tr("home_winws_version_unknown", lang)
            self._detail_rows["zapret_version"].setText(version_text)
            self._detail_rows["pid"].setText(pid_text)
            self._set_status_badge(self._is_strategy_runtime_active(name) if hasattr(self, "_is_strategy_runtime_active") else self.is_running)
            if external and hasattr(self, "strategy_external_note"):
                if is_linux():
                    self.strategy_external_note.setText(
                        tr("home_external_runtime_note", lang).format(self._runtime_process_name())
                    )
                else:
                    self.strategy_external_note.setText(tr_platform("home_external_winws_note", lang))
                self.strategy_external_note.show()
            elif hasattr(self, "strategy_external_note"):
                self.strategy_external_note.hide()
            self.action_button.setEnabled(self.is_running and not external)
            self.strategy_edit_btn.setEnabled(False)
            self.strategy_open_file_btn.setEnabled(False)
            self.strategy_open_winws_btn.setEnabled(os.path.isdir(get_winws_path()))
            self._update_favorite_button(None, False)
            self._refresh_primary_action_style()
            self._sync_run_state_ui()
            return

        self.strategy_detail_name.setText(name)
        self._update_favorite_button(name, True)

        winws_folder = get_winws_path()
        from src.features.editor.lib.editor_paths import resolve_strategy_bat_path

        bat_path = resolve_strategy_bat_path(winws_folder, name)
        self._detail_rows["file"].setText(bat_path if bat_path else "—")
        self._detail_rows["file"].setToolTip(bat_path)

        zapret_version = "—"
        try:
            from src.entities.winws.winws_version import read_local_version_from_winws_root

            zapret_version = read_local_version_from_winws_root(winws_folder) or "—"
        except Exception:
            pass
        self._detail_rows["zapret_version"].setText(zapret_version)
        self._detail_rows["pid"].setText(pid_text)

        is_active = (
            self._is_strategy_runtime_active(name)
            if hasattr(self, "_is_strategy_runtime_active")
            else (self.is_running and self.running_strategy == name)
        )
        self._set_status_badge(is_active)

        if external and is_active and hasattr(self, "strategy_external_note"):
            if is_linux():
                self.strategy_external_note.setText(
                    tr("home_external_runtime_note", lang).format(self._runtime_process_name())
                )
            else:
                self.strategy_external_note.setText(tr_platform("home_external_winws_note", lang))
            self.strategy_external_note.show()
        elif hasattr(self, "strategy_external_note"):
            self.strategy_external_note.hide()

        busy = (
            getattr(self, "_start_worker", None) and self._start_worker.isRunning()
        ) or (getattr(self, "_stop_worker", None) and self._stop_worker.isRunning())
        can_run = bool(bat_path)
        self.action_button.setEnabled(can_run and not busy)
        self.strategy_edit_btn.setEnabled(can_run)
        self.strategy_open_file_btn.setEnabled(can_run)
        self.strategy_open_winws_btn.setEnabled(os.path.isdir(winws_folder))
        self._refresh_primary_action_style()
        self._sync_run_state_ui()
        self._sync_external_winws_console()

    def _update_favorite_button(self, name: str | None, visible: bool) -> None:
        if not hasattr(self, "strategy_favorite_btn"):
            return
        self.strategy_favorite_btn.setVisible(visible)
        if not visible or not name:
            self.strategy_favorite_btn.setEnabled(False)
            return
        from src.shared.ui.assets.codicon_utils import codicon_icon

        lang = self.settings.get("language", "ru")
        fav = self._is_strategy_favorite(name)
        icon = codicon_icon("star-full" if fav else "star-empty", 14)
        if not icon.isNull():
            self.strategy_favorite_btn.setIcon(icon)
            self.strategy_favorite_btn.setIconSize(QSize(14, 14))
        self.strategy_favorite_btn.setText(
            tr("home_btn_favorite_remove" if fav else "home_btn_favorite_add", lang)
        )
        self.strategy_favorite_btn.setEnabled(True)

    def _show_strategy_list_context_menu(self, pos) -> None:
        if getattr(self, "is_running", False):
            item = self.strategy_list.itemAt(pos)
            if item is not None:
                active_idx = self._active_running_strategy_index()
                if active_idx >= 0 and self.strategy_list.row(item) != active_idx:
                    return
        item = self.strategy_list.itemAt(pos)
        if item is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if (
            not isinstance(name, str)
            or not name
            or name == "__external_winws__"
            or name.startswith("__header_")
        ):
            return
        lang = self.settings.get("language", "ru")
        menu = StyleMenu(self)
        fav = self._is_strategy_favorite(name)
        action = menu.addAction(
            tr("home_btn_favorite_remove" if fav else "home_btn_favorite_add", lang)
        )
        chosen = menu.exec(self.strategy_list.viewport().mapToGlobal(pos))
        if chosen != action:
            return
        self._set_strategy_favorite(name, not fav)
        self.load_bat_files()
        self._update_strategy_detail_panel()

    def _open_strategy_in_editor(self) -> None:
        name = self._get_selected_strategy_name()
        if not name:
            return
        filename = f"{name}.bat"
        editor = get_unified_editor_window(self, initial_tab=2)
        editor.open_file_at_line(2, filename, 1)
        editor.show()
        editor.raise_()
        editor.activateWindow()

    def _open_strategy_file_location(self) -> None:
        from src.features.editor.lib.editor_paths import resolve_strategy_bat_path
        from src.shared.lib.open_path import reveal_path_in_file_manager

        name = self._get_selected_strategy_name()
        if not name:
            return
        bat_path = resolve_strategy_bat_path(get_winws_path(), name)
        if not bat_path:
            return
        try:
            reveal_path_in_file_manager(bat_path)
        except Exception:
            return

    def _retranslate_home_panel(self) -> None:
        lang = self.settings.get("language", "ru")
        self.strategy_search.setPlaceholderText(tr("home_search_placeholder", lang))
        if hasattr(self, "strategy_check_updates_btn"):
            self.strategy_check_updates_btn.setToolTip(tr("home_check_updates_tooltip", lang))
            if hasattr(self.strategy_check_updates_btn, "set_codicon"):
                self.strategy_check_updates_btn.set_codicon("refresh")
        self._strategy_nothing_label.setText(tr("settings_nothing_found", lang))
        self._info_section_title.setText(tr("home_block_info", lang))
        self._actions_section_title.setText(tr("home_block_actions", lang))
        self._output_section_title.setText(tr("home_block_output", lang))
        field_labels = {
            "zapret_version": tr("home_field_zapret_version", lang),
            "pid": tr("home_field_pid", lang),
            "file": tr("home_field_file", lang),
        }
        for key, text in field_labels.items():
            if key in self._detail_labels:
                self._detail_labels[key].setText(text)
        self.strategy_edit_btn.setText(tr("home_btn_edit_editor", lang))
        self.strategy_open_file_btn.setText(tr("home_btn_open_location", lang))
        self.strategy_open_winws_btn.setText(tr_platform("home_btn_open_winws", lang))
        if (
            hasattr(self, "strategy_console")
            and self.strategy_console is not None
            and not self.strategy_console.toPlainText().strip()
        ):
            self.strategy_console.setPlainText(tr("home_console_empty", lang))
        if hasattr(self, "load_footer_info"):
            self.load_footer_info()
        elif hasattr(self, "load_version_info"):
            self.load_version_info()
        if hasattr(self, "_retranslate_strategy_list_headers"):
            self._retranslate_strategy_list_headers()
        self._refresh_primary_action_style()
        self._apply_home_action_icons()
        self._sync_run_state_ui()
        self._update_strategy_detail_panel()

    def _apply_home_action_icons(self) -> None:
        from src.shared.ui.assets.codicon_utils import codicon_icon

        icon_size = 14
        if hasattr(self, "action_button"):
            icon_name = "debug-stop" if getattr(self, "is_running", False) else "play"
            icon = codicon_icon(icon_name, icon_size)
            if not icon.isNull():
                self.action_button.setIcon(icon)
                self.action_button.setIconSize(QSize(icon_size, icon_size))
        secondary = (
            ("strategy_edit_btn", "edit"),
            ("strategy_open_file_btn", "go-to-file"),
            ("strategy_open_winws_btn", "folder-opened"),
        )
        for attr, icon_name in secondary:
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            icon = codicon_icon(icon_name, icon_size)
            if not icon.isNull():
                btn.setIcon(icon)
                btn.setIconSize(QSize(icon_size, icon_size))

    def _fork_icon_pixmap(self, size: int = 14) -> QPixmap:
        data = get_svg_qbytearray("repo-forked")
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        if data.isEmpty():
            return pix
        renderer = QSvgRenderer()
        if renderer.load(data):
            p = theme.palette()
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            color = theme.qcolor(p.accent)
            renderer.render(painter, QRectF(0, 0, size, size))
            painter.end()
        return pix

    def _zapret_icon_pixmap(self, size: int = 14) -> QPixmap:
        data = get_svg_qbytearray("list-tree")
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        if data.isEmpty():
            return pix
        renderer = QSvgRenderer()
        if renderer.load(data):
            p = theme.palette()
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            renderer.render(painter, QRectF(0, 0, size, size))
            painter.end()
        return pix

    def refresh_theme(self):
        """Обновляет виджеты с inline-стилями после смены темы."""
        p = theme.palette()
        accent = p.accent
        if hasattr(self, "menu_progress_bar") and hasattr(self.menu_progress_bar, "_apply_theme_colors"):
            self.menu_progress_bar._apply_theme_colors()
        self.strategy_search.setStyleSheet(theme.editor_search_field_style())
        self.strategy_list.setStyleSheet(theme.home_strategy_list_style())
        self._strategy_nothing_label.setStyleSheet(theme.nothing_found_style())
        if hasattr(self, "footer_label"):
            self.footer_label.setStyleSheet(theme.small_muted_label_style())
        if hasattr(self, "fork_icon_label") and self.fork_icon_label.isVisible():
            self.fork_icon_label.setPixmap(self._fork_icon_pixmap(14))
        if hasattr(self, "_apply_network_status_ui"):
            self._apply_network_status_ui()
        if hasattr(self, "strategy_check_updates_btn") and hasattr(
            self.strategy_check_updates_btn, "set_codicon"
        ):
            self.strategy_check_updates_btn.set_codicon("refresh")
        if hasattr(self, "load_footer_info"):
            self.load_footer_info()
        detail_style = (
            theme.dialog_form_stylesheet()
            + f"""
            QLabel#HomeSectionTitle {{
                color: {p.fg_muted};
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#HomeExternalNote {{
                color: {p.accent};
                font-size: 11px;
                padding: 2px 0px;
            }}
            QLabel#HomeStrategyName {{
                font-size: 16px;
                font-weight: 600;
                color: {p.fg_text};
            }}
            QLabel#HomeInfoCaption {{
                color: {p.fg_muted};
                font-size: 11px;
                min-width: 72px;
            }}
            QLabel#HomeInfoValue {{
                color: {p.fg_text};
                font-size: 12px;
            }}
            QLabel#HomeStrategyEmptyHint {{
                color: {p.fg_muted};
                font-size: 12px;
                padding: 24px 8px;
            }}
            QPushButton#HomeSecondaryAction {{
                padding: 4px 10px;
            }}
            QPushButton#HomeCheckUpdatesBtn {{
                border: 1px solid {p.border};
                border-radius: 4px;
                background-color: {p.bg_item};
            }}
            QPushButton#HomeCheckUpdatesBtn:hover {{
                background-color: {p.hover_bg};
            }}
            """
        )
        for block_name in (
            "HomeStrategyListBlock",
            "HomeInfoBlock",
            "HomeActionsBlock",
            "HomeConsoleBlock",
        ):
            block = self.findChild(QFrame, block_name)
            if block is not None:
                block.setStyleSheet("")
        self.setStyleSheet(detail_style)
        self._refresh_primary_action_style()
        self._apply_home_action_icons()
        if hasattr(self, "strategy_console"):
            theme.apply_home_console_text_widget(self.strategy_console)
            highlighter = getattr(self, "_strategy_console_highlighter", None)
            if highlighter is not None:
                highlighter.refresh_theme()
        if hasattr(self, "_output_section_title"):
            self._output_section_title.setStyleSheet(theme.editor_terminal_header_style())
        theme.refresh_editor_blocks(self)
        theme.apply_widget_theme(self.centralWidget())
        if hasattr(self, "_apply_strategy_list_visual_state"):
            self._apply_strategy_list_visual_state()
        if hasattr(self, "_update_strategy_detail_panel"):
            self._update_strategy_detail_panel()
