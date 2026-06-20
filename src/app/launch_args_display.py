"""Виджет справки CLI с подсветкой синтаксиса."""
from __future__ import annotations

from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from src.app.launch_registry import format_launch_reference_text
from src.features.editor.lib.line_number_editor import LineNumberPlainTextEdit
from src.shared.ui import theme


def _fmt(color: str, *, bold: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(theme.qcolor(color))
    if bold:
        fmt.setFontWeight(700)
    return fmt


class LaunchArgsHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        self._re_comment = QRegularExpression(r"^#.*$")
        self._re_example = QRegularExpression(
            r"^(ZapretDesktop\.exe|python\s+ZapretDesktop\.py)( .*)?$"
        )
        self._re_row = QRegularExpression(
            r"^(-[A-Za-z])\s+(--[a-z-]+)\s+(.*)$"
        )
        super().__init__(parent)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        sp = theme.syntax_palette()
        self._fmt_comment = _fmt(sp.comment)
        self._fmt_example = _fmt(sp.type_token, bold=True)
        self._fmt_short = _fmt(sp.keyword, bold=True)
        self._fmt_long = _fmt(sp.option)
        self._fmt_desc = _fmt(theme.palette().fg_muted)
        self._fmt_cmd = _fmt(sp.section, bold=True)
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        if self._re_comment.match(text).hasMatch():
            self.setFormat(0, len(text), self._fmt_comment)
            return

        ex = self._re_example.match(text)
        if ex.hasMatch():
            cmd = ex.captured(1) or ""
            args = ex.captured(2) or ""
            self.setFormat(0, len(cmd), self._fmt_cmd)
            if args:
                pos = len(cmd)
                for part in args.split():
                    if part.startswith("-"):
                        fmt = self._fmt_short if len(part) <= 2 else self._fmt_long
                        self.setFormat(pos + 1, len(part), fmt)
                    pos = text.find(part, pos) + len(part)
            return

        row = self._re_row.match(text)
        if row.hasMatch():
            short = row.captured(1)
            long_flag = row.captured(2)
            desc = row.captured(3)
            pos = 0
            if short:
                self.setFormat(pos, len(short), self._fmt_short)
                pos += len(short)
            gap = text.find(long_flag, pos)
            if gap > pos:
                pos = gap
            self.setFormat(pos, len(long_flag), self._fmt_long)
            pos += len(long_flag)
            if desc:
                self.setFormat(pos, len(desc), self._fmt_desc)
            return


class LaunchArgsReferenceWidget(QWidget):
    def __init__(self, lang: str = "ru", parent=None):
        super().__init__(parent)
        self._lang = lang
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.editor = LineNumberPlainTextEdit(self)
        self.editor.setReadOnly(True)
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        if hasattr(self.editor, "set_highlight_current_line_enabled"):
            self.editor.set_highlight_current_line_enabled(False)
        theme.apply_home_console_text_widget(self.editor)
        self._highlighter = LaunchArgsHighlighter(self.editor.document())
        layout.addWidget(self.editor, 1)
        self.set_content(lang)

    def set_content(self, lang: str | None = None) -> None:
        if lang is not None:
            self._lang = lang
        self.editor.setPlainText(format_launch_reference_text(self._lang))

    def refresh_theme(self) -> None:
        theme.apply_home_console_text_widget(self.editor)
        self._highlighter.refresh_theme()
