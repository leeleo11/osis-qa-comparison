"""Bounded, read-only access to a frozen AgentSkills snapshot."""

from __future__ import annotations

import hashlib
from pathlib import Path


class SkillAdapter:
    def __init__(self, skills_dir: str | Path, *, max_read_bytes: int = 200_000) -> None:
        self.root = Path(skills_dir).resolve()
        if not self.root.is_dir():
            raise NotADirectoryError(self.root)
        self.max_read_bytes = max_read_bytes

    def _inside(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("path escapes knowledge root") from exc
        return resolved

    def list_files(self) -> list[str]:
        return sorted(
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if path.is_file()
        )

    def read_file(self, relative_path: str) -> str:
        raw = Path(relative_path)
        if not relative_path or raw.is_absolute() or ".." in raw.parts:
            raise ValueError("knowledge path must be a safe relative path")
        path = self._inside(self.root / raw)
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.stat().st_size > self.max_read_bytes:
            raise ValueError(f"knowledge file exceeds {self.max_read_bytes} bytes")
        return path.read_text(encoding="utf-8", errors="replace")

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, object]]:
        terms = [term.casefold() for term in query.split() if term.strip()]
        if not terms:
            return []
        matches: list[dict[str, object]] = []
        for relative in self.list_files():
            try:
                text = self.read_file(relative)
            except (OSError, UnicodeError, ValueError):
                continue
            lowered = text.casefold()
            score = sum(lowered.count(term) for term in terms)
            if score:
                matches.append({"path": relative, "score": score})
        return sorted(matches, key=lambda item: (-int(item["score"]), str(item["path"])))[:limit]

    def bundle_hash(self) -> str:
        digest = hashlib.sha256()
        for relative in self.list_files():
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update((self.root / relative).read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    def fixed_bundle_text(self) -> str:
        sections = [f"# Knowledge snapshot sha256={self.bundle_hash()}"]
        for relative in self.list_files():
            sections.extend((f"\n## {relative}", self.read_file(relative)))
        return "\n".join(sections)
