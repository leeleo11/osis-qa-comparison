from __future__ import annotations

import json
from pathlib import Path

from scripts import run_dataset


def test_dry_run_lists_external_questions_without_gold(tmp_path: Path, capsys) -> None:
    parent = tmp_path / "parent"
    qa_dir = parent / "datasets" / "qa"
    qa_dir.mkdir(parents=True)
    (parent / ".agents" / "skills").mkdir(parents=True)
    (qa_dir / "system_prompt.txt").write_text("FINAL ANSWER:", encoding="utf-8")
    (qa_dir / "questions.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "qa-001",
                    "Question": "First argument?",
                    "Final answer": "no",
                    "category": "usage",
                    "source": "hidden.py",
                }
            ]
        ),
        encoding="utf-8",
    )
    code = run_dataset.main(
        [
            "--parent-repo",
            str(parent),
            "--architecture",
            "T2",
            "--skills-dir",
            str(parent / ".agents" / "skills"),
            "--dry-run",
        ]
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "qa-001" in output
    assert "hidden.py" not in output
    assert '"no"' not in output
