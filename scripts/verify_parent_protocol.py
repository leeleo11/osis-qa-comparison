"""Check local answer scoring against the pinned parent's canonical scorer."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.paths import resolve_parent_repo
from qa.data import load_external_questions
from qa.score import score_answer


def _load_parent_scorer(parent: Path):
    path = parent / "datasets" / "qa" / "score.py"
    spec = importlib.util.spec_from_file_location("osis_parent_qa_score", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load parent scorer: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verify(parent: Path) -> dict[str, object]:
    scorer = _load_parent_scorer(parent)
    questions = load_external_questions(parent)
    mismatches: list[str] = []
    checks = 0
    for sample in questions:
        private = sample.private_reference()
        canonical_item = {
            "Final answer": private.gold,
            "aliases": list(private.aliases),
        }
        candidates = [
            f"FINAL ANSWER: {private.gold}",
            f"<think>private reasoning</think>\nFINAL ANSWER: {private.gold}",
            f"<think>private reasoning\nFINAL ANSWER: {private.gold}</think>",
            f"FINAL ANSWER: <think>{private.gold}</think>",
            "FINAL ANSWER: __definitely_wrong__",
        ]
        candidates.extend(f"FINAL ANSWER: {alias}" for alias in private.aliases)
        for text in candidates:
            local = bool(score_answer(text, private.gold, private.aliases)["correct"])
            canonical = bool(scorer.score_item(text, canonical_item))
            checks += 1
            if local != canonical:
                mismatches.append(sample.task_id)
                break
    return {
        "ok": not mismatches,
        "questions": len(questions),
        "checks": checks,
        "mismatch_ids": sorted(set(mismatches)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-repo")
    args = parser.parse_args(argv)
    result = verify(resolve_parent_repo(args.parent_repo))
    print(json.dumps(result, ensure_ascii=False))
    return int(not result["ok"])


if __name__ == "__main__":
    raise SystemExit(main())
