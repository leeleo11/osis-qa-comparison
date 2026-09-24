"""T5: CrewAI native skills, delegation, and file tools. Same policy as the modeling line."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_DISABLE_TRACKING", "true")

from baselines._framework_common import (
    build_prompt,
    finish,
    model_api_settings,
    package_version,
    LIBRARY_LOOP_BOUND,
)
from common.weknora_read import hybrid_search, list_knowledge_bases


ROLE_ORDER = ("researcher", "answerer", "reviewer")
AGENT_POLICY = {"allow_code_execution": False, "allow_delegation": True}
_RESOURCE_ROOTS = ("references", "scripts", "assets")
_SKILL_NAME = re.compile(r"(?m)^name:\s*(?P<name>\S+)\s*$")
Runtime = Callable[[dict[str, Any], str], dict[str, Any]]


def role_blueprint() -> list[dict[str, Any]]:
    return [
        {"id": "researcher", "read_only": True, "goal": "Find exact public evidence."},
        {"id": "answerer", "read_only": False, "goal": "Draft the shortest supported answer."},
        {"id": "reviewer", "read_only": True, "goal": "Verify and emit FINAL ANSWER."},
    ]


def read_skill_resource(skills_dir: Path, skill_name: str, relative_path: str = "") -> str:
    skill_dir = None
    for child in Path(skills_dir).iterdir():
        skill_md = child / "SKILL.md"
        if not child.is_dir() or not skill_md.is_file():
            continue
        if child.name == skill_name:
            skill_dir = child
            break
        match = _SKILL_NAME.search(skill_md.read_text(encoding="utf-8", errors="replace"))
        if match and match.group("name") == skill_name:
            skill_dir = child
            break
    if skill_dir is None:
        return f"Skill {skill_name!r} is not available."
    relative = relative_path.strip().replace("\\", "/")
    if not relative:
        return "No resource files."
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] not in _RESOURCE_ROOTS:
        return "Path must be one file inside references/, scripts/, or assets/."
    target = skill_dir / path
    if not target.is_file():
        return f"File not found: {path.as_posix()}"
    return target.read_text(encoding="utf-8", errors="replace")


def _file_tools(root: Path, *, write: bool) -> list[Any]:
    from crewai_tools import DirectoryReadTool, FileReadTool, FileWriterTool

    tools: list[Any] = [
        DirectoryReadTool(directory=str(root)),
        FileReadTool(base_dir=str(root)),
    ]
    if write:
        tools.append(FileWriterTool(base_dir=str(root)))
    return tools


def _crewai_runtime(request: dict[str, Any], prompt: str) -> dict[str, Any]:
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
        "reasoning_effort": settings["reasoning_effort"],
    }
    if settings["max_tokens"] is not None:
        llm_kwargs["max_tokens"] = settings["max_tokens"]
    llm = LLM(**llm_kwargs)
    skills_dir = Path(request["skills_dir"])
    notes = Path(request["workspace"]) / "t5_notes"
    notes.mkdir(parents=True, exist_ok=True)

    @tool("read_skill_resource")
    def read_skill_resource_tool(skill_name: str, relative_path: str = "") -> str:
        """List or read one resource file. load_skill itself returns only SKILL.md."""

        return read_skill_resource(skills_dir, skill_name, relative_path)

    @tool("list_knowledge_bases")
    def list_knowledge_bases_tool() -> str:
        """List WeKnora knowledge bases. Read-only."""

        return list_knowledge_bases()

    @tool("hybrid_search")
    def hybrid_search_tool(kb_id: str, query: str, match_count: int = 5) -> str:
        """Hybrid-search one WeKnora knowledge base by id or name."""

        return hybrid_search(kb_id, query, match_count)

    resource = [read_skill_resource_tool, list_knowledge_bases_tool, hybrid_search_tool]
    read_tools = [*resource, *_file_tools(skills_dir, write=False)]
    researcher = Agent(
        role="OSIS knowledge researcher",
        goal="Load the mounted skills and find exact public evidence.",
        backstory="Uses the crew load_skill tool. Does not guess.",
        llm=llm,
        tools=read_tools,
        max_iter=LIBRARY_LOOP_BOUND,
        verbose=False,
        **AGENT_POLICY,
    )
    answerer = Agent(
        role="OSIS API answerer",
        goal="Turn the evidence into the shortest FINAL ANSWER.",
        backstory="May write notes with the File Writer Tool. The answer itself is text.",
        llm=llm,
        tools=[*read_tools, *_file_tools(notes, write=True)],
        max_iter=LIBRARY_LOOP_BOUND,
        verbose=False,
        **AGENT_POLICY,
    )
    reviewer = Agent(
        role="Read-only answer reviewer",
        goal="Check the draft and emit one FINAL ANSWER line.",
        backstory="Reads skills and notes. Does not write.",
        llm=llm,
        tools=[*read_tools, *_file_tools(notes, write=False)],
        max_iter=LIBRARY_LOOP_BOUND,
        verbose=False,
        **AGENT_POLICY,
    )
    research_task = Task(
        description="Use load_skill. You may delegate or ask a coworker.\n\n" + prompt,
        expected_output="Concise evidence and a proposed answer.",
        agent=researcher,
    )
    answer_task = Task(
        description="Draft the shortest supported answer.",
        expected_output="A draft ending in FINAL ANSWER.",
        agent=answerer,
        context=[research_task],
    )
    review_task = Task(
        description="Check the draft and return exactly one final answer line.",
        expected_output="FINAL ANSWER: [answer]",
        agent=reviewer,
        context=[research_task, answer_task],
    )
    result = Crew(
        agents=[researcher, answerer, reviewer],
        tasks=[research_task, answer_task, review_task],
        process=Process.sequential,
        verbose=False,
        skills=[skills_dir],
    ).kickoff()
    outputs = list(getattr(result, "tasks_output", None) or [])
    return {
        "final_answer": str(getattr(result, "raw", result)),
        "roles_completed": list(ROLE_ORDER[: len(outputs)]),
        "delegation": True,
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
        "allow_delegation": True,
        "model": request.get("model"),
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        output = (runtime or _crewai_runtime)(request, build_prompt(request))
        metadata.update(output)
        if not str(output.get("final_answer") or "").strip():
            raise RuntimeError("crew returned an empty answer")
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
