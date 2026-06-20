"""Диалог экспорта данных в zip."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.shared.ui.assets.embedded_assets import get_app_icon
from src.features.export.export_bundle import ExportOptions, build_export_zip
from src.shared.lib.path_utils import get_winws_path
from src.shared.i18n.translator import tr, tr_platform
from src.shared.ui import theme
from src.shared.ui.standard_dialog import StandardDialog
from src.widgets.custom_checkbox import CustomCheckBox as QCheckBox


class ExportBundleDialog(StandardDialog):
    def __init__(self, parent=None, language: str = "ru"):
        self.lang = language
        self._syncing_checks = False
        super().__init__(
            parent=parent,
            title=tr("export_bundle_title", language),
            width=520,
            height=380,
            icon=get_app_icon(),
            theme="dark",
        )
        self._build_ui()
        self.refresh_theme()

    def _build_ui(self):
        layout = self.getContentLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.hint_label = QLabel(tr("export_bundle_hint", self.lang))
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.cb_all = QCheckBox(tr_platform("export_bundle_all", self.lang))
        self.cb_winws = QCheckBox(tr_platform("export_bundle_winws", self.lang))
        self.cb_config = QCheckBox(tr("export_bundle_config", self.lang))
        self.cb_zapret = QCheckBox(tr_platform("export_bundle_zapret", self.lang))
        for cb in (self.cb_all, self.cb_winws, self.cb_config, self.cb_zapret):
            cb.setChecked(True)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(cb)

        self.cb_all.toggled.connect(self._on_all_toggled)
        for cb in (self.cb_winws, self.cb_config, self.cb_zapret):
            cb.toggled.connect(self._on_item_toggled)

        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet(theme.muted_label_style())
        layout.addWidget(self.path_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.export_btn = QPushButton(tr("export_bundle_action", self.lang))
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.clicked.connect(self._run_export)
        self.cancel_btn = QPushButton(tr("settings_cancel", self.lang))
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.export_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        self._update_path_hint()

    def _on_all_toggled(self, checked: bool):
        if self._syncing_checks:
            return
        self._syncing_checks = True
        for cb in (self.cb_winws, self.cb_config, self.cb_zapret):
            cb.setChecked(checked)
        self._syncing_checks = False

    def _on_item_toggled(self, _checked: bool):
        if self._syncing_checks:
            return
        self._syncing_checks = True
        self.cb_all.setChecked(
            self.cb_winws.isChecked()
            and self.cb_config.isChecked()
            and self.cb_zapret.isChecked()
        )
        self._syncing_checks = False

    def _update_path_hint(self):
        winws = get_winws_path()
        self.path_label.setText(tr_platform("export_bundle_winws_path", self.lang).format(winws))

    def _options(self) -> ExportOptions:
        winws = self.cb_winws.isChecked()
        return ExportOptions(
            strategies=winws,
            lists=winws,
            bin=winws,
            config=self.cb_config.isChecked(),
            zapret=self.cb_zapret.isChecked(),
        )

    def _run_export(self):
        default_name = f"zapret_export_{datetime.now():%Y%m%d_%H%M%S}.zip"
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("export_bundle_title", self.lang),
            default_name,
            "ZIP archives (*.zip)",
        )
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"

        count, err = build_export_zip(path, self._options())
        if err == "nothing_selected":
            QMessageBox.warning(
                self,
                tr("export_bundle_title", self.lang),
                tr("export_bundle_nothing_selected", self.lang),
            )
            return
        if err == "empty":
            QMessageBox.warning(
                self,
                tr("export_bundle_title", self.lang),
                tr("export_bundle_empty", self.lang),
            )
            return
        if err:
            QMessageBox.critical(
                self,
                tr("export_error_title", self.lang),
                tr("export_error", self.lang).format(err),
            )
            return

        QMessageBox.information(
            self,
            tr("export_bundle_title", self.lang),
            tr("export_bundle_success", self.lang).format(count, path),
        )
        self.accept()

    def refresh_theme(self):
        super().refresh_theme()
        self.content_frame.setStyleSheet(theme.dialog_form_stylesheet())
        if hasattr(self, "path_label"):
            self.path_label.setStyleSheet(theme.muted_label_style())
        if hasattr(self, "hint_label"):
            p = theme.palette()
            self.hint_label.setStyleSheet(f"color: {p.fg_text}; background: transparent;")
