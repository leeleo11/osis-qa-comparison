"""Serialization gate for every model or framework request."""

from __future__ import annotations

from typing import Any

from .schema import QATaskSpec


def sanitize_for_model(task: QATaskSpec) -> dict[str, Any]:
    if not isinstance(task, QATaskSpec):
        raise TypeError("sanitize_for_model accepts QATaskSpec only")
    return {"Question": task.question}
