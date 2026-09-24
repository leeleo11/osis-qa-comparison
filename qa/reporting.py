"""Aggregate local run artifacts without exposing private answers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


EFFICIENCY_SCALE_S = 240.0


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def collect_records(runs_root: str | Path) -> list[dict[str, Any]]:
    root = Path(runs_root).resolve()
    records: list[dict[str, Any]] = []
    for evaluation_path in sorted(root.rglob("evaluation.json")):
        if "_archive" in evaluation_path.relative_to(root).parts:
            continue
        run = evaluation_path.parent
        evaluation = _read(evaluation_path)
        manifest = _read(run / "manifest.json")
        task = _read(run / "input.json")
        status = str(manifest.get("status") or "")
        if status not in {"completed", "failed"}:
            continue
        records.append(
            {
                "architecture_id": str(manifest.get("architecture_id") or ""),
                "status": status,
                "failure_code": str(manifest.get("failure_code") or ""),
                "task_id": str(task.get("task_id") or manifest.get("task_id") or ""),
                "category": str(task.get("category") or "unknown"),
                "result_tree": "/".join(run.relative_to(root).parts[:-1]),
                "correct": bool(evaluation.get("correct")),
                "pred": str(evaluation.get("pred") or ""),
                "elapsed_s": float(
                    manifest.get("generation_elapsed_s", manifest.get("elapsed_s")) or 0.0
                ),
                "run_dir": str(run),
            }
        )
    return records


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    correct = sum(bool(record.get("correct")) for record in records)
    errors = sum(str(record.get("status") or "") == "failed" for record in records)
    accuracy = correct / n if n else 0.0
    mean_elapsed = sum(float(record.get("elapsed_s") or 0.0) for record in records) / n if n else 0.0
    efficiency = 1.0 / (1.0 + mean_elapsed / EFFICIENCY_SCALE_S)
    by_category: dict[str, dict[str, Any]] = {}
    for record in records:
        category = str(record.get("category") or "unknown")
        slot = by_category.setdefault(category, {"n": 0, "correct": 0})
        slot["n"] += 1
        slot["correct"] += int(bool(record.get("correct")))
    for slot in by_category.values():
        slot["accuracy"] = round(slot["correct"] / slot["n"], 6) if slot["n"] else 0.0
    return {
        "n": n,
        "correct": correct,
        "errors": errors,
        "accuracy": round(accuracy, 6),
        "mean_elapsed_s": round(mean_elapsed, 6),
        "efficiency": round(efficiency, 6),
        "overall": round(0.80 * accuracy + 0.20 * efficiency, 6),
        "by_category": by_category,
        "failed_ids": [
            str(record.get("task_id") or "")
            for record in records
            if str(record.get("status") or "") == "failed"
        ],
    }


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    architectures: dict[str, dict[str, Any]] = {}
    for architecture in sorted({str(record.get("architecture_id") or "") for record in records}):
        selected = [record for record in records if record.get("architecture_id") == architecture]
        architectures[architecture] = _summary(selected)
    return {"n_records": len(records), "architectures": architectures}


def write_reports(output_dir: str | Path, records: list[dict[str, Any]]) -> dict[str, Path]:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / "summary.json"
    records_path = output / "records.csv"
    summary_path.write_text(
        json.dumps(summarize_records(records), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    fields = [
        "architecture_id",
        "task_id",
        "category",
        "result_tree",
        "status",
        "failure_code",
        "correct",
        "pred",
        "elapsed_s",
        "run_dir",
    ]
    with records_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in fields})
    return {"summary": summary_path, "records": records_path}
