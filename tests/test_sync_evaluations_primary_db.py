from __future__ import annotations

from jobpipe.cli.sync_evaluations import mirror_to_primary_db
from jobpipe.core.primary_db import connect_primary_db


def test_mirror_to_primary_db_writes_evaluations_and_events(tmp_path):
    db_path = tmp_path / "jobpipe.sqlite"

    latest_rows = [
        {
            "job_id": "job-1",
            "run_id": "run-1",
            "run_mtime": 1713260000.0,
            "run_seen_at": "2026-04-17T10:00:00Z",
            "title": "Senior PM",
            "employer": "Example AS",
            "sector": "Private",
            "work_city": "Oslo",
            "work_county": "Oslo",
            "work_postalCode": "0001",
            "applicationDue": "2026-04-30",
            "source_url": "https://example.test/job-1",
            "application_url": "",
            "triage_decision": "APPLY",
            "triage_confidence": 0.91,
            "triage_explanation": "Strong overlap.",
            "triage_signals": "platform_suggested",
            "reverse_decision": "",
            "reverse_confidence": None,
            "reverse_rationale": "",
            "fit_score": 82,
            "pivot_score": 35,
            "final_decision": "APPLY",
            "final_confidence": 0.88,
            "recommendation_reason": "Good fit.",
            "cv_focus": "Lead with PM and SaaS work.",
            "feedback_flags": "",
            "description_snip": "Brief description",
            "skip_reason": "passed",
            "raw_index_json": "{}",
            "raw_match_json": "{\"overlaps\": [\"PM\"]}",
            "raw_pivot_json": "{}",
            "raw_moderator_json": "{}",
            "replay_input_json": {
                "job_id": "job-1",
                "title": "Senior PM",
                "employer_name": "Example AS",
                "source": "nav_sheet",
                "sourceurl": "https://example.test/job-1",
                "applicationUrl": "",
                "work_city": "Oslo",
                "work_county": "Oslo",
                "work_postalCode": "0001",
                "applicationDue": "2026-04-30",
                "description_html": "<p>PM role</p>",
            },
            "closed_at": "",
            "updated_at": "2026-04-17T10:05:00Z",
        }
    ]
    event_rows = [
        {
            "run_id": "run-1",
            "job_id": "job-1",
            "run_mtime": 1713260000.0,
            "seen_at": "2026-04-17T10:00:00Z",
            "final_decision": "APPLY",
            "final_confidence": 0.88,
            "triage_decision": "APPLY",
            "triage_confidence": 0.91,
            "fit_score": 82,
            "pivot_score": 35,
            "applicationDue": "2026-04-30",
            "title": "Senior PM",
            "employer": "Example AS",
            "work_city": "Oslo",
            "work_county": "Oslo",
            "work_postalCode": "0001",
            "source_url": "https://example.test/job-1",
            "application_url": "",
            "raw_index_json": "{}",
        }
    ]

    mirror_to_primary_db(db_path, "candidate-a", latest_rows, event_rows)

    conn = connect_primary_db(db_path)
    try:
        evaluation = conn.execute(
            """
            SELECT candidate_id, job_id, final_decision, fit_score, triage_signals, recommendation_reason
            FROM job_evaluations
            WHERE candidate_id = ? AND job_id = ?
            """,
            ["candidate-a", "job-1"],
        ).fetchone()
        event = conn.execute(
            """
            SELECT candidate_id, run_id, job_id, final_decision, fit_score
            FROM job_run_events
            WHERE candidate_id = ? AND run_id = ? AND job_id = ?
            """,
            ["candidate-a", "run-1", "job-1"],
        ).fetchone()
        claim_count = conn.execute(
            "SELECT COUNT(*) FROM job_claims WHERE job_id = ?",
            ["job-1"],
        ).fetchone()[0]
        signal_count = conn.execute(
            "SELECT COUNT(*) FROM job_selection_signals WHERE job_id = ?",
            ["job-1"],
        ).fetchone()[0]
        selection_assessment = conn.execute(
            """
            SELECT structural_pass, selection_risk_level, screenability_score
            FROM job_selection_assessments
            WHERE candidate_id = ? AND job_id = ?
            """,
            ["candidate-a", "job-1"],
        ).fetchone()
        decision_table = conn.execute(
            """
            SELECT act_now, can_do_score, can_get_score
            FROM job_decision_tables
            WHERE candidate_id = ? AND job_id = ?
            """,
            ["candidate-a", "job-1"],
        ).fetchone()
        watchlist_count = conn.execute(
            "SELECT COUNT(*) FROM watchlists WHERE candidate_id = ?",
            ["candidate-a"],
        ).fetchone()[0]
        change_event = conn.execute(
            """
            SELECT change_type, materiality
            FROM change_events
            WHERE candidate_id = ? AND job_id = ?
            ORDER BY detected_at DESC
            LIMIT 1
            """,
            ["candidate-a", "job-1"],
        ).fetchone()
        replay_input = conn.execute(
            """
            SELECT source_name, source_url, title, employer, input_payload_json
            FROM job_replay_inputs
            WHERE job_id = ?
            """,
            ["job-1"],
        ).fetchone()
    finally:
        conn.close()

    assert evaluation is not None
    assert evaluation[2] == "APPLY"
    assert evaluation[3] == 82
    assert evaluation[4] == "platform_suggested"
    assert evaluation[5] == "Good fit."

    assert event is not None
    assert event[3] == "APPLY"
    assert event[4] == 82

    assert claim_count >= 2
    assert signal_count >= 1

    assert selection_assessment is not None
    assert selection_assessment[0] == 1
    assert selection_assessment[1] in {"low", "medium", "high", "very_high"}
    assert selection_assessment[2] >= 0

    assert decision_table is not None
    assert decision_table[0] in {"pursue_now", "review_then_pursue", "monitor", "skip"}
    assert decision_table[1] >= 0
    assert decision_table[2] >= 0

    assert watchlist_count >= 1

    assert change_event is not None
    assert change_event[0] == "new_job"
    assert change_event[1] in {"medium", "high"}

    assert replay_input is not None
    assert replay_input[0] == "nav_sheet"
    assert replay_input[1] == "https://example.test/job-1"
    assert replay_input[2] == "Senior PM"
    assert replay_input[3] == "Example AS"
    assert "Senior PM" in replay_input[4]
