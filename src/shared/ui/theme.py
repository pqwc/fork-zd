from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
import re

EDITOR_BLOCK_RADIUS = 8
EDITOR_FIELD_HEIGHT = 26
CONTROL_RADIUS = 6
PANEL_RADIUS = 8
TAB_RADIUS = 6


def input_field_height_qss(
    *,
    h: int | None = None,
    pad_h: str = "8px",
    bordered: bool = True,
) -> str:
    """Высота поля ровно h px снаружи (1px border учитывается в inner)."""
    if h is None:
        h = EDITOR_FIELD_HEIGHT
    inner = h - 2 if bordered else h
    return (
        f"height: {inner}px; "
        f"min-height: {inner}px; "
        f"max-height: {inner}px; "
        f"padding-top: 0px; "
        f"padding-bottom: 0px; "
        f"padding-left: {pad_h}; "
        f"padding-right: {pad_h};"
    )


class Theme(Enum):
    DARK = "dark"
    LIGHT = "light"


@dataclass(frozen=True)
class ThemePalette:
    """Палитра TrustRouter (тёмная) + зеркальная светлая тема."""

    bg_window: str
    bg_panel: str
    bg_item: str
    bg_secondary: str
    fg_text: str
    fg_muted: str
    accent: str
    accent_hover: str
    accent_subtle: str
    border: str
    hover_bg: str
    overlay_border: str
    line_number_bg: str
    line_number_fg: str
    line_number_current_fg: str
    current_line_bg: str
    occurrence_bg: str
    scrollbar_track: str
    scrollbar_handle: str


@dataclass(frozen=True)
class SyntaxPalette:
    """Цвета подсветки синтаксиса для текущей темы."""

    comment: str
    section: str
    identifier: str
    string: str
    keyword: str
    operator: str
    number: str
    type_token: str
    label: str
    option: str


_DARK_SYNTAX = SyntaxPalette(
    comment="#6A9955",
    section="#808080",
    identifier="#9CDCFE",
    string="#CE9178",
    keyword="#C586C0",
    operator="#D7BA7D",
    number="#B5CEA8",
    type_token="#569CD6",
    label="#DCDCAA",
    option="#808080",
)

_LIGHT_SYNTAX = SyntaxPalette(
    comment="#008000",
    section="#5a5a5a",
    identifier="#0451a5",
    string="#a31515",
    keyword="#af00db",
    operator="#795e26",
    number="#098658",
    type_token="#0070c1",
    label="#8b6914",
    option="#666666",
)


def syntax_palette() -> SyntaxPalette:
    """Палитра подсветки синтаксиса для текущей темы."""
    return _LIGHT_SYNTAX if _current_theme is Theme.LIGHT else _DARK_SYNTAX


