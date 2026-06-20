"""
Animated Progress Bar in VS Code style
"""

from PyQt6.QtCore import QRect, QTimer, Qt
from PyQt6.QtWidgets import QProgressBar
from PyQt6.QtGui import QColor, QLinearGradient, QPainter


class AnimatedProgressBar(QProgressBar):
    """Progress bar with VS Code-style animation"""

    _BAR_WIDTH = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_indeterminate = False
        self._hidden = False
        self.animation_position = 0.0
        self.animation_speed = 2.5
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)

        self.setTextVisible(False)
        self.setRange(0, 100)
        self.setValue(0)
        self._apply_theme_colors()
        self.setAutoFillBackground(True)
        self.setFixedHeight(2)
        self.setProgressHidden(True)

    def _apply_theme_colors(self):
        from src.shared.ui import theme

        p = theme.palette()
        self.progress_color = theme.qcolor(p.accent)
        self.background_color = theme.qcolor(p.accent, 51)
        self.setStyleSheet(f"""
            QProgressBar {{
                background-color: {p.bg_window};
                border: none;
            }}
            QProgressBar::chunk {{
                background: transparent;
            }}
        """)

    def setIndeterminate(self, indeterminate: bool):
        """Set indeterminate mode (infinite animation)."""
        self.is_indeterminate = indeterminate
        if indeterminate:
            self.setRange(0, 100)
            self.setValue(0)
            if not self._hidden:
                self.animation_timer.start(16)
        else:
            self.animation_timer.stop()
            self.setRange(0, 100)
            self.setValue(0)
            self.update()

    def _update_animation(self):
        if not self.is_indeterminate or self._hidden:
            return
        width = max(self.width(), 1)
        cycle_length = width + self._BAR_WIDTH
        self.animation_position += self.animation_speed
        if self.animation_position >= cycle_length:
            self.animation_position -= cycle_length
        self.update()

    def setProgressHidden(self, hidden: bool):
        """Hide progress animation without changing layout height."""
        self._hidden = hidden
        self.setFixedHeight(2)
        if hidden:
            self.animation_timer.stop()
        elif self.is_indeterminate:
            self.animation_timer.start(16)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = max(self.width(), 1)
        cycle_length = width + self._BAR_WIDTH
        if cycle_length > 0:
            self.animation_position %= cycle_length

    def paintEvent(self, event):
        if self._hidden or self.height() <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        painter.fillRect(rect, self.background_color)

        if self.is_indeterminate:
            width = max(rect.width(), 1)
            bar_width = min(self._BAR_WIDTH, max(40, width // 3))
            cycle_length = width + bar_width
            pos = self.animation_position % cycle_length

            gradient = QLinearGradient(pos - bar_width, 0, pos, 0)
            fade_ratio = 0.35
            transparent = QColor(0, 0, 0, 0)
            gradient.setColorAt(0.0, transparent)
            gradient.setColorAt(fade_ratio, self.progress_color)
            gradient.setColorAt(1.0 - fade_ratio, self.progress_color)
            gradient.setColorAt(1.0, transparent)

            painter.fillRect(rect, gradient)
        elif self.maximum() > 0 and self.value() > 0:
            progress_width = int((self.value() / self.maximum()) * rect.width())
            progress_rect = QRect(0, 0, progress_width, rect.height())
            painter.fillRect(progress_rect, self.progress_color)

    def setValue(self, value: int):
        if not self.is_indeterminate:
            super().setValue(value)

    def startAnimation(self):
        if self.is_indeterminate and not self._hidden:
            self.animation_timer.start(16)

    def stopAnimation(self):
        self.animation_timer.stop()
