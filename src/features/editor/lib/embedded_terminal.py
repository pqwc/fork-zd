"""Встроенный терминал редактора стратегий (cmd на Windows, bash на Linux)."""
from __future__ import annotations

import locale
import os
import sys
from dataclasses import dataclass

from PyQt6.QtCore import QProcess, QProcessEnvironment, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent, QTextCursor
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from src.features.editor.lib.line_number_editor import LineNumberPlainTextEdit
from src.shared.i18n.translator import tr
from src.shared.lib.process_utils import terminate_process_tree
from src.shared.ui import theme


@dataclass(frozen=True)
class TerminalProfile:
    name: str
    program: str
    arguments: list[str]
    encoding: str
    eol: bytes
    prompt_suffix: str
    chain_separator: str
    supports_color_cmd: bool
    supports_title_cmd: bool


def build_terminal_profile() -> TerminalProfile:
    if sys.platform == "win32":
        return TerminalProfile(
            name="cmd",
            program="cmd.exe",
            arguments=["/Q", "/K", "chcp 1251>nul"],
            encoding="cp1251",
            eol=b"\r\n",
            prompt_suffix="> ",
            chain_separator="&",
            supports_color_cmd=True,
            supports_title_cmd=True,
        )
    encoding = locale.getpreferredencoding(False) or "utf-8"
    return TerminalProfile(
        name="bash",
        program="/bin/bash" if os.path.isfile("/bin/bash") else "bash",
        arguments=["--noprofile", "--norc", "-i"],
        encoding=encoding,
        eol=b"\n",
        prompt_suffix="$ ",
        chain_separator=";",
        supports_color_cmd=False,
        supports_title_cmd=False,
    )


