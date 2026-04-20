from __future__ import annotations

import sqlite3

from jobpipe.model import JobSyncApplicationStatusEvent
from jobpipe.runtime.jobsync import record_jobsync_application_status_event


def test_record_jobsync_application_status_event_writes_db_summary_and_event(tmp_path) -> None:
    db_path = tmp_path / "jobpipe.sqlite"

    event = JobSyncApplicationStatusEvent(
        job_id="job-1",
        candidate_id="candidate-a",
        event_type="applied",
        event_at="2026-04-20T10:00:00Z",
        source="jobsync",
        notes="Submitted from companion workflow.",
        metadata_json={"channel": "jobsync-import"},
    )

    recorded = record_jobsync_application_status_event(db_path, event)
    assert recorded.event_type == "applied"

    con = sqlite3.connect(str(db_path))
    summary = con.execute(
        "SELECT current_stage, current_outcome, effective_status, notes_latest "
        "FROM application_summary WHERE candidate_id = ? AND job_id = ?",
        ["candidate-a", "job-1"],
    ).fetchone()
    stored_event = con.execute(
        "SELECT event_type, source, notes FROM application_events WHERE candidate_id = ? AND job_id = ?",
        ["candidate-a", "job-1"],
    ).fetchone()
    con.close()

    assert summary == ("applied", "", "applied", "Submitted from companion workflow.")
    assert stored_event == ("applied", "jobsync", "Submitted from companion workflow.")


def test_record_jobsync_terminal_event_updates_outcome(tmp_path) -> None:
    db_path = tmp_path / "jobpipe.sqlite"

    record_jobsync_application_status_event(
        db_path,
        JobSyncApplicationStatusEvent(
            job_id="job-1",
            candidate_id="candidate-a",
            event_type="applied",
            event_at="2026-04-20T10:00:00Z",
            source="jobsync",
        ),
    )
    record_jobsync_application_status_event(
        db_path,
        JobSyncApplicationStatusEvent(
            job_id="job-1",
            candidate_id="candidate-a",
            event_type="rejected",
            event_at="2026-04-22T10:00:00Z",
            source="jobsync",
            notes="Rejected after first review.",
        ),
    )

    con = sqlite3.connect(str(db_path))
    summary = con.execute(
        "SELECT current_stage, current_outcome, effective_status, notes_latest "
        "FROM application_summary WHERE candidate_id = ? AND job_id = ?",
        ["candidate-a", "job-1"],
    ).fetchone()
    con.close()

    assert summary == ("applied", "rejected", "rejected", "Rejected after first review.")
