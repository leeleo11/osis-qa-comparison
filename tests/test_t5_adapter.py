from __future__ import annotations

from pathlib import Path

from baselines.t5_crewai import adapter


def test_t5_has_research_answer_review_role_chain() -> None:
    roles = adapter.role_blueprint()
    assert [role["id"] for role in roles] == ["researcher", "answerer", "reviewer"]
    assert roles[-1]["read_only"] is True
    assert adapter.allocate_model_calls(9) == (3, 3, 3)


def test_t5_injected_runtime_records_role_delegation(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skills.mkdir()
    request = {
        "task": {"task_id": "qa-001", "Question": "First arg?", "category": "usage"},
        "system_prompt": "FINAL ANSWER:",
        "skills_dir": str(skills),
        "workspace": str(tmp_path / "run"),
        "model": "m",
        "max_steps": 9,
    }

    def runtime(_request: dict, prompt: str, _tools) -> dict:
        assert "First arg?" in prompt
        assert "qa-001" not in prompt
        assert '"category"' not in prompt
        return {
            "final_answer": "FINAL ANSWER: no",
            "model_calls": 6,
            "tool_calls": 4,
            "roles_completed": ["researcher", "answerer", "reviewer"],
        }

    result = adapter.run_generation(request, runtime=runtime)
    assert result["status"] == "completed"
    assert result["roles_completed"] == ["researcher", "answerer", "reviewer"]
