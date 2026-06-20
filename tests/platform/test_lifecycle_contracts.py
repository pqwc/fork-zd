"""Lifecycle/state-machine contract tests (audit §7, REV-P3-07)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.entities.winws.winws_manager import WinwsManager
from src.pages.main.mixins.strategy_run_mixin import StrategyRunMixin
from src.pages.main.mixins.tools_mixin import ToolsMixin
from src.pages.main.mixins.updates_mixin import UpdatesMixin
from src.pages.main.workers import StartWorker


def _worker_stub(running: bool = False):
    worker = MagicMock()
    worker.isRunning = MagicMock(return_value=running)
    return worker


class _StrategyHost(StrategyRunMixin):
    def __init__(self) -> None:
        self.user_stopped = False
        self.is_running = False
        self.running_strategy = None
        self._stop_worker = None
        self._start_worker = None
        self.settings = {}
        self.winws_manager = MagicMock()
        self.winws_manager.is_running.return_value = True
        self.strategy_list = MagicMock()
        self.strategy_list.setCurrentRow = MagicMock()

    def _get_stored_winws_pid(self):
        return None

    def _detect_running_strategy(self, proc=None):
        return "general"

    def _find_strategy_index_by_data(self, _name):
        return 0

    def _capture_running_winws_pid(self):
        return 123

    def _persist_running_winws_pid(self, _pid):
        pass


class _ToolsHost(ToolsMixin):
    def __init__(self, *, own_session: bool) -> None:
        self.running_strategy = "general"
        self.is_running = True
        self.user_stopped = False
        self._started_winws_this_session = own_session
        self.settings = {"last_strategy": "general"}

    def _is_own_winws_session(self):
        return self._started_winws_this_session

    def _get_selected_strategy_name(self):
        return "general"

    def _persist_setting(self, *_args, **_kwargs):
        pass


class _UpdatesHost(UpdatesMixin):
    def __init__(self) -> None:
        self.winws_manager = MagicMock()
        self.settings = {"language": "ru"}

    def _get_stored_winws_pid(self):
        return None

    def _runtime_process_label(self):
        return "nfqws"


class StrategyRunContractTests(unittest.TestCase):
    def test_may_sync_blocked_when_user_stopped(self):
        host = _StrategyHost()
        host.user_stopped = True
        host._sync_runtime_state_from_process()
        self.assertFalse(host.is_running)

    def test_may_sync_blocked_during_stop_worker(self):
        host = _StrategyHost()
        host._stop_worker = _worker_stub(running=True)
        host._sync_runtime_state_from_process()
        self.assertFalse(host.is_running)

    def test_action_should_stop_false_during_start_worker(self):
        host = _StrategyHost()
        host._start_worker = _worker_stub(running=True)
        host.is_running = False
        self.assertFalse(host._action_should_stop())

    def test_ui_shows_running_false_during_start_only(self):
        host = _StrategyHost()
        host._start_worker = _worker_stub(running=True)
        host.winws_manager.is_running.return_value = False
        self.assertFalse(host._ui_shows_running())

    def test_action_should_stop_true_when_process_active(self):
        host = _StrategyHost()
        host.winws_manager.is_running.return_value = True
        self.assertTrue(host._action_should_stop())


class UpdatesContractTests(unittest.TestCase):
    def test_runtime_running_uses_is_running_not_systemd(self):
        host = _UpdatesHost()
        host.winws_manager.is_running.return_value = True
        host.winws_manager.is_runtime_active = MagicMock(return_value=False)
        self.assertTrue(host._is_runtime_process_running())
        host.winws_manager.is_runtime_active.assert_not_called()

    def test_should_emit_update_signal_respects_shutdown_flag(self):
        host = _UpdatesHost()
        host._is_shutting_down = False
        self.assertTrue(host._should_emit_update_signal())
        host._is_shutting_down = True
        self.assertFalse(host._should_emit_update_signal())


class ToolsRestoreContractTests(unittest.TestCase):
    def test_capture_records_external_session(self):
        host = _ToolsHost(own_session=False)
        snap = host._capture_pre_test_strategy_state()
        self.assertFalse(snap["was_own_session"])

    def test_capture_records_own_session(self):
        host = _ToolsHost(own_session=True)
        snap = host._capture_pre_test_strategy_state()
        self.assertTrue(snap["was_own_session"])


class WinwsManagerTests(unittest.TestCase):
    @patch("src.entities.winws.winws_manager.psutil.process_iter")
    def test_stop_all_terminates_winws_processes(self, mock_iter):
        proc = MagicMock()
        proc.info = {"pid": 42, "name": "winws.exe"}
        mock_iter.return_value = [proc]
        proc.is_running.return_value = False

        WinwsManager().stop_all()

        proc.terminate.assert_called_once()


class _MainWinStub:
    def __init__(self, mgr, *, pending_stop: bool = False) -> None:
        self.winws_manager = mgr
        self._pending_stop_after_start = pending_stop

    def _prepare_auto_restart_apps(self) -> None:
        pass

    def _get_winws_start_timeout(self) -> float:
        return 15.0


class StartWorkerContractTests(unittest.TestCase):
    @patch("src.pages.main.workers.time.sleep")
    @patch("src.pages.main.workers.subprocess.Popen")
    def test_waits_for_winws_before_success(self, mock_popen, _mock_sleep):
        mock_popen.return_value = MagicMock()
        mgr = MagicMock()
        mgr.is_running.side_effect = [False, True, True]

        main_win = _MainWinStub(mgr)

        results: list[tuple] = []
        worker = StartWorker(main_win, "/tmp/winws/general.bat", "/tmp/winws", False)
        worker.done_signal.connect(lambda ok, proc, err: results.append((ok, err)))
        worker.run()

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0][0])
        self.assertGreaterEqual(mgr.is_running.call_count, 2)

    @patch("src.pages.main.workers.time.sleep")
    @patch("src.pages.main.workers.subprocess.Popen")
    def test_cancelled_start_emits_failure(self, mock_popen, _mock_sleep):
        mock_popen.return_value = MagicMock()
        mgr = MagicMock()
        mgr.is_running.return_value = False

        main_win = _MainWinStub(mgr, pending_stop=True)

        results: list[tuple] = []
        worker = StartWorker(main_win, "/tmp/winws/general.bat", "/tmp/winws", False)
        worker.done_signal.connect(lambda ok, proc, err: results.append((ok, err)))
        worker.run()

        self.assertFalse(results[0][0])
        self.assertEqual(results[0][1], "cancelled")


if __name__ == "__main__":
    unittest.main()
