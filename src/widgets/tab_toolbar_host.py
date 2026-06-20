"""Вкладки + панель инструментов в одной строке (без QTabWidget::cornerWidget)."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from src.shared.ui import theme
from src.widgets.unified_toolbar import UnifiedToolbar


class TabToolbarHost(QWidget):
    """Искусственный контейнер: QTabBar слева, toolbar справа, контент снизу."""

    currentChanged = pyqtSignal(int)

    def __init__(self, parent=None, *, widget_id: str = ""):
        super().__init__(parent)
        self._widget_id = widget_id
        if widget_id:
            self.setObjectName(widget_id)
        self._icon_size = QSize(14, 16)
        self._toolbar: QWidget | None = None
        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.timeout.connect(self._sync_toolbar_height)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = QWidget()
        self._header.setObjectName("TabToolbarHeader")
        self._header_layout = QHBoxLayout(self._header)
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(8)

        self._tab_bar = QTabBar(self._header)
        self._tab_bar.setDrawBase(False)
        self._header_layout.addWidget(self._tab_bar, 1, Qt.AlignmentFlag.AlignBottom)

        self._toolbar_slot = QWidget(self._header)
        self._toolbar_slot.setObjectName("TabToolbarSlot")
        self._toolbar_slot_layout = QHBoxLayout(self._toolbar_slot)
        self._toolbar_slot_layout.setContentsMargins(0, 0, 0, 0)
        self._toolbar_slot_layout.setSpacing(0)
        self._header_layout.addWidget(
            self._toolbar_slot,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
        )

        root.addWidget(self._header)

        self._pane = QFrame()
        self._pane.setObjectName("TabToolbarPane")
        pane_layout = QVBoxLayout(self._pane)
        pane_layout.setContentsMargins(4, 4, 4, 4)
        pane_layout.setSpacing(0)

        self._stack = QStackedWidget()
        pane_layout.addWidget(self._stack, 1)
        root.addWidget(self._pane, 1)

        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._tab_bar and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.LayoutRequest,
        ):
            self._schedule_toolbar_sync()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._schedule_toolbar_sync()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._schedule_toolbar_sync()

    def _schedule_toolbar_sync(self) -> None:
        self._sync_timer.start(0)

    def _on_tab_changed(self, index: int) -> None:
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)
        self.currentChanged.emit(index)

    def _sync_toolbar_height(self) -> None:
        if self._tab_bar.count() == 0:
            return
        tab_height = self._tab_bar.tabRect(0).height()
        if tab_height <= 0:
            tab_height = 32
        header_h = max(tab_height, UnifiedToolbar.ROW_HEIGHT + 2)
        self._header.setFixedHeight(header_h)
        if isinstance(self._toolbar, UnifiedToolbar):
            self._toolbar.match_tab_height(tab_height)

    def set_tab_bar(self, tab_bar: QTabBar) -> None:
        if tab_bar is self._tab_bar:
            return
        self._tab_bar.currentChanged.disconnect(self._on_tab_changed)
        self._tab_bar.removeEventFilter(self)
        self._header_layout.removeWidget(self._tab_bar)
        self._tab_bar.setParent(None)
        self._tab_bar.deleteLater()

        self._tab_bar = tab_bar
        tab_bar.setParent(self._header)
        tab_bar.setDrawBase(False)
        tab_bar.currentChanged.connect(self._on_tab_changed)
        tab_bar.installEventFilter(self)
        self._header_layout.insertWidget(0, tab_bar, 1, Qt.AlignmentFlag.AlignBottom)
        self._schedule_toolbar_sync()

    def setTabBar(self, tab_bar: QTabBar) -> None:
        self.set_tab_bar(tab_bar)

    def set_toolbar(self, toolbar: QWidget | None) -> None:
        while self._toolbar_slot_layout.count():
            item = self._toolbar_slot_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self._toolbar = toolbar
        if toolbar is not None:
            self._toolbar_slot_layout.addWidget(toolbar)
        self._schedule_toolbar_sync()

    def toolbar(self) -> QWidget | None:
        return self._toolbar

    def apply_theme(self, *, widget_id: str | None = None, selected_bg: str | None = None) -> None:
        if widget_id is not None:
            self._widget_id = widget_id
            self.setObjectName(widget_id)
        self.setStyleSheet(
            theme.tab_toolbar_host_stylesheet(
                widget_id=self._widget_id,
                selected_bg=selected_bg,
            )
        )
        if isinstance(self._toolbar, UnifiedToolbar):
            self._toolbar.apply_theme()

    def setDocumentMode(self, _enabled: bool) -> None:
        pass

    def setIconSize(self, size: QSize) -> None:
        self._icon_size = size

    def tabBar(self) -> QTabBar:
        return self._tab_bar

    def count(self) -> int:
        return self._tab_bar.count()

    def addTab(self, widget: QWidget, label: str) -> int:
        self._stack.addWidget(widget)
        idx = self._tab_bar.addTab(label)
        self._schedule_toolbar_sync()
        return idx

    def setTabText(self, index: int, text: str) -> None:
        self._tab_bar.setTabText(index, text)

    def setTabIcon(self, index: int, icon) -> None:
        self._tab_bar.setTabIcon(index, icon)

    def setTabToolTip(self, index: int, tip: str) -> None:
        self._tab_bar.setTabToolTip(index, tip)

    def currentIndex(self) -> int:
        return self._tab_bar.currentIndex()

    def setCurrentIndex(self, index: int) -> None:
        self._tab_bar.setCurrentIndex(index)

    def widget(self, index: int) -> QWidget | None:
        if 0 <= index < self._stack.count():
            return self._stack.widget(index)
        return None

    def indexOf(self, widget: QWidget) -> int:
        return self._stack.indexOf(widget)
