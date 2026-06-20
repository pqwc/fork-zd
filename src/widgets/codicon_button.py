"""Кнопка с иконкой VS Code Codicon."""
from PyQt6.QtWidgets import QPushButton, QSizePolicy
from PyQt6.QtCore import Qt, QSize, QRectF
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

from src.shared.ui.assets.embedded_assets import get_svg_qbytearray


class CodiconButton(QPushButton):
    def __init__(
        self,
        icon_name: str,
        tooltip: str = "",
        parent=None,
        size: int = 16,
        button_size: int | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("CodiconButton")
        self._icon_name = icon_name
        self._icon_size = size
        self._button_size = button_size if button_size is not None else 32
        self._icon_offset_x = 0
        self._icon_offset_y = 0
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setFixedSize(self._button_size, self._button_size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._apply_icon()

    def set_button_size(self, size: int):
        self._button_size = size
        self.setFixedSize(size, size)
        self._apply_icon()

    def set_icon_offset(self, dx: int, dy: int):
        self._icon_offset_x = dx
        self._icon_offset_y = dy
        self._apply_icon()

    def set_codicon(self, icon_name: str):
        self._icon_name = icon_name
        self._apply_icon()

    def _apply_icon(self):
        data = get_svg_qbytearray(self._icon_name)
        if data.isEmpty():
            return
        renderer = QSvgRenderer()
        if not renderer.load(data):
            return
        pix = QPixmap(self._button_size, self._button_size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        ox = (self._button_size - self._icon_size) // 2 + self._icon_offset_x
        oy = (self._button_size - self._icon_size) // 2 + self._icon_offset_y
        renderer.render(
            painter,
            QRectF(ox, oy, self._icon_size, self._icon_size),
        )
        painter.end()
        self.setIcon(QIcon(pix))
        self.setIconSize(QSize(self._button_size, self._button_size))
