"""Export thin JobSync case projections from canonical JobPipe state."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable, List, Optional

from jobpipe.projections import build_jobsync_application_case_projections
from jobpipe.projections.dashboard import build_payload
from jobpipe.runtime.paths import artifacts_root, exports_root, primary_db_path

_DEFAULT_CANDIDATE_ID = (os.environ.get("JOBPIPE_CANDIDATE_ID") or "default").strip() or "default"
_DEFAULT_DECISIONS = ("APPLY_STRONGLY", "APPLY", "REVIEW_HIGH", "REVIEW_LOW")


def _selected_rows(
    rows: Iterable[dict],
    *,
    job_ids: set[str],
    decisions: set[str],
) -> list[dict]:
    selected: list[dict] = []
    for row in rows:
        job_id = str(row.get("job_id") or "").strip()
        decision = str(row.get("final_decision") or "").strip()
        if job_ids and job_id not in job_ids:
            continue
        if decisions and decision not in decisions:
            continue
        selected.append(row)
    return selected


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Export thin JobSync application-case projections from canonical JobPipe state."
    )
    parser.add_argument(
        "--artifacts",
        "--out-runs",
        dest="artifacts_dir",
        default=str(artifacts_root()),
        help=f"Artifact runs directory (default: {artifacts_root()})",
    )
    parser.add_argument(
        "--db",
        default=str(primary_db_path()),
        help=f"Path to primary jobpipe.sqlite (default: {primary_db_path()})",
    )
    parser.add_argument(
        "--candidate-id",
        default=_DEFAULT_CANDIDATE_ID,
        help=f"Candidate ID for primary DB reads (default: {_DEFAULT_CANDIDATE_ID})",
    )
    parser.add_argument(
        "--job-id",
        action="append",
        default=[],
        help="Export only the specified job_id. May be passed multiple times.",
    )
    parser.add_argument(
        "--decision",
        action="append",
        default=list(_DEFAULT_DECISIONS),
        help=(
            "Include only these final decisions. Repeat to override/add. "
            f"Defaults: {', '.join(_DEFAULT_DECISIONS)}"
        ),
    )
    parser.add_argument(
        "--out",
        default=str(exports_root() / "jobsync_cases.json"),
        help=f"Output JSON path (default: {exports_root() / 'jobsync_cases.json'})",
    )
    args = parser.parse_args(argv)

    payload = build_payload(
        Path(args.artifacts_dir),
        primary_db_path_=Path(args.db),
        candidate_id=args.candidate_id,
    )
    rows = _selected_rows(
        payload.get("jobs", []),
        job_ids={str(job_id).strip() for job_id in args.job_id if str(job_id).strip()},
        decisions={str(decision).strip() for decision in args.decision if str(decision).strip()},
    )
    cases = [case.model_dump(mode="json") for case in build_jobsync_application_case_projections(rows)]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "candidate_id": args.candidate_id,
                "generated_at": payload.get("generated_at"),
                "count": len(cases),
                "cases": cases,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"JobSync cases exported: {out_path}")
    print(f"  {len(cases)} case(s)")


if __name__ == "__main__":
    main()
