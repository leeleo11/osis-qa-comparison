"""Create isolated Python 3.13 environments for framework-specific dependencies."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def environment_plan(root: str | Path = ROOT) -> dict[str, dict[str, Any]]:
    base = Path(root).resolve() / ".venvs"
    return {
        "main": {"path": base / "main", "extra": "test"},
        "T2": {"path": base / "t2", "extra": "t2"},
        "T3": {"path": base / "t3", "extra": "t3"},
        "T4": {"path": base / "t4", "extra": "t4"},
        "T5": {"path": base / "t5", "extra": "t5"},
    }


def python_in(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if __import__("os").name == "nt" else "bin/python")


def setup(*, dry_run: bool = False) -> list[list[str]]:
    commands: list[list[str]] = []
    for item in environment_plan().values():
        path = Path(item["path"])
        create = ["uv", "venv", "--allow-existing", "--python", "3.13", str(path)]
        sync = ["uv", "sync", "--frozen", "--active", "--extra", str(item["extra"])]
        commands.extend((create, sync))
        if not dry_run:
            subprocess.run(create, cwd=ROOT, check=True)
            env = os.environ.copy()
            env["VIRTUAL_ENV"] = str(path)
            subprocess.run(sync, cwd=ROOT, env=env, check=True)
    return commands


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    for command in setup(dry_run=args.dry_run):
        print(subprocess.list2cmdline(command))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
