"""Окно диагностики в стиле окна тестирования."""
from __future__ import annotations

import json
import os
import platform
import re
import socket
from datetime import datetime

from PyQt6.QtCore import Qt, QThread, QTimer, QSize, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QFont, QBrush, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenuBar,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QFrame,
)

from src.entities.config.config_manager import VERSION
from src.entities.diagnostics.diagnostics_config import (
    build_ai_diagnostics_prompt,
    config_to_text,
    ensure_diagnostics_config,
    get_diagnostics_config_path,
    load_diagnostics_config,
    localize_diagnostics_config,
    make_command_template,
    parse_config_text,
    save_diagnostics_config,
)
from src.entities.diagnostics.diagnostics_runner import (
    checks_for_platform,
    critical_check_ids,
    default_enabled_checks,
    run_diagnostics,
)
from src.platform import is_linux
from src.platform import get_privilege_backend
from src.shared.ui.assets.embedded_assets import get_app_icon
from src.shared.lib.path_utils import get_winws_path
from src.shared.i18n.translator import tr, tr_platform
from src.features.editor.lib.editor_highlighters import DiagnosticsLogHighlighter, JsonHighlighter
from src.features.editor.lib.line_number_editor import LineNumberPlainTextEdit
from src.shared.ui import theme
from src.shared.ui.standard_dialog import StandardDialog
from src.widgets.codicon_button import CodiconButton
from src.widgets.custom_checkbox import CustomCheckBox as QCheckBox
from src.widgets.custom_combobox import CustomComboBox
from src.widgets.custom_context_widgets import ContextLineEdit
from src.widgets.style_menu import StyleMenu
from src.widgets.tab_toolbar_host import TabToolbarHost
from src.widgets.unified_toolbar import UnifiedToolbar

_TAB_ICONS = ("output", "settings-gear")

_ROLE_CHECK_ID = Qt.ItemDataRole.UserRole
_ROLE_IS_HEADER = Qt.ItemDataRole.UserRole + 1
_ROLE_CATEGORY = Qt.ItemDataRole.UserRole + 2

_STATUS_PREFIX = {
    "pass": "[OK]",
    "fail": "[FAIL]",
    "critical": "[CRITICAL]",
    "warn": "[WARN]",
    "info": "[INFO]",
}

# Категории нижней панели вывода: id → (statuses в логе,).
_OUTPUT_FILTER_CATEGORIES = (
    ("ok", ("pass",)),
    ("error", ("fail",)),
    ("critical", ("critical",)),
    ("warning", ("warn",)),
    ("info", ("info",)),
    ("output", ("output",)),
    ("section", ("section",)),
)

# Категории, включённые в нижней панели фильтра по умолчанию.
_DEFAULT_OUTPUT_FILTER_CATEGORIES = frozenset({"error", "critical", "warning"})


class _DiagnosticsTabBar(QTabBar):
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


class _DiagnosticsWorker(QThread):
    finished = pyqtSignal(list, dict)
    progress = pyqtSignal(str, str)

    def __init__(self, lang, enabled, auto_fix, custom_config):
        super().__init__()
        self._lang = lang
        self._enabled = enabled
        self._auto_fix = auto_fix
        self._custom_config = custom_config
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        results, summary = run_diagnostics(
            self._lang,
            self._enabled,
            self._auto_fix,
            custom_config=self._custom_config,
            stop_requested=lambda: self._stop,
            progress_callback=lambda status, msg: self.progress.emit(status, msg),
        )
        self.finished.emit(results, summary)


