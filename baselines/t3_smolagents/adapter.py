"""T3: smolagents CodeAgent with bounded knowledge tools."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from baselines._framework_common import (
    KnowledgeTools,
    build_prompt,
    finish,
    model_api_settings,
    package_version,
    resolve_max_steps,
)


Runtime = Callable[[dict[str, Any], str, KnowledgeTools], dict[str, Any]]


def _smolagents_runtime(request: dict[str, Any], prompt: str, tools: KnowledgeTools) -> dict[str, Any]:
    from smolagents import CodeAgent, LogLevel, OpenAIServerModel, tool

    settings = model_api_settings(request)
    kwargs: dict[str, Any] = {
        "model_id": settings["model"],
        "api_base": settings["base_url"],
        "api_key": settings["api_key"],
        "client_kwargs": {"timeout": settings["timeout"], "max_retries": 2},
        "temperature": settings["temperature"],
        "seed": settings["seed"],
    }
    if settings["max_tokens"] is not None:
        kwargs["max_tokens"] = settings["max_tokens"]
    agent = CodeAgent(
        tools=[tool(function) for function in tools.functions()],
        model=OpenAIServerModel(**kwargs),
        max_steps=resolve_max_steps(request.get("max_steps")),
        verbosity_level=LogLevel.ERROR,
        additional_authorized_imports=[],
        return_full_result=True,
    )
    result = agent.run(prompt)
    steps = list(getattr(result, "steps", None) or [])
    return {
        "final_answer": str(getattr(result, "output", result)),
        "agent_state": str(getattr(result, "state", "success")),
        "model_calls": len(steps),
        "tool_calls": sum(len(getattr(step, "tool_calls", None) or []) for step in steps),
        "framework_steps": len(steps),
    }


def run_generation(request: dict[str, Any], *, runtime: Runtime | None = None) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T3",
        "framework": "smolagents",
        "framework_version": package_version("smolagents"),
        "interaction_mode": "codeact",
        "model": request.get("model"),
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        output = (runtime or _smolagents_runtime)(request, build_prompt(request), KnowledgeTools(request))
        metadata.update(output)
        failed = str(output.get("agent_state", "")).casefold() == "max_steps_error"
        if not str(output.get("final_answer") or "").strip():
            failed = True
        metadata.update(status="failed" if failed else "completed", stop_reason="max_steps" if failed else "completed")
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T3", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