def _mirror_hex(hex_color: str) -> str:
    """Инвертирует #RRGGBB — зеркало тёмной палитры для светлой."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    return "#" + "".join(f"{255 - int(h[i : i + 2], 16):02x}" for i in (0, 2, 4))


def _mirror_rgba(value: str) -> str:
    m = re.fullmatch(
        r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)",
        value,
    )
    if not m:
        return value
    r, g, b, a = m.groups()
    return f"rgba({255 - int(r)}, {255 - int(g)}, {255 - int(b)}, {a})"


# Акцент не инвертируем — иначе получается нечитаемый цвет на светлом фоне.
_ACCENT_FIELDS = frozenset({"accent", "accent_hover", "accent_subtle"})


def _mirror_palette(source: ThemePalette) -> ThemePalette:
    """Строит светлую палитру как зеркало тёмной."""
    kwargs = {}
    for field in fields(source):
        value = getattr(source, field.name)
        if field.name in _ACCENT_FIELDS:
            kwargs[field.name] = value
        elif value.startswith("#"):
            kwargs[field.name] = _mirror_hex(value)
        elif value.startswith("rgba("):
            kwargs[field.name] = _mirror_rgba(value)
        else:
            kwargs[field.name] = value
    return ThemePalette(**kwargs)


# TrustRouter dark (frontend/src/app/globals.css)
_DARK_PALETTE = ThemePalette(
    bg_window="#141414",
    bg_panel="#181818",
    bg_item="#1c1c1c",
    bg_secondary="#212121",
    fg_text="#ececec",
    fg_muted="#9a9a9a",
    accent="#5b8def",
    accent_hover="#6e9bf5",
    accent_subtle="rgba(91, 141, 239, 0.2)",
    border="#242424",
    hover_bg="#252525",
    overlay_border="#303030",
    line_number_bg="#1c1c1c",
    line_number_fg="#737373",
    line_number_current_fg="#ececec",
    current_line_bg="#252525",
    occurrence_bg="#2a3348",
    scrollbar_track="#555555",
    scrollbar_handle="#444444",
)

# Светлая тема — зеркало _DARK_PALETTE (фоны/текст/границы), акцент как в тёмной
_LIGHT_PALETTE = _mirror_palette(_DARK_PALETTE)

_current_theme: Theme = Theme.DARK


def set_theme(theme_value) -> None:
    """Устанавливает текущую тему.

    Принимает как значение Enum Theme.DARK / Theme.LIGHT,
    так и строки 'dark' / 'light' (регистр не важен).
    """
    global _current_theme
    if isinstance(theme_value, Theme):
        _current_theme = theme_value
        return
    if isinstance(theme_value, str):
        name = theme_value.strip().lower()
        if name == "dark":
            _current_theme = Theme.DARK
        elif name == "light":
            _current_theme = Theme.LIGHT
        return


def palette() -> ThemePalette:
    """Возвращает палитру для текущей темы."""
    return _DARK_PALETTE if _current_theme is Theme.DARK else _LIGHT_PALETTE


def qcolor(hex_color: str, alpha: int = 255):
    """Создаёт QColor из hex-строки палитры (#RRGGBB)."""
    from PyQt6.QtGui import QColor

    h = hex_color.lstrip("#")
    if len(h) != 6:
        return QColor(0, 0, 0, alpha)
    return QColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def apply_widget_theme(widget, *, bg: str | None = None) -> None:
    """Применяет фон и палитру до show() — убирает белую вспышку при открытии окна."""
    from PyQt6.QtGui import QColor, QPalette

    p = palette()
    bg_color = bg or p.bg_window
    pal = widget.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor(bg_color))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(p.fg_text))
    pal.setColor(QPalette.ColorRole.Base, QColor(p.bg_panel))
    pal.setColor(QPalette.ColorRole.Text, QColor(p.fg_text))
    widget.setPalette(pal)
    widget.setAutoFillBackground(True)


def current_theme() -> Theme:
    """Возвращает текущую тему."""
    return _current_theme


def is_light() -> bool:
    """True если выбрана светлая тема."""
    return _current_theme is Theme.LIGHT


def compact_toolbar_button_style() -> str:
    """Компактные кнопки для панелей инструментов и заголовков редакторов."""
    p = palette()
    return f"""
        QPushButton {{
            background-color: {p.bg_item};
            color: {p.fg_text};
            border: 1px solid {p.border};
            padding: 2px 8px;
            border-radius: {CONTROL_RADIUS}px;
            font-size: 11px;
            min-height: 22px;
            max-height: 24px;
        }}
        QPushButton:hover {{
            background-color: {p.accent};
            border: 1px solid {p.accent};
            color: #ffffff;
        }}
        QPushButton:pressed {{
            background-color: {p.accent_hover};
            border: 1px solid {p.accent_hover};
            color: #ffffff;
        }}
    """


def muted_label_style() -> str:
    """Стиль приглушённого текста (статусы, подписи)."""
    p = palette()
    return f"color: {p.fg_muted}; font-size: 11px;"


def small_muted_label_style() -> str:
    """Мелкий приглушённый текст (версия, контакт)."""
    p = palette()
    return f"color: {p.fg_muted}; font-size: 10px; margin: 0px;"


def border_style() -> str:
    """Стиль рамки для панелей."""
    p = palette()
    return f"border: 1px solid {p.border};"


def tab_bar_first_border_style() -> str:
    """Стиль левой границы первой вкладки."""
    p = palette()
    return f"QTabBar::tab:first {{ border-left: 1px solid {p.border}; }}"


def tab_toolbar_host_stylesheet(*, widget_id: str = "", selected_bg: str | None = None) -> str:
    """Стили TabToolbarHost: вкладки + toolbar в одной строке, контент в рамке."""
    p = palette()
    tab_selected = selected_bg or p.bg_secondary
    prefix = f"TabToolbarHost#{widget_id}" if widget_id else "TabToolbarHost"
    return f"""
        {prefix} {{
            background: transparent;
        }}
        {prefix} QWidget#TabToolbarHeader {{
            background: transparent;
        }}
        {prefix} QWidget#TabToolbarSlot {{
            background: transparent;
        }}
        {prefix} QFrame#TabToolbarPane {{
            background-color: {p.bg_panel};
            border: 1px solid {p.border};
            border-radius: 8px;
            margin-top: 8px;
        }}
        {prefix} QTabBar {{
            background: transparent;
            border: none;
        }}
        {prefix} QTabBar::tab {{
            background-color: {p.bg_window};
            color: {p.fg_muted};
            border: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
            border-radius: 8px 8px 0px 0px;
            padding: 6px 12px 6px 10px;
            margin: 0px 6px 0px 0px;
            min-width: 72px;
        }}
        {prefix} QTabBar::tab:selected {{
            background-color: {tab_selected};
            color: {p.fg_text};
            border: 1px solid {p.border};
            border-bottom: 1px solid {tab_selected};
            margin-bottom: -1px;
            padding-bottom: 7px;
        }}
        {prefix} QTabBar::tab:hover:!selected {{
            background-color: {p.hover_bg};
            color: {p.fg_text};
        }}
    """


