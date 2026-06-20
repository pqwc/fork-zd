"""Диалог первого запуска: указать каталог Linux-адаптера (service.sh)."""
from __future__ import annotations

import os

from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from src.entities.config.config_manager import ConfigManager
from src.shared.i18n.translator import tr
from src.shared.lib.path_utils import validate_linux_runtime_folder
from src.shared.ui.assets.embedded_assets import get_app_icon
from src.shared.ui.standard_dialog import StandardDialog


class LinuxRuntimeSetupDialog(StandardDialog):
    def __init__(self, parent, config: ConfigManager) -> None:
        self.config = config
        settings = config.load_settings()
        self.lang = settings.get("language", "ru")

        super().__init__(
            parent=parent,
            title=tr("linux_runtime_setup_title", self.lang),
            width=520,
            height=280,
            icon=get_app_icon(),
        )

        layout = self.getContentLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        hint = QLabel(tr("linux_runtime_setup_text", self.lang))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(tr("linux_runtime_setup_placeholder", self.lang))
        row.addWidget(self.path_edit, 1)

        browse_btn = QPushButton(tr("linux_runtime_setup_browse", self.lang))
        browse_btn.clicked.connect(self._browse)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #e51400;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        skip_btn = QPushButton(tr("linux_runtime_setup_skip", self.lang))
        skip_btn.clicked.connect(self.reject)
        btn_row.addWidget(skip_btn)
        ok_btn = QPushButton(tr("linux_runtime_setup_save", self.lang))
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._save)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _browse(self) -> None:
        start = self.path_edit.text().strip() or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("linux_runtime_setup_browse", self.lang),
            start,
        )
        if folder:
            self.path_edit.setText(folder)

    def _save(self) -> None:
        path = self.path_edit.text().strip()
        ok, reason = validate_linux_runtime_folder(path)
        if not ok:
            messages = {
                "not_directory": tr("linux_runtime_setup_err_not_dir", self.lang),
                "missing_service_sh": tr("linux_runtime_setup_err_no_service", self.lang),
                "not_configured": tr("linux_runtime_setup_err_empty", self.lang),
            }
            self.error_label.setText(
                messages.get(reason, tr("linux_runtime_setup_err_no_service", self.lang))
            )
            self.error_label.show()
            return
        self.config.set_setting("runtime_path", os.path.abspath(path))
        self.config.set_setting("runtime_type", "zapret-linux")
        self.accept()
