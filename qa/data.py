"""Load the external parent dataset while keeping gold fields private."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .schema import QATaskSpec


@dataclass(frozen=True, slots=True)
class PrivateAnswer:
    gold: str
    aliases: tuple[str, ...] = ()
    source: str = ""

    def __post_init__(self) -> None:
        if not self.gold.strip():
            raise ValueError("private gold answer must not be empty")


@dataclass(frozen=True, slots=True)
class ExternalQuestion:
    public: QATaskSpec
    private: PrivateAnswer

    @property
    def task_id(self) -> str:
        return self.public.task_id

    def to_public_task(self) -> QATaskSpec:
        return self.public

    def private_reference(self) -> PrivateAnswer:
        return self.private


def _item(value: Any) -> ExternalQuestion:
    if not isinstance(value, dict):
        raise ValueError("each QA question must be an object")
    if any(str(key).lower() == "split" for key in value):
        raise ValueError("QA protocol is all-test and must not contain a split field")
    public = QATaskSpec(
        task_id=str(value.get("task_id") or "").strip(),
        question=str(value.get("Question") or "").strip(),
        category=str(value.get("category") or "").strip(),
    )
    aliases = value.get("aliases") or []
    if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
        raise ValueError(f"{public.task_id}: aliases must be a list of strings")
    private = PrivateAnswer(
        gold=str(value.get("Final answer") or "").strip(),
        aliases=tuple(alias.strip() for alias in aliases if alias.strip()),
        source=str(value.get("source") or "").strip(),
    )
    return ExternalQuestion(public=public, private=private)


def load_external_questions(
    parent_repo: str | Path,
    questions_path: str | Path | None = None,
) -> list[ExternalQuestion]:
    parent = Path(parent_repo).resolve()
    path = (
        Path(questions_path).expanduser().resolve()
        if questions_path is not None
        else parent / "datasets" / "qa" / "questions.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"questions file must be a JSON array: {path}")
    questions = [_item(value) for value in payload]
    ids = [question.task_id for question in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate QA task_id")
    return questions


def load_system_prompt(parent_repo: str | Path, path: str | Path | None = None) -> str:
    parent = Path(parent_repo).resolve()
    source = (
        Path(path).expanduser().resolve()
        if path is not None
        else parent / "datasets" / "qa" / "system_prompt.txt"
    )
    text = source.read_text(encoding="utf-8").strip()
    if "FINAL ANSWER:" not in text:
        raise ValueError("QA system prompt must require FINAL ANSWER:")
    return text
