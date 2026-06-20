"""
Standard (native) main window implementation for PyQt6.
Uses system window frame instead of frameless custom title bar.
"""

import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QApplication
from PyQt6.QtGui import QIcon
from src.shared.ui.window_styles import main_window_flags, apply_native_window
from src.shared.ui import theme as ui_theme


class StandardMainWindow(QMainWindow):
    """Standard QMainWindow with system title bar."""

    def __init__(self, title="Window", width=800, height=600, icon_path=None, icon=None, theme="dark"):
        super().__init__()
        self.default_width = width
        self.default_height = height
        self.setWindowTitle(title)
        self.setFixedSize(width, height)
        self.setWindowFlags(main_window_flags())
        if icon is not None and not icon.isNull():
            self.setWindowIcon(icon)
        elif icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.content_layout = QVBoxLayout(self.central_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        self._native_style_done = False
        self._center_window()
        ui_theme.apply_widget_theme(self.central_widget)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._native_style_done:
            apply_native_window(self, maximize=False)
            self._native_style_done = True

    def setIconPath(self, icon_path):
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def setContentWidget(self, widget):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self.content_layout.addWidget(widget)

    def getContentLayout(self):
        return self.content_layout

    def _center_window(self):
        try:
            screen = QApplication.primaryScreen().geometry()
            x = (screen.width() - self.default_width) // 2
            y = (screen.height() - self.default_height) // 2
            self.setGeometry(x, y, self.default_width, self.default_height)
        except Exception as e:
            print(f"Error centering window: {e}")
