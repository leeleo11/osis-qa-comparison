"""T4: OpenHands Conversation with native progressive AgentSkills."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")

from baselines._framework_common import (
    KnowledgeTools,
    finish,
    model_visible_task,
    model_api_settings,
    package_version,
    resolve_max_steps,
)


T4_CUSTOM_TOOL_NAMES = ("list_knowledge_files", "search_knowledge", "read_knowledge_file")


class ReferenceKnowledgeTools(KnowledgeTools):
    """Reference access that leaves SKILL.md disclosure to InvokeSkillTool."""

    def _files(self) -> list[str]:
        return [
            relative
            for relative in self.reader.list_files()
            if Path(relative).name.casefold() != "skill.md"
        ]

    def list_knowledge_files(self) -> str:
        """List mounted public reference files, excluding skill bodies, as JSON."""
        return json.dumps(self._files(), ensure_ascii=False)

    def search_knowledge(self, query: str) -> str:
        """Search mounted reference files without disclosing skill bodies."""
        terms = [term.casefold() for term in query.split() if term.strip()]
        if not terms:
            return "[]"
        matches: list[dict[str, object]] = []
        for relative in self._files():
            try:
                lowered = self.reader.read_file(relative).casefold()
            except (OSError, UnicodeError, ValueError):
                continue
            score = sum(lowered.count(term) for term in terms)
            if score:
                matches.append({"path": relative, "score": score})
        selected = sorted(
            matches, key=lambda item: (-int(item["score"]), str(item["path"]))
        )[:20]
        return json.dumps(selected, ensure_ascii=False)

    def read_knowledge_file(self, relative_path: str) -> str:
        """Read one mounted public reference file, excluding every SKILL.md."""
        if Path(relative_path).name.casefold() == "skill.md":
            return "TOOL_ERROR: SKILL.md must be loaded with native invoke_skill"
        return super().read_knowledge_file(relative_path)


Runtime = Callable[[dict[str, Any], str, ReferenceKnowledgeTools, list[Any]], dict[str, Any]]


def _load_native_skills(skills_dir: Path, loader: Callable[[Path], Any] | None = None) -> list[Any]:
    if loader is None:
        from openhands.sdk.skills import load_skills_from_dir

        loader = load_skills_from_dir
    groups = loader(Path(skills_dir))
    result: list[Any] = []
    for group in groups:
        if isinstance(group, dict):
            result.extend(group.values())
    return result


def build_t4_prompt(request: dict[str, Any]) -> str:
    return (
        str(request.get("system_prompt") or "").strip()
        + "\n\nUse the native invoke_skill tool (OpenHands InvokeSkillTool) first to load the "
        "relevant OSIS AgentSkill. Search or read its mounted public references only when needed. "
        "Answer the question and finish with exactly one concise FINAL ANSWER line.\n\nQuestion:\n"
        + model_visible_task(request)["Question"]
    ).strip()


def _expose(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
    function: Callable[..., str],
) -> Any:
    from openhands.sdk import Tool
    from openhands.sdk.tool import Action, Observation, ToolDefinition, ToolExecutor, register_tool

    action_type = Action.from_mcp_schema(
        f"{name}_action",
        {"type": "object", "properties": properties, "required": required},
    )

    class HarnessObservation(Observation):
        """Bounded harness tool output."""

    class Executor(ToolExecutor):
        def __call__(self, action, conversation=None):  # noqa: ANN001
            arguments = {key: value for key, value in action.model_dump().items() if key in properties}
            try:
                return HarnessObservation.from_text(text=str(function(**arguments)))
            except Exception as exc:  # noqa: BLE001
                return HarnessObservation.from_text(
                    text=f"TOOL_ERROR: {type(exc).__name__}: {exc}", is_error=True
                )

    class Definition(ToolDefinition[action_type, HarnessObservation]):
        @classmethod
        def create(cls, conv_state=None, **kwargs):  # noqa: ANN001
            return [
                cls(
                    description=description,
                    action_type=action_type,
                    observation_type=HarnessObservation,
                    executor=Executor(),
                )
            ]

    Definition.name = name
    definition = Definition.create()[0]
    register_tool(name, definition)
    return Tool(name=name)


def _event_summary(events: list[Any]) -> tuple[list[dict[str, Any]], int, int, list[str]]:
    trace: list[dict[str, Any]] = []
    response_ids: set[str] = set()
    tool_calls = 0
    invoked: list[str] = []
    for event in events:
        response_id = getattr(event, "llm_response_id", None)
        if response_id:
            response_ids.add(str(response_id))
        tool_name = str(getattr(event, "tool_name", None) or "")
        if type(event).__name__ == "ActionEvent" or tool_name:
            tool_calls += 1
        if tool_name.casefold() in {"invoke_skill", "invokeskilltool"}:
            action = getattr(event, "action", None)
            name = str(getattr(action, "name", "") or getattr(action, "skill_name", "") or "")
            if name:
                invoked.append(name)
        trace.append(
            {
                "kind": type(event).__name__,
                "tool_name": tool_name,
                "llm_response_id": str(response_id or ""),
            }
        )
    return trace, len(response_ids) or int(bool(events)), tool_calls, invoked


def _openhands_runtime(
    request: dict[str, Any],
    prompt: str,
    tools: ReferenceKnowledgeTools,
    native_skills: list[Any],
) -> dict[str, Any]:
    from openhands.sdk import Agent, AgentContext, Conversation, LLM
    from openhands.sdk.conversation import get_agent_final_response

    settings = model_api_settings(request)
    llm_kwargs: dict[str, Any] = {
        "model": f"openai/{settings['model']}",
        "base_url": settings["base_url"],
        "api_key": settings["api_key"],
        "timeout": int(settings["timeout"]),
        "num_retries": 2,
        "api_mode": "chat",
        "temperature": settings["temperature"],
        "seed": settings["seed"],
        "usage_id": "t4-qa",
    }
    if settings["max_tokens"] is not None:
        llm_kwargs["max_output_tokens"] = settings["max_tokens"]
    exposed = [
        _expose("list_knowledge_files", "List mounted public knowledge files.", {}, [], tools.list_knowledge_files),
        _expose(
            "search_knowledge",
            "Search mounted public OSIS knowledge.",
            {"query": {"type": "string"}},
            ["query"],
            tools.search_knowledge,
        ),
        _expose(
            "read_knowledge_file",
            "Read one mounted public knowledge file.",
            {"relative_path": {"type": "string"}},
            ["relative_path"],
            tools.read_knowledge_file,
        ),
    ]
    agent = Agent(
        llm=LLM(**llm_kwargs),
        tools=exposed,
        agent_context=AgentContext(
            skills=native_skills,
            load_user_skills=False,
            load_public_skills=False,
            load_project_skills=False,
            load_memory=False,
        ),
    )
    workspace = Path(request["workspace"]) / "t4_conversation"
    workspace.mkdir(parents=True, exist_ok=True)
    conversation = Conversation(
        agent=agent,
        workspace=str(workspace),
        max_iteration_per_run=resolve_max_steps(request.get("max_steps")),
        visualizer=None,
        delete_on_close=False,
        stuck_detection_thresholds={
            "action_observation": 16,
            "action_error": 8,
            "monologue": 8,
            "alternating_pattern": 24,
        },
    )
    try:
        conversation.send_message(prompt)
        conversation.run()
        events = list(getattr(conversation.state, "events", []) or [])
        trace, model_calls, tool_calls, invoked = _event_summary(events)
        status = str(getattr(conversation.state, "execution_status", ""))
        return {
            "final_answer": get_agent_final_response(events) or "",
            "execution_status": status,
            "model_calls": model_calls,
            "tool_calls": tool_calls,
            "framework_steps": len(events),
            "native_skill_invocations": invoked,
            "events": trace,
        }
    finally:
        conversation.close()


def run_generation(
    request: dict[str, Any],
    *,
    runtime: Runtime | None = None,
    skill_loader: Callable[[Path], Any] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T4",
        "framework": "openhands",
        "framework_version": package_version("openhands-sdk"),
        "interaction_mode": "codeact",
        "skill_loading": "openhands_native_progressive",
        "native_skill_count": 0,
        "model": request.get("model"),
        "model_calls": 0,
        "tool_calls": 0,
        "framework_steps": 0,
        "status": "failed",
    }
    try:
        native = _load_native_skills(Path(request["skills_dir"]), loader=skill_loader)
        metadata["native_skill_count"] = len(native)
        output = (runtime or _openhands_runtime)(
            request, build_t4_prompt(request), ReferenceKnowledgeTools(request), native
        )
        metadata.update(output)
        execution = str(output.get("execution_status", "")).upper()
        failed = "ERROR" in execution or "STUCK" in execution or not str(output.get("final_answer") or "").strip()
        metadata.update(status="failed" if failed else "completed", stop_reason=execution.lower() or "completed")
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T4", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
