"""T6 calls the parent QA agent. It does not rebuild the parent's files."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

from baselines._framework_common import finish, model_visible_task


def parent_chat(request: dict[str, Any]) -> dict[str, Any]:
    """Call datasets/qa/run_eval.py chat_via_agent on the parent's OpenCode."""

    import importlib.util
    from types import SimpleNamespace

    parent = Path(str(request.get("parent_repo") or os.environ.get("OSIS_PARENT_REPO") or ""))
    path = parent / "datasets" / "qa" / "run_eval.py"
    if not path.is_file():
        raise FileNotFoundError(f"parent QA runner is missing: {path}")
    spec = importlib.util.spec_from_file_location("parent_qa_run_eval", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load parent QA runner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    item = {"task_id": request.get("task_id") or request["task"]["task_id"]}
    args = SimpleNamespace(
        opencode_url=str(request.get("opencode_url") or ""),
        model=request["model"],
        provider=str(request.get("provider") or "osisapi"),
        variant=request.get("variant") or "",
        timeout=float(request.get("generation_timeout_s") or 1800),
    )
    return module.chat_via_agent(
        args,
        item,
        str(request.get("system_prompt") or ""),
        str(model_visible_task(request)["Question"]),
    )


def run_generation(request: dict[str, Any], *, chat: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T6",
        "framework": "osis-ai-native",
        "interaction_mode": "parent_session",
        "skill_loading": "parent_repo",
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        output = (chat or parent_chat)(request)
        answer = str(output.get("raw") or output.get("final_answer") or "").strip()
        if not answer:
            raise RuntimeError("OSIS-AI returned no final answer")
        usage = output.get("usage") or {}
        metadata.update(
            final_answer=answer,
            model_calls=int(output.get("model_calls") or usage.get("model_calls") or 0),
            tool_calls=int(output.get("tool_calls") or 0),
            tokens=usage or output.get("tokens"),
            latency_s=output.get("latency_s"),
            status="completed",
            stop_reason="completed",
        )
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T6", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
