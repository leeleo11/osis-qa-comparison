"""T1: one model request with a deterministic fixed knowledge bundle."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

import requests

from baselines._framework_common import (
    finish,
    model_visible_task,
    model_api_settings,
    normalize_tokens,
)
from common.skill_adapter import SkillAdapter


Completion = Callable[[str, dict[str, object]], dict[str, object]]


def build_t1_prompt(request: dict[str, Any]) -> str:
    reader = SkillAdapter(request["skills_dir"])
    return (
        str(request.get("system_prompt") or "").strip()
        + "\n\nYou are T1, the direct one-shot baseline. You have one response and no tools. "
        "Use the fixed public knowledge bundle below, answer the public question, and finish with "
        "exactly one concise FINAL ANSWER line.\n\nQuestion:\n"
        + model_visible_task(request)["Question"]
        + "\n\nPUBLIC KNOWLEDGE SNAPSHOT:\n"
        + reader.fixed_bundle_text()
    )


def _http_completion(prompt: str, settings: dict[str, object]) -> dict[str, object]:
    base_url = str(settings["base_url"]).rstrip("/")
    headers = {"Content-Type": "application/json"}
    if settings.get("api_key"):
        headers["Authorization"] = f"Bearer {settings['api_key']}"
    payload: dict[str, object] = {
        "model": settings["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": settings["temperature"],
        "seed": settings["seed"],
    }
    if settings.get("max_tokens") is not None:
        payload["max_tokens"] = settings["max_tokens"]
    response = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=float(settings["timeout"]),
    )
    response.raise_for_status()
    body = response.json()
    choice = body["choices"][0]
    message = choice.get("message") or {}
    return {
        "text": message.get("content") or message.get("reasoning_content") or "",
        "usage": body.get("usage") or {},
        "finish_reason": choice.get("finish_reason"),
    }


def run_generation(request: dict[str, Any], *, completion: Completion | None = None) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T1",
        "framework": "direct-one-shot",
        "interaction_mode": "one_shot",
        "model": request.get("model"),
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        metadata["model_calls"] = 1
        response = (completion or _http_completion)(build_t1_prompt(request), model_api_settings(request))
        text = str(response.get("text") or "").strip()
        if not text:
            raise RuntimeError("model returned an empty answer")
        metadata.update(
            status="completed",
            final_answer=text,
            tokens=normalize_tokens(response.get("usage")),
            stop_reason=response.get("finish_reason") or "completed",
        )
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T1", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
