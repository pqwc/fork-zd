"""ServiceShRunner subprocess wrapper tests."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.platform.linux.service_sh_runner import ServiceShRunner


class ServiceShRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="zd-service-sh-")
        self.service_sh = os.path.join(self.tmp, "service.sh")
        with open(self.service_sh, "w", encoding="utf-8") as f:
            f.write("#!/bin/bash\necho ok\n")

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_is_available_when_service_sh_exists(self):
        runner = ServiceShRunner(self.tmp)
        self.assertTrue(runner.is_available())

    def test_is_available_false_without_service_sh(self):
        runner = ServiceShRunner(tempfile.gettempdir())
        self.assertFalse(runner.is_available())

    def test_run_missing_service_returns_127(self):
        runner = ServiceShRunner(tempfile.gettempdir())
        result = runner.run(["strategy", "list"])
        self.assertEqual(result.returncode, 127)
        self.assertIn("not found", result.stderr.lower())

    @patch("src.platform.linux.service_sh_runner.subprocess.run")
    def test_run_invokes_bash_service_sh(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
        runner = ServiceShRunner(self.tmp)
        result = runner.run(["strategy", "list"], timeout=5)
        self.assertTrue(result.ok)
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "bash")
        self.assertEqual(cmd[1], self.service_sh)
        self.assertEqual(cmd[2:], ["strategy", "list"])


if __name__ == "__main__":
    unittest.main()
