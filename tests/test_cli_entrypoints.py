from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_verify_parent_protocol_is_directly_executable() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/verify_parent_protocol.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    "script",
    [
        "scripts/export_repro_workspace.py",
        "scripts/run_campaign.py",
        "scripts/run_dataset.py",
        "scripts/summarize_results.py",
    ],
)
def test_cli_help_works_from_repo_root(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, completed.stderr


def test_public_smoke_is_directly_executable() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/run_public_smoke.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, completed.stderr
    assert '"status": "completed"' in completed.stdout