class DiagnosticsDialog(StandardDialog):
    def __init__(self, parent=None, settings=None, config=None):
        self.settings = dict(settings or {})
        self.config = config
        self.lang = self.settings.get("language", "ru")
        super().__init__(
            parent=parent,
            title=tr("menu_run_diagnostics", self.lang),
            width=960,
            height=640,
            icon=get_app_icon(),
            theme="dark",
            resizable=True,
        )
        self._worker: _DiagnosticsWorker | None = None
        self._check_items: dict[str, QListWidgetItem] = {}
        self._category_headers: dict[str, QListWidgetItem] = {}
        self._is_running = False
        self._auto_scroll_enabled = True
        self._config_dirty = False
        self._is_loading_config = False
        self._defer_output_events = False
        self._log_entries: list[dict[str, str]] = []
        self._category_filter_cbs: dict[str, QCheckBox] = {}

        self._init_menus()
        self._init_ui()
        self._load_check_settings()
        self._load_config_editor()
        self.retranslate_ui()
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        search_shortcut.activated.connect(self._focus_search_shortcut)
        self._apply_pointer_cursors(
            self.btn_start,
            self.btn_stop,
            self.auto_fix_cb,
            self.save_config_btn,
            self.reload_config_btn,
            self.insert_template_btn,
            self.copy_ai_prompt_btn,
        )

    def _init_menus(self):
        self.menu_bar = QMenuBar()
        self.menu_bar.setNativeMenuBar(False)

        self.view_menu = StyleMenu(self)
        self.view_menu.setTitle(tr("test_menu_view", self.lang))
        self.auto_scroll_action = QAction(tr("test_auto_scroll", self.lang), self)
        self.auto_scroll_action.setCheckable(True)
        self.auto_scroll_action.setChecked(True)
        self.auto_scroll_action.toggled.connect(self._on_auto_scroll_toggled)
        self.view_menu.addAction(self.auto_scroll_action)
        self.add_fullscreen_view_action(self.view_menu, self.lang)

        self.export_log_action = QAction(tr("diag_export_log", self.lang), self)
        self.export_log_action.triggered.connect(self._export_txt)

        self.menu_bar.addMenu(self.view_menu)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.export_log_action)
        if hasattr(self, "title_bar"):
            self.title_bar.addLeftWidget(self.menu_bar)

    def _init_ui(self):
        layout = self.getContentLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.tabs = TabToolbarHost(self, widget_id="DiagnosticsTabWidget")
        self.tabs.setTabBar(_DiagnosticsTabBar(self.tabs))
        self._apply_tabs_style()
        self.tabs.set_toolbar(self._create_toolbar())

        results_tab = QWidget()
        results_layout = QVBoxLayout(results_tab)
        theme.apply_editor_tab_content_layout(results_layout)

        mono = self._diagnostics_mono_font()
        self.output_editor = LineNumberPlainTextEdit()
        self.output_editor.setReadOnly(True)
        self.output_editor.setFrameShape(QFrame.Shape.NoFrame)
        self.output_editor.setFont(QFont(mono, 10))
        self._output_highlighter = DiagnosticsLogHighlighter(self.output_editor.document())
        self._style_output_editor()

        self._full_log_block = self._build_full_log_block()
        self._filtered_log_block = self._build_filtered_log_block()

        top_wrapper = QWidget()
        top_layout = QVBoxLayout(top_wrapper)
        top_layout.setContentsMargins(0, 0, 0, 3)
        top_layout.setSpacing(0)
        top_layout.addWidget(self._full_log_block)

        bottom_wrapper = QWidget()
        bottom_wrapper.setMinimumHeight(100)
        bottom_layout = QVBoxLayout(bottom_wrapper)
        bottom_layout.setContentsMargins(0, 3, 0, 0)
        bottom_layout.setSpacing(0)
        bottom_layout.addWidget(self._filtered_log_block)

        self._results_splitter = QSplitter(Qt.Orientation.Vertical)
        self._results_splitter.setObjectName("DiagResultsSplitter")
        self._results_splitter.addWidget(top_wrapper)
        self._results_splitter.addWidget(bottom_wrapper)
        theme.configure_invisible_splitter(self._results_splitter)
        self._results_splitter.setCollapsible(0, False)
        self._results_splitter.setCollapsible(1, False)
        self._full_log_block.setMinimumHeight(120)
        self._results_splitter.setStretchFactor(0, 3)
        self._results_splitter.setStretchFactor(1, 2)
        self._results_splitter.setSizes([360, 200])

        results_layout.addWidget(self._results_splitter, 1)
        self.tabs.addTab(results_tab, "")

        config_tab = QWidget()
        config_layout = QVBoxLayout(config_tab)
        theme.apply_editor_tab_content_layout(config_layout)

        self._config_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._config_splitter.setObjectName("DiagConfigSplitter")
        self._config_splitter.addWidget(self._build_settings_panel())
        self._config_splitter.addWidget(self._build_config_editor_panel())
        theme.configure_editor_horizontal_splitter(self._config_splitter)
        self._config_splitter.setStretchFactor(0, 0)
        self._config_splitter.setStretchFactor(1, 1)
        self._config_splitter.setSizes([248, 620])
        self._config_splitter.splitterMoved.connect(self._on_config_splitter_moved)
        config_layout.addWidget(self._config_splitter, 1)
        self.tabs.addTab(config_tab, "")

        layout.addWidget(self.tabs)

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
        if hasattr(self, "title_bar"):
            self.title_bar.addCenterWidget(self.status_label)

    @staticmethod
    def _diagnostics_mono_font() -> str:
        try:
            return get_privilege_backend().get_ui_font_family()
        except Exception:
            return "Monospace" if is_linux() else "Consolas"

    def _style_output_editor(self):
        theme.apply_home_console_text_widget(self.output_editor)

    def _build_log_block_header(self, title: str) -> QLabel:
        label = QLabel(title)
        label.setObjectName("HomeConsoleHeader")
        label.setStyleSheet(theme.editor_terminal_header_style())
        return label

    def _build_full_log_block(self):
        block = theme.create_editor_block("DiagFullLogBlock")
        outer = QVBoxLayout(block)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._full_log_title = self._build_log_block_header(
            tr("diag_out_block_full", self.lang)
        )
        outer.addWidget(self._full_log_title)
        outer.addWidget(self.output_editor, 1)

        bottom_pad = QWidget()
        bottom_pad.setFixedHeight(6)
        outer.addWidget(bottom_pad)
        return block

    def _build_filtered_log_block(self):
        block = theme.create_editor_block("DiagFilteredLogBlock")
        outer = QVBoxLayout(block)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._filtered_log_title = self._build_log_block_header(
            tr("diag_out_block_filtered", self.lang)
        )
        outer.addWidget(self._filtered_log_title)

        toolbar = QWidget()
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 6, 8, 6)
        toolbar_layout.setSpacing(6)

        self.output_search_edit = ContextLineEdit()
        self.output_search_edit.setFixedHeight(theme.EDITOR_FIELD_HEIGHT)
        self.output_search_edit.setStyleSheet(theme.editor_search_field_style())
        self.output_search_edit.textChanged.connect(self._refresh_filtered_output)
        toolbar_layout.addWidget(self.output_search_edit)

        categories_row = QWidget()
        categories_layout = QHBoxLayout(categories_row)
        categories_layout.setContentsMargins(0, 0, 0, 0)
        categories_layout.setSpacing(10)
        for cat_id, _statuses in _OUTPUT_FILTER_CATEGORIES:
            cb = QCheckBox(tr(f"diag_out_cat_{cat_id}", self.lang))
            cb.setChecked(cat_id in _DEFAULT_OUTPUT_FILTER_CATEGORIES)
            cb.toggled.connect(lambda _checked: self._refresh_filtered_output())
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            self._category_filter_cbs[cat_id] = cb
            categories_layout.addWidget(cb)
        categories_layout.addStretch(1)
        toolbar_layout.addWidget(categories_row)
        outer.addWidget(toolbar)

        self.filtered_output_editor = LineNumberPlainTextEdit()
        self.filtered_output_editor.setReadOnly(True)
        self.filtered_output_editor.setFrameShape(QFrame.Shape.NoFrame)
        self.filtered_output_editor.setFont(QFont(self._diagnostics_mono_font(), 10))
        self._filtered_output_highlighter = DiagnosticsLogHighlighter(
            self.filtered_output_editor.document()
        )
        theme.apply_home_console_text_widget(self.filtered_output_editor)
        outer.addWidget(self.filtered_output_editor, 1)

        bottom_pad = QWidget()
        bottom_pad.setFixedHeight(6)
        outer.addWidget(bottom_pad)
        return block

    def _status_to_output_category(self, status: str) -> str:
        for cat_id, statuses in _OUTPUT_FILTER_CATEGORIES:
            if status in statuses:
                return cat_id
        return "info"

    def _record_log_entry(self, status: str, display_line: str) -> None:
        self._log_entries.append({"status": status, "display": display_line})
        self._refresh_filtered_output()

    def _ingest_plain_log_lines(self, text: str) -> None:
        self._log_entries = []
        for line in text.splitlines():
            if not line.strip():
                continue
            if line.strip().startswith("="):
                self._log_entries.append({"status": "section", "display": line})
                continue
            match = re.match(
                r"^\[\d{2}:\d{2}:\d{2}\]\s+"
                r"(\[OK\]|\[FAIL\]|\[CRITICAL\]|\[WARN\]|\[INFO\])\s+(.*)$",
                line,
            )
            if match:
                prefix = match.group(1)
                status = {
                    "[OK]": "pass",
                    "[FAIL]": "fail",
                    "[CRITICAL]": "critical",
                    "[WARN]": "warn",
                    "[INFO]": "info",
                }.get(prefix, "info")
                self._log_entries.append({"status": status, "display": line})
                continue
            if line.startswith("    "):
                self._log_entries.append({"status": "output", "display": line})
                continue
            self._log_entries.append({"status": "info", "display": line})

    def _refresh_filtered_output(self) -> None:
        if not hasattr(self, "filtered_output_editor"):
            return

        query = self.output_search_edit.text().strip().lower()
        enabled_categories = {
            cat_id
            for cat_id, cb in self._category_filter_cbs.items()
            if cb.isChecked()
        }

        lines: list[str] = []
        for entry in self._log_entries:
            cat_id = self._status_to_output_category(entry["status"])
            if cat_id not in enabled_categories:
                continue
            display = entry["display"]
            if query and query not in display.lower():
                continue
            lines.append(display)

        self.filtered_output_editor.setPlainText("\n".join(lines))
        if self._auto_scroll_enabled and lines:
            cursor = self.filtered_output_editor.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.filtered_output_editor.setTextCursor(cursor)

    def _build_settings_panel(self) -> QWidget:
        container = QWidget()
        container.setMinimumWidth(200)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.checks_filter_edit = ContextLineEdit()
        self.checks_filter_edit.setFixedHeight(26)
        self.checks_filter_edit.setStyleSheet(theme.editor_search_field_style())
        self.checks_filter_edit.textChanged.connect(self._apply_checks_filter)
        layout.addWidget(self.checks_filter_edit)

        checks_block = theme.create_editor_block("DiagChecksBlock")
        checks_layout = QVBoxLayout(checks_block)
        checks_layout.setContentsMargins(4, 4, 4, 4)
        checks_layout.setSpacing(0)

        self.checks_list = QListWidget()
        self.checks_list.setStyleSheet(theme.diag_checks_list_style())
        self.checks_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checks_list.setSpacing(0)
        self.checks_list.setAlternatingRowColors(False)
        self.checks_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.checks_list.itemChanged.connect(self._on_check_item_changed)

        self._checks_list_stack = QStackedWidget()
        self._checks_list_stack.addWidget(self.checks_list)

        nothing_widget = QWidget()
        nothing_layout = QVBoxLayout(nothing_widget)
        nothing_layout.setContentsMargins(0, 0, 0, 0)
        self._checks_nothing_label = QLabel(tr("settings_nothing_found", self.lang))
        self._checks_nothing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._checks_nothing_label.setStyleSheet(theme.nothing_found_style())
        nothing_layout.addWidget(self._checks_nothing_label)
        self._checks_list_stack.addWidget(nothing_widget)
        self._checks_list_stack.setCurrentIndex(0)

        checks_layout.addWidget(self._checks_list_stack, 1)
        layout.addWidget(checks_block, 1)

        self.auto_fix_cb = QCheckBox(tr("diag_auto_fix", self.lang))
        self.auto_fix_cb.setChecked(self.settings.get("diagnostics_auto_fix", True))
        self.auto_fix_cb.toggled.connect(lambda _v: self._save_check_settings())

        self.windows_cmds_hint = QLabel(tr_platform("diag_config_shell_hint", self.lang))
        self.windows_cmds_hint.setWordWrap(True)
        self.windows_cmds_hint.setStyleSheet(theme.muted_label_style())
        layout.addWidget(self.windows_cmds_hint)

        if is_linux():
            self.auto_fix_cb.hide()
        else:
            layout.addWidget(self.auto_fix_cb)

        self._populate_checks_list()
        return container

    def _style_category_header(self, item: QListWidgetItem) -> None:
        p = theme.palette()
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setForeground(QBrush(theme.qcolor(p.fg_muted)))
        item.setSizeHint(QSize(-1, 26))

    def _populate_checks_list(self) -> None:
        saved_states = {
            cid: item.checkState()
            for cid, item in self._check_items.items()
        }
        self.checks_list.blockSignals(True)
        self.checks_list.clear()
        self._check_items.clear()
        self._category_headers.clear()

        categories: dict[str, list] = {}
        for check in checks_for_platform():
            categories.setdefault(check.category, []).append(check)

        for cat_id, checks in categories.items():
            if not checks:
                continue
            cat_title = tr(cat_id, self.lang)
            header = QListWidgetItem(cat_title)
            header.setData(_ROLE_IS_HEADER, True)
            header.setData(_ROLE_CATEGORY, cat_id)
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._style_category_header(header)
            self.checks_list.addItem(header)
            self._category_headers[cat_id] = header

            for check in checks:
                label = tr(f"diag_check_{check.check_id}", self.lang)
                item = QListWidgetItem(label)
                item.setData(_ROLE_CHECK_ID, check.check_id)
                item.setData(_ROLE_CATEGORY, cat_id)
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsSelectable
                )
                state = saved_states.get(check.check_id, Qt.CheckState.Checked)
                item.setCheckState(state)
                if check.critical:
                    item.setToolTip(tr("diag_check_critical_hint", self.lang))
                self.checks_list.addItem(item)
                self._check_items[check.check_id] = item

        self.checks_list.blockSignals(False)
        self._apply_checks_filter(self.checks_filter_edit.text())

    def _apply_checks_filter(self, text: str) -> None:
        query = text.strip().lower()
        visible_checks = 0
        category_visible: dict[str, bool] = {cat_id: False for cat_id in self._category_headers}

        for item in self._check_items.values():
            check_id = item.data(_ROLE_CHECK_ID)
            cat_id = item.data(_ROLE_CATEGORY)
            label = tr(f"diag_check_{check_id}", self.lang).lower()
            cat_label = tr(cat_id, self.lang).lower() if cat_id else ""
            visible = (
                not query
                or query in label
                or query in cat_label
                or query in check_id.lower()
            )
            item.setHidden(not visible)
            if visible:
                visible_checks += 1
                if cat_id:
                    category_visible[cat_id] = True

        for cat_id, header in self._category_headers.items():
            header.setHidden(not category_visible.get(cat_id, False))

        if query and visible_checks == 0:
            self._checks_list_stack.setCurrentIndex(1)
        else:
            self._checks_list_stack.setCurrentIndex(0)

    def _build_config_editor_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        config_block = theme.create_editor_block("DiagConfigBlock")
        config_layout = QVBoxLayout(config_block)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(6)

        self.config_hint = QLabel()
        self.config_hint.setStyleSheet(theme.editor_terminal_header_style())
        header_layout.addWidget(self.config_hint, 1)

        self.save_config_btn = QPushButton(tr("diag_config_save", self.lang))
        self.save_config_btn.clicked.connect(self._save_config_from_editor)
        self.reload_config_btn = QPushButton(tr("diag_config_reload", self.lang))
        self.reload_config_btn.clicked.connect(self._reload_config_from_disk)
        self.insert_template_btn = QPushButton(tr("diag_insert_cmd_template", self.lang))
        self.insert_template_btn.clicked.connect(self._insert_command_template)
        self.copy_ai_prompt_btn = QPushButton(tr("diag_copy_ai_prompt", self.lang))
        self.copy_ai_prompt_btn.clicked.connect(self._copy_ai_prompt)
        header_layout.addWidget(self.save_config_btn)
        header_layout.addWidget(self.reload_config_btn)
        header_layout.addWidget(self.insert_template_btn)
        header_layout.addWidget(self.copy_ai_prompt_btn)
        self._apply_compact_config_buttons()
        config_layout.addWidget(header)

        self.config_editor = LineNumberPlainTextEdit()
        try:
            mono = get_privilege_backend().get_ui_font_family()
        except Exception:
            mono = "Monospace" if is_linux() else "Consolas"
        self.config_editor.setFont(QFont(mono, 10))
        self._config_highlighter = JsonHighlighter(self.config_editor.document())
        self.config_editor.textChanged.connect(self._on_config_text_changed)
        theme.apply_editor_text_widget(self.config_editor)
        config_layout.addWidget(self.config_editor, 1)
        layout.addWidget(config_block, 1)
        return container

    @staticmethod
    def _apply_pointer_cursors(*widgets):
        for widget in widgets:
            widget.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_compact_config_buttons(self) -> None:
        style = theme.compact_toolbar_button_style()
        for btn in (
            self.save_config_btn,
            self.reload_config_btn,
            self.insert_template_btn,
            self.copy_ai_prompt_btn,
        ):
            btn.setStyleSheet(style)
            btn.setFixedHeight(24)

    def _create_toolbar(self) -> UnifiedToolbar:
        bar = UnifiedToolbar(self)
        self.btn_start = CodiconButton("play", tr("diag_run_button", self.lang), self)
        self.btn_stop = CodiconButton("debug-stop", tr("test_stop_button", self.lang), self)
        self.btn_start.clicked.connect(self._start_diagnostics)
        self.btn_stop.clicked.connect(self._stop_diagnostics)

        self.preset_combo = CustomComboBox(self)
        self.preset_combo.addItem(tr("diag_select_all", self.lang), "all")
        self.preset_combo.addItem(tr("diag_critical_only", self.lang), "critical")
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)

        bar.add_button(self.btn_start)
        bar.add_button(self.btn_stop)
        bar.add_separator()
        bar.add_combobox(self.preset_combo, 150, flat=True)
        self._transport_toolbar = bar
        self._update_transport_buttons()
        return bar

    def _apply_tabs_style(self):
        self.tabs.setDocumentMode(False)
        self.tabs.setIconSize(QSize(14, 16))
        tab_bar = self.tabs.tabBar()
        tab_bar.setUsesScrollButtons(True)
        tab_bar.setExpanding(False)
        tab_bar.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.apply_theme(widget_id="DiagnosticsTabWidget")

    def _focus_checks_search(self) -> None:
        if hasattr(self, "checks_filter_edit"):
            self.checks_filter_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self.checks_filter_edit.selectAll()

    def _focus_search_shortcut(self) -> None:
        if self.tabs.currentIndex() == 0 and hasattr(self, "output_search_edit"):
            self.output_search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self.output_search_edit.selectAll()
            return
        self._focus_checks_search()

    def refresh_theme(self):
        self._apply_tabs_style()
        self._style_output_editor()
        self._update_tabs_icons()
        p = theme.palette()
        if hasattr(self, "checks_filter_edit"):
            self.checks_filter_edit.setStyleSheet(theme.editor_search_field_style())
        if hasattr(self, "checks_list"):
            self.checks_list.setStyleSheet(theme.diag_checks_list_style())
            for header in getattr(self, "_category_headers", {}).values():
                self._style_category_header(header)
        if hasattr(self, "config_hint"):
            self.config_hint.setStyleSheet(theme.editor_terminal_header_style())
        if hasattr(self, "_config_splitter"):
            theme.configure_editor_horizontal_splitter(self._config_splitter)
        theme.refresh_editor_blocks(self)
        theme.refresh_round_clip_widgets(self)
        if hasattr(self, "config_editor"):
            theme.apply_editor_text_widget(self.config_editor)
            self.config_editor.refresh_editor_colors()
        if hasattr(self, "_config_highlighter") and hasattr(self._config_highlighter, "refresh_theme"):
            self._config_highlighter.refresh_theme()
        if hasattr(self, "_output_highlighter") and hasattr(self._output_highlighter, "refresh_theme"):
            self._output_highlighter.refresh_theme()
        if hasattr(self, "output_editor"):
            theme.apply_home_console_text_widget(self.output_editor)
            self.output_editor.refresh_editor_colors()
        if hasattr(self, "filtered_output_editor"):
            theme.apply_home_console_text_widget(self.filtered_output_editor)
            self.filtered_output_editor.refresh_editor_colors()
        if hasattr(self, "output_search_edit"):
            self.output_search_edit.setStyleSheet(theme.editor_search_field_style())
        for title_attr in ("_full_log_title", "_filtered_log_title"):
            title = getattr(self, title_attr, None)
            if title is not None:
                title.setStyleSheet(theme.editor_terminal_header_style())
        if hasattr(self, "_filtered_output_highlighter") and hasattr(
            self._filtered_output_highlighter, "refresh_theme"
        ):
            self._filtered_output_highlighter.refresh_theme()
        if hasattr(self, "_results_splitter"):
            theme.configure_invisible_splitter(self._results_splitter)
        if hasattr(self, "preset_combo") and hasattr(self.preset_combo, "apply_theme"):
            self.preset_combo.apply_theme()
        if hasattr(self, "status_label"):
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    color: {p.fg_text};
                    font-size: 12px;
                    background-color: transparent;
                    border: none;
                }}
            """)
        toolbar = getattr(self, "_transport_toolbar", None)
        if toolbar and hasattr(toolbar, "apply_theme"):
            toolbar.apply_theme()
        self._apply_theme()

    def retranslate_ui(self):
        self.setWindowTitle(tr("menu_run_diagnostics", self.lang))
        self.view_menu.setTitle(tr("test_menu_view", self.lang))
        self.auto_scroll_action.setText(tr("test_auto_scroll", self.lang))
        if hasattr(self, "_fullscreen_action"):
            self._fullscreen_action.setText(tr("editor_fullscreen", self.lang))
        self.export_log_action.setText(tr("diag_export_log", self.lang))

        self.tabs.setTabText(0, tr("diag_tab_results", self.lang))
        self.tabs.setTabText(1, tr("diag_tab_config", self.lang))
        self._update_tabs_icons()

        self.checks_filter_edit.setPlaceholderText(tr("diag_search_placeholder", self.lang))
        if hasattr(self, "_full_log_title"):
            self._full_log_title.setText(tr("diag_out_block_full", self.lang))
        if hasattr(self, "_filtered_log_title"):
            self._filtered_log_title.setText(tr("diag_out_block_filtered", self.lang))
        if hasattr(self, "output_search_edit"):
            self.output_search_edit.setPlaceholderText(
                tr("diag_output_search_placeholder", self.lang)
            )
        for cat_id, cb in self._category_filter_cbs.items():
            cb.setText(tr(f"diag_out_cat_{cat_id}", self.lang))
        self.auto_fix_cb.setText(tr("diag_auto_fix", self.lang))
        if hasattr(self, "windows_cmds_hint"):
            self.windows_cmds_hint.setText(tr_platform("diag_config_shell_hint", self.lang))
        if is_linux():
            self.auto_fix_cb.hide()
        else:
            self.auto_fix_cb.show()
        self.config_hint.setText(
            f"{tr_platform('diag_config_hint', self.lang)}  ·  {get_diagnostics_config_path()}"
        )
        self.save_config_btn.setText(tr("diag_config_save", self.lang))
        self.reload_config_btn.setText(tr("diag_config_reload", self.lang))
        if hasattr(self, "insert_template_btn"):
            self.insert_template_btn.setText(tr("diag_insert_cmd_template", self.lang))
        if hasattr(self, "copy_ai_prompt_btn"):
            self.copy_ai_prompt_btn.setText(tr("diag_copy_ai_prompt", self.lang))
        if hasattr(self, "save_config_btn"):
            self._apply_compact_config_buttons()
        self._checks_nothing_label.setText(tr("settings_nothing_found", self.lang))
        self._populate_checks_list()
        if hasattr(self, "preset_combo"):
            self._retranslate_preset_combo()
        self.btn_start.setToolTip(tr("diag_run_button", self.lang))
        self.btn_stop.setToolTip(tr("test_stop_button", self.lang))

    def _on_config_splitter_moved(self, _pos: int, _index: int) -> None:
        self._clamp_config_splitter_sizes()

    def _clamp_config_splitter_sizes(self) -> None:
        splitter = self._config_splitter
        left_min, left_max, right_min = 200, 360, 280
        left, right = splitter.sizes()
        total = left + right
        if total <= 0:
            return

        changed = False
        if left < left_min:
            left = left_min
            right = max(right_min, total - left)
            changed = True
        elif left > left_max:
            left = left_max
            right = max(right_min, total - left)
            changed = True
        if right < right_min:
            right = right_min
            left = min(left_max, max(left_min, total - right))
            changed = True

        if changed:
            splitter.blockSignals(True)
            splitter.setSizes([left, right])
            splitter.blockSignals(False)

    def _retranslate_preset_combo(self):
        combo = self.preset_combo
        current_mode = combo.itemData(combo.currentIndex()) if combo.currentIndex() >= 0 else "all"
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(tr("diag_select_all", self.lang), "all")
        combo.addItem(tr("diag_critical_only", self.lang), "critical")
        for index in range(combo.count()):
            if combo.itemData(index) == current_mode:
                combo.setCurrentIndex(index)
                break
        combo.blockSignals(False)

    def _update_tabs_icons(self):
        from src.shared.ui.assets.codicon_utils import codicon_icon

        for index, icon_name in enumerate(_TAB_ICONS):
            if index >= self.tabs.count():
                break
            icon = codicon_icon(icon_name, 14)
            if not icon.isNull():
                self.tabs.setTabIcon(index, icon)

    def _update_transport_buttons(self):
        running = self._is_running
        self.btn_start.setVisible(not running)
        self.btn_stop.setVisible(running)
        self.preset_combo.setEnabled(not running)

    def _on_auto_scroll_toggled(self, checked: bool):
        self._auto_scroll_enabled = checked

    def _on_check_item_changed(self, item: QListWidgetItem):
        if item.data(_ROLE_IS_HEADER):
            return
        self._save_check_settings()

    def _load_check_settings(self):
        saved = self.settings.get("diagnostics_enabled_checks") or {}
        if not isinstance(saved, dict):
            saved = {}
        defaults = default_enabled_checks()
        self.checks_list.blockSignals(True)
        for check_id, item in self._check_items.items():
            enabled = saved.get(check_id, defaults.get(check_id, True))
            item.setCheckState(
                Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
            )
        self.checks_list.blockSignals(False)

    def _save_check_settings(self):
        enabled = {
            cid: item.checkState() == Qt.CheckState.Checked
            for cid, item in self._check_items.items()
        }
        auto_fix = self.auto_fix_cb.isChecked()
        if not self._persist_config_setting("diagnostics_enabled_checks", enabled):
            return
        if not self._persist_config_setting("diagnostics_auto_fix", auto_fix):
            return

    def _persist_config_setting(self, key, value):
        previous = self.settings.get(key)
        self.settings[key] = value
        if self.config and self.config.set_setting(key, value):
            return True
        self.settings[key] = previous
        QMessageBox.warning(
            self,
            tr("msg_error", self.lang),
            tr("msg_config_save_failed", self.lang),
        )
        return False

    def closeEvent(self, event):
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.stop()
            try:
                worker.finished.disconnect(self._on_diagnostics_finished)
            except (TypeError, RuntimeError):
                pass
            worker.wait(5000)
            if worker.isRunning():
                worker.terminate()
                worker.wait(1000)
        self._worker = None
        self._is_running = False
        super().closeEvent(event)

    def _set_all_checks_true(self):
        self._set_all_checks(True)

    def _set_all_checks_false(self):
        self._set_all_checks(False)

    def _set_all_checks(self, value: bool):
        state = Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
        self.checks_list.blockSignals(True)
        for item in self._check_items.values():
            item.setCheckState(state)
        self.checks_list.blockSignals(False)
        self._save_check_settings()

    def _select_critical_only(self):
        critical = set(critical_check_ids())
        self.checks_list.blockSignals(True)
        for cid, item in self._check_items.items():
            item.setCheckState(
                Qt.CheckState.Checked if cid in critical else Qt.CheckState.Unchecked
            )
        self.checks_list.blockSignals(False)
        self._save_check_settings()

    def _on_preset_changed(self, index: int):
        mode = self.preset_combo.itemData(index)
        if mode == "critical":
            self._select_critical_only()
        elif mode == "all":
            self._set_all_checks_true()

    def _get_enabled_checks(self) -> dict[str, bool]:
        return {
            cid: item.checkState() == Qt.CheckState.Checked
            for cid, item in self._check_items.items()
        }

    def _load_config_editor(self):
        self._is_loading_config = True
        cfg = localize_diagnostics_config(ensure_diagnostics_config(), self.lang)
        self.config_editor.setPlainText(config_to_text(cfg))
        self._is_loading_config = False
        self._config_dirty = False

    def _on_config_text_changed(self):
        if self._is_loading_config:
            return
        self._config_dirty = True

    def _parse_editor_config(self) -> dict | None:
        text = self.config_editor.toPlainText().strip()
        if not text:
            return {"version": 1, "custom_commands": []}
        try:
            return parse_config_text(text)
        except (json.JSONDecodeError, ValueError) as exc:
            QMessageBox.warning(
                self,
                tr("menu_run_diagnostics", self.lang),
                tr("diag_config_invalid", self.lang).format(str(exc)),
            )
            return None

    def _save_config_from_editor(self):
        cfg = self._parse_editor_config()
        if cfg is None:
            return
        save_diagnostics_config(cfg)
        self._config_dirty = False
        self.status_label.setText(tr("diag_config_saved", self.lang))

    def _reload_config_from_disk(self):
        self._is_loading_config = True
        cfg = localize_diagnostics_config(load_diagnostics_config(), self.lang)
        self.config_editor.setPlainText(config_to_text(cfg))
        self._is_loading_config = False
        self._config_dirty = False
        self.status_label.setText(tr("diag_config_reloaded", self.lang))

    def _insert_command_template(self):
        cfg = self._parse_editor_config()
        if cfg is None:
            return
        commands = cfg.setdefault("custom_commands", [])
        index = len(commands) + 1
        commands.append(make_command_template(index=index, lang=self.lang))
        self._is_loading_config = True
        self.config_editor.setPlainText(config_to_text(cfg))
        self._is_loading_config = False
        self._config_dirty = True
        self.status_label.setText(tr("diag_cmd_template_inserted", self.lang))

    def _copy_ai_prompt(self):
        cfg = None
        text = self.config_editor.toPlainText().strip()
        if text:
            try:
                cfg = parse_config_text(text)
            except (json.JSONDecodeError, ValueError):
                cfg = load_diagnostics_config()
        else:
            cfg = load_diagnostics_config()

        os_info = f"{platform.system()} {platform.release()} ({platform.version()})"
        prompt = build_ai_diagnostics_prompt(
            lang=self.lang,
            app_version=VERSION,
            winws_path=get_winws_path(),
            os_info=os_info,
            current_config=cfg,
        )
        QApplication.clipboard().setText(prompt)
        self.status_label.setText(tr("diag_ai_prompt_copied", self.lang))

    def _format_report_os_line(self) -> str:
        release = platform.release()
        version = platform.version()
        arch = platform.machine()
        if is_linux():
            return f"Linux {release} ({arch})"
        return f"Windows {release} (Build {version}, {arch})"

    def _build_report_header(self) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        host = socket.gethostname()
        user = os.environ.get("USERNAME") or os.environ.get("USER") or "?"
        os_line = self._format_report_os_line()
        winws = get_winws_path()
        enabled_count = sum(1 for v in self._get_enabled_checks().values() if v)
        auto_fix = tr("diag_yes", self.lang) if self.auto_fix_cb.isChecked() else tr("diag_no", self.lang)
        sep = "=" * 78
        lines = [
            sep,
            tr("diag_header_title", self.lang),
            sep,
            tr("diag_header_datetime", self.lang).format(now),
            tr("diag_header_host", self.lang).format(host),
            tr("diag_header_user", self.lang).format(user),
            tr("diag_header_os", self.lang).format(os_line),
            tr_platform("diag_header_winws", self.lang).format(winws),
            tr("diag_header_app", self.lang).format(VERSION),
            tr("diag_header_checks", self.lang).format(enabled_count),
            tr("diag_header_auto_fix", self.lang).format(auto_fix),
            sep,
            "",
        ]
        return "\n".join(lines)

    def _start_diagnostics(self):
        if self._worker and self._worker.isRunning():
            return
        if self._config_dirty:
            self._save_config_from_editor()

        custom_config = self._parse_editor_config()
        if custom_config is None:
            return

        self._save_check_settings()
        header = self._build_report_header()
        self.output_editor.clear()
        self.output_editor.setPlainText(header)
        self._ingest_plain_log_lines(header)
        self._refresh_filtered_output()
        self.status_label.setText(tr("diag_running", self.lang))

        self._is_running = True
        self._diag_user_stopped = False
        self._update_transport_buttons()

        self._worker = _DiagnosticsWorker(
            self.lang,
            self._get_enabled_checks(),
            self.auto_fix_cb.isChecked(),
            custom_config,
        )
        self._worker.progress.connect(self._on_diagnostics_progress)
        self._worker.finished.connect(self._on_diagnostics_finished)
        self._worker.start()

    def _stop_diagnostics(self):
        if self._worker and self._worker.isRunning():
            self._diag_user_stopped = True
            self._worker.stop()
            self.status_label.setText(tr("diag_stopped", self.lang))

    @pyqtSlot(str, str)
    def _on_diagnostics_progress(self, status: str, message: str):
        self._append_line(status, message)

    @pyqtSlot(list, dict)
    def _on_diagnostics_finished(self, results, summary):
        self._is_running = False
        self._update_transport_buttons()
        if not getattr(self, "_diag_user_stopped", False):
            self._append_line("info", tr("diag_completed", self.lang))
        self.status_label.setText(tr("diag_summary", self.lang).format(
            summary.get("pass", 0),
            summary.get("fail", 0),
            summary.get("warn", 0),
        ))
        self._worker = None

    def _append_line(self, status: str, message: str):
        if status == "output":
            display = f"    {message}"
            self.output_editor.appendPlainText(display)
            self._record_log_entry("output", display)
            if self._auto_scroll_enabled:
                cursor = self.output_editor.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.output_editor.setTextCursor(cursor)
            if not getattr(self, "_defer_output_events", False):
                QApplication.processEvents()
            return

        if message.startswith("==="):
            self.output_editor.appendPlainText(message)
            self._record_log_entry("section", message)
        elif "\n" in message:
            parts = message.split("\n")
            for index, part in enumerate(parts):
                if index == 0:
                    self._append_timestamped_line(status, part)
                else:
                    self._append_line("output", part)
            if self._auto_scroll_enabled:
                cursor = self.output_editor.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.output_editor.setTextCursor(cursor)
            if not getattr(self, "_defer_output_events", False):
                QApplication.processEvents()
            return
        else:
            self._append_timestamped_line(status, message)

        if self._auto_scroll_enabled:
            cursor = self.output_editor.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.output_editor.setTextCursor(cursor)
        if not getattr(self, "_defer_output_events", False):
            QApplication.processEvents()

    def _append_timestamped_line(self, status: str, message: str):
        prefix = _STATUS_PREFIX.get(status, "[INFO]")
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {prefix} {message}"
        self.output_editor.appendPlainText(line)
        self._record_log_entry(status, line)

    def _export_txt(self):
        content = self.output_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, tr("diag_export_log", self.lang), tr("export_no_data", self.lang))
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("diag_export_log", self.lang),
            f"diagnostics_{datetime.now():%Y%m%d_%H%M%S}.txt",
            "Text Files (*.txt)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            QMessageBox.information(self, tr("diag_export_log", self.lang), tr("export_success", self.lang).format(path))