def detached_tab_widget_stylesheet(*, selected_bg: str | None = None, widget_id: str = "") -> str:
    """Стиль QTabWidget с отдельными вкладками (как в окне тестирования)."""
    p = palette()
    tab_selected = selected_bg or p.bg_secondary
    prefix = f"QTabWidget#{widget_id}" if widget_id else "QTabWidget"
    tab_prefix = f"{prefix} QTabBar" if widget_id else "QTabBar"
    return f"""
        {prefix}::pane {{
            background-color: {p.bg_panel};
            border: 1px solid {p.border};
            border-radius: 8px;
            margin-top: 8px;
            padding: 1px;
            top: 0px;
        }}
        {tab_prefix} {{
            background: transparent;
            border: none;
        }}
        {prefix}::tab-bar {{
            alignment: left;
            left: 0px;
            top: 0px;
        }}
        {tab_prefix}::tab {{
            background-color: {p.bg_window};
            color: {p.fg_muted};
            border: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
            border-radius: 8px 8px 0px 0px;
            padding: 6px 12px 6px 10px;
            margin: 0px 6px 0px 0px;
            min-width: 72px;
        }}
        {tab_prefix}::tab:selected {{
            background-color: {tab_selected};
            color: {p.fg_text};
            border: 1px solid {p.border};
            border-bottom: 1px solid {tab_selected};
            margin-bottom: -1px;
            padding-bottom: 7px;
        }}
        {tab_prefix}::tab:hover:!selected {{
            background-color: {p.hover_bg};
            color: {p.fg_text};
        }}
    """


def editor_block_stylesheet(object_name: str) -> str:
    """Отдельный блок (список, редактор, вывод) внутри вкладки."""
    return f"""
        QFrame#{object_name} {{
            background: transparent;
            border: none;
        }}
    """


def create_editor_block(object_name: str, parent=None):
    """Закруглённый блок редактора с клипом содержимого."""
    from src.widgets.rounded_clip import RoundedClipFrame

    frame = RoundedClipFrame(
        object_name,
        radius=EDITOR_BLOCK_RADIUS,
        parent=parent,
    )
    frame.setStyleSheet(editor_block_stylesheet(object_name))
    return frame


def diag_checks_list_style() -> str:
    """Список проверок диагностики — как файловый список редактора."""
    p = palette()
    return f"""
        QListWidget {{
            background-color: transparent;
            border: none;
            color: {p.fg_text};
            outline: none;
            padding: 0px;
        }}
        QListWidget::item {{
            height: 24px;
            padding: 0px 8px;
            margin: 1px 0px;
            border: none;
            border-radius: 4px;
        }}
        QListWidget::item:hover {{
            background-color: {p.hover_bg};
        }}
        QListWidget::item:selected {{
            background-color: {p.hover_bg};
            color: {p.fg_text};
        }}
        QListWidget::item:selected:!active {{
            background-color: {p.hover_bg};
            color: {p.fg_text};
        }}
        QListWidget::item:checked {{
            background-color: transparent;
        }}
        QListWidget::item:checked:selected {{
            background-color: {p.hover_bg};
        }}
    """


def diag_checks_block_stylesheet() -> str:
    """Блок списка проверок диагностики."""
    name = "DiagChecksBlock"
    return editor_block_stylesheet(name)


def block_stylesheet(object_name: str) -> str:
    if object_name == "DiagChecksBlock":
        return diag_checks_block_stylesheet()
    return editor_block_stylesheet(object_name)


def wrap_tab_page_content(widget, *, radius: int | None = None, bg: str | None = None):
    """Оборачивает содержимое вкладки QTabWidget для корректных скруглённых углов."""
    from src.widgets.rounded_clip import wrap_rounded_content

    if radius is None:
        radius = EDITOR_BLOCK_RADIUS
    p = palette()
    return wrap_rounded_content(
        widget,
        radius=radius,
        background=bg or p.bg_panel,
    )


