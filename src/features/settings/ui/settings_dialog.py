"""
Диалог настроек: поиск + список категорий слева, содержимое справа.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QBrush, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QFileDialog,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.shared.ui.assets.embedded_assets import get_app_icon
from src.shared.lib.github_utils import resolve_github_repo
from src.shared.lib.path_utils import get_base_path, validate_winws_folder, validate_linux_runtime_folder
from src.platform import is_linux
from src.platform.linux.network_interfaces import list_network_interfaces
from src.shared.i18n.translator import tr, tr_platform
from src.features.updates.app_updater import AppUpdater
from src.entities.zapret.zapret_updater import ZapretUpdater
from src.shared.ui import theme
from src.shared.ui.standard_dialog import StandardDialog
from src.app.launch_args_display import LaunchArgsReferenceWidget
from src.shared.ui.message_box_utils import configure_message_box
from PyQt6.QtWidgets import QMessageBox
from src.widgets.custom_checkbox import CustomCheckBox as QCheckBox
from src.widgets.custom_combobox import CustomComboBox
from src.widgets.custom_context_widgets import ContextLineEdit

_ROLE_PAGE = Qt.ItemDataRole.UserRole
_ROLE_IS_HEADER = Qt.ItemDataRole.UserRole + 1
_ROLE_SEARCH = Qt.ItemDataRole.UserRole + 2
_ROLE_SECTION = Qt.ItemDataRole.UserRole + 3


class _SettingsNavDelegate(QStyledItemDelegate):
    """Заголовки секций без hover/selection."""

    def __init__(self, header_role, parent=None):
        super().__init__(parent)
        self._header_role = header_role

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        if index.data(self._header_role):
            from PyQt6.QtWidgets import QStyle

            opt.state &= ~QStyle.StateFlag.State_MouseOver
            opt.state &= ~QStyle.StateFlag.State_Selected
            opt.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, opt, index)


from src.widgets.rounded_clip import RoundedClipFrame


class SettingsCard(RoundedClipFrame):
    """Карточка настройки с заголовком."""

    def __init__(self, title: str, parent=None):
        super().__init__(
            "SettingsCard",
            radius=theme.PANEL_RADIUS,
            parent=parent,
            bg="bg_panel",
            draw_border=True,
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)
        self._title = QLabel(title)
        self._title.setObjectName("SettingsCardTitle")
        outer.addWidget(self._title)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        outer.addLayout(self.body)

    def add_widget(self, widget):
        self.body.addWidget(widget)

    def add_layout(self, layout):
        self.body.addLayout(layout)


class SettingsDialog(StandardDialog):
    """Диалог настроек с поиском и списком категорий."""

    def __init__(
        self,
        parent=None,
        settings=None,
        config=None,
        autostart_manager=None,
        zapret_updater=None,
        winws_manager=None,
    ):
        self.settings = dict(settings or {})
        self.config = config
        self.autostart_manager = autostart_manager
        self.zapret_updater = zapret_updater
        self.winws_manager = winws_manager
        self.lang = self.settings.get("language", "ru")
        self._nav_items: list[QListWidgetItem] = []
        self._category_headers: dict[str, QListWidgetItem] = {}
        self._last_nav_item: QListWidgetItem | None = None

        super().__init__(
            parent=parent,
            title=tr("settings_dialog_title", self.lang),
            width=920,
            height=620,
            icon=get_app_icon(),
            theme="dark",
            resizable=True,
        )
        self._build_ui()
        self.refresh_theme()
        self.setMinimumSize(920, 620)
        self.resize(920, 620)

        shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self._focus_search)

    def accept(self):
        runtime_path = self.winws_path_edit.text().strip()
        if is_linux():
            if runtime_path:
                ok, reason = validate_linux_runtime_folder(runtime_path)
                if not ok:
                    detail = tr("linux_runtime_setup_err_no_service", self.lang)
                    if reason == "not_directory":
                        detail = tr("linux_runtime_setup_err_not_dir", self.lang)
                    msg = configure_message_box(QMessageBox(self))
                    msg.setWindowTitle(tr("msg_error", self.lang))
                    msg.setText(tr("settings_winws_path_invalid", self.lang).format(detail))
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.exec()
                    return
        else:
            ok, reason = validate_winws_folder(runtime_path)
            if not ok:
                if reason == "not_directory":
                    detail = tr("winws_setup_invalid_path", self.lang)
                else:
                    detail = tr("winws_setup_invalid_folder", self.lang)
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr("msg_error", self.lang))
                msg.setText(tr("settings_winws_path_invalid", self.lang).format(detail))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
                return
        super().accept()

    def _build_ui(self):
        layout = self.getContentLayout()
        theme.apply_editor_tab_content_layout(layout)
        layout.setSpacing(10)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("SettingsSplitter")
        self._splitter.addWidget(self._build_nav_panel())
        self._splitter.addWidget(self._build_content_panel())
        theme.configure_editor_horizontal_splitter(
            self._splitter,
            left_min=220,
            right_min=420,
        )
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([260, 620])
        layout.addWidget(self._splitter, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton(tr("settings_ok", self.lang))
        ok_btn.setDefault(True)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(tr("settings_cancel", self.lang))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self._populate_nav_list()
        self._select_first_page()

    def _build_nav_panel(self) -> QWidget:
        container = QWidget()
        container.setMinimumWidth(200)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.search_edit = ContextLineEdit()
        self.search_edit.setPlaceholderText(tr("settings_search_placeholder", self.lang))
        self.search_edit.setFixedHeight(theme.EDITOR_FIELD_HEIGHT)
        self.search_edit.textChanged.connect(self._apply_search_filter)
        layout.addWidget(self.search_edit)

        nav_block = theme.create_editor_block("SettingsNavBlock")
        nav_layout = QVBoxLayout(nav_block)
        nav_layout.setContentsMargins(4, 4, 4, 4)
        nav_layout.setSpacing(0)

        self.nav_list = QListWidget()
        self.nav_list.setItemDelegate(_SettingsNavDelegate(_ROLE_IS_HEADER, self.nav_list))
        self.nav_list.setStyleSheet(theme.editor_file_list_style())
        self.nav_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_list.currentItemChanged.connect(self._on_nav_selection_changed)
        self.nav_list.itemPressed.connect(self._on_nav_item_pressed)

        self._nav_stack = QStackedWidget()
        self._nav_stack.addWidget(self.nav_list)

        nothing_widget = QWidget()
        nothing_layout = QVBoxLayout(nothing_widget)
        nothing_layout.setContentsMargins(0, 0, 0, 0)
        self._nothing_label = QLabel(tr("settings_nothing_found", self.lang))
        self._nothing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._nothing_label.setStyleSheet(theme.nothing_found_style())
        nothing_layout.addWidget(self._nothing_label)
        self._nav_stack.addWidget(nothing_widget)
        self._nav_stack.setCurrentIndex(0)

        nav_layout.addWidget(self._nav_stack, 1)
        layout.addWidget(nav_block, 1)
        return container

    def _build_content_panel(self) -> QWidget:
        self.content_stack = QStackedWidget()
        self.content_stack.setMinimumWidth(360)
        self._create_pages()
        return self.content_stack

    def _populate_nav_list(self):
        self.nav_list.clear()
        self._nav_items.clear()
        self._category_headers.clear()

        sections = [
            (tr("settings_section_general", self.lang), [
                (tr("settings_category_language", self.lang), 0, "language"),
                (tr("settings_category_winws_path", self.lang), 1, "winws"),
                (tr("settings_category_tray", self.lang), 2, "tray"),
                (tr("settings_category_exit_behavior", self.lang), 3, "exit"),
            ]),
            (tr("settings_section_startup", self.lang), [
                (tr("settings_category_autostart", self.lang), 4, "autostart"),
                (tr("settings_category_filters", self.lang), 5, "filters"),
                *(
                    [(tr("settings_category_app_restart", self.lang), 6, "apps")]
                    if not is_linux()
                    else []
                ),
                (tr("settings_category_auto_update", self.lang), 8, "autoupdate"),
            ]),
            (tr("settings_section_advanced", self.lang), [
                (tr("settings_category_b_flag", self.lang), 7, "bflag"),
                (tr("settings_category_app_repo", self.lang), 9, "apprepo"),
                (tr("settings_category_zapret_repo", self.lang), 10, "zapretrepo"),
                (tr("settings_category_strategy_update", self.lang), 11, "stratupdate"),
                (tr("settings_category_launch_args", self.lang), 12, "launchargs"),
            ]),
        ]

        for section_title, items in sections:
            header = QListWidgetItem(section_title)
            header.setData(_ROLE_IS_HEADER, True)
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            header.setData(_ROLE_SEARCH, section_title.lower())
            self._style_section_header(header)
            self.nav_list.addItem(header)
            self._category_headers[section_title] = header

            for title, page_idx, slug in items:
                item = QListWidgetItem(title)
                item.setData(_ROLE_PAGE, page_idx)
                item.setData(_ROLE_SECTION, section_title)
                item.setData(_ROLE_SEARCH, f"{section_title} {title} {slug}".lower())
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.nav_list.addItem(item)
                self._nav_items.append(item)

    def _style_section_header(self, item: QListWidgetItem) -> None:
        p = theme.palette()
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setForeground(QBrush(theme.qcolor(p.fg_muted)))
        item.setSizeHint(QSize(-1, 26))

    def _select_first_page(self):
        for item in self._nav_items:
            if not item.isHidden():
                self.nav_list.setCurrentItem(item)
                return

    def _focus_search(self):
        self.search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search_edit.selectAll()

    def _on_nav_selection_changed(self, current: QListWidgetItem | None, _previous):
        if current is None or current.data(_ROLE_IS_HEADER):
            return
        self._last_nav_item = current
        page = current.data(_ROLE_PAGE)
        if page is not None:
            self.content_stack.setCurrentIndex(int(page))

    def _on_nav_item_pressed(self, item: QListWidgetItem):
        if item.data(_ROLE_IS_HEADER) and self._last_nav_item is not None:
            QTimer.singleShot(0, lambda: self.nav_list.setCurrentItem(self._last_nav_item))

    def _apply_search_filter(self, text: str):
        query = text.strip().lower()
        visible_count = 0
        section_visible = {title: False for title in self._category_headers}

        for item in self._nav_items:
            haystack = item.data(_ROLE_SEARCH) or item.text().lower()
            visible = not query or query in haystack
            item.setHidden(not visible)
            if visible:
                visible_count += 1
                section = item.data(_ROLE_SECTION)
                if section in section_visible:
                    section_visible[section] = True

        for section_title, header in self._category_headers.items():
            header.setHidden(not section_visible.get(section_title, False) and bool(query))

        if query and visible_count == 0:
            self._nav_stack.setCurrentIndex(1)
            self.nav_list.clearSelection()
        else:
            self._nav_stack.setCurrentIndex(0)
            current = self.nav_list.currentItem()
            if current is None or current.isHidden() or current.data(_ROLE_IS_HEADER):
                self._select_first_page()

    def _make_scroll_page(self, builder) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        inner.setObjectName("SettingsPage")
        page_layout = QVBoxLayout(inner)
        page_layout.setContentsMargins(4, 4, 8, 8)
        page_layout.setSpacing(12)
        builder(page_layout)
        page_layout.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    def _hint_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SettingsHint")
        label.setWordWrap(True)
        return label

    def _styled_table(self, columns: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(columns))
        table.setObjectName("SettingsTable")
        table.setHorizontalHeaderLabels(columns)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setShowGrid(False)
        table.setMinimumHeight(120)
        return table

    def _create_pages(self):
        self._page_language()
        self._page_winws()
        self._page_tray()
        self._page_exit()
        self._page_autostart()
        self._page_filters()
        self._page_apps()
        self._page_bflag()
        self._page_auto_update()
        self._page_app_repo()
        self._page_zapret_repo()
        self._page_strategy_update()
        self._page_launch_args()

    def _page_launch_args(self):
        def build(layout):
            card = SettingsCard(tr("settings_category_launch_args", self.lang))
            card.add_widget(self._hint_label(tr("settings_launch_args_hint", self.lang)))
            self.launch_args_ref = LaunchArgsReferenceWidget(self.lang, self)
            self.launch_args_ref.setMinimumHeight(360)
            card.add_widget(self.launch_args_ref)
            layout.addWidget(card)

        self.content_stack.addWidget(self._make_scroll_page(build))

    def _page_language(self):
        def build(layout):
            card = SettingsCard(tr("settings_category_language", self.lang))
            self.lang_combo = CustomComboBox()
            self.lang_combo.addItems([
                tr("settings_lang_russian", self.lang),
                tr("settings_lang_english", self.lang),
            ])
            self.lang_combo.setCurrentIndex(0 if self.settings.get("language", "ru") == "ru" else 1)
            card.add_widget(self.lang_combo)
            layout.addWidget(card)

        self.content_stack.addWidget(self._make_scroll_page(build))

    def _page_winws(self):
        def build(layout):
            label_key = (
                "settings_linux_runtime_path_label" if is_linux() else "settings_winws_path_label"
            )
            card = SettingsCard(tr(label_key, self.lang))
            row = QHBoxLayout()
            self.winws_path_edit = ContextLineEdit()
            placeholder_key = (
                "linux_runtime_setup_placeholder" if is_linux() else "settings_winws_path_placeholder"
            )
            self.winws_path_edit.setPlaceholderText(tr(placeholder_key, self.lang))
            if is_linux():
                path_value = (
                    self.settings.get("runtime_path", "").strip()
                    or self.settings.get("winws_path", "").strip()
                )
            else:
                path_value = self.settings.get("winws_path", "").strip()
            self.winws_path_edit.setText(path_value)
            row.addWidget(self.winws_path_edit, 1)
            browse_btn = QPushButton(tr("settings_winws_path_browse", self.lang))
            browse_btn.setFixedWidth(40)
            browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            browse_btn.clicked.connect(self._on_browse_winws_path)
            row.addWidget(browse_btn)
            card.add_layout(row)
            layout.addWidget(card)

            if is_linux():
                iface_card = SettingsCard(tr("settings_linux_interface_label", self.lang))
                self.linux_interface_combo = CustomComboBox()
                interfaces = list_network_interfaces(include_any=True)
                self.linux_interface_combo.addItems(interfaces)
                current_iface = (self.settings.get("linux_interface") or "any").strip() or "any"
                idx = self.linux_interface_combo.findText(current_iface)
                self.linux_interface_combo.setCurrentIndex(idx if idx >= 0 else 0)
                iface_card.add_widget(self.linux_interface_combo)
                layout.addWidget(iface_card)

                adv_card = SettingsCard(tr("settings_linux_advanced_label", self.lang))
                self.linux_init_combo = CustomComboBox()
                init_modes = [
                    ("auto", tr("settings_linux_init_auto", self.lang)),
                    ("systemd", tr("settings_linux_init_systemd", self.lang)),
                    ("run", tr("settings_linux_init_run", self.lang)),
                ]
                for _value, label in init_modes:
                    self.linux_init_combo.addItem(label, _value)
                current_init = (self.settings.get("linux_init_mode") or "auto").strip().lower()
                for idx, (value, _label) in enumerate(init_modes):
                    if value == current_init:
                        self.linux_init_combo.setCurrentIndex(idx)
                        break
                adv_card.add_widget(self.linux_init_combo)

                self.linux_firewall_combo = CustomComboBox()
                fw_modes = [
                    ("auto", tr("settings_linux_firewall_auto", self.lang)),
                    ("nftables", tr("settings_linux_firewall_nftables", self.lang)),
                    ("iptables", tr("settings_linux_firewall_iptables", self.lang)),
                ]
                for _value, label in fw_modes:
                    self.linux_firewall_combo.addItem(label, _value)
                current_fw = (self.settings.get("linux_firewall_backend") or "auto").strip().lower()
                for idx, (value, _label) in enumerate(fw_modes):
                    if value == current_fw:
                        self.linux_firewall_combo.setCurrentIndex(idx)
                        break
                adv_card.add_widget(self.linux_firewall_combo)
                layout.addWidget(adv_card)

        self.content_stack.addWidget(self._make_scroll_page(build))

    def _page_tray(self):
        def build(layout):
            card = SettingsCard(tr("settings_category_tray", self.lang))
            self.show_tray_cb = QCheckBox(tr("settings_show_tray", self.lang))
            self.show_tray_cb.setChecked(self.settings.get("show_in_tray", True))
            self.show_tray_cb.setCursor(Qt.CursorShape.PointingHandCursor)
            card.add_widget(self.show_tray_cb)

            self.start_minimized_cb = QCheckBox(tr("settings_start_minimized", self.lang))
            self.start_minimized_cb.setChecked(self.settings.get("start_minimized", False))
            self.start_minimized_cb.setCursor(Qt.CursorShape.PointingHandCursor)
            self.start_minimized_cb.setVisible(self.show_tray_cb.isChecked())

            def on_show_tray_toggled(checked: bool):
                self.start_minimized_cb.setVisible(checked)
                if not checked:
                    self.start_minimized_cb.setChecked(False)

            self.show_tray_cb.toggled.connect(on_show_tray_toggled)
            card.add_widget(self.start_minimized_cb)
            layout.addWidget(card)

        self.content_stack.addWidget(self._make_scroll_page(build))

    def _page_exit(self):
        def build(layout):
            card = SettingsCard(tr("settings_category_exit_behavior", self.lang))
            self.close_winws_cb = QCheckBox(tr_platform("settings_close_winws", self.lang))
            self.close_winws_cb.setChecked(self.settings.get("close_winws_on_exit", True))
            self.close_winws_cb.setCursor(Qt.CursorShape.PointingHandCursor)
            card.add_widget(self.close_winws_cb)
            layout.addWidget(card)

        self.content_stack.addWidget(self._make_scroll_page(build))

    def _setting_default(self, key: str):
        if self.config is not None:
            return self.config.default_settings.get(key)
        return None

    def _setting_bool(self, key: str) -> bool:
        if key in self.settings:
            return bool(self.settings[key])
        default = self._setting_default(key)
        return bool(default) if default is not None else False

    def _page_autostart(self):
        def build(layout):
            card = SettingsCard(tr("settings_category_autostart", self.lang))
            label_key = "settings_autostart_linux" if is_linux() else "settings_autostart_windows"
            tooltip_key = "settings_autostart_tooltip_linux" if is_linux() else "settings_autostart_tooltip"
            self.autostart_cb = QCheckBox(tr(label_key, self.lang))
            self.autostart_cb.setToolTip(tr(tooltip_key, self.lang))
            self.autostart_cb.setChecked(self.autostart_manager and self.autostart_manager.is_enabled())
            self.autostart_cb.setCursor(Qt.CursorShape.PointingHandCursor)
            card.add_widget(self.autostart_cb)

            self.auto_start_cb = QCheckBox(tr("settings_auto_start", self.lang))
            self.auto_start_cb.setChecked(self.settings.get("auto_start_last_strategy", False))
            self.auto_start_cb.setCursor(Qt.CursorShape.PointingHandCursor)
            card.add_widget(self.auto_start_cb)

            self.auto_restart_cb = QCheckBox(tr("settings_auto_restart_strategy", self.lang))
            self.auto_restart_cb.setChecked(self._setting_bool("auto_restart_strategy"))
            self.auto_restart_cb.setCursor(Qt.CursorShape.PointingHandCursor)
            card.add_widget(self.auto_restart_cb)
            layout.addWidget(card)

        self.content_stack.addWidget(self._make_scroll_page(build))

    def _page_filters(self):
        def build(layout):
            card = SettingsCard(tr("settings_category_filters", self.lang))
            self.game_filter_cb = QCheckBox(tr("settings_game_filter", self.lang))
            game_enabled = self.settings.get("game_filter_enabled", False)
            if self.winws_manager:
                game_enabled = self.winws_manager.is_game_filter_enabled()
            self.game_filter_cb.setChecked(game_enabled)
            self.game_filter_cb.setCursor(Qt.CursorShape.PointingHandCursor)
            card.add_widget(self.game_filter_cb)

            if is_linux():
                card.add_widget(self._hint_label(tr("linux_ipset_not_available", self.lang)))
            else:
                card.add_widget(QLabel(tr("settings_ipset_filter", self.lang) + ":"))
                self.ipset_combo = CustomComboBox()
                self.ipset_combo.addItems([
                    tr("settings_ipset_loaded", self.lang),
                    tr("settings_ipset_none", self.lang),
                    tr("settings_ipset_any", self.lang),
                ])
                ipset_mode = self.settings.get("ipset_filter_mode", "loaded")
                if self.winws_manager:
                    ipset_mode = self.winws_manager.get_ipset_mode()
                mode_idx = {"loaded": 0, "none": 1, "any": 2}.get(ipset_mode, 0)
                self.ipset_combo.setCurrentIndex(mode_idx)
                card.add_widget(self.ipset_combo)
            layout.addWidget(card)

        self.content_stack.addWidget(self._make_scroll_page(build))

    def _page_apps(self):
        def build(layout):
            card = SettingsCard(tr("settings_category_app_restart", self.lang))
            self.auto_restart_apps_cb = QCheckBox(tr("settings_auto_restart_apps_enabled", self.lang))
            self.auto_restart_apps_cb.setChecked(self.settings.get("auto_restart_apps_enabled", False))
            self.auto_restart_apps_cb.setCursor(Qt.CursorShape.PointingHandCursor)
            card.add_widget(self.auto_restart_apps_cb)
            card.add_widget(self._hint_label(tr("settings_app_restart_description", self.lang)))
            self.apps_table = self._styled_table([tr("settings_app_restart_column_app", self.lang)])
            for name in self.settings.get("auto_restart_apps", []):
                row = self.apps_table.rowCount()
                self.apps_table.insertRow(row)
                self.apps_table.setItem(row, 0, QTableWidgetItem(str(name)))
            card.add_widget(self.apps_table)

            btn_row = QHBoxLayout()
            add_btn = QPushButton(tr("settings_app_restart_add", self.lang))
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn = QPushButton(tr("settings_app_restart_remove", self.lang))
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.clicked.connect(self._on_add_app_clicked)
            remove_btn.clicked.connect(self._on_remove_app_clicked)
            btn_row.addWidget(add_btn)
            btn_row.addWidget(remove_btn)
            btn_row.addStretch(1)
            card.add_layout(btn_row)
            layout.addWidget(card)

        self.content_stack.addWidget(self._make_scroll_page(build))

    def _page_bflag(self):
        def build(layout):
            card_title = (
                tr("settings_category_linux_conf", self.lang)
                if is_linux()
                else tr("settings_category_b_flag", self.lang)
            )
            card = SettingsCard(card_title)
            if is_linux():
                cb_label = tr("settings_linux_conf_sync_on_update", self.lang)
            else:
                cb_label = tr("settings_b_flag_on_update", self.lang)
            self.add_b_on_update_cb = QCheckBox(cb_label)
            self.add_b_on_update_cb.setChecked(self.settings.get("add_b_flag_on_update", False))
            self.add_b_on_update_cb.setCursor(Qt.CursorShape.PointingHandCursor)
            card.add_widget(self.add_b_on_update_cb)

            btn_row = QHBoxLayout()
            if is_linux():
                sync_btn = QPushButton(tr("settings_linux_conf_sync_now", self.lang))
                sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                sync_btn.clicked.connect(self._on_sync_linux_conf_clicked)
                btn_row.addWidget(sync_btn)
            else:
                add_b_btn = QPushButton(tr("settings_b_flag_add", self.lang))
                add_b_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                add_b_btn.clicked.connect(self._on_add_b_clicked)
                remove_b_btn = QPushButton(tr("settings_b_flag_remove", self.lang))
                remove_b_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                remove_b_btn.clicked.connect(self._on_remove_b_clicked)
                btn_row.addWidget(add_b_btn)
                btn_row.addWidget(remove_b_btn)
            btn_row.addStretch(1)
            card.add_layout(btn_row)
            layout.addWidget(card)

        self.content_stack.addWidget(self._make_scroll_page(build))

    def _page_auto_update(self):
        def build(layout):
            card = SettingsCard(tr("settings_update_tab_auto", self.lang))
            card.add_widget(QLabel(tr("settings_auto_update_label", self.lang)))
            self.auto_update_combo = CustomComboBox()
            self.auto_update_combo.addItems([
                tr("settings_auto_update_none", self.lang),
                tr("settings_auto_update_app", self.lang),
                tr("settings_auto_update_strategies", self.lang),
                tr("settings_auto_update_all", self.lang),
            ])
            mode = self.settings.get("auto_update_mode", "none")
            mode_idx = {"none": 0, "app": 1, "strategies": 2, "all": 3}.get(mode, 0)
            self.auto_update_combo.setCurrentIndex(mode_idx)
            self.auto_update_combo.setToolTip(tr("settings_auto_update_tooltip", self.lang))
            card.add_widget(self.auto_update_combo)
            card.add_widget(self._hint_label(tr("settings_auto_update_tooltip", self.lang)))
            layout.addWidget(card)

        self.content_stack.addWidget(self._make_scroll_page(build))

    def _page_app_repo(self):
        def build(layout):
            card = SettingsCard(tr("settings_app_repo_label", self.lang))
            card.add_widget(self._hint_label(tr("settings_app_repo_hint", self.lang)))
            self.app_repo_edit = ContextLineEdit()
            self.app_repo_edit.setPlaceholderText(tr("settings_app_repo_placeholder", self.lang))
            self.app_repo_edit.setText(self.settings.get("app_repo", ""))
            self.app_repo_edit.textChanged.connect(self._update_app_repo_preview)
            card.add_widget(self.app_repo_edit)
            self.app_repo_current_label = QLabel()
            self.app_repo_current_label.setObjectName("SettingsHint")
            self.app_repo_current_label.setWordWrap(True)
            card.add_widget(self.app_repo_current_label)
            layout.addWidget(card)

        self.content_stack.addWidget(self._make_scroll_page(build))
        self._update_app_repo_preview()

    def _page_zapret_repo(self):
        def build(layout):
            card = SettingsCard(tr("settings_zapret_repo_label", self.lang))
            card.add_widget(self._hint_label(tr("settings_zapret_repo_hint", self.lang)))
            self.zapret_repo_edit = ContextLineEdit()
            self.zapret_repo_edit.setPlaceholderText(tr("settings_zapret_repo_placeholder", self.lang))
            self.zapret_repo_edit.setText(self.settings.get("zapret_repo", ""))
            self.zapret_repo_edit.textChanged.connect(self._update_zapret_repo_preview)
            card.add_widget(self.zapret_repo_edit)
            self.zapret_repo_current_label = QLabel()
            self.zapret_repo_current_label.setObjectName("SettingsHint")
            self.zapret_repo_current_label.setWordWrap(True)
            card.add_widget(self.zapret_repo_current_label)
            layout.addWidget(card)

        self.content_stack.addWidget(self._make_scroll_page(build))
        self._update_zapret_repo_preview()

    def _page_strategy_update(self):
        def build(layout):
            check_card = SettingsCard(tr("settings_update_tab_strategies", self.lang))
            self.remove_check_cb = QCheckBox(tr("settings_remove_check_zapret", self.lang))
            self.remove_check_cb.setChecked(self.settings.get("remove_check_updates", False))
            self.remove_check_cb.setCursor(Qt.CursorShape.PointingHandCursor)
            check_card.add_widget(self.remove_check_cb)
            layout.addWidget(check_card)

            ignore_card = SettingsCard(tr("settings_update_ignore_folders", self.lang))
            self.ignore_folders_table = self._styled_table(
                [tr("settings_update_ignore_folder_column", self.lang)]
            )
            ignore_list = self.settings.get("update_ignore_folders", ["lists"])
            if isinstance(ignore_list, list):
                for folder in ignore_list:
                    row = self.ignore_folders_table.rowCount()
                    self.ignore_folders_table.insertRow(row)
                    self.ignore_folders_table.setItem(row, 0, QTableWidgetItem(str(folder)))
            ignore_card.add_widget(self.ignore_folders_table)

            btn_row = QHBoxLayout()
            self.btn_add_ignore_folder = QPushButton(tr("settings_update_ignore_add", self.lang))
            self.btn_remove_ignore_folder = QPushButton(tr("settings_update_ignore_remove", self.lang))
            self.btn_add_ignore_folder.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_remove_ignore_folder.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_add_ignore_folder.clicked.connect(self._on_add_ignore_folder)
            self.btn_remove_ignore_folder.clicked.connect(self._on_remove_ignore_folder)
            btn_row.addWidget(self.btn_add_ignore_folder)
            btn_row.addWidget(self.btn_remove_ignore_folder)
            btn_row.addStretch(1)
            ignore_card.add_layout(btn_row)
            layout.addWidget(ignore_card)

        self.content_stack.addWidget(self._make_scroll_page(build))

    def _update_app_repo_preview(self):
        if not hasattr(self, "app_repo_current_label"):
            return
        slug = resolve_github_repo(
            self.app_repo_edit.text().strip(),
            AppUpdater.GITHUB_REPO,
        )
        self.app_repo_current_label.setText(
            tr("settings_app_repo_current", self.lang).format(slug)
        )

    def _update_zapret_repo_preview(self):
        if not hasattr(self, "zapret_repo_current_label"):
            return
        slug = resolve_github_repo(
            self.zapret_repo_edit.text().strip(),
            ZapretUpdater.GITHUB_REPO,
        )
        self.zapret_repo_current_label.setText(
            tr("settings_zapret_repo_current", self.lang).format(slug)
        )

    def refresh_theme(self):
        super().refresh_theme()
        p = theme.palette()

        self.content_frame.setStyleSheet(theme.dialog_form_stylesheet())
        self.nav_list.setStyleSheet(theme.editor_file_list_style())
        if hasattr(self, "launch_args_ref"):
            self.launch_args_ref.refresh_theme()

        card_style = f"""
            QFrame#SettingsCard {{
                background: transparent;
                border: none;
            }}
            QLabel#SettingsCardTitle {{
                font-size: 13px;
                font-weight: 600;
                color: {p.fg_text};
            }}
            QLabel#SettingsHint {{
                color: {p.fg_muted};
                font-size: 12px;
            }}
            QScrollArea#SettingsScroll {{
                background: transparent;
                border: none;
            }}
            QScrollArea#SettingsScroll > QWidget > QWidget#SettingsPage {{
                background: transparent;
            }}
            QTableWidget#SettingsTable {{
                background-color: {p.bg_item};
                color: {p.fg_text};
                border: none;
                gridline-color: {p.border};
                outline: none;
            }}
            QTableWidget#SettingsTable::item:selected {{
                background-color: {p.accent};
                color: #ffffff;
            }}
            QHeaderView::section {{
                background-color: {p.bg_panel};
                color: {p.fg_muted};
                border: none;
                border-bottom: 1px solid {p.border};
                padding: 6px 8px;
                font-weight: 600;
            }}
        """
        self.setStyleSheet(
            f"QDialog {{ background-color: {p.bg_window}; color: {p.fg_text}; }}"
            + card_style
        )
        theme.refresh_editor_blocks(self)

        for combo in (
            getattr(self, "lang_combo", None),
            getattr(self, "ipset_combo", None),
            getattr(self, "auto_update_combo", None),
        ):
            if combo is not None and hasattr(combo, "apply_theme"):
                combo.apply_theme()

        if hasattr(self, "_nothing_label"):
            self._nothing_label.setStyleSheet(theme.nothing_found_style())
        if hasattr(self, "app_repo_current_label"):
            self.app_repo_current_label.setStyleSheet(theme.muted_label_style())
        if hasattr(self, "zapret_repo_current_label"):
            self.zapret_repo_current_label.setStyleSheet(theme.muted_label_style())

    def _on_add_b_clicked(self):
        if self.parent() and hasattr(self.parent(), "add_b_flag_to_all_strategies"):
            self.parent().add_b_flag_to_all_strategies(silent=False)

    def _on_remove_b_clicked(self):
        if self.parent() and hasattr(self.parent(), "remove_b_flag_from_all_strategies"):
            self.parent().remove_b_flag_from_all_strategies(silent=False)

    def _on_sync_linux_conf_clicked(self):
        if self.parent() and hasattr(self.parent(), "sync_linux_conf_env_from_settings"):
            self.parent().sync_linux_conf_env_from_settings(silent=False)

    def _on_browse_winws_path(self):
        start = self.winws_path_edit.text().strip() or get_base_path()
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("settings_winws_path_label", self.lang),
            start,
        )
        if folder:
            self.winws_path_edit.setText(folder)

    def _on_add_app_clicked(self):
        app_name, ok = QInputDialog.getText(
            self,
            tr("settings_app_restart_add", self.lang),
            tr("settings_app_restart_column_app", self.lang) + ":",
        )
        if not ok:
            return
        app_name = app_name.strip()
        if not app_name:
            return
        if not app_name.lower().endswith(".exe"):
            app_name = f"{app_name}.exe"
        row = self.apps_table.rowCount()
        self.apps_table.insertRow(row)
        self.apps_table.setItem(row, 0, QTableWidgetItem(app_name))

    def _on_remove_app_clicked(self):
        row = self.apps_table.currentRow()
        if row < 0:
            return
        self.apps_table.removeRow(row)

    def _on_add_ignore_folder(self):
        folder, ok = QInputDialog.getText(
            self,
            tr("settings_update_ignore_add", self.lang),
            tr("settings_update_ignore_folder_column", self.lang) + ":",
        )
        if not ok:
            return
        folder = folder.strip()
        if not folder:
            return
        row = self.ignore_folders_table.rowCount()
        self.ignore_folders_table.insertRow(row)
        self.ignore_folders_table.setItem(row, 0, QTableWidgetItem(folder))

    def _on_remove_ignore_folder(self):
        row = self.ignore_folders_table.currentRow()
        if row < 0:
            return
        self.ignore_folders_table.removeRow(row)

    def get_settings_changes(self):
        """Возвращает словарь с изменениями настроек."""
        changes = {}

        lang = "ru" if self.lang_combo.currentIndex() == 0 else "en"
        if lang != self.settings.get("language", "ru"):
            changes["language"] = lang

        if self.show_tray_cb.isChecked() != self.settings.get("show_in_tray", True):
            changes["show_in_tray"] = self.show_tray_cb.isChecked()
        if self.show_tray_cb.isChecked():
            if self.start_minimized_cb.isChecked() != self.settings.get("start_minimized", False):
                changes["start_minimized"] = self.start_minimized_cb.isChecked()
        else:
            if self.settings.get("start_minimized", False):
                changes["start_minimized"] = False

        if self.close_winws_cb.isChecked() != self.settings.get("close_winws_on_exit", True):
            changes["close_winws_on_exit"] = self.close_winws_cb.isChecked()

        changes["autostart_enabled"] = self.autostart_cb.isChecked()

        if self.auto_start_cb.isChecked() != self.settings.get("auto_start_last_strategy", False):
            changes["auto_start_last_strategy"] = self.auto_start_cb.isChecked()
        if self.auto_restart_cb.isChecked() != self._setting_bool("auto_restart_strategy"):
            changes["auto_restart_strategy"] = self.auto_restart_cb.isChecked()

        if self.auto_restart_apps_cb.isChecked() != self.settings.get("auto_restart_apps_enabled", False):
            changes["auto_restart_apps_enabled"] = self.auto_restart_apps_cb.isChecked()

        if self.add_b_on_update_cb.isChecked() != self.settings.get("add_b_flag_on_update", False):
            changes["add_b_flag_on_update"] = self.add_b_on_update_cb.isChecked()

        auto_modes = ["none", "app", "strategies", "all"]
        auto_mode = auto_modes[self.auto_update_combo.currentIndex()]
        if auto_mode != self.settings.get("auto_update_mode", "none"):
            changes["auto_update_mode"] = auto_mode

        app_repo = self.app_repo_edit.text().strip()
        if app_repo != self.settings.get("app_repo", "").strip():
            changes["app_repo"] = app_repo

        if self.remove_check_cb.isChecked() != self.settings.get("remove_check_updates", False):
            changes["remove_check_updates"] = self.remove_check_cb.isChecked()

        game_enabled = self.game_filter_cb.isChecked()
        if game_enabled != self.settings.get("game_filter_enabled", False):
            changes["game_filter_enabled"] = game_enabled

        if hasattr(self, "ipset_combo"):
            ipset_mode = ["loaded", "none", "any"][self.ipset_combo.currentIndex()]
            if ipset_mode != self.settings.get("ipset_filter_mode", "loaded"):
                changes["ipset_filter_mode"] = ipset_mode

        winws_path = self.winws_path_edit.text().strip()
        if is_linux():
            if winws_path != self.settings.get("runtime_path", "").strip():
                changes["runtime_path"] = winws_path
            if hasattr(self, "linux_interface_combo"):
                iface = self.linux_interface_combo.currentText().strip() or "any"
                if iface != (self.settings.get("linux_interface") or "any"):
                    changes["linux_interface"] = iface
            if hasattr(self, "linux_init_combo"):
                init_mode = self.linux_init_combo.currentData() or "auto"
                if init_mode != (self.settings.get("linux_init_mode") or "auto"):
                    changes["linux_init_mode"] = init_mode
            if hasattr(self, "linux_firewall_combo"):
                fw = self.linux_firewall_combo.currentData() or "auto"
                if fw != (self.settings.get("linux_firewall_backend") or "auto"):
                    changes["linux_firewall_backend"] = fw
        elif winws_path != self.settings.get("winws_path", "").strip():
            changes["winws_path"] = winws_path

        zapret_repo = self.zapret_repo_edit.text().strip()
        if zapret_repo != self.settings.get("zapret_repo", "").strip():
            changes["zapret_repo"] = zapret_repo

        apps = []
        if hasattr(self, "apps_table"):
            for row in range(self.apps_table.rowCount()):
                item = self.apps_table.item(row, 0)
                if item:
                    name = item.text().strip()
                    if name:
                        if not is_linux() and not name.lower().endswith(".exe"):
                            name = f"{name}.exe"
                        apps.append(name)
        if apps != self.settings.get("auto_restart_apps", []):
            changes["auto_restart_apps"] = apps

        ignore_list = []
        for row in range(self.ignore_folders_table.rowCount()):
            item = self.ignore_folders_table.item(row, 0)
            if isinstance(item, QTableWidgetItem):
                text = item.text().strip()
                if text:
                    ignore_list.append(text)
        if ignore_list != self.settings.get("update_ignore_folders", []):
            changes["update_ignore_folders"] = ignore_list

        return changes
