"""
Нативное оформление окон Windows.

Правила:
- Qt window flags задаются один раз в __init__, до show().
- DWM (dark/light/цвет) — только после show(), через apply_native_window().
- set_caption_buttons — только для QMessageBox.
"""

from __future__ import annotations

import sys
from typing import Any

from src.shared.ui import native_window_styles


def _is_windows() -> bool:
    return sys.platform == "win32"


def _is_win11() -> bool:
    if not _is_windows():
        return False
    ver = sys.getwindowsversion()  # type: ignore[attr-defined]
    return ver.major >= 10 and ver.build >= 22000


def dialog_window_flags(*, resizable: bool = True):
    """Флаги QDialog — один раз до show()."""
    from PyQt6.QtCore import Qt

    flags = (
        Qt.WindowType.Dialog
        | Qt.WindowType.WindowTitleHint
        | Qt.WindowType.WindowCloseButtonHint
    )
    if resizable:
        flags |= (
            Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )
    return flags


def main_window_flags():
    """Флаги главного окна."""
    from PyQt6.QtCore import Qt

    return (
        Qt.WindowType.Window
        | Qt.WindowType.WindowTitleHint
        | Qt.WindowType.WindowMinimizeButtonHint
        | Qt.WindowType.WindowMaximizeButtonHint
        | Qt.WindowType.WindowCloseButtonHint
    )


def message_box_window_flags():
    """Флаги QMessageBox — только закрытие."""
    from PyQt6.QtCore import Qt

    return (
        Qt.WindowType.Dialog
        | Qt.WindowType.WindowTitleHint
        | Qt.WindowType.WindowCloseButtonHint
    )


def apply_window_style(window: Any) -> None:
    """DWM: dark/light и цвет заголовка (Win11)."""
    if not _is_windows():
        return

    header_color = "#141414"
    style_name = "dark"
    try:
        from src.shared.ui import theme

        header_color = theme.palette().bg_window
        style_name = "light" if theme.is_light() else "dark"
    except Exception:
        pass

    if _is_win11():
        try:
            native_window_styles.change_header_color(window, header_color)
        except Exception:
            pass

    try:
        native_window_styles.apply_style(window, style_name)
    except Exception:
        pass


def apply_native_window(
    window: Any,
    *,
    caption_buttons: bool = False,
    minimize: bool = True,
    maximize: bool = True,
    close: bool = True,
) -> None:
    """Применяет DWM-стили к уже показанному окну (вызывать из showEvent)."""
    if window is None:
        return
    try:
        if window.windowHandle() is None:
            return
    except Exception:
        return

    apply_window_style(window)

    if caption_buttons:
        native_window_styles.set_caption_buttons(
            window,
            minimize=minimize,
            maximize=maximize,
            close=close,
        )


def schedule_native_style(
    window: Any,
    *,
    caption_buttons: bool = False,
    minimize: bool = True,
    maximize: bool = True,
    close: bool = True,
    force: bool = False,
) -> None:
    """Отложенное применение (legacy). Предпочитайте apply_native_window в showEvent."""
    if window is None:
        return
    if not force and getattr(window, "_native_style_done", False):
        return

    from PyQt6.QtCore import QTimer

    def _apply() -> None:
        apply_native_window(
            window,
            caption_buttons=caption_buttons,
            minimize=minimize,
            maximize=maximize,
            close=close,
        )
        window._native_style_done = True

    QTimer.singleShot(0, _apply)
