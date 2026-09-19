from __future__ import annotations

from pathlib import Path

from scripts.export_repro_workspace import is_exportable


def test_export_filter_excludes_local_data_and_results() -> None:
    assert is_exportable(Path("README.md"))
    assert not is_exportable(Path("runs/formal/result.json"))
    assert not is_exportable(Path("tmp/qa-knowledge-snapshot/skill/SKILL.md"))
    assert not is_exportable(Path("configs/parent_repo.local.txt"))
