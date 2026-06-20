"""
Кастомный стиль Qt для отрисовки индикаторов из встроенных SVG.
Позволяет использовать SVG без файлов на диске.
"""
from PyQt6.QtWidgets import QProxyStyle, QStyle, QStyleOption, QStyleOptionMenuItem, QStyleOptionViewItem
from PyQt6.QtGui import QPainter, QIcon, QPixmap
from PyQt6.QtCore import QRect, Qt, QSize
from PyQt6.QtSvg import QSvgRenderer
from src.shared.ui.assets.embedded_assets import get_svg_qbytearray


class EmbeddedStyle(QProxyStyle):
    """Стиль с поддержкой встроенных SVG-иконок для индикаторов."""
    
    def __init__(self, base_style=None):
        super().__init__(base_style)
        self._renderers: dict[tuple[str, str], QSvgRenderer] = {}
        self._theme_color_key = ""
    
    def _theme_color(self) -> str:
        try:
            from src.shared.ui import theme as ui_theme
            return ui_theme.palette().fg_text
        except Exception:
            return "#ececec"

    def _get_renderer(self, name: str) -> QSvgRenderer | None:
        color = self._theme_color()
        if color != self._theme_color_key:
            self._renderers.clear()
            self._theme_color_key = color
        key = (name, color)
        cached = self._renderers.get(key)
        if cached is not None:
            return cached
        data = get_svg_qbytearray(name)
        if data.isEmpty():
            return None
        renderer = QSvgRenderer()
        if renderer.load(data):
            self._renderers[key] = renderer
            return renderer
        return None

    def reload_icons(self):
        """Сброс кэша после смены темы."""
        self._renderers.clear()
        self._theme_color_key = ""

    def _render_svg(self, painter: QPainter, rect: QRect, name: str):
        """Отрисовывает SVG в указанном прямоугольнике."""
        renderer = self._get_renderer(name)
        if renderer:
            from PyQt6.QtCore import QRectF
            renderer.render(painter, QRectF(rect))
    
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_IndicatorMenuCheckMark:
            if option.state & QStyle.StateFlag.State_On:
                self._render_svg(painter, option.rect, "check")
                return
        
        if element == QStyle.PrimitiveElement.PE_IndicatorCheckBox:
            rect = option.rect
            from PyQt6.QtGui import QColor
            from src.shared.ui import theme

            p = theme.palette()
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(p.bg_panel))
            painter.drawRoundedRect(rect, 3, 3)
            painter.setPen(QColor(p.border))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 3, 3)
            painter.restore()
            # Проверяем состояние checked (State_On)
            if option.state & QStyle.StateFlag.State_On:
                self._render_svg(painter, rect, "check")
            return
        
        # Также обрабатываем индикатор в item views (таблицы, списки)
        if element == QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck:
            rect = option.rect
            if option.state & QStyle.StateFlag.State_On:
                self._render_svg(painter, rect, "check")
            return
        
        if element == QStyle.PrimitiveElement.PE_IndicatorArrowDown:
            self._render_svg(painter, option.rect, "chevron-down")
            return
        
        if element == QStyle.PrimitiveElement.PE_IndicatorArrowRight:
            self._render_svg(painter, option.rect, "chevron-right")
            return
        
        super().drawPrimitive(element, option, painter, widget)
    
    def drawControl(self, element, option, painter, widget=None):
        super().drawControl(element, option, painter, widget)
    
    def standardIcon(self, standardIcon, option=None, widget=None):
        if standardIcon == QStyle.StandardPixmap.SP_TitleBarCloseButton:
            return self._create_icon("close")
        if standardIcon == QStyle.StandardPixmap.SP_ArrowDown:
            return self._create_icon("chevron-down")
        if standardIcon == QStyle.StandardPixmap.SP_ArrowRight:
            return self._create_icon("chevron-right")
        return super().standardIcon(standardIcon, option, widget)
    
    def _create_icon(self, name: str, size: int = 16) -> QIcon:
        """Создаёт QIcon из SVG."""
        renderer = self._get_renderer(name)
        if not renderer:
            return QIcon()
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
        return QIcon(pix)