def refresh_round_clip_widgets(root) -> None:
    """Переустанавливает маску на всех виджетах с _apply_round_clip под root."""
    from PyQt6.QtWidgets import QWidget

    for widget in root.findChildren(QWidget):
        clip = getattr(widget, "_apply_round_clip", None)
        if callable(clip):
            clip()


def refresh_editor_blocks(root) -> None:
    """Обновляет стили и маску всех EditorBlockFrame под root."""
    from PyQt6.QtWidgets import QFrame

    for frame in root.findChildren(QFrame):
        name = frame.objectName()
        if not name:
            continue
        if name.endswith("Block") or name.endswith("Panel"):
            frame.setStyleSheet(block_stylesheet(name))
            clip = getattr(frame, "_apply_round_clip", None)
            if callable(clip):
                clip()
            refresh_border = getattr(frame, "refresh_border_theme", None)
            if callable(refresh_border):
                refresh_border()
    refresh_round_clip_widgets(root)


def editor_panel_stylesheet(object_name: str) -> str:
    """Панель редактора без обводки."""
    p = palette()
    return f"""
        QFrame#{object_name} {{
            background-color: {p.bg_item};
            border: none;
        }}
    """


def rounded_panel_stylesheet(object_name: str) -> str:
    """Закруглённая панель для редактора и подобных окон."""
    return f"""
        QFrame#{object_name} {{
            background: transparent;
            border: none;
        }}
    """


def invisible_splitter_style() -> str:
    """QSplitter: невидимая ручка, но область перетаскивания сохранена."""
    return """
        QSplitter::handle {
            background: transparent;
            border: none;
            margin: 0px;
            padding: 0px;
        }
        QSplitter::handle:horizontal {
            width: 8px;
        }
        QSplitter::handle:vertical {
            height: 8px;
        }
    """


def configure_editor_horizontal_splitter(
    splitter,
    *,
    left_min: int = 200,
    right_min: int = 280,
) -> None:
    """Горизонтальный сплиттер редактора: без схлопывания панелей."""
    configure_invisible_splitter(splitter)
    splitter.setCollapsible(0, False)
    splitter.setCollapsible(1, False)
    if splitter.count() >= 1:
        left = splitter.widget(0)
        if left is not None:
            left.setMinimumWidth(left_min)
    if splitter.count() >= 2:
        right = splitter.widget(1)
        if right is not None:
            right.setMinimumWidth(right_min)


def configure_invisible_splitter(splitter) -> None:
    """Настраивает QSplitter с невидимым, но рабочим разделителем."""
    from PyQt6.QtCore import Qt

    splitter.setHandleWidth(8)
    splitter.setChildrenCollapsible(False)
    splitter.setOpaqueResize(True)
    splitter.setStyleSheet(invisible_splitter_style())
    splitter.setCursor(Qt.CursorShape.ArrowCursor)


def editor_tab_content_margins() -> tuple[int, int, int, int]:
    """Отступы содержимого вкладки редактора (left, top, right, bottom)."""
    return (8, 8, 8, 12)


def apply_editor_tab_content_layout(layout) -> None:
    """Единые отступы и spacing для содержимого вкладки редактора."""
    left, top, right, bottom = editor_tab_content_margins()
    layout.setContentsMargins(left, top, right, bottom)
    layout.setSpacing(0)


def editor_search_field_style() -> str:
    p = palette()
    field_bg = p.bg_item
    return f"""
        QLineEdit, ContextLineEdit {{
            background-color: {field_bg};
            color: {p.fg_text};
            border: 1px solid {p.border};
            border-radius: {CONTROL_RADIUS}px;
            {input_field_height_qss(bordered=True)}
        }}
        QLineEdit:focus, ContextLineEdit:focus {{
            border-color: {p.accent};
            background-color: {p.bg_item};
        }}
    """


def compact_field_stylesheet(*, bordered: bool = True) -> str:
    """Поля ввода той же высоты, что поиск в редакторе (26px)."""
    p = palette()
    border = f"1px solid {p.border}" if bordered else "none"
    focus_border = f"1px solid {p.accent}" if bordered else "none"
    return f"""
        QLineEdit, ContextLineEdit {{
            background-color: {p.bg_item};
            color: {p.fg_text};
            border: {border};
            border-radius: {CONTROL_RADIUS}px;
            {input_field_height_qss(bordered=bordered)}
        }}
        QLineEdit:focus, ContextLineEdit:focus {{
            border: {focus_border};
            background-color: {p.bg_item};
        }}
        QAbstractSpinBox, ContextSpinBox, QSpinBox, QDoubleSpinBox {{
            background-color: {p.bg_item};
            color: {p.fg_text};
            border: {border};
            border-radius: {CONTROL_RADIUS}px;
            {input_field_height_qss(pad_h="6px", bordered=bordered)}
        }}
        QAbstractSpinBox:focus, ContextSpinBox:focus {{
            border: {focus_border};
        }}
        CustomComboBox {{
            height: {EDITOR_FIELD_HEIGHT}px;
            min-height: {EDITOR_FIELD_HEIGHT}px;
            max-height: {EDITOR_FIELD_HEIGHT}px;
            padding: 0px;
            margin: 0px;
            border: none;
            background: transparent;
        }}
    """


