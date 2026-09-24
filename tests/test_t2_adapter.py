from __future__ import annotations

from pathlib import Path

from baselines.t2_langgraph import adapter


def test_t2_runs_react_with_read_only_knowledge_tools(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "doc.md").write_text("answer=no", encoding="utf-8")
    request = {
        "task": {"task_id": "qa-001", "Question": "Exists?", "category": "hallucination"},
        "system_prompt": "FINAL ANSWER:",
        "skills_dir": str(skills),
        "workspace": str(tmp_path / "run"),
        "model": "m",
    }

    def runtime(_request: dict, prompt: str, tools) -> dict:
        assert "Exists?" in prompt
        assert "qa-001" not in prompt
        assert '"category"' not in prompt
        assert [fn.__name__ for fn in tools.functions()] == [
            "list_skills",
            "read_skill",
            "read_skill_reference",
            "list_reference_files",
            "search_skill_cases",
            "list_knowledge_files",
            "search_knowledge",
            "read_knowledge_file",
        ]
        return {"final_answer": "FINAL ANSWER: 否", "model_calls": 2, "tool_calls": 1}

    result = adapter.run_generation(request, runtime=runtime)
    assert result["status"] == "completed"
    assert result["interaction_mode"] == "react"
    assert result["tool_calls"] == 1
