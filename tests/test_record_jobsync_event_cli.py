from __future__ import annotations

import json
import sqlite3

from jobpipe.cli import record_jobsync_event


def test_record_jobsync_event_cli_writes_primary_db(tmp_path, capsys) -> None:
    db_path = tmp_path / "jobpipe.sqlite"

    record_jobsync_event.main(
        [
            "job-123",
            "applied",
            "--candidate-id",
            "candidate-a",
            "--db",
            str(db_path),
            "--notes",
            "Sent via jobsync",
            "--metadata-json",
            '{"channel": "jobsync"}',
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert output["job_id"] == "job-123"
    assert output["event_type"] == "applied"
    assert output["metadata_json"]["channel"] == "jobsync"

    con = sqlite3.connect(str(db_path))
    summary = con.execute(
        "SELECT current_stage, current_outcome, effective_status, notes_latest FROM application_summary "
        "WHERE candidate_id = ? AND job_id = ?",
        ["candidate-a", "job-123"],
    ).fetchone()
    event = con.execute(
        "SELECT event_type, source, notes FROM application_events WHERE candidate_id = ? AND job_id = ?",
        ["candidate-a", "job-123"],
    ).fetchone()
    con.close()

    assert summary == ("applied", "", "applied", "Sent via jobsync")
    assert event == ("applied", "jobsync", "Sent via jobsync")
