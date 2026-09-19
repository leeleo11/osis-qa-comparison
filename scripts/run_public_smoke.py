"""No-network smoke for the public task boundary and T1 adapter."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baselines.t1_direct.adapter import run_generation


def main() -> int:
    workspace = ROOT / "tmp" / "public-smoke" / "run"
    skills = ROOT / "tmp" / "public-smoke" / "knowledge"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / "SMOKE.md").write_text("Synthetic documentation: the answer is smoke-ok.\n", encoding="utf-8")
    request = {
        "task": {"task_id": "qa-smoke", "Question": "Synthetic answer?", "category": "usage"},
        "system_prompt": "Finish with FINAL ANSWER:",
        "skills_dir": str(skills),
        "workspace": str(workspace),
        "model": "offline-smoke",
    }
    result = run_generation(
        request,
        completion=lambda _prompt, _settings: {
            "text": "FINAL ANSWER: smoke-ok",
            "usage": {"total_tokens": 1},
            "finish_reason": "stop",
        },
    )
    print(json.dumps({"status": result["status"], "model_calls": result["model_calls"]}))
    return int(result["status"] != "completed")


if __name__ == "__main__":
    raise SystemExit(main())
