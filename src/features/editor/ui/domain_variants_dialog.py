"""Диалог поиска реальных доменов и поддоменов сайта."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from src.entities.domain.domain_variants import discover_site_domains
from src.shared.i18n.translator import tr
from src.shared.ui import theme
from src.widgets.custom_context_widgets import ContextLineEdit


class _DiscoveryWorker(QThread):
    domain_found = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    finished_ok = pyqtSignal(list, object)
    finished_error = pyqtSignal(str)

    def __init__(self, domain: str):
        super().__init__()
        self.domain = domain
        self._domains: list[str] = []

    def run(self):
        try:
            def on_domain(host: str) -> None:
                self._domains.append(host)
                self.domain_found.emit(host)

            def on_status(source: str) -> None:
                self.status_changed.emit(source)

            result, note = discover_site_domains(
                self.domain,
                on_domain=on_domain,
                on_status=on_status,
            )
            if not result:
                self.finished_error.emit(note or "empty")
            else:
                self.finished_ok.emit(result, note)
        except ValueError as exc:
            self.finished_error.emit(str(exc))
        except Exception as exc:
            self.finished_error.emit(str(exc))


class DomainVariantsDialog(QDialog):
    """Поиск доменов через CT-логи (crt.sh) и hostsearch."""

    def __init__(self, parent=None, language: str = "ru", initial_domain: str = ""):
        super().__init__(parent)
        self.language = language
        self._worker: _DiscoveryWorker | None = None
        self._found_domains: list[str] = []
        from src.shared.ui.assets.embedded_assets import get_app_icon

        self.setWindowIcon(get_app_icon())
        self.setWindowTitle(tr("domain_variants_title", language))
        self.setMinimumSize(520, 420)
        self.resize(560, 480)

        p = theme.palette()
        theme.apply_widget_theme(self)
        self.setStyleSheet(
            f"QDialog {{ background-color: {p.bg_window}; color: {p.fg_text}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(QLabel(tr("domain_variants_description", language)))

        self.domain_edit = ContextLineEdit()
        self.domain_edit.setPlaceholderText("google.com")
        if initial_domain:
            self.domain_edit.setText(initial_domain)
        self.domain_edit.returnPressed.connect(self._start_search)
        layout.addWidget(self.domain_edit)

        btn_row = QHBoxLayout()
        self.search_btn = QPushButton(tr("domain_variants_generate", language))
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.clicked.connect(self._start_search)
        btn_row.addWidget(self.search_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.result_edit = QPlainTextEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setFont(QFont("Consolas", 10))
        theme.apply_test_panel_text_widget(self.result_edit)
        layout.addWidget(self.result_edit, 1)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet(theme.muted_label_style())
        layout.addWidget(self.count_label)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.copy_btn = QPushButton(tr("domain_variants_copy", language))
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.clicked.connect(self._copy)
        self.insert_btn = QPushButton(tr("domain_variants_insert", language))
        self.insert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.insert_btn.clicked.connect(self._insert)
        self.close_btn = QPushButton(tr("settings_cancel", language))
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.reject)
        actions.addWidget(self.copy_btn)
        actions.addWidget(self.insert_btn)
        actions.addWidget(self.close_btn)
        layout.addLayout(actions)

        self._apply_field_style()

    def _apply_field_style(self):
        p = theme.palette()
        h = theme.EDITOR_FIELD_HEIGHT
        self.domain_edit.setStyleSheet(f"""
            QLineEdit, ContextLineEdit {{
                background-color: {p.bg_window};
                color: {p.fg_text};
                border: 1px solid {p.border};
                border-radius: {theme.CONTROL_RADIUS}px;
                {theme.input_field_height_qss(h=h, bordered=True)}
            }}
        """)

    def _set_busy(self, busy: bool):
        self.search_btn.setEnabled(not busy)
        self.domain_edit.setEnabled(not busy)

    def _update_count(self, partial: bool = False):
        count = len(self._found_domains)
        text = tr("domain_variants_count", self.language).format(count)
        if partial:
            text += " — " + tr("domain_variants_searching_short", self.language)
        self.count_label.setText(text)

    def _start_search(self):
        raw = self.domain_edit.text().strip()
        if not raw:
            self.result_edit.setPlainText(tr("domain_variants_empty_input", self.language))
            self.count_label.setText("")
            self._found_domains.clear()
            return

        if self._worker and self._worker.isRunning():
            return

        self._set_busy(True)
        self._found_domains.clear()
        self.result_edit.setPlainText(tr("domain_variants_searching", self.language))
        self.count_label.setText("")

        self._worker = _DiscoveryWorker(raw)
        self._worker.domain_found.connect(self._on_domain_found)
        self._worker.status_changed.connect(self._on_status_changed)
        self._worker.finished_ok.connect(self._on_search_ok)
        self._worker.finished_error.connect(self._on_search_error)
        self._worker.start()

    def _on_domain_found(self, host: str):
        if not self._found_domains:
            self.result_edit.clear()
        self._found_domains.append(host)
        self.result_edit.appendPlainText(host)
        self._update_count(partial=True)
        cursor = self.result_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.result_edit.setTextCursor(cursor)

    def _on_status_changed(self, source: str):
        if source == "crt.sh":
            self.result_edit.setPlainText(tr("domain_variants_status_crt", self.language))
            self._found_domains.clear()
        elif source == "hostsearch":
            if self._found_domains:
                self.result_edit.appendPlainText("")
                self.result_edit.appendPlainText(
                    tr("domain_variants_status_hostsearch", self.language)
                )
            else:
                self.result_edit.setPlainText(
                    tr("domain_variants_status_hostsearch", self.language)
                )

    def _on_search_ok(self, result: list, note):
        self._set_busy(False)
        self._found_domains = list(result)
        self.result_edit.setPlainText("\n".join(result))
        count_text = tr("domain_variants_count", self.language).format(len(result))
        if note:
            count_text += " — " + tr("domain_variants_partial", self.language)
        self.count_label.setText(count_text)

    def _on_search_error(self, error: str):
        self._set_busy(False)
        if error == "requests_missing":
            text = tr("domain_variants_no_requests", self.language)
        elif error == "invalid_domain":
            text = tr("domain_variants_invalid", self.language)
        elif error == "empty":
            text = tr("domain_variants_empty", self.language)
        else:
            text = tr("domain_variants_error", self.language).format(error)
        self.result_edit.setPlainText(text)
        self.count_label.setText("")

    def _copy(self):
        text = self.result_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    def _insert(self):
        text = self.result_edit.toPlainText().strip()
        if not text:
            return
        parent = self.parent()
        if parent and hasattr(parent, "insert_text_to_current_editor"):
            parent.insert_text_to_current_editor(text + "\n")
            self.accept()
            return
        QApplication.clipboard().setText(text)
        self.accept()

    def get_result_text(self) -> str:
        return self.result_edit.toPlainText().strip()

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.wait(2000)
        super().closeEvent(event)
