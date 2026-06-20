from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PyQt6.QtGui import QPainter, QPainterPath, QPen, QIcon, QWheelEvent, QPixmap, QFontMetrics
from PyQt6.QtCore import Qt, QRectF, QSize, pyqtSignal, QPoint, QEvent
from PyQt6.QtSvg import QSvgRenderer
from .style_menu import StyleMenu
from src.shared.ui.assets.embedded_assets import get_svg_qbytearray
from src.shared.ui import theme


class CustomComboBox(QWidget):
    """Кастомный ComboBox на базе StyleMenu."""

    currentTextChanged = pyqtSignal(str)
    currentIndexChanged = pyqtSignal(int)

    _CHEVRON_SIZE = 14
    _ARROW_BTN = 22

    def __init__(self, parent=None, *, draw_border=True, draw_background=True):
        super().__init__(parent)

        self._draw_border = draw_border
        self._draw_background = draw_background
        self._toolbar_flat = False
        self.items = []
        self.current_index = -1
        self.min_width = 0
        self._menu_visible = False
        self._action_by_index = {}

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 0, 6, 0)
        self._layout.setSpacing(2)

        self.text_label = QLabel()
        self.text_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.text_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.text_label.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred
        )
        self._update_text_style()
        self._layout.addWidget(self.text_label, 1)

        self.arrow_button = QPushButton()
        self.arrow_button.setFlat(True)
        self.arrow_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.arrow_button.setFixedSize(self._ARROW_BTN, self._ARROW_BTN)
        self.arrow_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.arrow_button.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0px; margin: 0px; }"
        )

        data = get_svg_qbytearray("chevron-down")
        self.chevron_renderer = None
        if not data.isEmpty():
            renderer = QSvgRenderer()
            if renderer.load(data):
                self.chevron_renderer = renderer
        self._refresh_chevron_icon()

        self._layout.addWidget(
            self.arrow_button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self.menu = StyleMenu(self)

        self.arrow_button.clicked.connect(self.show_menu)
        self.menu.aboutToShow.connect(self._on_menu_about_to_show)
        self.menu.aboutToHide.connect(self._on_menu_about_to_hide)

        self.text_label.installEventFilter(self)
        self.arrow_button.installEventFilter(self)

        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAutoFillBackground(False)
        self.setFixedHeight(theme.EDITOR_FIELD_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def _layout_horizontal_extra(self) -> int:
        m = self._layout.contentsMargins()
        return m.left() + m.right() + self._layout.spacing() + self._ARROW_BTN

    def _text_pixel_width(self, text: str) -> int:
        if not text:
            return 0
        return QFontMetrics(self.text_label.font()).horizontalAdvance(text)

    def _widest_item_text_width(self) -> int:
        width = 0
        for item in self.items:
            if item.get("separator", False):
                continue
            width = max(width, self._text_pixel_width(item.get("text", "")))
        return width

    def _content_width(self) -> int:
        text_w = self._text_pixel_width(self.text_label.text())
        if text_w <= 0:
            text_w = self._widest_item_text_width()
        return self._layout_horizontal_extra() + text_w + 4

    def _refresh_geometry(self) -> None:
        content_w = max(self.min_width, self._content_width())
        super().setMinimumWidth(content_w)
        self.updateGeometry()

    def setDrawBorder(self, draw: bool):
        self._draw_border = draw
        self.update()

    def setDrawBackground(self, draw: bool):
        self._draw_background = draw
        self.update()

    def setToolbarFlat(self, flat: bool):
        """Компактный режим внутри UnifiedToolbar."""
        self._toolbar_flat = flat
        if flat:
            from src.widgets.unified_toolbar import UnifiedToolbar

            self.setFixedHeight(UnifiedToolbar.ROW_HEIGHT)
            self._layout.setContentsMargins(4, 0, 2, 0)
            self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        else:
            self.setFixedHeight(theme.EDITOR_FIELD_HEIGHT)
            self._layout.setContentsMargins(8, 0, 6, 0)
            self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._refresh_chevron_icon()
        self._refresh_geometry()
        self.update()

    def sizeHint(self):
        from src.widgets.unified_toolbar import UnifiedToolbar

        h = UnifiedToolbar.ROW_HEIGHT if self._toolbar_flat else theme.EDITOR_FIELD_HEIGHT
        w = max(self.min_width, self._content_width())
        return QSize(w, h)

    def minimumSizeHint(self):
        h = theme.EDITOR_FIELD_HEIGHT
        if self._toolbar_flat:
            from src.widgets.unified_toolbar import UnifiedToolbar
            h = UnifiedToolbar.ROW_HEIGHT
        w = max(self.min_width, self._content_width())
        return QSize(w, h)

    def _refresh_chevron_icon(self):
        p = theme.palette()
        if self.chevron_renderer is None:
            glyph = "▴" if self._menu_visible else "▾"
            self.arrow_button.setIcon(QIcon())
            self.arrow_button.setText(glyph)
            self.arrow_button.setStyleSheet(
                "QPushButton { background: transparent; border: none; padding: 0px; margin: 0px; "
                f"color: {p.fg_muted}; font-size: 11px; }}"
            )
            return

        self.arrow_button.setText("")
        size = self._CHEVRON_SIZE
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        target = QRectF(0, 0, size, size)
        if self._menu_visible:
            painter.translate(target.center())
            painter.rotate(180)
            painter.translate(-target.center())
        self.chevron_renderer.render(painter, target)
        painter.end()
        self.arrow_button.setIcon(QIcon(pix))
        self.arrow_button.setIconSize(QSize(size, size))
        self.arrow_button.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0px; margin: 0px; }"
        )

    def paintEvent(self, event):
        if not (self._draw_border or self._draw_background):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path.addRoundedRect(rect, theme.CONTROL_RADIUS, theme.CONTROL_RADIUS)

        p = theme.palette()
        if not self.isEnabled():
            border_color = theme.qcolor(p.border, 120)
            background_color = theme.qcolor(p.bg_panel, 180)
        else:
            border_color = theme.qcolor(p.accent if self.hasFocus() else p.border, 220)
            if self._toolbar_flat:
                background_color = theme.qcolor(p.bg_panel, 230 if theme.is_light() else 255)
            else:
                background_color = theme.qcolor(p.bg_item, 255)

        if self._draw_background:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background_color)
            painter.drawPath(path)

        if self._draw_border:
            pen = QPen(border_color, 1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.setFocus()
            self.show_menu()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if not self.isEnabled():
            event.ignore()
            return

        if event.key() in (
            Qt.Key.Key_Space,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            self.show_menu()
        elif event.key() == Qt.Key.Key_Up:
            self._step_prev()
        elif event.key() == Qt.Key.Key_Down:
            self._step_next()
        else:
            super().keyPressEvent(event)

    def _step_prev(self):
        new_index = self.current_index - 1
        while new_index >= 0:
            if not self.items[new_index].get("separator", False):
                self.setCurrentIndex(new_index)
                return True
            new_index -= 1
        return False

    def _step_next(self):
        new_index = self.current_index + 1
        while new_index < len(self.items):
            if not self.items[new_index].get("separator", False):
                self.setCurrentIndex(new_index)
                return True
            new_index += 1
        return False

    def wheelEvent(self, event: QWheelEvent):
        if not self.isEnabled() or not self.items:
            super().wheelEvent(event)
            return
        if event.angleDelta().y() > 0:
            if self._step_prev():
                event.accept()
                return
        elif self._step_next():
            event.accept()
            return
        super().wheelEvent(event)

    def eventFilter(self, obj, event):
        if obj in (self.text_label, self.arrow_button):
            if event.type() == QEvent.Type.MouseButtonPress:
                if (
                    event.button() == Qt.MouseButton.LeftButton
                    and self.isEnabled()
                    and obj is self.text_label
                ):
                    self.setFocus()
                    self.show_menu()
                    return True
            if event.type() == QEvent.Type.Wheel and self.isEnabled() and self.items:
                if event.angleDelta().y() > 0:
                    self._step_prev()
                else:
                    self._step_next()
                return True
        return super().eventFilter(obj, event)

    def addItem(self, text, userData=None):
        idx = len(self.items)
        self.items.append({"text": text, "data": userData, "separator": False})

        action = self.menu.addAction(text)
        action.setData(userData)
        action.setCheckable(True)
        action.setChecked(idx == self.current_index)
        action.triggered.connect(lambda _checked, i=idx: self._on_item_selected(i))
        self._action_by_index[idx] = action

        if self.current_index == -1:
            self.setCurrentIndex(idx)
        self._refresh_geometry()

    def addItems(self, texts):
        for text in texts:
            self.addItem(text)

    def insertItem(self, index, text, userData=None):
        self.items.insert(index, {"text": text, "data": userData, "separator": False})
        self._rebuild_menu()
        if index <= self.current_index:
            self.current_index += 1

    def insertSeparator(self, index):
        self.items.insert(index, {"text": "", "data": None, "separator": True})
        self._rebuild_menu()
        if index <= self.current_index:
            self.current_index += 1

    def removeItem(self, index):
        if not (0 <= index < len(self.items)):
            return
        self.items.pop(index)
        self._rebuild_menu()

        if index < self.current_index:
            self.current_index -= 1
        elif index == self.current_index:
            if self.items:
                new_index = min(self.current_index, len(self.items) - 1)
                while (
                    0 <= new_index < len(self.items)
                    and self.items[new_index].get("separator", False)
                ):
                    new_index = new_index + 1 if new_index < len(self.items) - 1 else new_index - 1
                if (
                    0 <= new_index < len(self.items)
                    and not self.items[new_index].get("separator", False)
                ):
                    self.setCurrentIndex(new_index)
                else:
                    self.current_index = -1
                    self.text_label.setText("")
            else:
                self.current_index = -1
                self.text_label.setText("")

    def clear(self):
        self.items.clear()
        self.menu.clear()
        self._action_by_index.clear()
        self.current_index = -1
        self.text_label.setText("")
        self.text_label.setToolTip("")
        self._update_text_style()
        self._refresh_geometry()

    def _rebuild_menu(self):
        self.menu.clear()
        self._action_by_index.clear()
        for idx, item in enumerate(self.items):
            if item.get("separator", False):
                self.menu.addSeparator()
            else:
                action = self.menu.addAction(item["text"])
                action.setData(item["data"])
                action.setCheckable(True)
                action.setChecked(idx == self.current_index)
                action.triggered.connect(lambda _checked, i=idx: self._on_item_selected(i))
                self._action_by_index[idx] = action
        self._refresh_geometry()

    def _on_item_selected(self, index):
        if 0 <= index < len(self.items) and not self.items[index].get("separator", False):
            self.setCurrentIndex(index)

    def setCurrentIndex(self, index):
        if not (0 <= index < len(self.items)):
            return
        if self.items[index].get("separator", False):
            return

        old_index = self.current_index
        self.current_index = index
        text = self.items[index]["text"]
        self.text_label.setText(text)
        self.text_label.setToolTip(text)

        if old_index in self._action_by_index:
            self._action_by_index[old_index].setChecked(False)
        if index in self._action_by_index:
            self._action_by_index[index].setChecked(True)

        self._update_text_style()
        self._refresh_geometry()

        if old_index != index and not self.signalsBlocked():
            self.currentIndexChanged.emit(index)
            self.currentTextChanged.emit(self.items[index]["text"])

    def setCurrentText(self, text):
        for idx, item in enumerate(self.items):
            if not item.get("separator", False) and item["text"] == text:
                self.setCurrentIndex(idx)
                return

    def findText(self, text):
        for idx, item in enumerate(self.items):
            if not item.get("separator", False) and item["text"] == text:
                return idx
        return -1

    def currentIndex(self):
        return self.current_index

    def currentText(self):
        if 0 <= self.current_index < len(self.items):
            item = self.items[self.current_index]
            if not item.get("separator", False):
                return item["text"]
        return ""

    def currentData(self):
        if 0 <= self.current_index < len(self.items):
            item = self.items[self.current_index]
            if not item.get("separator", False):
                return item["data"]
        return None

    def itemText(self, index):
        if 0 <= index < len(self.items):
            item = self.items[index]
            if not item.get("separator", False):
                return item["text"]
        return ""

    def itemData(self, index):
        if 0 <= index < len(self.items):
            item = self.items[index]
            if not item.get("separator", False):
                return item["data"]
        return None

    def count(self):
        return len(self.items)

    def show_menu(self):
        if not self.isEnabled() or not self.items:
            return
        pos = self.mapToGlobal(QPoint(0, self.height()))
        self.menu.setMinimumWidth(max(self.width(), self._content_width()))
        self.menu.exec(pos)

    def _on_menu_about_to_show(self):
        self._menu_visible = True
        self._refresh_chevron_icon()

    def _on_menu_about_to_hide(self):
        self._menu_visible = False
        self._refresh_chevron_icon()

    def setMinimumWidth(self, width):
        self.min_width = width
        self._refresh_geometry()

    def setEditable(self, editable):
        pass

    def setPlaceholderText(self, text):
        if self.current_index == -1:
            self.text_label.setText(text)
            self.text_label.setToolTip(text)
            self._update_text_style(placeholder=True)
            self._refresh_geometry()

    def apply_theme(self):
        self._update_text_style()
        self._refresh_chevron_icon()
        self.update()

    def _update_styles(self):
        self.arrow_button.setEnabled(self.isEnabled())
        self._update_text_style()
        self.update()

    def _update_text_style(self, placeholder: bool = False):
        p = theme.palette()
        if not self.isEnabled():
            color = p.fg_muted
        else:
            color = p.fg_muted if placeholder or self.current_index == -1 else p.fg_text
        self.text_label.setStyleSheet(f"""
            QLabel {{
                background-color: transparent;
                color: {color};
                padding: 0px;
                margin: 0px;
                border: none;
            }}
        """)

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self._update_styles()
