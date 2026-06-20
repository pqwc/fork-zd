"""
Окно «Дополнения»: список слева и форма справа в стиле редактора.
"""
from __future__ import annotations

import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.entities.config.config_manager import ConfigManager
from src.shared.ui.assets.embedded_assets import get_app_icon
from src.shared.i18n.translator import tr
from src.shared.ui import theme
from src.shared.ui.standard_dialog import StandardDialog
from src.widgets.codicon_button import CodiconButton
from src.widgets.custom_combobox import CustomComboBox
from src.widgets.custom_context_widgets import ContextLineEdit
from src.widgets.style_menu import StyleMenu

_ROLE_INDEX = Qt.ItemDataRole.UserRole

DEFAULT_ADDONS = [
    {"name": "Flowseal (zapret-discord-youtube)", "url": "https://github.com/Flowseal/zapret-discord-youtube"},
]


def _get_addons_from_config() -> list[dict]:
    try:
        addons = ConfigManager().get_setting("addons")
        if addons and isinstance(addons, list):
            return [{"name": str(a.get("name", "")), "url": str(a.get("url", ""))} for a in addons]
    except Exception:
        pass
    return list(DEFAULT_ADDONS)


def _save_addons_to_config(addons: list[dict]) -> None:
    try:
        ConfigManager().set_setting("addons", addons)
    except Exception:
        pass