def editor_file_list_style() -> str:
    p = palette()
    return f"""
        QListWidget {{
            background-color: transparent;
            border: none;
            color: {p.fg_text};
            outline: none;
            padding: 0px;
        }}
        QListWidget::item {{
            height: 24px;
            padding: 0px 8px;
            margin: 1px 0px;
            border: none;
            border-radius: 4px;
        }}
        QListWidget::item:hover {{
            background-color: {p.hover_bg};
        }}
        QListWidget::item:selected {{
            background-color: {p.accent};
            color: #ffffff;
        }}
        QListWidget::item:selected:!active {{
            background-color: {p.hover_bg};
            color: {p.fg_text};
        }}
    """


def home_strategy_list_style() -> str:
    """Список стратегий на главной: цвета строк задаются из кода (запущена / остальные)."""
    p = palette()
    return f"""
        QListWidget {{
            background-color: transparent;
            border: none;
            color: {p.fg_text};
            outline: none;
            padding: 0px;
        }}
        QListWidget::item {{
            height: 26px;
            padding: 0px 8px;
            margin: 1px 0px;
            border: none;
            border-radius: 4px;
        }}
        QListWidget::item:hover:!selected {{
            background-color: {p.hover_bg};
        }}
        QListWidget::item:selected {{
            background-color: {p.hover_bg};
            color: {p.fg_text};
        }}
    """


def editor_surface_style() -> str:
    """Стиль текстового редактора внутри панели."""
    p = palette()
    return (
        f"QPlainTextEdit {{ background-color: {p.bg_item}; border: none; padding: 6px; }}"
    )


def apply_editor_text_widget(widget) -> None:
    """Единый фон редактора и палитра для QPlainTextEdit."""
    from PyQt6.QtGui import QPalette

    p = palette()
    widget.setStyleSheet(editor_surface_style())
    widget.setAutoFillBackground(True)
    pal = widget.palette()
    pal.setColor(QPalette.ColorRole.Base, qcolor(p.bg_item))
    widget.setPalette(pal)


def apply_home_console_text_widget(widget) -> None:
    """Консоль главного окна — фон как у блока списка (#1c1c1c в тёмной теме)."""
    apply_editor_text_widget(widget)


def test_panel_text_style() -> str:
    """Текстовая панель вкладок окна тестирования."""
    p = palette()
    return f"""
        QPlainTextEdit {{
            background-color: {p.bg_panel};
            color: {p.fg_text};
            border: none;
            padding: 4px;
        }}
    """


def apply_test_panel_text_widget(widget) -> None:
    """Стиль вывода как на вкладках окна тестирования."""
    from PyQt6.QtGui import QPalette

    p = palette()
    widget.setStyleSheet(test_panel_text_style())
    widget.setAutoFillBackground(True)
    pal = widget.palette()
    pal.setColor(QPalette.ColorRole.Base, qcolor(p.bg_panel))
    widget.setPalette(pal)


def dialog_form_stylesheet() -> str:
    """Поля ввода и группы в диалогах (создание стратегии и т.п.)."""
    p = palette()
    radius = CONTROL_RADIUS
    return f"""
        {compact_field_stylesheet(bordered=True)}
        QGroupBox {{
            color: {p.fg_text};
            border: 1px solid {p.border};
            border-radius: {radius}px;
            margin-top: 10px;
            padding-top: 8px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: {p.fg_muted};
        }}
        QLabel {{
            color: {p.fg_text};
            background: transparent;
        }}
        CustomComboBox:focus {{
            border-color: {p.accent};
        }}
    """


def editor_terminal_header_style() -> str:
    p = palette()
    return (
        f"background-color: {p.bg_item}; color: {p.fg_muted}; "
        f"font-size: 11px; padding: 4px 10px; margin: 0px; border: none;"
    )


def list_widget_style() -> str:
    """Стиль QListWidget (файлы, списки)."""
    p = palette()
    return f"""QListWidget {{
        background-color: {p.bg_panel};
        border: none;
        color: {p.fg_text};
    }}
    QListWidget::item {{ height: 20px; }}
    QListWidget::item:hover {{ background-color: {p.hover_bg}; }}
    QListWidget::item:selected {{ background-color: {p.accent}; color: #ffffff; }}"""


