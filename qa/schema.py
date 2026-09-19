"""Public model-visible QA task contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


PRIVATE_FIELDS = frozenset(
    {"Final answer", "final_answer", "gold", "aliases", "source", "answer"}
)
VALID_CATEGORIES = frozenset({"usage", "hallucination", "template"})


@dataclass(frozen=True, slots=True)
class QATaskSpec:
    task_id: str
    question: str
    category: str
    protocol_version: str = "qa-gaia-v1"
    total_timeout_s: int = 1800

    def __post_init__(self) -> None:
        if not self.task_id.startswith("qa-"):
            raise ValueError("task_id must start with qa-")
        if not self.question.strip():
            raise ValueError("Question must not be empty")
        if self.category not in VALID_CATEGORIES:
            raise ValueError(f"unknown QA category: {self.category}")
        if self.total_timeout_s <= 0:
            raise ValueError("total_timeout_s must be positive")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "QATaskSpec":
        exposed_private = PRIVATE_FIELDS.intersection(value)
        if exposed_private:
            raise ValueError(f"private field is forbidden in public task: {sorted(exposed_private)}")
        return cls(
            task_id=str(value.get("task_id") or "").strip(),
            question=str(value.get("Question", value.get("question", ""))).strip(),
            category=str(value.get("category") or "").strip(),
            protocol_version=str(value.get("protocol_version") or "qa-gaia-v1"),
            total_timeout_s=int(value.get("total_timeout_s") or 1800),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "task_id": self.task_id,
            "Question": self.question,
            "category": self.category,
            "total_timeout_s": self.total_timeout_s,
        }
