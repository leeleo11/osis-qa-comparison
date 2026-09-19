"""Run the six-framework QA matrix with a dedicated serial T6 lane."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.paths import resolve_parent_repo
from scripts.run_dataset import build_runner, select_questions


def campaign_order(architectures: Iterable[str]) -> tuple[list[str], list[str]]:
    normalized = sorted({str(item).upper() for item in architectures})
    return [item for item in normalized if item != "T6"], [item for item in normalized if item == "T6"]


def run_campaign(
    *,
    runner: Any,
    samples: list[Any],
    architectures: list[str],
    seed: int,
    model: str,
    label: str,
    variant: str = "",
    resume: bool = False,
    jobs: int = 1,
    max_steps: int = 80,
    max_output_tokens: int = 0,
) -> list[dict[str, Any]]:
    parallel, serial = campaign_order(architectures)
    results: list[dict[str, Any]] = []

    def one(sample: Any, architecture: str) -> dict[str, Any]:
        return runner.run(
            sample,
            architecture,
            seed=seed,
            model=model,
            label=label,
            variant=variant,
            resume=resume,
            max_steps=max_steps,
            max_output_tokens=max_output_tokens,
        )

    work = [(sample, architecture) for architecture in parallel for sample in samples]
    if jobs > 1 and work:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = [pool.submit(one, sample, architecture) for sample, architecture in work]
            for future in as_completed(futures):
                results.append(future.result())
    else:
        results.extend(one(sample, architecture) for sample, architecture in work)
    for architecture in serial:
        for sample in samples:
            results.append(one(sample, architecture))
    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-repo")
    parser.add_argument("--questions")
    parser.add_argument("--system-prompt")
    parser.add_argument("--task-id", action="append")
    parser.add_argument("--architectures", nargs="+", default=[f"T{i}" for i in range(1, 7)])
    parser.add_argument("--skills-dir", required=True)
    parser.add_argument("--runs-dir")
    parser.add_argument("--model", required=True)
    parser.add_argument("--variant", default="")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--label", required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--opencode-executable", default="")
    parser.add_argument("--osis-agents-file", default="")
    parser.add_argument("--max-steps", type=int, default=80)
    parser.add_argument("--max-output-tokens", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--jobs", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    parent = resolve_parent_repo(args.parent_repo)
    questions = select_questions(args, parent)
    runner = build_runner(args, parent)
    results = run_campaign(
        runner=runner,
        samples=questions,
        architectures=args.architectures,
        seed=args.seed,
        model=args.model,
        label=args.label,
        variant=args.variant,
        resume=args.resume,
        jobs=max(1, args.jobs),
        max_steps=args.max_steps,
        max_output_tokens=args.max_output_tokens,
    )
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
