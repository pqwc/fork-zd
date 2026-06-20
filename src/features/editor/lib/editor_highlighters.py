"""
Подсветка синтаксиса для вкладок редактора: списки, drivers\\etc, .bat
"""

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt6.QtCore import QRegularExpression

from src.shared.ui import theme


def _format(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class _ThemedHighlighter(QSyntaxHighlighter):
    """Базовый highlighter с обновлением цветов при смене темы."""

    def refresh_theme(self) -> None:
        self._build_rules()
        self.rehighlight()

    def _build_rules(self) -> None:
        raise NotImplementedError


class ListHighlighter(_ThemedHighlighter):
    """Подсветка для списков (list-*.txt, ipset-*.txt): комментарии #."""

    def __init__(self, parent=None):
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        super().__init__(parent)
        self._build_rules()

    def _build_rules(self) -> None:
        sp = theme.syntax_palette()
        self._rules = [
            (QRegularExpression("#[^\n]*"), _format(sp.comment)),
        ]

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


class TargetsTxtHighlighter(_ThemedHighlighter):
    """Подсветка targets.txt: секции, комментарии, KeyName = \"value\"."""

    def __init__(self, parent=None):
        self._fmt_comment = QTextCharFormat()
        self._fmt_section = QTextCharFormat()
        self._fmt_key = QTextCharFormat()
        self._fmt_eq = QTextCharFormat()
        self._fmt_value = QTextCharFormat()
        self._re_section = QRegularExpression(r"^\s*###[^\n]*")
        self._re_comment = QRegularExpression(r"#.*$")
        self._re_assign = QRegularExpression(
            r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(\"[^\"]*\")(\s*)$"
        )
        super().__init__(parent)
        self._build_rules()

    def _build_rules(self) -> None:
        sp = theme.syntax_palette()
        self._fmt_comment = _format(sp.comment, italic=True)
        self._fmt_section = _format(sp.section, bold=True)
        self._fmt_key = _format(sp.identifier)
        self._fmt_eq = _format(sp.operator)
        self._fmt_value = _format(sp.string)

    def highlightBlock(self, text: str) -> None:
        if self._re_section.match(text).hasMatch():
            self.setFormat(0, len(text), self._fmt_section)
            return

        assign = self._re_assign.match(text)
        if assign.hasMatch():
            lead = assign.captured(1)
            if lead:
                self.setFormat(0, len(lead), self._fmt_comment)
            key_start = assign.capturedStart(2)
            self.setFormat(key_start, assign.capturedLength(2), self._fmt_key)
            eq_start = assign.capturedStart(3)
            self.setFormat(eq_start, assign.capturedLength(3), self._fmt_eq)
            val_start = assign.capturedStart(4)
            self.setFormat(val_start, assign.capturedLength(4), self._fmt_value)
            trail = assign.captured(5)
            if trail:
                self.setFormat(assign.capturedStart(5), len(trail), self._fmt_comment)
            return

        comment = self._re_comment.match(text)
        if comment.hasMatch():
            self.setFormat(comment.capturedStart(), comment.capturedLength(), self._fmt_comment)


class EtcHighlighter(_ThemedHighlighter):
    """Подсветка для hosts, lmhosts и т.д.: комментарии #, IP-адреса."""

    def __init__(self, parent=None):
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        super().__init__(parent)
        self._build_rules()

    def _build_rules(self) -> None:
        sp = theme.syntax_palette()
        self._rules = [
            (QRegularExpression("#[^\n]*"), _format(sp.comment)),
            (
                QRegularExpression(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
                _format(sp.type_token),
            ),
        ]

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


class BatHighlighter(_ThemedHighlighter):
    """Подсветка для .bat: комментарии, ключевые слова, строки, переменные, числа, метки."""

    def __init__(self, parent=None):
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        super().__init__(parent)
        self._build_rules()

    def _build_rules(self) -> None:
        sp = theme.syntax_palette()
        self._rules = []

        fmt_string = _format(sp.string)
        self._rules.append((QRegularExpression(r'"[^"]*"'), fmt_string))
        self._rules.append((QRegularExpression(r"'[^']*'"), fmt_string))

        fmt_keyword = _format(sp.keyword)
        keywords = [
            r"\becho\b", r"\bset\b", r"\bif\b", r"\belse\b", r"\bgoto\b", r"\bcall\b",
            r"\bcd\b", r"\bcls\b", r"\bexit\b", r"\bfor\b", r"\bin\b", r"\bdo\b",
            r"\bstart\b", r"\bendlocal\b", r"\bsetlocal\b", r"\bpushd\b", r"\bpopd\b",
            r"\bshift\b", r"\bpause\b", r"\bbreak\b", r"\bnot\b", r"\bdefined\b",
            r"\bexist\b", r"\berrorlevel\b", r"\bcmd\b", r"\bchoice\b",
            r"\bchcp\b", r"\btimeout\b", r"\btype\b", r"\bcopy\b", r"\bdel\b",
            r"\bmove\b", r"\brename\b", r"\bxcopy\b", r"\bfind\b", r"\bfindstr\b",
            r"\bnetsh\b", r"\bpowershell\b", r"\btaskkill\b", r"\btasklist\b",
            r"\bipconfig\b", r"\bping\b", r"\bsc\b", r"\bschtasks\b", r"\breg\b",
            r"\battrib\b", r"\bmkdir\b", r"\brmdir\b", r"\bdir\b", r"\bmd\b", r"\brd\b",
            r"\bcolor\b", r"\btitle\b", r"\bver\b", r"\bvol\b", r"\bmore\b",
            r"\bassoc\b", r"\bftype\b", r"\bpath\b", r"\bwhere\b", r"\bwhoami\b",
        ]
        for kw in keywords:
            self._rules.append(
                (
                    QRegularExpression(kw, QRegularExpression.PatternOption.CaseInsensitiveOption),
                    fmt_keyword,
                )
            )

        fmt_operator = _format(sp.operator)
        self._rules.append(
            (
                QRegularExpression(
                    r"\b(equ|neq|lss|leq|gtr|geq)\b",
                    QRegularExpression.PatternOption.CaseInsensitiveOption,
                ),
                fmt_operator,
            )
        )

        fmt_option = _format(sp.option)
        self._rules.append((QRegularExpression(r"\s/([a-zA-Z][a-zA-Z0-9-]*)"), fmt_option))

        fmt_variable = _format(sp.identifier)
        self._rules.append((QRegularExpression(r"%[^%\s]+%"), fmt_variable))
        self._rules.append((QRegularExpression(r"%~[a-zA-Z]*[0-9]*"), fmt_variable))
        self._rules.append((QRegularExpression(r"%[0-9*]"), fmt_variable))
        self._rules.append((QRegularExpression(r"![^!\s]+!"), fmt_variable))
        self._rules.append((QRegularExpression(r"%%[a-zA-Z]"), fmt_variable))
        self._rules.append((QRegularExpression(r"^\s@"), fmt_option))

        fmt_device = _format(sp.type_token)
        self._rules.append(
            (
                QRegularExpression(
                    r"\b(nul|con|prn|aux)\b",
                    QRegularExpression.PatternOption.CaseInsensitiveOption,
                ),
                fmt_device,
            )
        )

        self._rules.append((QRegularExpression(r"&&|\|\|"), fmt_operator))
        self._rules.append((QRegularExpression(r"(?<=\d)\s*[+\-*/%]\s*(?=\d)"), fmt_operator))
        self._rules.append((QRegularExpression(r"[()[\]{}]"), fmt_operator))

        fmt_number = _format(sp.number)
        self._rules.append((QRegularExpression(r"\b0x[0-9A-Fa-f]+\b"), fmt_number))
        self._rules.append((QRegularExpression(r"\b\d+\b"), fmt_number))

        fmt_param = _format(sp.identifier)
        self._rules.append((QRegularExpression(r"--[a-zA-Z0-9-]+"), fmt_param))

        fmt_label = _format(sp.label)
        self._rules.append((QRegularExpression(r"^\s*:[a-zA-Zа-яА-ЯёЁ0-9_]+\s*$"), fmt_label))
        self._rules.append((QRegularExpression(r"(?<!:):[a-zA-Zа-яА-ЯёЁ0-9_]+"), fmt_label))

        fmt_var_assign = _format(sp.identifier)
        self._rules.append(
            (
                QRegularExpression(
                    r"\b(?!echo\b)[a-zA-Z_а-яА-ЯёЁ][a-zA-Z0-9_а-яА-ЯёЁ]*\s*=",
                    QRegularExpression.PatternOption.CaseInsensitiveOption,
                ),
                fmt_var_assign,
            )
        )

        fmt_comment = _format(sp.comment, italic=True)
        self._rules.append(
            (
                QRegularExpression(
                    r"\brem\b[^\n]*",
                    QRegularExpression.PatternOption.CaseInsensitiveOption,
                ),
                fmt_comment,
            )
        )
        self._rules.append((QRegularExpression("::[^\n]*"), fmt_comment))

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


class JsonHighlighter(_ThemedHighlighter):
    """Подсветка JSON для конфигов."""

    def __init__(self, parent=None):
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        super().__init__(parent)
        self._build_rules()

    def _build_rules(self) -> None:
        sp = theme.syntax_palette()
        self._rules = [
            (
                QRegularExpression(r'"[^"\\]*(?:\\.[^"\\]*)*"\\s*:'),
                _format(sp.identifier),
            ),
            (
                QRegularExpression(r'"[^"\\]*(?:\\.[^"\\]*)*"'),
                _format(sp.string),
            ),
            (QRegularExpression(r"\b(true|false|null)\b"), _format(sp.type_token)),
            (
                QRegularExpression(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"),
                _format(sp.number),
            ),
        ]

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


class DiagnosticsLogHighlighter(_ThemedHighlighter):
    """Подсветка лога диагностики: заголовки, время, статусы OK/FAIL/WARN/INFO."""

    def __init__(self, parent=None):
        self._fmt_header = QTextCharFormat()
        self._fmt_time = QTextCharFormat()
        self._fmt_ok = QTextCharFormat()
        self._fmt_fail = QTextCharFormat()
        self._fmt_critical = QTextCharFormat()
        self._fmt_warn = QTextCharFormat()
        self._fmt_info = QTextCharFormat()
        self._fmt_output = QTextCharFormat()
        self._re_header = QRegularExpression(r"^=+.*=+$")
        self._re_line = QRegularExpression(
            r"^(\[\d{2}:\d{2}:\d{2}\])(\s+)(\[OK\]|\[FAIL\]|\[CRITICAL\]|\[WARN\]|\[INFO\])(\s+)(.*)$"
        )
        self._re_output = QRegularExpression(r"^(\s{4})(.*)$")
        super().__init__(parent)
        self._build_rules()

    def _build_rules(self) -> None:
        sp = theme.syntax_palette()
        ok_color = "#098658" if theme.is_light() else "#4EC9B0"
        fail_color = "#a31515" if theme.is_light() else "#F44747"
        critical_color = "#c42b2b" if theme.is_light() else "#ff6b6b"
        warn_color = "#8b6914" if theme.is_light() else "#DCDCAA"
        self._fmt_header = _format(sp.section, bold=True)
        self._fmt_time = _format(sp.option)
        self._fmt_ok = _format(ok_color, bold=True)
        self._fmt_fail = _format(fail_color, bold=True)
        self._fmt_critical = _format(critical_color, bold=True)
        self._fmt_warn = _format(warn_color, bold=True)
        self._fmt_info = _format(sp.type_token)
        self._fmt_output = _format(sp.comment)

    def highlightBlock(self, text: str) -> None:
        if self._re_header.match(text).hasMatch():
            self.setFormat(0, len(text), self._fmt_header)
            return

        output_match = self._re_output.match(text)
        if output_match.hasMatch():
            indent = output_match.captured(1)
            body = output_match.captured(2)
            if indent:
                self.setFormat(0, len(indent), self._fmt_time)
            if body:
                self.setFormat(len(indent), len(body), self._fmt_output)
            return

        match = self._re_line.match(text)
        if not match.hasMatch():
            return

        pos = 0
        time_part = match.captured(1)
        self.setFormat(pos, len(time_part), self._fmt_time)
        pos += len(time_part)

        gap1 = match.captured(2)
        pos += len(gap1)

        status = match.captured(3)
        status_fmt = {
            "[OK]": self._fmt_ok,
            "[FAIL]": self._fmt_fail,
            "[CRITICAL]": self._fmt_critical,
            "[WARN]": self._fmt_warn,
            "[INFO]": self._fmt_info,
        }.get(status, self._fmt_info)
        self.setFormat(pos, len(status), status_fmt)
        pos += len(status)

        gap2 = match.captured(4)
        pos += len(gap2)

        message = match.captured(5)
        if message:
            msg_fmt = self._fmt_critical if status == "[CRITICAL]" else self._fmt_time
            self.setFormat(pos, len(message), msg_fmt)


class TracebackHighlighter(_ThemedHighlighter):
    """Подсветка Python traceback в окне критической ошибки."""

    def __init__(self, parent=None):
        self._fmt_header = QTextCharFormat()
        self._fmt_file = QTextCharFormat()
        self._fmt_line_no = QTextCharFormat()
        self._fmt_code = QTextCharFormat()
        self._fmt_exc = QTextCharFormat()
        self._re_header = QRegularExpression(r"^Traceback \(most recent call last\):\s*$")
        self._re_file = QRegularExpression(
            r'^(\s*File ")([^"]+)(")(, line )(\d+)(, in .*)?$'
        )
        self._re_exc = QRegularExpression(
            r"^([A-Za-z_][\w.]*(?:Error|Exception|Warning|Exit|Interrupt))(:)(.*)$"
        )
        super().__init__(parent)
        self._build_rules()

    def _build_rules(self) -> None:
        sp = theme.syntax_palette()
        critical = "#c42b2b" if theme.is_light() else "#ff6b6b"
        self._fmt_header = _format(sp.section, bold=True)
        self._fmt_file = _format(sp.string)
        self._fmt_line_no = _format(sp.number, bold=True)
        self._fmt_code = _format(sp.comment)
        self._fmt_exc = _format(critical, bold=True)

    def highlightBlock(self, text: str) -> None:
        if self._re_header.match(text).hasMatch():
            self.setFormat(0, len(text), self._fmt_header)
            return

        file_match = self._re_file.match(text)
        if file_match.hasMatch():
            pos = 0
            for idx in (1, 2, 3, 4, 5):
                part = file_match.captured(idx)
                if not part:
                    continue
                fmt = self._fmt_file
                if idx == 2:
                    fmt = self._fmt_file
                elif idx == 4:
                    fmt = self._fmt_line_no
                elif idx in (1, 3, 5):
                    fmt = self._fmt_code
                self.setFormat(pos, len(part), fmt)
                pos += len(part)
            return

        exc_match = self._re_exc.match(text)
        if exc_match.hasMatch():
            pos = 0
            for idx, fmt in ((1, self._fmt_exc), (2, self._fmt_code), (3, self._fmt_exc)):
                part = exc_match.captured(idx)
                if not part:
                    continue
                self.setFormat(pos, len(part), fmt)
                pos += len(part)
            return

        if text.startswith("    "):
            self.setFormat(0, len(text), self._fmt_code)
