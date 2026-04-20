from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from jobpipe.core.io import now_iso
from jobpipe.core.primary_db import (
    connect_primary_db,
    ensure_candidate,
    insert_application_event,
    upsert_application_summary,
)
from jobpipe.model import JobSyncApplicationStatusEvent

_VALID_STAGES = {"shortlisted", "called", "applied", "interview", "second_interview"}
_VALID_OUTCOMES = {"accepted", "rejected", "dismissed"}


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_existing_summary(
    conn: sqlite3.Connection,
    *,
    candidate_id: str,
    job_id: str,
) -> dict[str, str]:
    row = conn.execute(
        """
        SELECT current_stage, current_outcome, effective_status, notes_latest
        FROM application_summary
        WHERE candidate_id = ? AND job_id = ?
        """,
        [candidate_id, job_id],
    ).fetchone()
    if not row:
        return {
            "current_stage": "",
            "current_outcome": "",
            "effective_status": "",
            "notes_latest": "",
        }
    return {
        "current_stage": str(row[0] or ""),
        "current_outcome": str(row[1] or ""),
        "effective_status": str(row[2] or ""),
        "notes_latest": str(row[3] or ""),
    }


def record_jobsync_application_status_event(
    db_path: str | Path,
    event: JobSyncApplicationStatusEvent,
) -> JobSyncApplicationStatusEvent:
    normalized = JobSyncApplicationStatusEvent.model_validate(event)
    conn = connect_primary_db(db_path)
    try:
        ensure_candidate(conn, candidate_id=normalized.candidate_id)

        existing = _load_existing_summary(
            conn,
            candidate_id=normalized.candidate_id,
            job_id=normalized.job_id,
        )

        current_stage = existing["current_stage"]
        current_outcome = existing["current_outcome"]
        effective_status = existing["effective_status"]
        notes_latest = normalized.notes or existing["notes_latest"]

        if normalized.event_type in _VALID_OUTCOMES:
            current_outcome = normalized.event_type
            effective_status = normalized.event_type
        elif normalized.event_type in _VALID_STAGES:
            current_stage = normalized.event_type
            if not current_outcome:
                effective_status = normalized.event_type

        insert_application_event(
            conn,
            {
                "application_event_id": f"jobsync_evt_{uuid.uuid4().hex[:20]}",
                "candidate_id": normalized.candidate_id,
                "job_id": normalized.job_id,
                "event_type": normalized.event_type,
                "event_at": normalized.event_at,
                "source": normalized.source,
                "notes": normalized.notes,
                "metadata_json": dict(normalized.metadata_json),
                "created_at": _utc_now_z(),
            },
        )

        upsert_application_summary(
            conn,
            {
                "candidate_id": normalized.candidate_id,
                "job_id": normalized.job_id,
                "current_stage": current_stage,
                "current_outcome": current_outcome,
                "effective_status": effective_status,
                "last_event_at": normalized.event_at,
                "notes_latest": notes_latest,
                "updated_at": now_iso(),
            },
        )

        conn.commit()
        return normalized
    finally:
        conn.close()


__all__ = [
    "record_jobsync_application_status_event",
]
