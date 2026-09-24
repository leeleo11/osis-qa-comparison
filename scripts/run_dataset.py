"""Run one architecture against the external parent QA questions."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.paths import resolve_parent_repo, resolve_run_root
from common.weknora_read import apply_parent_weknora
from qa.data import load_external_questions, load_system_prompt
from qa.runner import QARunner
from scripts.setup_framework_envs import environment_plan, python_in


def parent_commit(parent: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=parent, text=True, encoding="utf-8"
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def discover_framework_pythons(root: Path = ROOT) -> dict[str, Path]:
    plan = environment_plan(root)
    result: dict[str, Path] = {}
    main_python = python_in(Path(plan["main"]["path"]))
    if main_python.is_file():
        result.update(T1=main_python, T6=main_python)
    for architecture in ("T2", "T3", "T4", "T5"):
        executable = python_in(Path(plan[architecture]["path"]))
        if executable.is_file():
            result[architecture] = executable
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-repo")
    parser.add_argument("--questions")
    parser.add_argument("--system-prompt")
    parser.add_argument("--task-id", action="append")
    parser.add_argument("--architecture", required=True, choices=[f"T{i}" for i in range(1, 7)])
    parser.add_argument("--skills-dir", required=True)
    parser.add_argument("--runs-dir")
    parser.add_argument("--model", default="deepseek-v4.1-flash-expires-on-0910")
    parser.add_argument("--variant", default="")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--label", default="formal")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--opencode-executable", default="")
    parser.add_argument("--osis-agents-file", default="")
    parser.add_argument("--max-steps", type=int, default=80)
    parser.add_argument("--max-output-tokens", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def select_questions(args: argparse.Namespace, parent: Path):
    questions = load_external_questions(parent, args.questions)
    if args.task_id:
        selected = set(args.task_id)
        questions = [question for question in questions if question.task_id in selected]
    return questions


def build_runner(args: argparse.Namespace, parent: Path) -> QARunner:
    base_url = args.base_url or os.environ.get("OSIS_MODEL_BASE_URL", "")
    key = os.environ.get("OSIS_MODEL_API_KEY") or os.environ.get("OSIS_API_KEY") or ""
    if not key:
        raise RuntimeError("OSIS_MODEL_API_KEY is not set")
    os.environ["OSIS_MODEL_API_KEY"] = key
    os.environ["OSIS_PARENT_REPO"] = str(parent)
    apply_parent_weknora(parent)
    return QARunner(
        runs_root=resolve_run_root(args.runs_dir),
        skills_dir=Path(args.skills_dir),
        system_prompt=load_system_prompt(parent, args.system_prompt),
        parent_commit=parent_commit(parent),
        parent_repo=parent,
        opencode_executable=(args.opencode_executable or os.environ.get("OPENCODE_EXE") or None),
        osis_agents_file=(args.osis_agents_file or os.environ.get("OSIS_AGENTS_FILE") or None),
        base_url=base_url,
        framework_pythons=discover_framework_pythons(),
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    parent = resolve_parent_repo(args.parent_repo)
    questions = select_questions(args, parent)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "questions": len(questions),
                    "tasks": [
                        {"task_id": item.task_id, "category": item.public.category}
                        for item in questions
                    ],
                },
                ensure_ascii=False,
            )
        )
        return 0
    runner = build_runner(args, parent)
    results = [
        runner.run(
            question,
            args.architecture,
            seed=args.seed,
            model=args.model,
            label=args.label,
            variant=args.variant,
            resume=args.resume,
            max_steps=args.max_steps,
            max_output_tokens=args.max_output_tokens,
        )
        for question in questions
    ]
    print(
        json.dumps(
            {
                "completed": sum(item["status"] == "completed" for item in results),
                "correct": sum(bool(item.get("evaluation", {}).get("correct")) for item in results),
                "total": len(results),
            }
        )
    )
    return int(any(item["status"] != "completed" for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
