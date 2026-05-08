"""Read-only JobPipe artifact run discovery for ApplicationWorkspaceHub."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_cases import ArtifactWorkspaceHub


@dataclass(frozen=True)
class ArtifactRunRef:
    """Opaque reference to a local JobPipe artifact run."""

    id: str
    case_count: int
    failed_case_count: int = 0


@dataclass(frozen=True)
class ArtifactRunSource:
    """Resolve valid JobPipe artifact runs under an output root."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    def list_runs(self) -> list[ArtifactRunRef]:
        refs: list[ArtifactRunRef] = []
        for run_dir in _candidate_run_dirs(self.root):
            ref = _run_ref(run_dir)
            if ref is not None:
                refs.append(ref)
        refs.sort(key=lambda ref: ref.id, reverse=True)
        return refs

    def latest_run(self) -> ArtifactRunRef | None:
        runs = self.list_runs()
        return runs[0] if runs else None

    def resolve(self, run_id: str | None = None) -> Path | None:
        if run_id:
            run_dir = self.root / run_id
            return run_dir if _run_ref(run_dir) is not None else None

        latest = self.latest_run()
        return self.root / latest.id if latest else None


def build_latest_artifact_workspace_hub(out_root: str | Path) -> ArtifactWorkspaceHub | None:
    """Create an artifact hub for the newest valid run under an out-runs root."""

    run_dir = ArtifactRunSource(Path(out_root)).resolve()
    if run_dir is None:
        return None
    return ArtifactWorkspaceHub(run_dir)


def _candidate_run_dirs(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return [path for path in root.iterdir() if path.is_dir()]


def _run_ref(run_dir: Path) -> ArtifactRunRef | None:
    index_path = run_dir / "index.jsonl"
    if not index_path.exists():
        return None

    case_count = _index_case_count(index_path)
    job_dirs = [path for path in run_dir.iterdir() if path.is_dir()]
    if case_count == 0 and not job_dirs:
        return None

    failed_case_count = sum(1 for path in job_dirs if (path / "pipeline_error.json").exists())
    if job_dirs and failed_case_count >= len(job_dirs):
        return None

    return ArtifactRunRef(
        id=run_dir.name,
        case_count=case_count or max(0, len(job_dirs) - failed_case_count),
        failed_case_count=failed_case_count,
    )


def _index_case_count(path: Path) -> int:
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            value: Any = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            count += 1
    return count


__all__ = [
    "ArtifactRunRef",
    "ArtifactRunSource",
    "build_latest_artifact_workspace_hub",
]
