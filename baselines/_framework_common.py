"""Shared helpers used inside isolated T1-T5 framework processes."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import time
from pathlib import Path
from typing import Any

from common.skill_adapter import SkillAdapter


def load_request(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    args = parser.parse_args(argv)
    return json.loads(Path(args.request).read_text(encoding="utf-8"))


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def resolve_max_steps(value: object, *, default: int = 80) -> int:
    try:
        steps = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return steps if steps > 0 else default


def resolve_max_tokens(value: object) -> int | None:
    try:
        tokens = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return tokens if tokens > 0 else None


def model_visible_task(request: dict[str, Any]) -> dict[str, str]:
    task = request.get("task")
    if not isinstance(task, dict):
        raise ValueError("request task must be an object")
    question = str(task.get("Question") or "").strip()
    if not question:
        raise ValueError("request task must contain Question")
    return {"Question": question}


def build_prompt(request: dict[str, Any]) -> str:
    return (
        (str(request.get("system_prompt") or "").strip())
        + "\n\nAnswer the following OSIS API question. Use only the mounted public knowledge. "
        "Do not inspect datasets, evaluator files, other runs, or hidden answers. "
        "Research as needed, then end with exactly one concise FINAL ANSWER line.\n\nQuestion:\n"
        + model_visible_task(request)["Question"]
    ).strip()


class KnowledgeTools:
    """Identical bounded read-only knowledge capability for generic agents."""

    def __init__(self, request: dict[str, Any]) -> None:
        self.reader = SkillAdapter(Path(request["skills_dir"]))

    def list_knowledge_files(self) -> str:
        """List every mounted public knowledge file as JSON."""
        return json.dumps(self.reader.list_files(), ensure_ascii=False)

    def search_knowledge(self, query: str) -> str:
        """Search mounted knowledge and return ranked file paths.

        Args:
            query: Space-separated API names or concepts.
        """
        try:
            return json.dumps(self.reader.search(query), ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return f"TOOL_ERROR: {type(exc).__name__}: {exc}"

    def read_knowledge_file(self, relative_path: str) -> str:
        """Read one mounted public knowledge file.

        Args:
            relative_path: Exact path returned by list/search.
        """
        try:
            return self.reader.read_file(relative_path)
        except Exception as exc:  # noqa: BLE001
            return f"TOOL_ERROR: {type(exc).__name__}: {exc}"

    def functions(self) -> list[Any]:
        return [self.list_knowledge_files, self.search_knowledge, self.read_knowledge_file]


def model_api_settings(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": request["model"],
        "base_url": request.get("base_url") or os.environ.get("OSIS_MODEL_BASE_URL", ""),
        "api_key": request.get("api_key") or os.environ.get("OSIS_MODEL_API_KEY", ""),
        "temperature": float(request.get("temperature", 0.0)),
        "seed": int(request.get("seed", 0)),
        "timeout": float(request.get("request_timeout_s", 180.0)),
        "max_tokens": resolve_max_tokens(request.get("max_output_tokens", request.get("max_tokens"))),
    }


def normalize_tokens(value: Any) -> dict[str, int]:
    if not value:
        return {}
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, dict):
        return {}
    aliases = {
        "prompt_tokens": ("prompt_tokens", "input_tokens"),
        "completion_tokens": ("completion_tokens", "output_tokens"),
        "total_tokens": ("total_tokens",),
    }
    result: dict[str, int] = {}
    for target, keys in aliases.items():
        for key in keys:
            raw = value.get(key)
            if isinstance(raw, (int, float)):
                result[target] = int(raw)
                break
    if "total_tokens" not in result and result:
        result["total_tokens"] = result.get("prompt_tokens", 0) + result.get("completion_tokens", 0)
    return result


def finish(
    workspace: str | Path,
    architecture_id: str,
    metadata: dict[str, Any],
    started: float,
) -> dict[str, Any]:
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    result = dict(metadata)
    result.setdefault("architecture_id", architecture_id)
    result["elapsed_s"] = max(0.0, time.monotonic() - started)
    (root / f"{architecture_id.lower()}_generation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result
