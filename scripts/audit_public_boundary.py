"""Fail closed when publishable files contain data, results, or credentials."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = frozenset(
    {"datasets", "runs", "reports", "results", "private", "seeded", ".venvs", "tmp"}
)
FORBIDDEN_NAMES = frozenset(
    {"questions.json", "results.jsonl", "generation_request.json", "parent_repo.local.txt"}
)
TEXT_SUFFIXES = frozenset(
    {".py", ".md", ".txt", ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg"}
)
_CREDENTIAL = re.compile(
    r"(?i)(?:OSIS_MODEL_API_KEY|QA_API_KEY|OPENAI_API_KEY)\s*[:=]\s*[\"']?"
    r"(?!\{env:|\$|<|os\.environ|getenv)([^\s\"',;}]{8,})"
)
_TOKEN = re.compile(r"\b(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{16,}\b")


def audit_paths(paths: Iterable[str]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for raw in paths:
        path = Path(str(raw).replace("\\", "/"))
        lowered = {part.casefold() for part in path.parts}
        if lowered.intersection(FORBIDDEN_PARTS) or path.name.casefold() in FORBIDDEN_NAMES:
            findings.append({"kind": "forbidden_path", "path": path.as_posix()})
    return findings


def scan_text(path: str, text: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if _CREDENTIAL.search(text) or _TOKEN.search(text):
        findings.append({"kind": "credential", "path": path})
    return findings


def _tracked() -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files"], cwd=ROOT, text=True, encoding="utf-8"
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def run_audit(paths: list[str] | None = None) -> list[dict[str, str]]:
    selected = paths if paths is not None else _tracked()
    findings = audit_paths(selected)
    for relative in selected:
        file = ROOT / relative
        if not file.is_file() or file.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        findings.extend(scan_text(relative, text))
    return findings


def main() -> int:
    findings = run_audit()
    print(json.dumps({"ok": not findings, "findings": findings}, ensure_ascii=False, indent=2))
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
