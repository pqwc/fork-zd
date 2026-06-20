"""diagnostics_mixin methods for MainWindow."""
from src.features.diagnostics.ui.diagnostics_dialog import DiagnosticsDialog


class DiagnosticsMixin:
    def run_diagnostics(self):
        """Открывает окно диагностики с настройкой проверок."""
        dialog = DiagnosticsDialog(parent=self, settings=self.settings, config=self.config)
        dialog.exec()
        if self.config:
            self.settings = self.config.load_settings()
