"""T2: LangGraph create_agent with streamed ReAct knowledge use."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from baselines._framework_common import (
    KnowledgeTools,
    build_prompt,
    finish,
    model_api_settings,
    LIBRARY_LOOP_BOUND,
    package_version,
)


Runtime = Callable[[dict[str, Any], str, KnowledgeTools], dict[str, Any]]


def _langgraph_runtime(request: dict[str, Any], prompt: str, tools: KnowledgeTools) -> dict[str, Any]:
    from langchain.agents import create_agent
    from langchain_core.tools import StructuredTool
    from langchain_openai import ChatOpenAI

    settings = model_api_settings(request)
    kwargs: dict[str, Any] = {
        "model": settings["model"],
        "base_url": settings["base_url"],
        "api_key": settings["api_key"],
        "temperature": settings["temperature"],
        "seed": settings["seed"],
        "timeout": settings["timeout"],
    }
    if settings["max_tokens"] is not None:
        kwargs["max_tokens"] = settings["max_tokens"]
    agent = create_agent(
        model=ChatOpenAI(**kwargs),
        tools=[StructuredTool.from_function(function) for function in tools.functions()],
    )
    seen = 0
    model_calls = 0
    tool_calls = 0
    final = ""
    trace: list[dict[str, Any]] = []
    for state in agent.stream(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"recursion_limit": LIBRARY_LOOP_BOUND},
        stream_mode="values",
    ):
        messages = list(state.get("messages") or []) if isinstance(state, dict) else []
        for message in messages[seen:]:
            kind = type(message).__name__
            content = str(getattr(message, "content", "") or "")
            calls = list(getattr(message, "tool_calls", None) or [])
            if kind == "AIMessage":
                model_calls += 1
                final = content or final
            elif kind == "ToolMessage":
                tool_calls += 1
            trace.append({"kind": kind, "tool_names": [call.get("name", "") for call in calls if isinstance(call, dict)]})
        seen = max(seen, len(messages))
    return {"final_answer": final, "model_calls": model_calls, "tool_calls": tool_calls, "trace": trace}


def run_generation(request: dict[str, Any], *, runtime: Runtime | None = None) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T2",
        "framework": "langgraph",
        "framework_version": package_version("langgraph"),
        "interaction_mode": "react",
        "model": request.get("model"),
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        metadata.update((runtime or _langgraph_runtime)(request, build_prompt(request), KnowledgeTools(request)))
        if not str(metadata.get("final_answer") or "").strip():
            raise RuntimeError("LangGraph returned no final answer")
        metadata.update(status="completed", stop_reason="completed")
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T2", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