class TerminalConsoleEdit(LineNumberPlainTextEdit):
    """Консоль терминала: без контекстного меню, ПКМ = вставка."""

    def __init__(self, controller: "EmbeddedTerminal", parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            if self.textCursor().hasSelection():
                self.copy()
            else:
                self.paste()
            return
        super().mouseReleaseEvent(event)

    def paste(self):
        from PyQt6.QtWidgets import QApplication

        text = QApplication.clipboard().text()
        if not text:
            return
        start = self._controller.input_start
        cursor = self.textCursor()
        pos = max(cursor.position(), start)
        cursor.setPosition(pos)
        cursor.insertText(text)
        self.setTextCursor(cursor)


class EmbeddedTerminal(QWidget):
    """Панель встроенного терминала с QProcess."""

    output_appended = pyqtSignal()

    _CMD_COLORS = {
        "0": "#0c0c0c",
        "1": "#0037da",
        "2": "#13a10e",
        "3": "#3a96dd",
        "4": "#c50f1f",
        "5": "#881798",
        "6": "#c19c00",
        "7": "#cccccc",
        "8": "#767676",
        "9": "#3b78ff",
        "a": "#16c60c",
        "b": "#61d6d6",
        "c": "#e74856",
        "d": "#b4009e",
        "e": "#f9f1a5",
        "f": "#f2f2f2",
    }

    def __init__(
        self,
        parent=None,
        *,
        working_directory: str,
        language: str = "ru",
        register_pid=None,
    ):
        super().__init__(parent)
        self.language = language
        self.cwd = working_directory or ""
        self.profile = build_terminal_profile()
        self._title = self.profile.name
        self._register_pid_cb = register_pid
        self.input_start = 0
        self._cursor_fixing = False

        self._process = QProcess(self)
        self._setup_process()

        self._header = QLabel(tr("editor_terminal_header", self.language).format(self._title))
        self._header.setStyleSheet(theme.editor_terminal_header_style())

        self.console = TerminalConsoleEdit(self, self)
        self.console.setFrameShape(QFrame.Shape.NoFrame)
        self.console.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        theme.apply_editor_text_widget(self.console)
        if hasattr(self.console, "set_highlight_current_line_enabled"):
            self.console.set_highlight_current_line_enabled(False)
        self.console.setFont(QFont("Consolas", 9))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self.console, 1)

        bottom_pad = QWidget()
        bottom_pad.setFixedHeight(8)
        p = theme.palette()
        bottom_pad.setStyleSheet(f"background-color: {p.bg_item};")
        layout.addWidget(bottom_pad)

        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.readyReadStandardError.connect(self._on_output)
        self._process.started.connect(self._on_started)

    def _setup_process(self) -> None:
        env = QProcessEnvironment.systemEnvironment()
        if sys.platform != "win32":
            env.insert("PS1", "$ ")
            env.insert("PS2", "> ")
            env.insert("TERM", "dumb")
        self._process.setProcessEnvironment(env)
        self._process.setProgram(self.profile.program)
        self._process.setArguments(self.profile.arguments)
        if os.path.isdir(self.cwd):
            self._process.setWorkingDirectory(self.cwd)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

    def start(self) -> None:
        if self._process.state() == QProcess.ProcessState.Running:
            return
        self._process.start()

    def stop(self) -> None:
        pid = int(self._process.processId()) if self._process.state() != QProcess.ProcessState.NotRunning else 0
        try:
            if self._process.state() != QProcess.ProcessState.NotRunning:
                self._process.kill()
                self._process.waitForFinished(2000)
        except Exception:
            pass
        if pid > 0:
            terminate_process_tree(pid)

    def restart(self) -> None:
        self.stop()
        self.console.appendPlainText("\n^C\n")
        self.input_start = self.console.document().characterCount() - 1
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.start()

    def refresh_theme(self) -> None:
        self._header.setStyleSheet(theme.editor_terminal_header_style())
        if not getattr(self.console, "_line_number_bg_override", None):
            theme.apply_editor_text_widget(self.console)
        self.console.refresh_editor_colors()

    def update_title_label(self) -> None:
        self._header.setText(tr("editor_terminal_header", self.language).format(self._title or self.profile.name))

    def append_prompt(self) -> None:
        if sys.platform == "win32":
            folder = self.cwd or ""
            prompt = f"{folder}> " if folder else "> "
        else:
            short = os.path.basename(self.cwd.rstrip("/")) or self.cwd or "~"
            prompt = f"{short}{self.profile.prompt_suffix}"
        self.console.insertPlainText(prompt)
        self.input_start = self.console.document().characterCount() - len(prompt)
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    def clear_screen(self) -> None:
        if sys.platform == "win32":
            folder = self.cwd or ""
            prompt = f"{folder}> " if folder else "> "
        else:
            short = os.path.basename(self.cwd.rstrip("/")) or self.cwd or "~"
            prompt = f"{short}{self.profile.prompt_suffix}"
        self.console.clear()
        self.console.setPlainText(prompt)
        self.input_start = len(prompt)
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    def run_command(self, cmd_text: str, *, allow_empty: bool = False) -> None:
        cmd_text = cmd_text.strip()
        if not allow_empty and not cmd_text:
            return
        if self._process.state() != QProcess.ProcessState.Running:
            self.start()
        if self._process.state() == QProcess.ProcessState.Running:
            payload = (cmd_text if cmd_text else "") + self.profile.eol.decode()
            self._process.write(payload.encode(self.profile.encoding, errors="ignore"))

    def handle_key_press(self, event: QKeyEvent) -> bool:
        key = event.key()
        mods = event.modifiers()
        cursor = self.console.textCursor()

        if self.input_start > cursor.document().characterCount():
            self.input_start = cursor.document().characterCount()

        ctrl = Qt.KeyboardModifier.ControlModifier
        if mods == ctrl and self._process.state() == QProcess.ProcessState.Running:
            if key in (Qt.Key.Key_C, Qt.Key.Key_Pause, Qt.Key.Key_Cancel):
                self.restart()
                return True
            ctrl_map = {
                Qt.Key.Key_D: b"\x04",
                Qt.Key.Key_Z: b"\x1a",
                Qt.Key.Key_L: b"\x0c",
            }
            if key in ctrl_map:
                self._process.write(ctrl_map[key])
                return True

        if key == Qt.Key.Key_A and mods == ctrl:
            return True

        if key == Qt.Key.Key_Backspace and cursor.hasSelection():
            return True
        if key == Qt.Key.Key_Backspace and not cursor.hasSelection() and cursor.position() <= self.input_start:
            return True

        if key in (Qt.Key.Key_Left, Qt.Key.Key_Home) and cursor.position() <= self.input_start:
            return True

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            doc = self.console.document()
            full_text = doc.toPlainText()
            cmd = "" if self.input_start >= len(full_text) else full_text[self.input_start:].replace("\u2029", "\n").strip()

            self.console.appendPlainText("")
            self.console.moveCursor(QTextCursor.MoveOperation.End)
            self.input_start = self.console.document().characterCount() - 1

            parts = self._split_command_chain(cmd)
            handled_all = True
            for part in parts:
                if self._handle_builtin_command(part):
                    continue
                self.run_command(part, allow_empty=True)
                handled_all = False

            if handled_all:
                self.append_prompt()
            return True

        if cursor.position() < self.input_start:
            cursor.setPosition(self.input_start)
            self.console.setTextCursor(cursor)
        return False

    def on_cursor_changed(self) -> None:
        if self._cursor_fixing:
            return
        cursor = self.console.textCursor()
        doc = self.console.document()
        if self.input_start > doc.characterCount():
            self.input_start = max(0, doc.characterCount() - 1)
        if cursor.hasSelection():
            return
        if cursor.position() < self.input_start:
            self._cursor_fixing = True
            try:
                cursor.setPosition(self.input_start)
                self.console.setTextCursor(cursor)
            finally:
                self._cursor_fixing = False

    def _split_command_chain(self, raw_cmd: str) -> list[str]:
        if not raw_cmd.strip():
            return [""]
        if sys.platform == "win32":
            parts: list[str] = []
            buf: list[str] = []
            escape = False
            for ch in raw_cmd:
                if escape:
                    buf.append(ch)
                    escape = False
                    continue
                if ch == "^":
                    escape = True
                    continue
                if ch == "&":
                    part = "".join(buf).strip()
                    if part:
                        parts.append(part)
                    buf = []
                else:
                    buf.append(ch)
            last = "".join(buf).strip()
            if last:
                parts.append(last)
            return parts or [""]

        sep = self.profile.chain_separator
        return [p.strip() for p in raw_cmd.split(sep) if p.strip()] or [""]

    def _handle_builtin_command(self, part: str) -> bool:
        pl = part.lower()
        if pl in ("cls", "clear"):
            self.clear_screen()
            return True
        if self.profile.supports_color_cmd and pl.startswith("color "):
            attr = pl[6:].strip().replace(" ", "")
            if len(attr) >= 2:
                bg_c = self._CMD_COLORS.get(attr[0])
                fg_c = self._CMD_COLORS.get(attr[1])
                if bg_c and fg_c:
                    self.console.setStyleSheet(f"background-color: {bg_c}; color: {fg_c}; border: none;")
                    if hasattr(self.console, "_line_number_bg_override"):
                        self.console._line_number_bg_override = bg_c
                    if hasattr(self.console, "refresh_line_number_area"):
                        self.console.refresh_line_number_area()
                    return True
        if self.profile.supports_title_cmd and pl.startswith("title "):
            self._title = part[6:].strip() or self.profile.name
            self.update_title_label()
            return True
        return False

    def _on_started(self) -> None:
        pid = int(self._process.processId())
        if pid > 0 and self._register_pid_cb:
            self._register_pid_cb(pid)

    def _on_output(self) -> None:
        data = bytes(self._process.readAllStandardOutput())
        if not data:
            data = bytes(self._process.readAllStandardError())
        if not data:
            return
        text = data.decode(self.profile.encoding, errors="ignore")
        if not text:
            return
        self.console.insertPlainText(text)
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.input_start = self.console.document().characterCount() - 1
        self.output_appended.emit()
