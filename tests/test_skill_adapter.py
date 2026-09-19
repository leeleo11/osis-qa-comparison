from __future__ import annotations

from pathlib import Path

import pytest

from common.skill_adapter import SkillAdapter


def test_knowledge_listing_search_and_safe_read(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    (root / "osis-engine").mkdir(parents=True)
    (root / "osis-engine" / "SKILL.md").write_text("create_conc first parameter no", encoding="utf-8")
    (root / "osis-engine" / "pyosis_doc.py").write_text("def create_conc(no, name): ...", encoding="utf-8")
    reader = SkillAdapter(root)
    assert reader.list_files() == ["osis-engine/SKILL.md", "osis-engine/pyosis_doc.py"]
    assert reader.search("create_conc")[0]["score"] == 1
    assert "first parameter" in reader.read_file("osis-engine/SKILL.md")
    with pytest.raises(ValueError, match="safe relative"):
        reader.read_file("../secret.txt")


def test_bundle_is_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    (root / "b.md").write_text("b", encoding="utf-8")
    (root / "a.md").write_text("a", encoding="utf-8")
    first = SkillAdapter(root)
    assert first.bundle_hash() == SkillAdapter(root).bundle_hash()
    assert first.fixed_bundle_text().index("## a.md") < first.fixed_bundle_text().index("## b.md")
