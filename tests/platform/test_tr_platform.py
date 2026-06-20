"""tr_platform() Linux string selection."""
from unittest.mock import patch

from src.shared.i18n.translator import tr_platform


@patch("src.platform.is_linux", return_value=True)
def test_tr_platform_uses_linux_key(_mock):
    assert "nfqws" in tr_platform("settings_close_winws", "ru").lower()


@patch("src.platform.is_linux", return_value=False)
def test_tr_platform_uses_windows_key(_mock):
    assert "winws" in tr_platform("settings_close_winws", "en").lower()