class AddonsDialog(StandardDialog):
    """Дополнения: search + list | detail (как панели редактора)."""

    def __init__(self, parent=None, settings=None):
        self.settings = settings or {}
        self.lang = self.settings.get("language", "ru")
        self._addons = _get_addons_from_config()
        self._selected_index = -1
        self._syncing_fields = False

        super().__init__(
            parent=parent,
            title=tr("addons_title", self.lang),
            width=900,
            height=560,
            icon=get_app_icon(),
            resizable=True,
        )
        self._build_ui()
        self.refresh_theme()
        self._reload_list()
        self.setMinimumSize(900, 560)
        self.resize(900, 560)

    def _build_ui(self):
        layout = self.getContentLayout()
        theme.apply_editor_tab_content_layout(layout)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("AddonsSplitter")
        self._splitter.addWidget(self._build_list_panel())
        self._splitter.addWidget(self._build_detail_panel())
        theme.configure_editor_horizontal_splitter(
            self._splitter,
            left_min=220,
            right_min=360,
        )
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([260, 580])
        layout.addWidget(self._splitter, 1)

    def _build_list_panel(self) -> QWidget:
        container = QWidget()
        container.setMinimumWidth(200)
        container.setMaximumWidth(360)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(4)

        self.search_edit = ContextLineEdit()
        self.search_edit.setPlaceholderText(tr("addons_search_placeholder", self.lang))
        self.search_edit.setFixedHeight(theme.EDITOR_FIELD_HEIGHT)
        self.search_edit.textChanged.connect(self._apply_filter)
        search_row.addWidget(self.search_edit, 1)

        self.add_btn = CodiconButton("add", tr("addons_add", self.lang), size=16, button_size=26)
        self.add_btn.clicked.connect(self._on_add)
        self.remove_btn = CodiconButton("trash", tr("addons_remove", self.lang), size=16, button_size=26)
        self.remove_btn.clicked.connect(self._on_remove)
        search_row.addWidget(self.add_btn)
        search_row.addWidget(self.remove_btn)
        layout.addLayout(search_row)

        list_block = theme.create_editor_block("AddonsListBlock")
        list_layout = QVBoxLayout(list_block)
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(0)

        self.addons_list = QListWidget()
        self.addons_list.setStyleSheet(theme.editor_file_list_style())
        self.addons_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.addons_list.setSpacing(0)
        self.addons_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.addons_list.currentRowChanged.connect(self._on_list_selection_changed)
        self.addons_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.addons_list.customContextMenuRequested.connect(self._on_list_context_menu)

        self._list_stack = QStackedWidget()
        self._list_stack.addWidget(self.addons_list)

        nothing_widget = QWidget()
        nothing_layout = QVBoxLayout(nothing_widget)
        nothing_layout.setContentsMargins(0, 0, 0, 0)
        self._nothing_label = QLabel(tr("addons_nothing_found", self.lang))
        self._nothing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._nothing_label.setStyleSheet(theme.nothing_found_style())
        nothing_layout.addWidget(self._nothing_label)
        self._list_stack.addWidget(nothing_widget)
        self._list_stack.setCurrentIndex(0)

        list_layout.addWidget(self._list_stack, 1)
        layout.addWidget(list_block, 1)
        return container

    def _build_detail_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        detail_block = theme.create_editor_block("AddonsDetailBlock")
        detail_layout = QVBoxLayout(detail_block)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(10)

        self.detail_title = QLabel(tr("addons_details_title", self.lang))
        self.detail_title.setObjectName("AddonsDetailTitle")
        detail_layout.addWidget(self.detail_title)

        self.empty_label = QLabel(tr("addons_select_hint", self.lang))
        self.empty_label.setWordWrap(True)
        self.empty_label.setObjectName("AddonsEmptyHint")
        detail_layout.addWidget(self.empty_label)

        self.form_widget = QWidget()
        form = QVBoxLayout(self.form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        name_label = QLabel(tr("addons_col_name", self.lang))
        name_label.setObjectName("AddonsFieldLabel")
        form.addWidget(name_label)
        self.name_edit = ContextLineEdit()
        self.name_edit.setFixedHeight(theme.EDITOR_FIELD_HEIGHT)
        self.name_edit.textChanged.connect(self._on_field_changed)
        form.addWidget(self.name_edit)

        url_label = QLabel(tr("addons_col_url", self.lang))
        url_label.setObjectName("AddonsFieldLabel")
        form.addWidget(url_label)
        self.url_edit = ContextLineEdit()
        self.url_edit.setPlaceholderText("https://github.com/owner/repo")
        self.url_edit.setFixedHeight(theme.EDITOR_FIELD_HEIGHT)
        self.url_edit.textChanged.connect(self._on_field_changed)
        form.addWidget(self.url_edit)

        mode_label = QLabel(tr("addons_mode_label", self.lang))
        mode_label.setObjectName("AddonsFieldLabel")
        form.addWidget(mode_label)
        self.mode_combo = CustomComboBox()
        self.mode_combo.addItems([
            tr("addons_mode_full", self.lang),
            tr("addons_mode_lists", self.lang),
            tr("addons_mode_strategies", self.lang),
            tr("addons_mode_bin", self.lang),
        ])
        form.addWidget(self.mode_combo)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.download_btn = QPushButton(tr("addons_download", self.lang))
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.clicked.connect(self._on_download_current)
        self.open_btn = QPushButton(tr("addons_open_link", self.lang))
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.clicked.connect(self._on_open_current)
        action_row.addWidget(self.download_btn)
        action_row.addWidget(self.open_btn)
        action_row.addStretch(1)
        form.addLayout(action_row)

        detail_layout.addWidget(self.form_widget)
        detail_layout.addStretch(1)
        layout.addWidget(detail_block, 1)
        self._set_detail_enabled(False)
        return container

    def _set_detail_enabled(self, enabled: bool):
        self.form_widget.setVisible(enabled)
        self.empty_label.setVisible(not enabled)
        self.detail_title.setVisible(enabled)

    def _display_name(self, item: dict) -> str:
        name = (item.get("name") or "").strip()
        if name:
            return name
        url = (item.get("url") or "").strip()
        if url:
            return url.replace("https://", "").replace("http://", "")[:48]
        return tr("addons_untitled", self.lang)

    def _reload_list(self, select_index: int | None = None):
        query = self.search_edit.text().strip().lower() if hasattr(self, "search_edit") else ""
        self.addons_list.blockSignals(True)
        self.addons_list.clear()

        visible = 0
        first_visible_row = -1
        for index, item in enumerate(self._addons):
            label = self._display_name(item)
            haystack = f"{label} {item.get('url', '')}".lower()
            if query and query not in haystack:
                continue
            row = self.addons_list.count()
            if first_visible_row < 0:
                first_visible_row = row
            list_item = QListWidgetItem(label)
            list_item.setData(_ROLE_INDEX, index)
            self.addons_list.addItem(list_item)
            visible += 1

        self.addons_list.blockSignals(False)

        if visible == 0:
            self._list_stack.setCurrentIndex(1)
            self._selected_index = -1
            self._set_detail_enabled(False)
            return

        self._list_stack.setCurrentIndex(0)
        target = select_index if select_index is not None else self._selected_index
        row_to_select = first_visible_row
        if target >= 0:
            for row in range(self.addons_list.count()):
                if self.addons_list.item(row).data(_ROLE_INDEX) == target:
                    row_to_select = row
                    break
        self.addons_list.setCurrentRow(row_to_select)

    def _apply_filter(self, _text: str):
        self._reload_list(self._selected_index)

    def _on_list_selection_changed(self, row: int):
        if row < 0:
            self._selected_index = -1
            self._set_detail_enabled(False)
            return
        item = self.addons_list.item(row)
        if item is None:
            return
        index = item.data(_ROLE_INDEX)
        if index is None or index < 0 or index >= len(self._addons):
            return
        self._selected_index = int(index)
        self._set_detail_enabled(True)
        self._syncing_fields = True
        addon = self._addons[self._selected_index]
        self.name_edit.setText(addon.get("name", ""))
        self.url_edit.setText(addon.get("url", ""))
        self._syncing_fields = False

    def _on_field_changed(self):
        if self._syncing_fields or self._selected_index < 0:
            return
        self._addons[self._selected_index] = {
            "name": self.name_edit.text().strip(),
            "url": self.url_edit.text().strip(),
        }
        row = self.addons_list.currentRow()
        if row >= 0:
            item = self.addons_list.item(row)
            if item is not None:
                self.addons_list.blockSignals(True)
                item.setText(self._display_name(self._addons[self._selected_index]))
                self.addons_list.blockSignals(False)

    def _current_mode(self) -> str:
        mode_map = {0: "full", 1: "lists", 2: "strategies", 3: "bin"}
        return mode_map.get(self.mode_combo.currentIndex(), "full")

    def _on_add(self):
        self._commit_fields()
        self._addons.append({"name": "", "url": ""})
        new_index = len(self._addons) - 1
        _save_addons_to_config(self._addons)
        self._reload_list(new_index)

    def _on_remove(self):
        if self._selected_index < 0 or self._selected_index >= len(self._addons):
            return
        self._addons.pop(self._selected_index)
        _save_addons_to_config(self._addons)
        next_index = min(self._selected_index, len(self._addons) - 1)
        self._reload_list(next_index if next_index >= 0 else None)

    def _commit_fields(self):
        if self._selected_index >= 0:
            self._on_field_changed()

    def _on_download_current(self):
        self._commit_fields()
        if self._selected_index < 0:
            return
        item = self._addons[self._selected_index]
        name, url = item.get("name", ""), (item.get("url") or "").strip()
        if not url:
            return
        _save_addons_to_config(self._addons)
        parent = self.parent()
        mode = self._current_mode()
        if parent and hasattr(parent, "on_addon_download"):
            try:
                parent.on_addon_download(name, url, mode)
            except TypeError:
                parent.on_addon_download(name, url)

    def _on_open_current(self):
        self._commit_fields()
        if self._selected_index < 0:
            return
        url = (self._addons[self._selected_index].get("url") or "").strip()
        if url:
            webbrowser.open(url)

    def _on_list_context_menu(self, pos):
        row = self.addons_list.indexAt(pos).row()
        menu = StyleMenu(self)
        add_action = menu.addAction(tr("addons_add", self.lang))
        remove_action = menu.addAction(tr("addons_remove", self.lang))
        download_action = None
        open_action = None
        if row >= 0:
            menu.addSeparator()
            download_action = menu.addAction(tr("addons_download", self.lang))
            open_action = menu.addAction(tr("addons_open_link", self.lang))
        action = menu.exec(self.addons_list.mapToGlobal(pos))
        if action == add_action:
            self._on_add()
        elif action == remove_action:
            self._on_remove()
        elif action == download_action and row >= 0:
            self.addons_list.setCurrentRow(row)
            self._on_download_current()
        elif action == open_action and row >= 0:
            self.addons_list.setCurrentRow(row)
            self._on_open_current()

    def refresh_theme(self):
        super().refresh_theme()
        p = theme.palette()
        self.content_frame.setStyleSheet(
            theme.dialog_form_stylesheet()
            + f"""
            QLabel#AddonsDetailTitle {{
                font-size: 13px;
                font-weight: 600;
                color: {p.fg_text};
            }}
            QLabel#AddonsFieldLabel {{
                color: {p.fg_muted};
                font-size: 11px;
                margin-top: 2px;
            }}
            QLabel#AddonsEmptyHint {{
                color: {p.fg_muted};
                font-size: 12px;
            }}
            """
        )
        self.addons_list.setStyleSheet(theme.editor_file_list_style())
        if hasattr(self, "_nothing_label"):
            self._nothing_label.setStyleSheet(theme.nothing_found_style())
        if hasattr(self, "mode_combo") and hasattr(self.mode_combo, "apply_theme"):
            self.mode_combo.apply_theme()
        theme.refresh_editor_blocks(self)

    def accept(self):
        self._commit_fields()
        _save_addons_to_config(self._addons)
        super().accept()

    def closeEvent(self, event):
        self._commit_fields()
        _save_addons_to_config(self._addons)
        super().closeEvent(event)
