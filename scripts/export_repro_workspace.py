"""Export only tracked, publishable files to a clean reproduction directory."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_public_boundary import ROOT, run_audit


EXCLUDED_PARTS = frozenset(
    {".git", ".venvs", "tmp", "runs", "reports", "results", "datasets", "private", "seeded"}
)


def is_exportable(path: Path) -> bool:
    if {part.casefold() for part in path.parts}.intersection(EXCLUDED_PARTS):
        return False
    return path.name.casefold() != "parent_repo.local.txt"


def tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files"], cwd=ROOT, text=True, encoding="utf-8"
    )
    return [Path(line) for line in output.splitlines() if line.strip()]


def export(destination: str | Path) -> int:
    findings = run_audit()
    if findings:
        raise RuntimeError(f"public boundary audit failed: {findings}")
    target = Path(destination).resolve()
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"export destination is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    for relative in tracked_files():
        if not is_exportable(relative):
            continue
        source = ROOT / relative
        if not source.is_file():
            continue
        output = target / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, output)
        count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination")
    args = parser.parse_args(argv)
    print(f"exported {export(args.destination)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
