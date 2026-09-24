from __future__ import annotations

from pathlib import Path

from scripts.create_knowledge_snapshot import create_snapshot


def test_snapshot_copies_the_parent_skill_tree(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    skill = parent / ".agents" / "skills" / "osis-module-material"
    template = skill / "references" / "templates" / "bridge-a"
    template.mkdir(parents=True)
    (skill / "SKILL.md").write_text("skill", encoding="utf-8")
    (skill / "pyosis_doc.py").write_text("def create_conc(): ...", encoding="utf-8")
    (template / "项目画像.md").write_text("portrait", encoding="utf-8")
    (template / "main.py").write_text("private template code", encoding="utf-8")
    (parent / "datasets" / "qa").mkdir(parents=True)
    (parent / "datasets" / "qa" / "questions.json").write_text("SECRET GOLD", encoding="utf-8")
    output = tmp_path / "snapshot"

    manifest = create_snapshot(parent, output)

    assert (output / "osis-module-material" / "SKILL.md").is_file()
    assert (output / "osis-module-material" / "pyosis_doc.py").is_file()
    assert (output / "osis-module-material" / "references" / "templates" / "bridge-a" / "项目画像.md").is_file()
    assert (output / "osis-module-material" / "references" / "templates" / "bridge-a" / "main.py").is_file()
    assert "questions.json" not in "\n".join(manifest["files"])
    assert manifest["selection"] == "parent .agents/skills"
