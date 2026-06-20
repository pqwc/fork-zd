"""Скругление углов: маска содержимого + сглаженная обводка через QPainter."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QRegion
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QWidget

from src.shared.ui import theme


def apply_round_clip(widget: QWidget, radius: float) -> None:
    """Обрезает виджет и всех потомков по скруглённому прямоугольнику."""
    rect = widget.rect()
    if rect.width() <= 0 or rect.height() <= 0:
        return
    path = QPainterPath()
    path.addRoundedRect(QRectF(rect), radius, radius)
    widget.setMask(QRegion(path.toFillPolygon().toPolygon()))


class _RoundClipFilter(QObject):
    """Обновляет маску при изменении размера или показе виджета."""

    def __init__(self, widget: QWidget, radius: float):
        super().__init__(widget)
        self._widget = widget
        self._radius = radius
        widget.installEventFilter(self)

    def set_radius(self, radius: float) -> None:
        self._radius = radius

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._widget and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            apply_round_clip(self._widget, self._radius)
        return super().eventFilter(watched, event)


def install_round_clip(widget: QWidget, radius: float) -> None:
    """Подключает скругление через маску к любому виджету."""
    widget._clip_radius = radius

    def _apply_round_clip() -> None:
        apply_round_clip(widget, widget._clip_radius)

    widget._apply_round_clip = _apply_round_clip

    clip_filter = getattr(widget, "_round_clip_filter", None)
    if clip_filter is None:
        widget._round_clip_filter = _RoundClipFilter(widget, radius)
    else:
        clip_filter.set_radius(radius)
    _apply_round_clip()


def _resolve_bg_color(bg: str | None) -> str:
    p = theme.palette()
    if not bg:
        return p.bg_item
    if bg.startswith("#"):
        return bg
    return getattr(p, bg, p.bg_item)


def paint_rounded_panel(
    painter: QPainter,
    rect: QRectF,
    *,
    radius: float,
    bg_color: str,
    border_color: str | None = None,
    border_width: float = 1.0,
) -> None:
    """Заливает скруглённый прямоугольник и рисует обводку с антиалиасингом."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    draw_rect = rect
    if border_color and border_width > 0:
        inset = border_width / 2.0
        draw_rect = rect.adjusted(inset, inset, -inset, -inset)

    path = QPainterPath()
    path.addRoundedRect(draw_rect, radius, radius)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(bg_color)))
    painter.drawPath(path)

    if border_color and border_width > 0:
        pen = QPen(QColor(border_color))
        pen.setWidthF(border_width)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


class RoundedClipFrame(QFrame):
    """QFrame со скруглением через маску и обводкой через QPainter (не QSS border)."""

    def __init__(
        self,
        object_name: str = "",
        radius: float = 8,
        parent=None,
        *,
        bg: str | None = None,
        draw_border: bool | None = None,
    ):
        super().__init__(parent)
        if object_name:
            self.setObjectName(object_name)
        self._radius = float(radius)
        self._bg_key = bg
        self._draw_border_flag = draw_border
        self._bg_color = ""
        self._border_color: str | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        install_round_clip(self, self._radius)
        self.refresh_border_theme()

    def refresh_border_theme(self) -> None:
        self._bg_color = _resolve_bg_color(self._bg_key)
        draw = (
            self._draw_border_flag
            if self._draw_border_flag is not None
            else theme.is_light()
        )
        self._border_color = theme.palette().border if draw else None
        self.update()

    def refresh_theme(self) -> None:
        self.refresh_border_theme()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        paint_rounded_panel(
            painter,
            QRectF(self.rect()),
            radius=self._radius,
            bg_color=self._bg_color,
            border_color=self._border_color,
        )
        painter.end()
        super().paintEvent(event)


class RoundedContentWrapper(QWidget):
    """Обёртка для QPlainTextEdit, таблиц и других «квадратных» виджетов."""

    def __init__(self, content: QWidget | None = None, *, radius: float = 8, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._content = content
        if content is not None:
            layout.addWidget(content, 1)
        install_round_clip(self, radius)

    def content_widget(self) -> QWidget | None:
        return self._content


def wrap_rounded_content(
    widget: QWidget,
    *,
    radius: float = 8,
    background: str | None = None,
    parent=None,
) -> RoundedContentWrapper:
    """Оборачивает виджет в панель с маской по углам."""
    wrapper = RoundedContentWrapper(widget, radius=radius, parent=parent)
    if background:
        wrapper.setStyleSheet(f"background-color: {background}; border: none;")
    return wrapper
