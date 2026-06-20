"""Platform-specific diagnostics checks."""
from unittest.mock import patch

from src.entities.diagnostics.diagnostics_runner import checks_for_platform


@patch("src.platform.detect_platform", return_value="linux")
def test_checks_for_platform_linux(_mock):
    ids = {c.check_id for c in checks_for_platform()}
    assert "linux_runtime" in ids
    assert "linux_nfqws_process" in ids
    assert "bfe" not in ids
    assert "winws_binary" not in ids


@patch("src.platform.detect_platform", return_value="windows")
def test_checks_for_platform_windows(_mock):
    ids = {c.check_id for c in checks_for_platform()}
    assert "winws_binary" in ids
    assert "linux_runtime" not in ids
