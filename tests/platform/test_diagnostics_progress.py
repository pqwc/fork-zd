"""Diagnostics runner progress callback."""
from unittest.mock import patch

from src.entities.diagnostics.diagnostics_runner import run_diagnostics


@patch("src.entities.diagnostics.diagnostics_runner.checks_for_platform", return_value=[])
def test_run_diagnostics_emits_progress(_checks):
    seen: list[tuple[str, str]] = []

    def on_progress(status: str, msg: str) -> None:
        seen.append((status, msg))

    results, summary = run_diagnostics(
        "ru",
        enabled={},
        custom_config={"custom_commands": []},
        progress_callback=on_progress,
    )
    assert results == seen
    assert summary == {"pass": 0, "fail": 0, "warn": 0, "info": 0}
