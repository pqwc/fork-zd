"""Subprocess-обёртка над service.sh (zapret-discord-youtube-linux)."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

DEFAULT_TIMEOUT_SEC = 180.0


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def combined_output(self) -> str:
        parts = [self.stdout.strip(), self.stderr.strip()]
        return "\n".join(p for p in parts if p)


class ServiceShRunner:
    def __init__(self, runtime_root: str) -> None:
        self.runtime_root = os.path.abspath(runtime_root)
        self.service_sh = os.path.join(self.runtime_root, "service.sh")

    def is_available(self) -> bool:
        return os.path.isfile(self.service_sh)

    def run(
        self,
        args: list[str],
        *,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        capture: bool = True,
    ) -> CommandResult:
        if not self.is_available():
            return CommandResult(127, "", "service.sh not found")

        cmd = ["bash", self.service_sh, *args]
        try:
            completed = subprocess.run(
                cmd,
                cwd=self.runtime_root,
                capture_output=capture,
                text=True,
                timeout=timeout,
                errors="replace",
            )
            return CommandResult(
                completed.returncode,
                completed.stdout or "",
                completed.stderr or "",
            )
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            err = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            return CommandResult(124, out, err or f"timeout after {timeout}s")
        except Exception as exc:
            return CommandResult(1, "", str(exc))

    def popen(
        self,
        args: list[str],
        *,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ) -> subprocess.Popen:
        cmd = ["bash", self.service_sh, *args]
        return subprocess.Popen(
            cmd,
            cwd=self.runtime_root,
            stdout=stdout,
            stderr=stderr,
            text=True,
            errors="replace",
            start_new_session=True,
        )
