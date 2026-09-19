from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa.data import load_external_questions
from qa.sanitize import sanitize_for_model
from qa.schema import QATaskSpec


def _parent(tmp_path: Path) -> Path:
    parent = tmp_path / "parent"
    qa_dir = parent / "datasets" / "qa"
    qa_dir.mkdir(parents=True)
    (parent / ".agents" / "skills" / "osis-engine").mkdir(parents=True)
    (parent / ".agents" / "skills" / "osis-engine" / "SKILL.md").write_text(
        "---\nname: OSIS Engine\ndescription: API routing\n---\nbody\n",
        encoding="utf-8",
    )
    (qa_dir / "system_prompt.txt").write_text("Finish with FINAL ANSWER:", encoding="utf-8")
    (qa_dir / "questions.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "qa-001",
                    "Question": "First argument?",
                    "Final answer": "no",
                    "aliases": ["material number"],
                    "category": "usage",
                    "source": "secret/source.py",
                }
            ]
        ),
        encoding="utf-8",
    )
    return parent


def test_public_task_contains_only_model_visible_fields() -> None:
    task = QATaskSpec(task_id="qa-001", question="First argument?", category="usage")
    assert sanitize_for_model(task) == {"Question": "First argument?"}


def test_schema_rejects_private_gold_fields() -> None:
    with pytest.raises(ValueError, match="private field"):
        QATaskSpec.from_dict(
            {
                "task_id": "qa-001",
                "Question": "First argument?",
                "category": "usage",
                "Final answer": "no",
            }
        )


def test_external_loader_keeps_gold_private(tmp_path: Path) -> None:
    sample = load_external_questions(_parent(tmp_path))[0]
    assert sample.to_public_task().question == "First argument?"
    assert sample.private_reference().gold == "no"
    assert sample.private_reference().aliases == ("material number",)
    serialized = json.dumps(sanitize_for_model(sample.to_public_task()))
    assert "qa-001" not in serialized
    assert "usage" not in serialized
    assert "Final answer" not in serialized
    assert "material number" not in serialized
    assert "secret/source.py" not in serialized


def test_external_loader_rejects_split_protocol(tmp_path: Path) -> None:
    parent = _parent(tmp_path)
    path = parent / "datasets" / "qa" / "questions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[0]["split"] = "train"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="split"):
        load_external_questions(parent)
