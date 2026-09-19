"""T6: native OpenCode/OSIS-AI session in a per-run isolated project."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from baselines._framework_common import finish, model_visible_task


Runtime = Callable[[dict[str, Any], Path, str, dict[str, str]], dict[str, Any]]


def build_agent_prompt(request: dict[str, Any]) -> str:
    return (
        str(request.get("system_prompt") or "").strip()
        + "\n\nFollow the native AGENTS.md workflow and use mounted AgentSkills progressively. "
        "Use only public knowledge, answer the question, and finish with exactly one concise "
        "FINAL ANSWER line.\n\nQuestion:\n"
        + model_visible_task(request)["Question"]
    ).strip()


def prepare_isolated_env(
    isolated: str | Path,
    skills_src: str | Path,
    base_url: str,
    *,
    model: str,
    seed: int = 0,
    max_steps: int = 80,
    agents_source: str | Path | None = None,
) -> dict[str, str]:
    root = Path(isolated).resolve()
    skills = Path(skills_src).resolve()
    root.mkdir(parents=True, exist_ok=True)
    agents = root / ".agents"
    agents.mkdir(parents=True, exist_ok=True)
    skills_dst = agents / "skills"
    if skills_dst.exists():
        shutil.rmtree(skills_dst)
    shutil.copytree(skills, skills_dst)
    instructions = agents / "AGENTS.md"
    if agents_source is not None:
        source = Path(agents_source).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"native OSIS-AI instructions are missing: {source}")
        shutil.copy2(source, instructions)
    else:
        instructions.write_text(
            "Use mounted AgentSkills progressively and follow the native OSIS-AI workflow.\n",
            encoding="utf-8",
        )
    experiment_instructions = agents / "QA_EXPERIMENT.md"
    experiment_instructions.write_text(
        "Use only the mounted AgentSkills and their public references. "
        "Never inspect datasets, evaluator code, other runs, user-level skills, or hidden answers. "
        "Research the public question and finish with exactly one concise FINAL ANSWER line.\n",
        encoding="utf-8",
    )
    config = {
        "$schema": "https://opencode.ai/config.json",
        "instructions": [str(instructions), str(experiment_instructions)],
        "model": f"comparison/{model}",
        "default_agent": "build",
        "agent": {
            "build": {
                "model": f"comparison/{model}",
                "temperature": 0.0,
                "steps": max(1, int(max_steps)),
                "options": {"seed": int(seed)},
            }
        },
        "provider": {
            "comparison": {
                "npm": "@ai-sdk/openai-compatible",
                "options": {"baseURL": str(base_url).rstrip("/"), "apiKey": "{env:OSIS_MODEL_API_KEY}"},
                "models": {model: {"name": model, "options": {"seed": int(seed)}}},
            }
        },
        "permission": {
            "*": "allow",
            "external_directory": "deny",
            "bash": "deny",
            "edit": "deny",
        },
    }
    (agents / "opencode.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    for key in tuple(env):
        normalized = key.upper()
        if normalized == "OSIS_MODEL_API_KEY":
            continue
        if normalized.endswith("_API_KEY") or normalized in {
            "OSIS_PARENT_REPO",
            "GITHUB_TOKEN",
            "GH_TOKEN",
            "QA_GOLD_PATH",
            "QA_DATASET_PATH",
        }:
            env.pop(key, None)
    env.update(
        {
            "OPENCODE_CONFIG_DIR": str(agents),
            "OPENCODE_DISABLE_AUTOUPDATE": "1",
            "XDG_CONFIG_HOME": str(root / "xdg-config"),
            "XDG_DATA_HOME": str(root / "xdg-data"),
            "XDG_CACHE_HOME": str(root / "xdg-cache"),
            "XDG_STATE_HOME": str(root / "xdg-state"),
        }
    )
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    for variable in ("NO_PROXY", "no_proxy"):
        current = {item.strip() for item in env.get(variable, "").split(",") if item.strip()}
        env[variable] = ",".join(sorted(current | local_hosts))
    for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        Path(env[key]).mkdir(parents=True, exist_ok=True)
    return env


def _wait_healthy(base_url: str, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{base_url}/global/health", timeout=2).status_code == 200:
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    raise RuntimeError("isolated OpenCode server did not become healthy")


def _native_runtime(
    request: dict[str, Any],
    project: Path,
    prompt: str,
    env: dict[str, str],
) -> dict[str, Any]:
    executable = request.get("opencode_executable") or os.environ.get("OPENCODE_EXE") or "opencode"
    port = int(request.get("t6_port") or os.environ.get("T6_AI_PORT", "4097"))
    server_url = f"http://127.0.0.1:{port}"
    log_path = Path(request["workspace"]) / "opencode_server.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [str(executable), "serve", "--port", str(port)],
            cwd=str(project),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            _wait_healthy(server_url, min(90.0, float(request.get("request_timeout_s", 90))))
            parent = request.get("parent_repo") or os.environ.get("OSIS_PARENT_REPO")
            if parent:
                parent_src = str(Path(parent) / "src")
                if parent_src not in sys.path:
                    sys.path.insert(0, parent_src)
            from opencode_client import OpencodeClient, QuestionMonitor, extract_stats, extract_text

            client = OpencodeClient(
                base_url=server_url,
                timeout=float(request.get("generation_timeout_s", 1800)),
            )
            session = client.create_session(f"qa:{request['task_id']}")
            monitor = QuestionMonitor(client, session, strategy="first", poll_interval=1.0)
            monitor.start()
            try:
                message = client.chat(
                    session,
                    prompt,
                    provider_id="comparison",
                    model_id=request["model"],
                    timeout=float(request.get("generation_timeout_s", 1800)),
                    variant=request.get("variant") or None,
                )
            finally:
                monitor.stop()
                try:
                    client.delete_session(session)
                except Exception:  # noqa: BLE001
                    pass
            stats = extract_stats(message)
            return {
                "final_answer": extract_text(message),
                "model_calls": int(stats.get("model_calls") or 0),
                "tool_calls": int(stats.get("tool_calls") or 0),
                "tokens": stats,
            }
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def run_generation(request: dict[str, Any], *, runtime: Runtime | None = None) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T6",
        "framework": "osis-ai-native",
        "interaction_mode": "native_stateful",
        "skill_loading": "isolated_native",
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        project = Path(request["workspace"]) / "t6_isolated_project"
        agents_source = request.get("osis_agents_file")
        if not agents_source and request.get("parent_repo"):
            agents_source = str(Path(request["parent_repo"]) / ".agents" / "AGENTS.md")
        env = prepare_isolated_env(
            project,
            request["skills_dir"],
            request.get("base_url", ""),
            model=request["model"],
            seed=int(request.get("seed", 0)),
            max_steps=int(request.get("max_steps", 80)),
            agents_source=agents_source,
        )
        output = (runtime or _native_runtime)(request, project, build_agent_prompt(request), env)
        metadata.update(output)
        if not str(output.get("final_answer") or "").strip():
            raise RuntimeError("OSIS-AI returned no final answer")
        metadata.update(status="completed", stop_reason="completed")
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T6", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
