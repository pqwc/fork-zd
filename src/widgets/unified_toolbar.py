"""Панель инструментов с единой рамкой (codicons + combobox)."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from src.shared.ui import theme as ui_theme
from src.widgets.codicon_button import CodiconButton
from src.widgets.custom_combobox import CustomComboBox
from src.widgets.rounded_clip import RoundedClipFrame

_TOOLBAR_PAD_LEFT = 6
_TOOLBAR_PAD_RIGHT = 6
_TOOLBAR_ROW_HEIGHT = 28
_TOOLBAR_SEP_HEIGHT = 20


class UnifiedToolbar(RoundedClipFrame):
    ROW_HEIGHT = _TOOLBAR_ROW_HEIGHT

    def __init__(self, parent=None):
        super().__init__(
            "UnifiedToolbar",
            radius=ui_theme.PANEL_RADIUS,
            parent=parent,
            bg="bg_panel",
            draw_border=True,
        )
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        self._layout = QHBoxLayout(self)
        self._layout.setSpacing(4)
        self._layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._set_vertical_margins(1, 3)
        self.apply_theme()

    def _set_vertical_margins(self, pad_top: int, pad_bottom: int) -> None:
        self._layout.setContentsMargins(
            _TOOLBAR_PAD_LEFT,
            pad_top,
            _TOOLBAR_PAD_RIGHT,
            pad_bottom,
        )

    def match_tab_height(self, tab_height: int) -> None:
        """Высота toolbar = высота вкладки; строка контента фиксирована."""
        height = max(tab_height, self.ROW_HEIGHT)
        extra = height - self.ROW_HEIGHT
        if extra <= 0:
            pad_top = 0
            pad_bottom = 0
        elif extra == 1:
            pad_top = 0
            pad_bottom = 1
        else:
            pad_top = 1
            pad_bottom = extra - pad_top
        self.setFixedHeight(height)
        self._set_vertical_margins(pad_top, pad_bottom)

    def apply_theme(self) -> None:
        self.refresh_border_theme()
        p = ui_theme.palette()
        self.setStyleSheet(f"""
            QFrame#UnifiedToolbar {{
                background: transparent;
                border: none;
            }}
            QFrame#UnifiedToolbar QPushButton#CodiconButton {{
                background: transparent;
                border: none;
                border-radius: {ui_theme.CONTROL_RADIUS}px;
                padding: 0px;
                margin: 0px;
            }}
            QFrame#UnifiedToolbar QPushButton#CodiconButton:hover {{
                background-color: {p.hover_bg};
            }}
            QFrame#UnifiedToolbar QPushButton#CodiconButton:pressed {{
                background-color: {p.accent_subtle};
            }}
            QFrame#UnifiedToolbar CustomComboBox {{
                padding: 0px;
                margin: 0px;
            }}
        """)

    def refresh_theme(self) -> None:
        self.apply_theme()

    def add_button(self, button: CodiconButton) -> None:
        button.set_button_size(self.ROW_HEIGHT)
        button.set_icon_offset(0, 1)
        self._layout.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)

    def add_separator(self, margin_h: int = 4) -> None:
        wrapper = QWidget()
        wrapper.setFixedSize(margin_h * 2 + 1, self.ROW_HEIGHT)
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(margin_h, 0, margin_h, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        sep = QWidget()
        sep.setFixedSize(1, _TOOLBAR_SEP_HEIGHT)
        p = ui_theme.palette()
        sep.setStyleSheet(f"background-color: {p.border};")
        wrapper_layout.addWidget(sep)
        self._layout.addWidget(wrapper, 0, Qt.AlignmentFlag.AlignVCenter)

    def add_combobox(self, combo: CustomComboBox, min_width: int = 140, *, flat: bool = False) -> None:
        if flat:
            combo.setDrawBorder(False)
            combo.setDrawBackground(False)
            combo.setToolbarFlat(True)
        combo.setMinimumWidth(min_width)
        self._layout.addWidget(combo, 0, Qt.AlignmentFlag.AlignVCenter)

    def add_stretch(self) -> None:
        self._layout.addStretch(1)
