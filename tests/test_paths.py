from __future__ import annotations

from pathlib import Path

import pytest

from common.paths import ParentRepoNotFound, resolve_parent_repo, resolve_run_root


def _parent(path: Path) -> Path:
    (path / ".agents" / "skills").mkdir(parents=True)
    (path / "datasets" / "qa").mkdir(parents=True)
    (path / "datasets" / "qa" / "questions.json").write_text("[]", encoding="utf-8")
    (path / "datasets" / "qa" / "system_prompt.txt").write_text("FINAL ANSWER:", encoding="utf-8")
    return path


def test_explicit_parent_is_marker_validated(tmp_path: Path) -> None:
    parent = _parent(tmp_path / "parent")
    assert resolve_parent_repo(parent) == parent.resolve()
    with pytest.raises(ParentRepoNotFound):
        resolve_parent_repo(tmp_path / "missing")


def test_run_root_can_be_external(tmp_path: Path) -> None:
    assert resolve_run_root(tmp_path / "outside") == (tmp_path / "outside").resolve()
