"""T5: sequential researcher, answerer, and read-only reviewer roles."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_DISABLE_TRACKING", "true")

from baselines._framework_common import (
    KnowledgeTools,
    build_prompt,
    finish,
    model_api_settings,
    package_version,
    resolve_max_steps,
)


ROLE_ORDER = ("researcher", "answerer", "reviewer")
Runtime = Callable[[dict[str, Any], str, KnowledgeTools], dict[str, Any]]


def role_blueprint() -> list[dict[str, Any]]:
    return [
        {"id": "researcher", "read_only": True, "goal": "Find exact public evidence."},
        {"id": "answerer", "read_only": True, "goal": "Draft the shortest supported answer."},
        {"id": "reviewer", "read_only": True, "goal": "Verify and emit FINAL ANSWER."},
    ]


def allocate_model_calls(max_steps: int) -> tuple[int, int, int]:
    total = max(3, int(max_steps))
    base, remainder = divmod(total, 3)
    return tuple(base + int(index < remainder) for index in range(3))  # type: ignore[return-value]


def _crewai_runtime(request: dict[str, Any], prompt: str, tools: KnowledgeTools) -> dict[str, Any]:
    from crewai import Agent, Crew, Process, Task
    from crewai.llm import LLM
    from crewai.tools import tool

    settings = model_api_settings(request)
    llm_kwargs: dict[str, Any] = {
        "model": settings["model"],
        "base_url": settings["base_url"],
        "api_key": settings["api_key"],
        "custom_openai": True,
        "timeout": settings["timeout"],
        "temperature": settings["temperature"],
        "seed": settings["seed"],
    }
    if settings["max_tokens"] is not None:
        llm_kwargs["max_tokens"] = settings["max_tokens"]
    llm = LLM(**llm_kwargs)
    budgets = allocate_model_calls(resolve_max_steps(request.get("max_steps")))
    tool_defs = [tool(function) for function in tools.functions()]
    policy = {
        "llm": llm,
        "tools": tool_defs,
        "allow_delegation": False,
        "allow_code_execution": False,
        "verbose": False,
    }
    researcher = Agent(
        role="OSIS knowledge researcher",
        goal="Find exact API or template evidence in mounted public knowledge.",
        backstory="A careful documentation researcher who does not guess.",
        max_iter=budgets[0],
        **policy,
    )
    answerer = Agent(
        role="OSIS API answerer",
        goal="Turn evidence into the shortest answer allowed by the protocol.",
        backstory="An API specialist who follows the requested answer format.",
        max_iter=budgets[1],
        **policy,
    )
    reviewer = Agent(
        role="Read-only answer reviewer",
        goal="Verify the draft against public knowledge and emit one FINAL ANSWER line.",
        backstory="An independent reviewer with no hidden-answer access.",
        max_iter=budgets[2],
        **policy,
    )
    research_task = Task(
        description="Research the public question and cite exact mounted evidence.\n\n" + prompt,
        expected_output="Concise evidence and a proposed answer.",
        agent=researcher,
    )
    answer_task = Task(
        description="Use the research evidence to draft the shortest supported answer.",
        expected_output="A draft ending in FINAL ANSWER.",
        agent=answerer,
        context=[research_task],
    )
    review_task = Task(
        description="Check the draft against public knowledge and return exactly one final answer line.",
        expected_output="FINAL ANSWER: [answer]",
        agent=reviewer,
        context=[research_task, answer_task],
    )
    result = Crew(
        agents=[researcher, answerer, reviewer],
        tasks=[research_task, answer_task, review_task],
        process=Process.sequential,
        verbose=False,
    ).kickoff()
    outputs = list(getattr(result, "tasks_output", None) or [])
    return {
        "final_answer": str(getattr(result, "raw", result)),
        "roles_completed": list(ROLE_ORDER[: len(outputs)]),
        "role_outputs": {
            role: str(output)[-2000:]
            for role, output in zip(ROLE_ORDER, outputs, strict=False)
        },
        "role_budgets": budgets,
        "model_calls": len(outputs),
        "tool_calls": 0,
    }


def run_generation(request: dict[str, Any], *, runtime: Runtime | None = None) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T5",
        "framework": "crewai",
        "framework_version": package_version("crewai"),
        "interaction_mode": "sequential_roles",
        "roles": list(ROLE_ORDER),
        "reviewer_write_access": False,
        "model": request.get("model"),
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        output = (runtime or _crewai_runtime)(request, build_prompt(request), KnowledgeTools(request))
        metadata.update(output)
        if not str(output.get("final_answer") or "").strip():
            raise RuntimeError("CrewAI returned no final answer")
        metadata.update(status="completed", stop_reason="completed")
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T5", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
