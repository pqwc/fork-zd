"""Linux runtime active detection."""
from unittest.mock import MagicMock, patch

from src.platform.linux.linux_runtime_manager import LinuxRuntimeManager


@patch.object(LinuxRuntimeManager, "is_running", return_value=False)
@patch.object(LinuxRuntimeManager, "service_is_active", return_value=True)
def test_is_runtime_active_via_systemd(_service, _running):
    mgr = LinuxRuntimeManager()
    assert mgr.is_runtime_active() is True


@patch.object(LinuxRuntimeManager, "is_running", return_value=True)
@patch.object(LinuxRuntimeManager, "service_is_active", return_value=False)
def test_is_runtime_active_via_process(_service, _running):
    mgr = LinuxRuntimeManager()
    assert mgr.is_runtime_active() is True