def nothing_found_style() -> str:
    """Стиль надписи «ничего не найдено»."""
    p = palette()
    return f"color: {p.fg_muted}; font-size: 13px;"


def panel_bg_style() -> str:
    """Фон панели."""
    p = palette()
    return f"background-color: {p.bg_panel};"


def console_style() -> str:
    """Стиль консоли — как у редактора."""
    return editor_surface_style()


def splitter_handle_style() -> str:
    """QSplitter без видимой линии (алиас для редактора и окон)."""
    return invisible_splitter_style()


def progress_bar_visible_style() -> str:
    """Видимый прогрессбар (тест, и т.п.)."""
    p = palette()
    return f"""QProgressBar {{
        background-color: {p.bg_panel};
        border: 1px solid {p.border};
        border-radius: 4px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {p.accent};
        border-radius: 4px;
    }}"""


_BASE_QSS = """
    QMainWindow {{
        background-color: {bg_window};
        color: {fg_text};
    }}
    QMainWindow::separator {{
        width: 7px;
        background: transparent;
    }}

    QLabel {{
        color: {fg_text};
    }}

    QMenuBar {{
        background-color: transparent;
        color: {fg_text};
        border: none;
    }}

    QMenuBar::item {{
        background-color: transparent;
        padding: 4px 8px;
        border-radius: {CONTROL_RADIUS}px;
        color: {fg_text};
        margin-top: 2px;
        margin-bottom: 2px;
    }}

    QMenuBar::item:selected,
    QMenuBar::item:pressed {{
        background-color: {hover_bg};
        color: {fg_text};
        border-radius: {CONTROL_RADIUS}px;
    }}

    QMenu {{
        background-color: transparent;
        border: none;
        padding: 6px 0px;
    }}

    QMenu::item {{
        padding: 6px 12px;
        color: {fg_text};
        border-radius: 3px;
        margin: 2px 6px;
    }}

    QMenu::item:selected {{
        background-color: {accent};
        border: none;
    }}

    QMenu::item:disabled {{
        color: {fg_muted};
        background-color: transparent;
    }}

    QMenu::separator {{
        height: 1px;
        background: {border};
        margin: 4px 0px;
    }}

    QMenu::indicator {{
        width: 16px;
        height: 16px;
        padding-left: 0px;
        margin-left: 0px;
    }}

    QMenu::item:has-indicator {{
        padding-left: 12px;
    }}

    QPushButton {{
        background-color: {bg_item};
        color: {fg_text};
        border: 1px solid {border};
        padding: 6px 12px;
        border-radius: {CONTROL_RADIUS}px;
        outline: none;
    }}

    QPushButton:hover {{
        background-color: {accent};
        border-color: {accent};
    }}

    QPushButton:pressed {{
        background-color: {accent_hover};
        border-color: {accent_hover};
        color: #ffffff;
    }}

    QPushButton:disabled {{
        background-color: {bg_panel};
        color: {fg_muted};
    }}

    QComboBox {{
        background-color: {bg_item};
        selection-background-color: {accent};
        color: {fg_text};
        border: 1px solid {border};
        border-radius: {CONTROL_RADIUS}px;
        height: 24px;
        min-height: 24px;
        max-height: 24px;
        padding-top: 0px;
        padding-bottom: 0px;
        padding-left: 8px;
        padding-right: 8px;
        min-width: 6em;
        outline: none;
    }}

    CustomComboBox {{
        height: 26px;
        min-height: 26px;
        max-height: 26px;
        padding: 0px;
        margin: 0px;
        border: none;
        background: transparent;
    }}

    QComboBox:hover {{
        background-color: {hover_bg};
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: right;
        width: 20px;
        border: none;
        border-top-right-radius: {CONTROL_RADIUS}px;
        border-bottom-right-radius: {CONTROL_RADIUS}px;
        background: transparent;
    }}

    QComboBox::down-arrow {{
        width: 16px;
        height: 16px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {bg_panel};
        border: 1px solid {border};
        selection-background-color: {accent};
        color: {fg_text};
    }}

    QLineEdit, ContextLineEdit {{
        background-color: {bg_item};
        color: {fg_text};
        border: 1px solid {border};
        border-radius: {CONTROL_RADIUS}px;
        height: 24px;
        min-height: 24px;
        max-height: 24px;
        padding-top: 0px;
        padding-bottom: 0px;
        padding-left: 8px;
        padding-right: 8px;
        outline: none;
    }}

    QLineEdit:focus, ContextLineEdit:focus {{
        border-color: {accent};
        background-color: {bg_item};
    }}

    QStatusBar {{
        background-color: {bg_window};
        color: {fg_text};
        border: none;
    }}

    QStatusBar QLabel {{
        color: {fg_text};
    }}

    QStatusBar::item {{
        border: none;
    }}

    QTreeView, QListView {{
        background-color: {bg_window};
        outline: none;
        color: {fg_text};
    }}

    QTreeView::item, QListView::item {{
        border: 1px solid transparent;
    }}

    QListWidget::item {{
        border: 1px solid transparent;
    }}

    QListWidget::item:alternate {{
        background-color: {bg_panel};
    }}

    QListWidget::item:hover {{
        background-color: {hover_bg};
    }}

    QListWidget::item:selected {{
        background-color: {accent};
        border: 1px solid {accent};
        color: #ffffff;
    }}

    QListWidget::item:selected:!active {{
        background-color: {bg_panel};
        color: {fg_text};
    }}

    QTreeView::branch:selected {{
        background-color: {accent};
        border: 1px solid {accent};
    }}

    QTreeView::item:selected, QListView::item:selected {{
        background-color: {accent};
        border: 1px solid {accent};
        color: #ffffff;
    }}

    QTreeView::item:hover:!selected, QListView::item:hover:!selected {{
        background-color: {bg_panel};
    }}

    QTreeView::item:!active:selected,
    QTreeView::branch:!active:selected {{
        background-color: {bg_panel};
        color: {fg_text};
    }}

    QTreeView::branch {{
        background-color: transparent;
    }}

    QSplitter::handle {{
        background: transparent;
        border: none;
        margin: 0px;
        padding: 0px;
    }}

    QSplitter::handle:horizontal {{
        width: 8px;
    }}

    QSplitter::handle:vertical {{
        height: 8px;
    }}

    QCheckBox {{
        color: {fg_text};
        spacing: 5px;
    }}

    QCheckBox::indicator {{
        width: 13px;
        height: 13px;
        border-radius: 3px;
        border: 1px solid {border};
        background-color: {bg_item};
    }}

    QRadioButton {{
        color: {fg_text};
        spacing: 5px;
    }}

    QRadioButton::indicator {{
        width: 13px;
        height: 13px;
        border: 1px solid {border};
        border-radius: 7px;
        background-color: {bg_item};
    }}

    QRadioButton::indicator:checked {{
        background-color: {accent};
        border: 1px solid {border};
        border-radius: 7px;
        width: 13px;
        height: 13px;
    }}

    QGroupBox {{
        border: 1px solid {border};
        border-radius: {CONTROL_RADIUS}px;
        margin-top: 10px;
        padding-top: 10px;
        color: {fg_text};
        background-color: transparent;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 3px;
        color: {fg_text};
    }}

    QTableView, QTableWidget {{
        background-color: {bg_panel};
        alternate-background-color: {bg_panel};
        color: {fg_text};
        gridline-color: {border};
        border: 1px solid {border};
        border-radius: 0px;
        selection-background-color: {accent};
        selection-color: #ffffff;
        outline: none;
    }}

    QTableView::item {{
        padding: 4px;
        border: none;
    }}

    QTableView::item:selected {{
        background-color: {accent};
        color: #ffffff;
    }}

    QTableView::item:hover:!selected {{
        background-color: {hover_bg};
    }}

    QHeaderView {{
        background-color: {bg_panel};
        color: {fg_text};
    }}

    QHeaderView::section {{
        background-color: {bg_panel};
        color: {fg_text};
        padding: 4px;
        border: none;
    }}

    QHeaderView::section:checked {{
        background-color: {accent};
        color: #ffffff;
    }}

    QHeaderView::section:hover {{
        background-color: {hover_bg};
    }}

    QTabWidget {{
        background-color: transparent;
        border: none;
    }}

    QTabWidget::pane {{
        background-color: {bg_panel};
        border: 1px solid {border};
        border-radius: 8px;
        margin-top: 10px;
        padding: 4px;
        top: -1px;
    }}

    QTabBar::scroller,
    QTabBar::scroller::left-arrow,
    QTabBar::scroller::right-arrow {{
        background-color: {border};
    }}

    QTabBar::tab {{
        background-color: {bg_window};
        color: {fg_muted};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 7px 12px;
        min-width: 80px;
        max-width: 200px;
        margin-right: 4px;
        margin-bottom: 2px;
    }}

    QTabBar::tab:selected {{
        background-color: {bg_panel};
        color: {fg_text};
        border: 1px solid {accent};
    }}
    
    QTabBar::tab:hover:!selected {{
        background-color: {hover_bg};
        color: {fg_text};
    }}
    
    QTabBar::close-button {{
        image: url({close_icon});
        subcontrol-position: right;       
    }}
    
    QTabBar::close-button:hover {{
        background-color: {hover_bg};
        width:20px;
        height:20px;
        border-radius: {CONTROL_RADIUS}px;
    }}

    QDialog {{
        background-color: {bg_window};
        color: {fg_text};
    }}
    
    QTextEdit, QPlainTextEdit {{
        background-color: {bg_item};
        color: {fg_text};
        border: 1px solid {border};
        border-radius: {CONTROL_RADIUS}px;
        padding: 6px;
        outline: none;
    }}

    QSpinBox, QDoubleSpinBox, ContextSpinBox {{
        background-color: {bg_item};
        color: {fg_text};
        border: 1px solid {border};
        border-radius: {CONTROL_RADIUS}px;
        height: 24px;
        min-height: 24px;
        max-height: 24px;
        padding-top: 0px;
        padding-bottom: 0px;
        padding-left: 6px;
        padding-right: 6px;
    }}

    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {accent};
        background-color: {bg_item};
    }}

    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        background-color: transparent;
        border-left: 1px solid {border};
    }}

    QProgressBar {{
        background-color: transparent;
        border: none;
        height: 2px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {accent};
        border: none;
        border-radius: 0px;
    }}

    /* Indeterminate progress bar (infinite animation) */
    QProgressBar[indeterminate="true"] {{
        background-color: {accent_subtle};
    }}

    QProgressBar[indeterminate="true"]::chunk {{
        background-color: {accent};
        border: none;
        border-radius: 0px;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 2px;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background-color: {scrollbar_handle};
        border-radius: 3px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {scrollbar_track};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
        border: none;
        background: none;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 6px;
        margin: 2px;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {scrollbar_handle};
        border-radius: 3px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {scrollbar_track};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
        border: none;
        background: none;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}
"""


