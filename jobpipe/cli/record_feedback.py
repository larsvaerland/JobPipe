from __future__ import annotations

import argparse
import io
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any

from jobpipe.core.io import load_env_file, now_iso

load_env_file(".env")

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from jobpipe.core.paths import primary_db_path
from jobpipe.core.primary_db import (
    connect_primary_db,
    ensure_candidate,
    insert_candidate_feedback_event,
)


DEFAULT_DB_PATH = primary_db_path()
DEFAULT_CANDIDATE_ID = (os.environ.get("JOBPIPE_CANDIDATE_ID") or "default").strip() or "default"

SIGNALS: dict[str, dict[str, str]] = {
    "good_recommendation": {
        "feedback_type": "recommendation_quality",
        "feedback_value": "good_recommendation",
        "label": "good recommendation",
    },
    "bad_recommendation": {
        "feedback_type": "recommendation_quality",
        "feedback_value": "bad_recommendation",
        "label": "bad recommendation",
    },
    "promote": {
        "feedback_type": "manual_override",
        "feedback_value": "promote",
        "label": "promote",
    },
    "demote": {
        "feedback_type": "manual_override",
        "feedback_value": "demote",
        "label": "demote",
    },
    "good_fit": {
        "feedback_type": "fit_judgment",
        "feedback_value": "good_fit",
        "label": "good fit",
    },
    "bad_fit": {
        "feedback_type": "fit_judgment",
        "feedback_value": "bad_fit",
        "label": "bad fit",
    },
}


def _connect(path: Path) -> sqlite3.Connection:
    conn = connect_primary_db(path)
    conn.row_factory = sqlite3.Row
    return conn


def _latest_evaluation_snapshot(
    conn: sqlite3.Connection,
    *,
    candidate_id: str,
    job_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT candidate_id, job_id, run_id, run_seen_at, title, employer,
               final_decision, final_confidence, fit_score, pivot_score,
               triage_decision, triage_confidence, recommendation_reason,
               applicationDue, source_url, application_url, updated_at
        FROM job_evaluations
        WHERE candidate_id = ? AND job_id = ?
        ORDER BY updated_at DESC, run_seen_at DESC
        LIMIT 1
        """,
        [candidate_id, job_id],
    ).fetchone()
    return dict(row) if row is not None else None


def record_feedback(
    *,
    db_path: Path,
    candidate_id: str,
    job_id: str,
    signal: str,
    notes: str = "",
    source: str = "manual",
) -> dict[str, Any]:
    signal_key = (signal or "").strip().lower()
    if signal_key not in SIGNALS:
        valid = ", ".join(sorted(SIGNALS))
        raise ValueError(f"Unsupported feedback signal '{signal}'. Valid signals: {valid}")

    signal_def = SIGNALS[signal_key]
    conn = _connect(db_path)
    try:
        ensure_candidate(conn, candidate_id=candidate_id)
        snapshot = _latest_evaluation_snapshot(conn, candidate_id=candidate_id, job_id=job_id)
        event_id = f"fb_{uuid.uuid4().hex[:20]}"
        created_at = now_iso()
        evaluation_id = ""
        evidence_json: dict[str, Any] = {
            "signal": signal_key,
        }
        if snapshot:
            evaluation_id = f"{snapshot.get('run_id') or ''}:{job_id}"
            evidence_json["evaluation"] = {
                "run_id": snapshot.get("run_id") or "",
                "title": snapshot.get("title") or "",
                "employer": snapshot.get("employer") or "",
                "final_decision": snapshot.get("final_decision") or "",
                "final_confidence": snapshot.get("final_confidence"),
                "fit_score": snapshot.get("fit_score"),
                "pivot_score": snapshot.get("pivot_score"),
                "triage_decision": snapshot.get("triage_decision") or "",
                "triage_confidence": snapshot.get("triage_confidence"),
                "recommendation_reason": snapshot.get("recommendation_reason") or "",
                "application_due": snapshot.get("applicationDue") or "",
                "source_url": snapshot.get("source_url") or "",
                "application_url": snapshot.get("application_url") or "",
                "updated_at": snapshot.get("updated_at") or "",
            }

        insert_candidate_feedback_event(
            conn,
            {
                "feedback_event_id": event_id,
                "candidate_id": candidate_id,
                "job_id": job_id,
                "evaluation_id": evaluation_id,
                "feedback_type": signal_def["feedback_type"],
                "feedback_value": signal_def["feedback_value"],
                "source": (source or "manual").strip() or "manual",
                "notes": (notes or "").strip(),
                "evidence_json": evidence_json,
                "created_at": created_at,
            },
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "feedback_event_id": event_id,
        "candidate_id": candidate_id,
        "job_id": job_id,
        "signal": signal_key,
        "feedback_type": signal_def["feedback_type"],
        "feedback_value": signal_def["feedback_value"],
        "notes": (notes or "").strip(),
        "source": (source or "manual").strip() or "manual",
        "created_at": created_at,
        "has_evaluation_context": snapshot is not None,
        "evaluation_id": evaluation_id,
        "evaluation": evidence_json.get("evaluation", {}),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record explicit candidate feedback for a job recommendation.")
    parser.add_argument("job_id", help="Canonical job id to attach the feedback to.")
    parser.add_argument(
        "signal",
        choices=sorted(SIGNALS),
        help="Feedback signal to record.",
    )
    parser.add_argument("--notes", default="", help="Optional operator note explaining the feedback.")
    parser.add_argument("--source", default="manual", help="Source label for the feedback event.")
    parser.add_argument(
        "--candidate-id",
        default=DEFAULT_CANDIDATE_ID,
        help=f"Candidate id in the primary DB. Default: {DEFAULT_CANDIDATE_ID}",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Primary DB path. Default: {DEFAULT_DB_PATH}",
    )
    parser.add_argument("--json", action="store_true", help="Print the recorded event as JSON.")
    return parser


def _print_result(result: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    summary = (
        f"Recorded {SIGNALS[result['signal']]['label']} for {result['job_id']}"
        f" [{result['feedback_type']}={result['feedback_value']}]"
    )
    print(summary)
    if result.get("evaluation"):
        evaluation = result["evaluation"]
        title = evaluation.get("title") or ""
        employer = evaluation.get("employer") or ""
        final_decision = evaluation.get("final_decision") or ""
        fit_score = evaluation.get("fit_score")
        pivot_score = evaluation.get("pivot_score")
        print(
            "  Evaluation context: "
            f"{employer} | {title} | {final_decision} | fit={fit_score} | pivot={pivot_score}"
        )
    else:
        print("  Evaluation context: none")
    if result.get("notes"):
        print(f"  Notes: {result['notes']}")


def main() -> int:
    args = _parser().parse_args()
    result = record_feedback(
        db_path=Path(args.db),
        candidate_id=(args.candidate_id or DEFAULT_CANDIDATE_ID).strip() or DEFAULT_CANDIDATE_ID,
        job_id=(args.job_id or "").strip(),
        signal=args.signal,
        notes=args.notes,
        source=args.source,
    )
    _print_result(result, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
