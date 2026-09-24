"""T3: smolagents CodeAgent. Knowledge is read with pathlib, not harness tools."""

from __future__ import annotations

import html
import re
import time
from pathlib import Path
from typing import Any, Callable

from baselines._framework_common import (
    finish,
    model_visible_task,
    model_api_settings,
    LIBRARY_LOOP_BOUND,
    package_version,
)


AUTHORIZED_IMPORTS = ["json", "pathlib"]
Runtime = Callable[[dict[str, Any], str], dict[str, Any]]
_DSML_TAG = r"(?:｜｜DSML｜｜|\|DSML\|)"
_DSML_PARAMETER = re.compile(
    rf"<{_DSML_TAG}\s+invoke\s+name=[\"'](?P<invoke>[^\"']+)[\"'][^>]*>"
    rf"\s*<{_DSML_TAG}\s+parameter\s+name=[\"'](?P<parameter>[^\"']+)[\"'][^>]*>"
    rf"(?P<body>.*?)</{_DSML_TAG}\s+parameter>.*?</{_DSML_TAG}\s+invoke>",
    re.DOTALL,
)


def normalize_code_agent_output(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        body = html.unescape(match.group("body")).strip()
        if match.group("invoke") == "code" or match.group("parameter") == "code":
            return f"<code>\n{body}\n</code>"
        return match.group(0)

    return _DSML_PARAMETER.sub(replace, text)


def build_t3_prompt(request: dict[str, Any]) -> str:
    question = model_visible_task(request)["Question"]
    system = str(request.get("system_prompt") or "").strip()
    skills = Path(request["skills_dir"])
    return (
        f"{system}\n\nUse import pathlib to read the mounted knowledge directory. "
        "Each subdirectory that contains SKILL.md is one skill. "
        "Do not read parent datasets, gold answers, or other runs. "
        "Finish with exactly one FINAL ANSWER line.\n\n"
        f"Knowledge directory:\n{skills}\n\nQuestion:\n{question}"
    ).strip()


def _smolagents_runtime(request: dict[str, Any], prompt: str) -> dict[str, Any]:
    from smolagents import CodeAgent, LogLevel, OpenAIServerModel

    class _CodeActCompatibleOpenAIModel(OpenAIServerModel):
        def generate(self, messages, *args, **kwargs):  # type: ignore[no-untyped-def]
            response = super().generate(messages, *args, **kwargs)
            content = getattr(response, "content", None)
            if isinstance(content, str):
                response.content = normalize_code_agent_output(content)
            return response

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
        tools=[],
        model=_CodeActCompatibleOpenAIModel(**kwargs),
        max_steps=LIBRARY_LOOP_BOUND,
        verbosity_level=LogLevel.ERROR,
        additional_authorized_imports=AUTHORIZED_IMPORTS,
        return_full_result=True,
    )
    result = agent.run(prompt)
    steps = list(getattr(result, "steps", None) or [])
    return {
        "final_answer": str(getattr(result, "output", result)),
        "agent_state": str(getattr(result, "state", "success")),
        "authorized_imports": list(AUTHORIZED_IMPORTS),
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
        "authorized_imports": list(AUTHORIZED_IMPORTS),
        "model": request.get("model"),
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        output = (runtime or _smolagents_runtime)(request, build_t3_prompt(request))
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
