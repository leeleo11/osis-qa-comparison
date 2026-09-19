"""Dispatch one request in-process or through a framework-specific Python."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any


MODULES = {
    "T1": "baselines.t1_direct.adapter",
    "T2": "baselines.t2_langgraph.adapter",
    "T3": "baselines.t3_smolagents.adapter",
    "T4": "baselines.t4_openhands.adapter",
    "T5": "baselines.t5_crewai.adapter",
    "T6": "baselines.t6_osisai.adapter",
}


def dispatch_generation(request: dict[str, Any]) -> dict[str, Any]:
    architecture = str(request["architecture_id"]).upper()
    try:
        module_name = MODULES[architecture]
    except KeyError as exc:
        raise ValueError(f"unknown architecture: {architecture}") from exc
    python_executable = (request.get("framework_pythons") or {}).get(architecture)
    if python_executable:
        workspace = Path(request["workspace"])
        request_path = workspace / "adapter_request.json"
        serializable = {key: value for key, value in request.items() if key != "framework_pythons"}
        request_path.write_text(
            json.dumps(serializable, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [str(python_executable), "-m", module_name, "--request", str(request_path)],
            cwd=str(Path(__file__).resolve().parents[1]),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=float(
                request.get("generation_timeout_s") or request.get("total_timeout_s") or 1800
            ),
        )
        if completed.returncode != 0:
            raise RuntimeError(f"adapter process failed: {completed.stderr[-1000:]}")
        record = workspace / f"{architecture.lower()}_generation.json"
        if not record.is_file():
            raise RuntimeError(f"adapter did not write {record.name}")
        return json.loads(record.read_text(encoding="utf-8"))
    module = __import__(module_name, fromlist=["run_generation"])
    return module.run_generation(request)
