from __future__ import annotations

from pathlib import Path

from baselines.t4_openhands import adapter


def test_t4_prompt_requires_native_invoke_skill() -> None:
    prompt = adapter.build_t4_prompt(
        {
            "task": {"task_id": "qa-001", "Question": "First arg?", "category": "usage"},
            "system_prompt": "FINAL ANSWER:",
        }
    )
    assert "invoke_skill" in prompt
    assert "OpenHands InvokeSkillTool" in prompt
    assert "file editor" in prompt
    assert "terminal" in prompt
    assert "First arg?" in prompt
    assert "qa-001" not in prompt
    assert '"category"' not in prompt


def test_t4_flattens_all_native_skill_groups(tmp_path: Path) -> None:
    calls: list[Path] = []

    def loader(path: Path):
        calls.append(path)
        return ({"a": "A"}, {"b": "B"}, {"c": "C"})

    assert adapter._load_native_skills(tmp_path, loader=loader) == ["A", "B", "C"]
    assert calls == [tmp_path]


def test_t4_run_uses_native_skills_without_custom_tools(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "osis-module-material"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("native skill", encoding="utf-8")
    seen: dict[str, object] = {}

    def runtime(_request, _prompt, native_skills):
        seen["native"] = native_skills
        return {
            "final_answer": "FINAL ANSWER: no",
            "execution_status": "FINISHED",
            "native_skill_invocations": ["osis-module-material"],
        }

    result = adapter.run_generation(
        {
            "task": {"Question": "First arg?"},
            "system_prompt": "FINAL ANSWER:",
            "skills_dir": str(tmp_path / "skills"),
            "workspace": str(tmp_path / "run"),
            "model": "m",
        },
        runtime=runtime,
        skill_loader=lambda _path: ({"material": "native-material-skill"}, {}, {}),
    )
    assert result["status"] == "completed"
    assert seen["native"] == ["native-material-skill"]
    assert not hasattr(adapter, "ReferenceKnowledgeTools")
    assert not hasattr(adapter, "T4_CUSTOM_TOOL_NAMES")
