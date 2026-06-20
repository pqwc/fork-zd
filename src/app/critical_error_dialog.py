"""Окно критической ошибки в стиле редактора (traceback + подсветка)."""
from __future__ import annotations

import os
import sys
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout

from src.shared.ui.assets.embedded_assets import get_app_icon
from src.shared.i18n.translator import tr
from src.features.editor.lib.editor_highlighters import TracebackHighlighter
from src.features.editor.lib.line_number_editor import LineNumberPlainTextEdit
from src.shared.ui import theme
from src.shared.ui.standard_dialog import StandardDialog


class CriticalErrorDialog(StandardDialog):
    def __init__(
        self,
        parent=None,
        *,
        lang: str = "ru",
        summary: str = "",
        traceback_text: str = "",
    ):
        self.lang = lang
        self._summary = summary or ""
        self._traceback_text = traceback_text or ""
        super().__init__(
            parent=parent,
            title=tr("crash_dialog_title", lang),
            width=820,
            height=520,
            icon=get_app_icon(),
            resizable=True,
        )
        self._build_ui()
        self._fill_content()

    def _build_ui(self) -> None:
        layout = self.getContentLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        hint = QLabel(tr("crash_dialog_hint", self.lang))
        hint.setWordWrap(True)
        hint.setStyleSheet(theme.small_muted_label_style())
        self._hint_label = hint
        layout.addWidget(hint)

        summary_label = QLabel(self._summary)
        summary_label.setWordWrap(True)
        summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        p = theme.palette()
        err_color = "#c42b2b" if theme.is_light() else "#ff6b6b"
        summary_label.setStyleSheet(
            f"color: {err_color}; font-weight: 600; font-size: 11pt; padding: 2px 0;"
        )
        layout.addWidget(summary_label)

        self.trace_editor = LineNumberPlainTextEdit()
        self.trace_editor.setReadOnly(True)
        self.trace_editor.setFont(QFont("Consolas", 10))
        theme.apply_test_panel_text_widget(self.trace_editor)
        self._highlighter = TracebackHighlighter(self.trace_editor.document())

        editor_panel = theme.wrap_tab_page_content(self.trace_editor)
        layout.addWidget(editor_panel, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)

        self.copy_btn = QPushButton(tr("crash_btn_copy", self.lang))
        self.copy_btn.clicked.connect(self._copy_report)
        self.save_btn = QPushButton(tr("crash_btn_save", self.lang))
        self.save_btn.clicked.connect(self._save_report)
        self.close_btn = QPushButton(tr("crash_btn_close", self.lang))
        self.close_btn.setDefault(True)
        self.close_btn.clicked.connect(self.accept)

        for btn in (self.copy_btn, self.save_btn, self.close_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            buttons.addWidget(btn)

        layout.addLayout(buttons)

    def _full_report_text(self) -> str:
        lines = [
            tr("crash_dialog_title", self.lang),
            "=" * 60,
            f"{self._summary}",
            "",
            self._traceback_text.strip(),
            "",
            f"Python: {sys.version}",
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        return "\n".join(lines)

    def _fill_content(self) -> None:
        body = self._traceback_text.strip()
        if body:
            self.trace_editor.setPlainText(body)
        else:
            self.trace_editor.setPlainText(self._summary)
        cursor = self.trace_editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self.trace_editor.setTextCursor(cursor)

    def _copy_report(self) -> None:
        QGuiApplication.clipboard().setText(self._full_report_text())
        QMessageBox.information(
            self,
            tr("crash_dialog_title", self.lang),
            tr("crash_copied", self.lang),
        )

    def _save_report(self) -> None:
        from PyQt6.QtWidgets import QFileDialog

        default_name = f"ZapretDesktop_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("crash_btn_save", self.lang),
            default_name,
            "Text (*.txt);;All files (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._full_report_text())
            QMessageBox.information(
                self,
                tr("crash_dialog_title", self.lang),
                tr("crash_saved", self.lang).format(os.path.abspath(path)),
            )
        except OSError as e:
            QMessageBox.warning(
                self,
                tr("crash_dialog_title", self.lang),
                tr("crash_save_failed", self.lang).format(str(e)),
            )

    def refresh_theme(self):
        if hasattr(self, "_hint_label"):
            self._hint_label.setStyleSheet(theme.small_muted_label_style())
        if hasattr(self, "trace_editor"):
            theme.apply_test_panel_text_widget(self.trace_editor)
            if hasattr(self, "_highlighter") and hasattr(self._highlighter, "refresh_theme"):
                self._highlighter.refresh_theme()
            self.trace_editor.refresh_editor_colors()
