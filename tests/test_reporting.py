from __future__ import annotations

import json
from pathlib import Path

from qa.reporting import collect_records, summarize_records, write_reports


def _run(
    root: Path,
    arch: str,
    task: str,
    category: str,
    correct: bool,
    elapsed: float,
    *,
    status: str = "completed",
) -> None:
    run = root / arch / task / "seed-0"
    run.mkdir(parents=True)
    (run / "input.json").write_text(
        json.dumps({"task_id": task, "category": category}), encoding="utf-8"
    )
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "architecture_id": arch,
                "elapsed_s": 999.0,
                "generation_elapsed_s": elapsed,
                "status": status,
            }
        ),
        encoding="utf-8",
    )
    (run / "evaluation.json").write_text(
        json.dumps({"correct": correct, "pred": "x"}), encoding="utf-8"
    )


def test_reporting_aggregates_by_architecture_and_category(tmp_path: Path) -> None:
    _run(tmp_path, "T1", "qa-001", "usage", True, 2.0)
    _run(tmp_path, "T1", "qa-002", "hallucination", False, 4.0)
    records = collect_records(tmp_path)
    summary = summarize_records(records)
    t1 = summary["architectures"]["T1"]
    assert t1["n"] == 2
    assert t1["accuracy"] == 0.5
    assert t1["mean_elapsed_s"] == 3.0
    assert t1["by_category"]["usage"]["accuracy"] == 1.0
    assert t1["by_category"]["hallucination"]["accuracy"] == 0.0
    assert 0.59 < t1["overall"] < 0.60


def test_write_reports_creates_json_and_csv(tmp_path: Path) -> None:
    _run(tmp_path / "runs", "T2", "qa-001", "usage", True, 1.0)
    records = collect_records(tmp_path / "runs")
    outputs = write_reports(tmp_path / "out", records)
    assert outputs["summary"].is_file()
    assert outputs["records"].is_file()
    assert "architecture_id" in outputs["records"].read_text(encoding="utf-8")


def test_reporting_counts_failed_generation_in_denominator(tmp_path: Path) -> None:
    _run(tmp_path, "T3", "qa-001", "usage", True, 2.0)
    _run(tmp_path, "T3", "qa-002", "usage", False, 240.0, status="failed")
    records = collect_records(tmp_path)
    summary = summarize_records(records)["architectures"]["T3"]
    assert summary["n"] == 2
    assert summary["correct"] == 1
    assert summary["errors"] == 1
    assert summary["accuracy"] == 0.5
