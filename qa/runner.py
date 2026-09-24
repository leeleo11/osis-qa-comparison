"""Unified run, scoring, and artifact boundary for all six QA architectures."""

from __future__ import annotations

import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from common.adapters import get_adapter
from common.skill_adapter import SkillAdapter

from .data import ExternalQuestion
from .sanitize import sanitize_for_model
from .score import score_answer


Generator = Callable[[dict[str, Any]], dict[str, Any]]
EFFICIENCY_SCALE_S = 240.0


def _segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-._")
    return cleaned or "run"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dispatch_generation(request: dict[str, Any]) -> dict[str, Any]:
    from common.dispatch import dispatch_generation as dispatch

    return dispatch(request)


class QARunner:
    def __init__(
        self,
        *,
        runs_root: str | Path,
        skills_dir: str | Path,
        system_prompt: str,
        generator: Generator | None = None,
        parent_commit: str = "unknown",
        parent_repo: str | Path | None = None,
        opencode_executable: str | Path | None = None,
        osis_agents_file: str | Path | None = None,
        base_url: str = "",
        framework_pythons: dict[str, str | Path] | None = None,
    ) -> None:
        self.runs_root = Path(runs_root).resolve()
        self.skills_dir = Path(skills_dir).resolve()
        self.system_prompt = system_prompt.strip()
        self.generator = generator or dispatch_generation
        self.parent_commit = parent_commit
        self.parent_repo = Path(parent_repo).resolve() if parent_repo is not None else None
        self.opencode_executable = (
            Path(opencode_executable).resolve() if opencode_executable is not None else None
        )
        self.osis_agents_file = (
            Path(osis_agents_file).resolve() if osis_agents_file is not None else None
        )
        self.base_url = base_url
        self.framework_pythons = {
            key.upper(): str(Path(value).resolve())
            for key, value in (framework_pythons or {}).items()
        }

    def _run_dir(
        self,
        label: str,
        architecture: str,
        task_id: str,
        seed: int,
        category: str,
    ) -> Path:
        return (
            self.runs_root
            / _segment(label)
            / architecture
            / "qa"
            / _segment(category)
            / f"{_segment(task_id)}__seed{seed}"
        )

    def _archive_existing(self, run_dir: Path) -> Path:
        relative = run_dir.relative_to(self.runs_root)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        destination = self.runs_root / "_archive" / stamp / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(run_dir), str(destination))
        return destination

    def run(
        self,
        sample: ExternalQuestion,
        architecture_id: str,
        *,
        seed: int,
        model: str,
        label: str,
        variant: str = "",
        resume: bool = False,
        max_steps: int = 80,
        max_output_tokens: int = 0,
    ) -> dict[str, Any]:
        architecture = architecture_id.upper()
        adapter = get_adapter(architecture)
        public = sample.to_public_task()
        private = sample.private_reference()
        run_dir = self._run_dir(
            label,
            architecture,
            public.task_id,
            int(seed),
            public.category,
        )
        result_path = run_dir / "run_result.json"
        if resume and result_path.is_file():
            prior = json.loads(result_path.read_text(encoding="utf-8"))
            if prior.get("status") == "completed":
                return {**prior, "run_dir": str(run_dir), "resumed": True}
        archived_run: Path | None = None
        if run_dir.exists():
            archived_run = self._archive_existing(run_dir)
        run_dir.mkdir(parents=True)
        started = time.monotonic()
        task_payload = sanitize_for_model(public)
        _write_json(run_dir / "input.json", public.to_dict())
        manifest: dict[str, Any] = {
            "protocol_version": public.protocol_version,
            "task_id": public.task_id,
            "architecture_id": architecture,
            "framework": adapter.framework,
            "framework_version": adapter.framework_version,
            "model": model,
            "variant": variant,
            "seed": int(seed),
            "max_steps": int(max_steps),
            "max_output_tokens": int(max_output_tokens),
            "parent_commit": self.parent_commit,
            "knowledge_bundle_sha256": SkillAdapter(self.skills_dir).bundle_hash(),
            "status": "running",
        }
        result: dict[str, Any] = {
            "status": "failed",
            "architecture_id": architecture,
            "task_id": public.task_id,
            "failure_code": None,
            "evaluation": {},
        }
        try:
            request = {
                "architecture_id": architecture,
                "task": task_payload,
                "task_id": public.task_id,
                "total_timeout_s": int(public.total_timeout_s),
                "seed": int(seed),
                "system_prompt": self.system_prompt,
                "workspace": str(run_dir),
                "skills_dir": str(self.skills_dir),
                "model": model,
                "variant": variant,
                "base_url": self.base_url,
                "temperature": 0.0,
                "request_timeout_s": min(300.0, float(public.total_timeout_s)),
                "generation_timeout_s": float(public.total_timeout_s),
                "max_steps": int(max_steps),
                "max_output_tokens": int(max_output_tokens),
                "framework_pythons": self.framework_pythons,
            }
            if self.parent_repo is not None:
                request["parent_repo"] = str(self.parent_repo)
            if self.opencode_executable is not None:
                request["opencode_executable"] = str(self.opencode_executable)
            if self.osis_agents_file is not None:
                request["osis_agents_file"] = str(self.osis_agents_file)
            generation = self.generator(request)
            _write_json(run_dir / "generation.json", generation)
            manifest["generation_elapsed_s"] = max(
                0.0, float(generation.get("elapsed_s") or 0.0)
            )
            if generation.get("status") != "completed":
                raise RuntimeError(str(generation.get("error") or generation.get("status")))
            scored = score_answer(
                str(generation.get("final_answer") or ""),
                private.gold,
                private.aliases,
            )
            elapsed = max(0.0, float(generation.get("elapsed_s") or 0.0))
            efficiency = 1.0 / (1.0 + elapsed / EFFICIENCY_SCALE_S)
            accuracy = float(bool(scored["correct"]))
            evaluation = {
                **scored,
                "accuracy": accuracy,
                "efficiency": round(efficiency, 6),
                "overall": round(0.80 * accuracy + 0.20 * efficiency, 6),
            }
            _write_json(run_dir / "evaluation.json", evaluation)
            result.update(status="completed", evaluation=evaluation)
            manifest.update(
                status="completed",
                model_calls=int(generation.get("model_calls") or 0),
                tool_calls=int(generation.get("tool_calls") or 0),
                tokens=generation.get("tokens") or {},
            )
        except Exception as exc:  # noqa: BLE001
            failed_elapsed = max(
                0.0,
                float(
                    manifest.get("generation_elapsed_s")
                    or (time.monotonic() - started)
                ),
            )
            manifest.setdefault("generation_elapsed_s", failed_elapsed)
            failed_efficiency = 1.0 / (1.0 + failed_elapsed / EFFICIENCY_SCALE_S)
            evaluation = {
                "pred": "",
                "correct": False,
                "accuracy": 0.0,
                "efficiency": round(failed_efficiency, 6),
                "overall": round(0.20 * failed_efficiency, 6),
            }
            _write_json(run_dir / "evaluation.json", evaluation)
            result.update(
                failure_code="GENERATION_FAILED",
                error=f"{type(exc).__name__}: {exc}"[:800],
                evaluation=evaluation,
            )
            manifest.update(
                status="failed",
                failure_code=result["failure_code"],
                error=result["error"],
            )
        finally:
            manifest["elapsed_s"] = round(time.monotonic() - started, 3)
            if archived_run is not None:
                manifest["archived_previous_run"] = str(archived_run)
            _write_json(run_dir / "manifest.json", manifest)
            _write_json(result_path, {**result, "manifest": "manifest.json"})
        return {**result, "run_dir": str(run_dir), "resumed": False}
