"""CLI wrapper for the dashboard projection."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List, Optional

from jobpipe.core.io import load_env_file
from jobpipe.projections.dashboard import _load_app_state_merged, build_payload, export
from jobpipe.runtime.paths import artifacts_root, exports_root, primary_db_path, repo_root

load_env_file(".env")

_PRIMARY_DB_PATH = primary_db_path()
_DEFAULT_CANDIDATE_ID = (os.environ.get("JOBPIPE_CANDIDATE_ID") or "default").strip() or "default"


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Build a self-contained dashboard HTML from the primary JobPipe DB.")
    parser.add_argument(
        "--artifacts",
        "--out-runs",
        dest="artifacts_dir",
        default=str(artifacts_root()),
        help=f"Artifact runs directory (default: {artifacts_root()})",
    )
    parser.add_argument(
        "--template",
        default=str(repo_root() / "reports" / "dashboard_template.html"),
        help="HTML template",
    )
    parser.add_argument(
        "--out",
        default=str(exports_root() / "dashboard.html"),
        help=f"Output HTML path (default: {exports_root() / 'dashboard.html'})",
    )
    parser.add_argument("--app-state", default="", help="Optional application_state.json fallback path.")
    parser.add_argument("--db", default=str(_PRIMARY_DB_PATH), help="Path to primary jobpipe.sqlite")
    parser.add_argument(
        "--candidate-id",
        default=_DEFAULT_CANDIDATE_ID,
        help=f"Candidate ID for primary DB reads (default: {_DEFAULT_CANDIDATE_ID})",
    )
    args = parser.parse_args(argv)

    state_path = Path(args.app_state) if args.app_state else None
    export(
        Path(args.artifacts_dir),
        Path(args.template),
        Path(args.out),
        state_path=state_path,
        primary_db_path_=Path(args.db),
        candidate_id=args.candidate_id,
    )


__all__ = [
    "_load_app_state_merged",
    "build_payload",
    "export",
    "main",
]


if __name__ == "__main__":
    main()
