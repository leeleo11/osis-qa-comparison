from __future__ import annotations

import json
from pathlib import Path

from baselines.t6_osisai import adapter


def test_t6_prompt_is_question_only_contract() -> None:
    prompt = adapter.build_agent_prompt(
        {
            "task": {"task_id": "qa-001", "Question": "First arg?", "category": "usage"},
            "system_prompt": "Finish with FINAL ANSWER:",
        }
    )
    assert "First arg?" in prompt
    assert "FINAL ANSWER:" in prompt
    assert "Final answer" not in prompt
    assert "qa-001" not in prompt
    assert '"category"' not in prompt


def test_t6_isolated_config_pins_model_and_env_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    monkeypatch.setenv("OSIS_PARENT_REPO", "C:/private/parent")
    monkeypatch.setenv("QA_API_KEY", "private-evaluator-key")
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-provider-key")
    monkeypatch.setenv("OSIS_MODEL_API_KEY", "comparison-gateway-key")
    skills = tmp_path / "skills"
    (skills / "osis-engine").mkdir(parents=True)
    (skills / "osis-engine" / "SKILL.md").write_text("skill", encoding="utf-8")
    native_agents = tmp_path / "native" / "AGENTS.md"
    native_agents.parent.mkdir()
    native_agents.write_text("native OSIS-AI workflow", encoding="utf-8")
    env = adapter.prepare_isolated_env(
        tmp_path / "isolated",
        skills,
        "http://gateway/v1",
        model="model-x",
        seed=17,
        max_steps=23,
        agents_source=native_agents,
    )
    config = json.loads((tmp_path / "isolated" / ".agents" / "opencode.json").read_text(encoding="utf-8"))
    assert config["provider"]["comparison"]["options"]["apiKey"] == "{env:OSIS_MODEL_API_KEY}"
    assert "model-x" in config["provider"]["comparison"]["models"]
    assert config["provider"]["comparison"]["models"]["model-x"]["options"]["seed"] == 17
    assert config["agent"]["build"]["temperature"] == 0.0
    assert config["agent"]["build"]["steps"] == 23
    assert config["agent"]["build"]["options"]["seed"] == 17
    assert config["permission"]["external_directory"] == "deny"
    assert config["permission"]["bash"] == "deny"
    assert config["permission"]["edit"] == "deny"
    assert len(config["instructions"]) == 2
    assert Path(env["OPENCODE_CONFIG_DIR"]).is_dir()
    assert Path(env["XDG_CONFIG_HOME"]).is_dir()
    assert {"127.0.0.1", "localhost", "::1"}.issubset(set(env["NO_PROXY"].split(",")))
    assert "OSIS_PARENT_REPO" not in env
    assert "QA_API_KEY" not in env
    assert "OPENAI_API_KEY" not in env
    assert env["OSIS_MODEL_API_KEY"] == "comparison-gateway-key"
    assert (tmp_path / "isolated" / ".agents" / "skills" / "osis-engine" / "SKILL.md").is_file()
    assert (tmp_path / "isolated" / ".agents" / "AGENTS.md").read_text(encoding="utf-8") == "native OSIS-AI workflow"
