from __future__ import annotations

import json
from pathlib import Path

from baselines._framework_common import KnowledgeTools, build_prompt, finish, model_api_settings


def _request(tmp_path: Path) -> dict:
    skills = tmp_path / "skills"
    (skills / "osis-engine").mkdir(parents=True)
    (skills / "osis-engine" / "SKILL.md").write_text("engine docs", encoding="utf-8")
    return {
        "task": {"task_id": "qa-001", "Question": "First parameter?", "category": "usage"},
        "system_prompt": "Finish with FINAL ANSWER:",
        "skills_dir": str(skills),
        "workspace": str(tmp_path / "run"),
        "model": "m",
    }


def test_shared_prompt_contains_only_public_contract(tmp_path: Path) -> None:
    prompt = build_prompt(_request(tmp_path))
    assert "First parameter?" in prompt
    assert "FINAL ANSWER:" in prompt
    assert "Final answer" not in prompt
    assert "aliases" not in prompt
    assert "qa-001" not in prompt
    assert '"category"' not in prompt


def test_knowledge_tools_are_read_only(tmp_path: Path) -> None:
    tools = KnowledgeTools(_request(tmp_path))
    names = [fn.__name__ for fn in tools.functions()]
    assert names[:5] == [
        "list_skills",
        "read_skill",
        "read_skill_reference",
        "list_reference_files",
        "search_skill_cases",
    ]
    assert "write" not in " ".join(names)
    assert "osis-engine/SKILL.md" in tools.list_knowledge_files()
    assert "engine docs" in tools.read_knowledge_file("osis-engine/SKILL.md")


def test_finish_persists_framework_record(tmp_path: Path) -> None:
    value = finish(tmp_path, "T2", {"status": "completed"}, 0.0)
    saved = json.loads((tmp_path / "t2_generation.json").read_text(encoding="utf-8"))
    assert value["architecture_id"] == "T2"
    assert saved["status"] == "completed"


def test_model_settings_preserve_experiment_seed() -> None:
    settings = model_api_settings({"model": "m", "seed": 17})
    assert settings["seed"] == 17
