from __future__ import annotations

import json
from pathlib import Path

from qa.data import ExternalQuestion, PrivateAnswer
from qa.runner import QARunner
from qa.reporting import collect_records
from qa.schema import QATaskSpec


def test_runner_never_sends_gold_to_generator(tmp_path: Path) -> None:
    seen: list[dict] = []

    def generate(request: dict) -> dict:
        seen.append(request)
        return {
            "status": "completed",
            "final_answer": "analysis\nFINAL ANSWER: no",
            "elapsed_s": 2.0,
            "model_calls": 1,
            "tool_calls": 0,
            "tokens": {"total_tokens": 12},
        }

    skills = tmp_path / "skills"
    (skills / "osis-engine").mkdir(parents=True)
    (skills / "osis-engine" / "SKILL.md").write_text("skill", encoding="utf-8")
    sample = ExternalQuestion(
        public=QATaskSpec(task_id="qa-001", question="First argument?", category="usage"),
        private=PrivateAnswer(gold="no", aliases=("material number",), source="hidden.py"),
    )
    runner = QARunner(
        runs_root=tmp_path / "runs",
        skills_dir=skills,
        system_prompt="Finish with FINAL ANSWER:",
        generator=generate,
        parent_commit="abc123",
        parent_repo=tmp_path / "parent",
        opencode_executable=tmp_path / "opencode.exe",
        osis_agents_file=tmp_path / "native-AGENTS.md",
    )
    result = runner.run(sample, "T1", seed=0, model="model-x", label="smoke")
    assert result["status"] == "completed"
    assert result["evaluation"]["correct"] is True
    assert result["evaluation"]["accuracy"] == 1.0
    assert 0.99 < result["evaluation"]["overall"] <= 1.0
    request_blob = json.dumps(seen[0], ensure_ascii=False)
    assert "material number" not in request_blob
    assert "hidden.py" not in request_blob
    assert '"Final answer"' not in request_blob
    assert seen[0]["parent_repo"] == str((tmp_path / "parent").resolve())
    assert seen[0]["opencode_executable"] == str((tmp_path / "opencode.exe").resolve())
    assert seen[0]["osis_agents_file"] == str((tmp_path / "native-AGENTS.md").resolve())
    assert seen[0]["task"] == {"Question": "First argument?"}
    assert seen[0]["task_id"] == "qa-001"
    assert seen[0]["seed"] == 0
    input_blob = (Path(result["run_dir"]) / "input.json").read_text(encoding="utf-8")
    assert "material number" not in input_blob
    assert '"Final answer"' not in input_blob
    assert '"task_id": "qa-001"' in input_blob
    assert '"category": "usage"' in input_blob
    manifest = json.loads((Path(result["run_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["generation_elapsed_s"] == 2.0


def test_runner_scores_wrong_answer_zero_accuracy(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skills.mkdir()
    sample = ExternalQuestion(
        public=QATaskSpec(task_id="qa-002", question="Exists?", category="hallucination"),
        private=PrivateAnswer(gold="否"),
    )
    runner = QARunner(
        runs_root=tmp_path / "runs",
        skills_dir=skills,
        system_prompt="FINAL ANSWER:",
        generator=lambda _request: {
            "status": "completed",
            "final_answer": "FINAL ANSWER: 是",
            "elapsed_s": 0,
        },
    )
    result = runner.run(sample, "T2", seed=7, model="m", label="wrong")
    assert result["evaluation"]["correct"] is False
    assert result["evaluation"]["accuracy"] == 0.0
    assert result["evaluation"]["overall"] == 0.2


def test_runner_archives_existing_attempt_before_rerun(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skills.mkdir()
    sample = ExternalQuestion(
        public=QATaskSpec(task_id="qa-003", question="Exists?", category="usage"),
        private=PrivateAnswer(gold="yes"),
    )
    attempts = iter((1, 2))

    def generate(_request: dict) -> dict:
        attempt = next(attempts)
        return {
            "status": "completed",
            "final_answer": "FINAL ANSWER: yes",
            "elapsed_s": float(attempt),
            "attempt": attempt,
        }

    runner = QARunner(
        runs_root=tmp_path / "runs",
        skills_dir=skills,
        system_prompt="FINAL ANSWER:",
        generator=generate,
    )
    first = runner.run(sample, "T1", seed=0, model="m", label="repeat")
    second = runner.run(sample, "T1", seed=0, model="m", label="repeat")
    assert Path(first["run_dir"]) == Path(second["run_dir"])
    assert json.loads((Path(second["run_dir"]) / "generation.json").read_text(encoding="utf-8"))["attempt"] == 2
    archived = list((tmp_path / "runs" / "_archive").rglob("generation.json"))
    assert len(archived) == 1
    assert json.loads(archived[0].read_text(encoding="utf-8"))["attempt"] == 1
    assert len(collect_records(tmp_path / "runs")) == 1


def test_runner_records_generation_failure_as_incorrect(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skills.mkdir()
    sample = ExternalQuestion(
        public=QATaskSpec(task_id="qa-004", question="Exists?", category="hallucination"),
        private=PrivateAnswer(gold="否"),
    )
    runner = QARunner(
        runs_root=tmp_path / "runs",
        skills_dir=skills,
        system_prompt="FINAL ANSWER:",
        generator=lambda _request: {
            "status": "failed",
            "error": "gateway timeout",
            "elapsed_s": 240.0,
        },
    )
    result = runner.run(sample, "T2", seed=0, model="m", label="failure")
    assert result["status"] == "failed"
    assert result["evaluation"]["correct"] is False
    assert result["evaluation"]["accuracy"] == 0.0
    assert result["evaluation"]["efficiency"] == 0.5
    assert result["evaluation"]["overall"] == 0.1
    records = collect_records(tmp_path / "runs")
    assert len(records) == 1
    assert records[0]["status"] == "failed"
    assert records[0]["correct"] is False
