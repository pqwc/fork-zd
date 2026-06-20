"""UI прогресса обновления: модальное окно (ручной режим) или inline (авто)."""
from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from src.features.updates.ui.vs_update_dialog import VSUpdateDialog
from src.shared.ui import theme


class DialogUpdateProgress:
    """Прогресс через VSUpdateDialog — для ручного обновления из меню."""

    def __init__(self, parent, language: str = "ru"):
        self._dlg = VSUpdateDialog(parent, language)

    def set_status(self, text: str, show_details: bool = False) -> None:
        self._dlg.set_status(text, show_details)

    def add_detail(self, text: str) -> None:
        self._dlg.add_detail(text)

    def set_progress(self, value: float) -> None:
        self._dlg.set_progress(value)

    def set_indeterminate(self, indeterminate: bool = True) -> None:
        self._dlg.set_indeterminate(indeterminate)

    def show_cancel(self, show: bool = True) -> None:
        self._dlg.show_cancel(show)

    def show(self) -> None:
        self._dlg.show()
        QApplication.processEvents()

    def close(self) -> None:
        self._dlg.close()

    def is_cancelled(self) -> bool:
        return self._dlg.is_cancelled()


class InlineUpdateProgress:
    """Ненавязчивый прогресс: полоска под меню + текст в футере главного окна."""

    def __init__(self, main_window):
        self._win = main_window
        self._cancelled = False
        self._status = ""

    def set_status(self, text: str, show_details: bool = False) -> None:
        self._status = text
        self._set_footer(text)

    def add_detail(self, text: str) -> None:
        self._set_footer(text)

    def set_progress(self, value: float) -> None:
        bar = getattr(self._win, "menu_progress_bar", None)
        if bar is not None:
            if hasattr(bar, "setProgressHidden"):
                bar.setProgressHidden(False)
            bar.setIndeterminate(False)
            bar.setMaximum(100)
            bar.setValue(int(value))
        label = self._status or ""
        if value >= 0:
            self._set_footer(f"{label} {int(value)}%".strip())

    def set_indeterminate(self, indeterminate: bool = True) -> None:
        bar = getattr(self._win, "menu_progress_bar", None)
        if bar is not None and hasattr(bar, "setIndeterminate"):
            bar.setIndeterminate(indeterminate)

    def show_cancel(self, show: bool = True) -> None:
        pass

    def show(self) -> None:
        if hasattr(self._win, "_show_menu_progress_bar"):
            self._win._show_menu_progress_bar()

    def close(self) -> None:
        if hasattr(self._win, "_hide_menu_progress_bar"):
            self._win._hide_menu_progress_bar()

    def is_cancelled(self) -> bool:
        return self._cancelled

    def _set_footer(self, text: str) -> None:
        footer = getattr(self._win, "footer_label", None)
        if footer is None:
            return
        p = theme.palette()
        footer.setText(
            f'<span style="color:{p.accent};">{text}</span>'
        )


def create_update_progress(main_window, *, auto: bool, language: str = "ru"):
    if auto:
        return InlineUpdateProgress(main_window)
    return DialogUpdateProgress(main_window, language)
