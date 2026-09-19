from __future__ import annotations

from scripts.run_campaign import campaign_order, run_campaign


def test_t6_is_always_in_serial_lane() -> None:
    assert campaign_order(["T6", "T2", "T1", "T6"]) == (["T1", "T2"], ["T6"])


def test_campaign_runs_all_sample_architecture_pairs() -> None:
    calls: list[tuple[str, str]] = []

    class Runner:
        def run(self, sample, architecture, **_kwargs):
            calls.append((sample, architecture))
            return {"status": "completed", "task_id": sample, "architecture_id": architecture}

    results = run_campaign(
        runner=Runner(),
        samples=["qa-001", "qa-002"],
        architectures=["T2", "T6"],
        seed=0,
        model="m",
        label="x",
        jobs=1,
    )
    assert calls == [
        ("qa-001", "T2"),
        ("qa-002", "T2"),
        ("qa-001", "T6"),
        ("qa-002", "T6"),
    ]
    assert len(results) == 4
