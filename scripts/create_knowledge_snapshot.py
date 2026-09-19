"""Create the local QA knowledge snapshot allowed by the parent protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any


ALLOWED_NAMES = frozenset({"SKILL.md", "pyosis_doc.py", "项目画像.md"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _commit(parent: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=parent, text=True, encoding="utf-8"
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def create_snapshot(parent_repo: str | Path, output_dir: str | Path) -> dict[str, Any]:
    parent = Path(parent_repo).resolve()
    source = parent / ".agents" / "skills"
    output = Path(output_dir).resolve()
    if not source.is_dir():
        raise NotADirectoryError(source)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"snapshot output is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    hashes: dict[str, str] = {}
    for path in sorted(source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()):
        if not path.is_file() or path.name not in ALLOWED_NAMES:
            continue
        relative = path.relative_to(source)
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        key = relative.as_posix()
        copied.append(key)
        hashes[key] = _sha256(target)
    if not any(path.endswith("/SKILL.md") or path == "SKILL.md" for path in copied):
        raise RuntimeError("snapshot contains no SKILL.md files")
    manifest = {
        "protocol": "qa-gold-sources-v1",
        "parent_commit": _commit(parent),
        "selection": sorted(ALLOWED_NAMES),
        "files": copied,
        "sha256": hashes,
    }
    (output / "snapshot_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-repo", required=True)
    parser.add_argument("--output", default="tmp/qa-knowledge-snapshot")
    args = parser.parse_args(argv)
    manifest = create_snapshot(args.parent_repo, args.output)
    print(json.dumps({"files": len(manifest["files"]), "parent_commit": manifest["parent_commit"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
