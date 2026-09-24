from __future__ import annotations

from pathlib import Path

from baselines.t6_osisai import adapter


def test_t6_calls_parent_without_a_local_permission_config(tmp_path: Path) -> None:
    source = Path(adapter.__file__).read_text(encoding="utf-8")
    assert "chat_via_agent" in source
    assert "prepare_isolated_env" not in source
    assert '"bash"' not in source
    seen: dict[str, object] = {}

    def chat(request: dict[str, object]) -> dict[str, object]:
        seen["question"] = request["task"]["Question"]  # type: ignore[index]
        seen["model"] = request["model"]
        return {"raw": "FINAL ANSWER: no", "usage": {"total_tokens": 3}}

    result = adapter.run_generation(
        {
            "task": {"task_id": "qa-001", "Question": "First arg?", "category": "usage"},
            "system_prompt": "Finish with FINAL ANSWER:",
            "workspace": str(tmp_path / "run"),
            "model": "model-x",
        },
        chat=chat,
    )
    assert seen["question"] == "First arg?"
    assert seen["model"] == "model-x"
    assert result["interaction_mode"] == "parent_session"
    assert result["skill_loading"] == "parent_repo"
    assert result["final_answer"] == "FINAL ANSWER: no"
    assert not (tmp_path / "run" / ".agents").exists()


def test_t6_fails_without_the_parent_runner(tmp_path: Path) -> None:
    result = adapter.run_generation(
        {
            "task": {"task_id": "qa-001", "Question": "First arg?"},
            "workspace": str(tmp_path / "run"),
            "model": "m",
            "parent_repo": str(tmp_path / "missing-parent"),
        }
    )
    assert result["status"] == "failed"
    assert result["error_type"] == "FileNotFoundError"
