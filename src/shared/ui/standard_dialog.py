"""
Standard (native) dialog implementation for PyQt6.
Uses system window frame instead of frameless custom title bar.
"""

import os
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QWidget
from PyQt6.QtGui import QIcon, QGuiApplication, QKeySequence, QAction
from src.shared.ui.window_styles import dialog_window_flags, apply_native_window
from src.shared.ui import theme as ui_theme


class _TitleBarCompat:
    """Compatibility object: addLeftWidget/addCenterWidget add to a top bar."""

    def __init__(self, layout, top_bar):
        self._layout = layout
        self._top_bar = top_bar

    def addLeftWidget(self, widget):
        self._layout.insertWidget(0, widget)
        self._top_bar.show()

    def addCenterWidget(self, widget):
        self._layout.insertWidget(
            self._layout.count() - 1,
            widget,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )
        self._top_bar.show()


class StandardDialog(QDialog):
    """Standard QDialog with system title bar. Provides getContentLayout() and title_bar compat."""

    def __init__(
        self,
        parent=None,
        title="Dialog",
        width=500,
        height=400,
        icon_path=None,
        icon=None,
        theme=None,
        resizable=True,
        **_kwargs,
    ):
        super().__init__(parent)
        self._resizable = resizable
        self._target_width = width
        self._target_height = height
        self._native_style_done = False
        self._geometry_prepared = False

        self.setWindowFlags(dialog_window_flags(resizable=resizable))
        self.setWindowTitle(title)
        self.setMinimumSize(min(width, 300), min(height, 200))
        self.resize(width, height)
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)

        if icon is not None and not icon.isNull():
            self.setWindowIcon(icon)
        elif icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.top_bar = QWidget()
        self.top_bar_layout = QHBoxLayout(self.top_bar)
        self.top_bar_layout.setContentsMargins(4, 2, 4, 2)
        self.top_bar_layout.setSpacing(4)
        self.top_bar_layout.addStretch(1)
        self.title_bar = _TitleBarCompat(self.top_bar_layout, self.top_bar)
        self.top_bar.hide()
        self.main_layout.addWidget(self.top_bar)

        self.content_frame = QWidget()
        self.content_frame.setObjectName("contentFrame")
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(10)
        self.main_layout.addWidget(self.content_frame, 1)

        self.status_bar = None
        self.frame_layout = self.main_layout
        self._apply_theme()

    def addStatusBar(self):
        from PyQt6.QtWidgets import QStatusBar

        if self.status_bar is None:
            self.status_bar = QStatusBar()
            self.main_layout.addWidget(self.status_bar)
        return self.status_bar

    def getContentLayout(self):
        return self.content_layout

    def _apply_theme(self):
        p = ui_theme.palette()
        ui_theme.apply_widget_theme(self)
        ui_theme.apply_widget_theme(self.content_frame, bg=p.bg_window)
        self.setStyleSheet(
            f"QDialog {{ background-color: {p.bg_window}; color: {p.fg_text}; }}"
        )

    def refresh_theme(self):
        self._apply_theme()
        self._native_style_done = False

    def enable_maximize_button(self) -> None:
        """Совместимость: используйте resizable=True в __init__."""

    def add_fullscreen_view_action(self, menu, lang: str):
        from src.shared.i18n.translator import tr

        self._fullscreen_action = QAction(tr("editor_fullscreen", lang), self)
        self._fullscreen_action.setShortcut(QKeySequence("F11"))
        self._fullscreen_action.setCheckable(True)
        self._fullscreen_action.triggered.connect(self.toggle_fullscreen)
        menu.addAction(self._fullscreen_action)
        return self._fullscreen_action

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            if hasattr(self, "_fullscreen_action"):
                self._fullscreen_action.setChecked(False)
        else:
            self.showFullScreen()
            if hasattr(self, "_fullscreen_action"):
                self._fullscreen_action.setChecked(True)

    def _prepare_geometry(self) -> None:
        """Размер и позиция до первого кадра — без «маленького окна»."""
        if self._geometry_prepared:
            return
        self.resize(self._target_width, self._target_height)
        if self.layout() is not None:
            self.layout().activate()
        self._center_on_parent_or_screen()
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
        self._geometry_prepared = True

    def _schedule_native_style(self) -> None:
        if self._native_style_done:
            return

        def _apply() -> None:
            if self._native_style_done or not self.isVisible():
                return
            apply_native_window(self)
            self._native_style_done = True

        QTimer.singleShot(0, _apply)

    def show(self):
        self._prepare_geometry()
        super().show()

    def exec(self):
        self._prepare_geometry()
        return super().exec()

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_native_style()

    def _center_on_parent_or_screen(self):
        try:
            parent = self.parent()
            screen = None
            if parent and hasattr(parent, "geometry") and parent.isVisible():
                screen = QGuiApplication.screenAt(parent.geometry().center())
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            available = screen.availableGeometry() if screen else QGuiApplication.primaryScreen().availableGeometry()

            if parent and hasattr(parent, "geometry") and parent.isVisible():
                pr = parent.geometry()
                x = pr.x() + (pr.width() - self.width()) // 2
                y = pr.y() + (pr.height() - self.height()) // 2
            else:
                x = available.x() + (available.width() - self.width()) // 2
                y = available.y() + (available.height() - self.height()) // 2

            x = max(available.x(), min(x, available.x() + available.width() - self.width()))
            y = max(available.y(), min(y, available.y() + available.height() - self.height()))
            self.move(x, y)
        except Exception:
            pass
