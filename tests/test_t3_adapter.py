from __future__ import annotations

from pathlib import Path

from baselines.t3_smolagents import adapter


def test_t3_runs_codeagent_runtime(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "doc.md").write_text("answer=3", encoding="utf-8")
    request = {
        "task": {"task_id": "qa-003", "Question": "How many?", "category": "template"},
        "system_prompt": "FINAL ANSWER:",
        "skills_dir": str(skills),
        "workspace": str(tmp_path / "run"),
        "model": "m",
    }

    def runtime(_request: dict, prompt: str, tools) -> dict:
        assert "How many?" in prompt
        assert "qa-003" not in prompt
        assert '"category"' not in prompt
        assert tools.search_knowledge("answer")
        return {"final_answer": "FINAL ANSWER: 3", "model_calls": 3, "tool_calls": 2}

    result = adapter.run_generation(request, runtime=runtime)
    assert result["status"] == "completed"
    assert result["interaction_mode"] == "codeact"
    assert result["model_calls"] == 3
