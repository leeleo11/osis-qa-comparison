"""Portable discovery for the external parent repository and run root."""

from __future__ import annotations

import os
from pathlib import Path


FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
ENV_VAR = "OSIS_PARENT_REPO"
RUN_ROOT_ENV = "OSIS_QA_RUN_ROOT"
LOCAL_CONFIG_FILENAME = "parent_repo.local.txt"
CONFIG_FILENAME = "parent_repo.txt"
_MARKERS = (
    Path(".agents/skills"),
    Path("datasets/qa/questions.json"),
    Path("datasets/qa/system_prompt.txt"),
)


class ParentRepoNotFound(RuntimeError):
    pass


def _valid(path: Path) -> bool:
    try:
        return path.is_dir() and all((path / marker).exists() for marker in _MARKERS)
    except OSError:
        return False


def _configured() -> Path | None:
    for name in (LOCAL_CONFIG_FILENAME, CONFIG_FILENAME):
        config = FRAMEWORK_ROOT / "configs" / name
        try:
            lines = config.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            candidate = Path(os.path.expandvars(value)).expanduser()
            return (candidate if candidate.is_absolute() else FRAMEWORK_ROOT / candidate).resolve()
    return None


def resolve_parent_repo(explicit: str | os.PathLike[str] | None = None) -> Path:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit).expanduser().resolve())
    elif os.environ.get(ENV_VAR):
        candidates.append(Path(os.path.expandvars(os.environ[ENV_VAR])).expanduser().resolve())
    else:
        configured = _configured()
        if configured is not None:
            candidates.append(configured)
        candidates.append((FRAMEWORK_ROOT.parent / "osis-skill-enhance-main").resolve())
    for candidate in candidates:
        if _valid(candidate):
            return candidate
    shown = candidates[0] if candidates else "<none>"
    raise ParentRepoNotFound(
        f"cannot locate QA parent repo ({shown}); use --parent-repo, {ENV_VAR}, "
        f"or configs/{LOCAL_CONFIG_FILENAME}"
    )


def resolve_run_root(explicit: str | os.PathLike[str] | None = None) -> Path:
    raw = explicit if explicit is not None else os.environ.get(RUN_ROOT_ENV)
    path = Path(raw).expanduser() if raw is not None else FRAMEWORK_ROOT / "runs"
    if not path.is_absolute():
        path = FRAMEWORK_ROOT / path
    return path.resolve()
