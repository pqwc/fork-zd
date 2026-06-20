"""Утилиты для иконок VS Code Codicons."""
from PyQt6.QtCore import QSize, Qt, QRectF
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from src.shared.ui.assets.embedded_assets import get_svg_qbytearray


def codicon_icon(name: str, size: int = 16) -> QIcon:
    """Создаёт QIcon из codicon SVG."""
    data = get_svg_qbytearray(name)
    if data.isEmpty():
        return QIcon()
    renderer = QSvgRenderer()
    if not renderer.load(data):
        return QIcon()
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return QIcon(pix)


def codicon_tab_icon(name: str, size: int = 14, y_offset: int = 2) -> QIcon:
    """Codicon для вкладок: с небольшим смещением вниз для выравнивания с текстом."""
    data = get_svg_qbytearray(name)
    if data.isEmpty():
        return QIcon()
    renderer = QSvgRenderer()
    if not renderer.load(data):
        return QIcon()
    height = size + y_offset
    pix = QPixmap(size, height)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter, QRectF(0, y_offset, size, size))
    painter.end()
    return QIcon(pix)


def codicon_colored_pixmap(name: str, size: int, color: str) -> QPixmap:
    """Codicon с заданным цветом (tint через SourceIn)."""
    from PyQt6.QtGui import QColor

    icon = codicon_icon(name, size)
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    if icon.isNull():
        return pix
    base = icon.pixmap(size, size)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.drawPixmap(0, 0, base)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pix.rect(), QColor(color))
    painter.end()
    return pix


def codicon_icon_sized(name: str, size: int = 16) -> tuple[QIcon, QSize]:
    icon = codicon_icon(name, size)
    return icon, QSize(size, size)
