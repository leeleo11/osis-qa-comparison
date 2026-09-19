from __future__ import annotations

from pathlib import Path

from baselines.t1_direct import adapter


def test_t1_uses_one_completion_with_fixed_knowledge_bundle(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "doc.md").write_text("create_conc(no, name)", encoding="utf-8")
    request = {
        "task": {"task_id": "qa-001", "Question": "First argument?", "category": "usage"},
        "system_prompt": "Finish with FINAL ANSWER:",
        "skills_dir": str(skills),
        "workspace": str(tmp_path / "run"),
        "model": "m",
        "seed": 11,
    }
    seen: list[str] = []

    def completion(prompt: str, settings: dict) -> dict:
        seen.append(prompt)
        assert settings["seed"] == 11
        return {"text": "FINAL ANSWER: no", "usage": {"total_tokens": 8}, "finish_reason": "stop"}

    result = adapter.run_generation(request, completion=completion)
    assert len(seen) == 1
    assert "create_conc(no, name)" in seen[0]
    assert "qa-001" not in seen[0]
    assert '"category"' not in seen[0]
    assert result["status"] == "completed"
    assert result["model_calls"] == 1
    assert result["tool_calls"] == 0
    assert result["final_answer"] == "FINAL ANSWER: no"
