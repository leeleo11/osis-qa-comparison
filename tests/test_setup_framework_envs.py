from __future__ import annotations

from pathlib import Path

from scripts.setup_framework_envs import environment_plan, setup


def test_environment_plan_separates_framework_dependencies(tmp_path: Path) -> None:
    plan = environment_plan(tmp_path)
    assert set(plan) == {"main", "T2", "T3", "T4", "T5"}
    assert plan["T2"]["extra"] == "t2"
    assert plan["T4"]["extra"] == "t4"
    assert str(plan["T3"]["path"]).endswith("t3")


def test_setup_syncs_each_environment_from_frozen_lock() -> None:
    commands = setup(dry_run=True)
    sync_commands = [command for command in commands if command[:2] == ["uv", "sync"]]
    assert len(sync_commands) == 5
    assert all("--frozen" in command and "--active" in command for command in sync_commands)
    assert not any(command[:2] == ["uv", "pip"] for command in commands)
    create_commands = [command for command in commands if command[:2] == ["uv", "venv"]]
    assert all("--allow-existing" in command for command in create_commands)
