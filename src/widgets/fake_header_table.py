"""Таблица с кастомной строкой заголовков (настоящий QHeaderView скрыт)."""
from PyQt6.QtCore import QTimer, Qt, QRectF
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from src.shared.ui import theme
from src.widgets.rounded_clip import install_round_clip, paint_rounded_panel


class FakeHeaderTable(QWidget):
    """Обёртка над QTableWidget: отображает заголовки вручную, экспорт не затрагивает."""

    _RADIUS = 8

    def __init__(self, table: QTableWidget | None = None, parent=None):
        super().__init__(parent)
        self.table = table or QTableWidget()
        self._header_labels: list[QLabel] = []

        self.table.horizontalHeader().setVisible(False)
        self.table.setCornerButtonEnabled(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header_row = QFrame()
        self._header_row.setObjectName("fakeTableHeader")
        self._header_layout = QHBoxLayout(self._header_row)
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(0)

        layout.addWidget(self._header_row)
        layout.addWidget(self.table, 1)

        self._apply_header_style()
        install_round_clip(self, self._RADIUS)
        self._rebuild_header_labels()

        header = self.table.horizontalHeader()
        header.sectionResized.connect(self._sync_column_widths)
        header.geometriesChanged.connect(self._sync_column_widths)
        self.table.horizontalHeader().sectionCountChanged.connect(
            lambda *_: self._rebuild_header_labels()
        )

        QTimer.singleShot(0, self._sync_column_widths)

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter

        p = theme.palette()
        painter = QPainter(self)
        paint_rounded_panel(
            painter,
            QRectF(self.rect()),
            radius=self._RADIUS,
            bg_color=p.bg_panel,
            border_color=p.border,
        )
        painter.end()
        super().paintEvent(event)

    def _apply_header_style(self):
        p = theme.palette()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: transparent; border: none;")
        self._header_row.setStyleSheet(f"""
            QFrame#fakeTableHeader {{
                background-color: {p.bg_panel};
                border: none;
                border-bottom: 1px solid {p.border};
            }}
            QLabel#fakeTableHeaderCell {{
                background-color: transparent;
                color: {p.fg_muted};
                padding: 8px 10px;
                font-weight: 600;
                border: none;
            }}
        """)

    def _rebuild_header_labels(self):
        while self._header_layout.count():
            item = self._header_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._header_labels.clear()

        for col in range(self.table.columnCount()):
            label = QLabel()
            label.setObjectName("fakeTableHeaderCell")
            header_item = self.table.horizontalHeaderItem(col)
            label.setText(header_item.text() if header_item else "")
            label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            label.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
            )
            self._header_layout.addWidget(label)
            self._header_labels.append(label)

        self._sync_column_widths()

    def set_header_labels(self, labels: list[str]):
        """Обновляет заголовки для отображения и для экспорта."""
        self.table.setHorizontalHeaderLabels(labels)
        if len(self._header_labels) != len(labels):
            self._rebuild_header_labels()
            return
        for col, text in enumerate(labels):
            self._header_labels[col].setText(text)

    def _sync_column_widths(self):
        if not self._header_labels:
            return
        header = self.table.horizontalHeader()
        for col, label in enumerate(self._header_labels):
            if col >= self.table.columnCount():
                break
            label.setFixedWidth(header.sectionSize(col))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._sync_column_widths)