def _close_icon_url() -> str:
    """Путь/data-url к иконке закрытия вкладки (codicons)."""
    try:
        from src.shared.ui.assets.codicons_manager import get_icon_path
        from src.shared.ui.assets.embedded_assets import get_svg_data_url

        path = get_icon_path("close")
        if path:
            return path.replace("\\", "/")
        data_url = get_svg_data_url("close")
        if data_url:
            return data_url
    except Exception:
        pass
    from src.shared.lib.path_utils import get_resource_path

    subdir = "light" if is_light() else "dark"
    path = get_resource_path(f"resources/assets/{subdir}/close.svg")
    return path.replace("\\", "/")


def app_stylesheet() -> str:
    """Возвращает полный stylesheet приложения для текущей темы.

    Один QSS-шаблон заполняется цветами из текущей палитры.
    """
    p = palette()
    return _BASE_QSS.format(
        bg_window=p.bg_window,
        bg_panel=p.bg_panel,
        bg_item=p.bg_item,
        fg_text=p.fg_text,
        fg_muted=p.fg_muted,
        accent=p.accent,
        accent_hover=p.accent_hover,
        accent_subtle=p.accent_subtle,
        border=p.border,
        hover_bg=p.hover_bg,
        scrollbar_handle=p.scrollbar_handle,
        scrollbar_track=p.scrollbar_track,
        close_icon=_close_icon_url(),
        CONTROL_RADIUS=CONTROL_RADIUS,
        PANEL_RADIUS=PANEL_RADIUS,
        TAB_RADIUS=TAB_RADIUS,
    )


def apply_application_theme(app=None) -> None:
    """Применяет текущую тему ко всему приложению и обновляет окна с кастомными стилями."""
    from PyQt6.QtWidgets import QApplication

    if app is None:
        app = QApplication.instance()
    if app is None:
        return

    app.setStyleSheet(app_stylesheet())

    style = app.style()
    if hasattr(style, "reload_icons"):
        style.reload_icons()

    seen: set[int] = set()
    for widget in app.allWidgets():
        wid = id(widget)
        if wid in seen:
            continue
        seen.add(wid)
        for method_name in ("refresh_theme", "apply_theme", "_apply_theme_colors"):
            method = getattr(widget, method_name, None)
            if callable(method):
                try:
                    method()
                except Exception:
                    pass
                break

    try:
        from src.shared.ui.window_styles import apply_native_window

        for window in app.topLevelWidgets():
            if window.isWindow() and window.isVisible():
                apply_native_window(window)
                window._native_style_done = True
    except Exception:
        pass

