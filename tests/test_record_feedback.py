from __future__ import annotations

import json

from jobpipe.cli.record_feedback import record_feedback
from jobpipe.core.primary_db import connect_primary_db, ensure_candidate, upsert_job_evaluation


def _seed_eval(conn, *, candidate_id: str, job_id: str, run_id: str) -> None:
    upsert_job_evaluation(
        conn,
        {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "run_id": run_id,
            "run_mtime": 1713350000.0,
            "run_seen_at": "2026-04-17T14:00:00Z",
            "title": "Senior Product Manager",
            "employer": "Example AS",
            "sector": "",
            "work_city": "Oslo",
            "work_county": "Oslo",
            "work_postalCode": "",
            "applicationDue": "",
            "source_url": f"https://example.test/{job_id}",
            "application_url": "https://example.test/apply",
            "triage_decision": "REVIEW",
            "triage_confidence": 0.7,
            "triage_explanation": "",
            "triage_signals": "",
            "reverse_decision": "",
            "reverse_confidence": None,
            "reverse_rationale": "",
            "fit_score": 66,
            "pivot_score": 41,
            "final_decision": "REVIEW_HIGH",
            "final_confidence": 0.81,
            "recommendation_reason": "Strong adjacent role with credible transfer.",
            "cv_focus": "",
            "feedback_flags": "",
            "description_snip": "",
            "skip_reason": "passed",
            "raw_index_json": "{}",
            "raw_match_json": json.dumps({"gaps": [], "hard_blockers": []}, ensure_ascii=False),
            "raw_pivot_json": "{}",
            "raw_moderator_json": "{}",
            "closed_at": "",
            "updated_at": "2026-04-17T14:00:00Z",
        },
    )


def test_record_feedback_persists_manual_signal_with_evaluation_context(tmp_path):
    db_path = tmp_path / "jobpipe.sqlite"
    conn = connect_primary_db(db_path)
    ensure_candidate(conn, candidate_id="candidate-a")
    _seed_eval(conn, candidate_id="candidate-a", job_id="job-123", run_id="run-1")
    conn.commit()
    conn.close()

    result = record_feedback(
        db_path=db_path,
        candidate_id="candidate-a",
        job_id="job-123",
        signal="promote",
        notes="This is a stronger adjacent match than the current rank implies.",
    )

    assert result["feedback_type"] == "manual_override"
    assert result["feedback_value"] == "promote"
    assert result["has_evaluation_context"] is True
    assert result["evaluation"]["title"] == "Senior Product Manager"
    assert result["evaluation"]["fit_score"] == 66

    conn = connect_primary_db(db_path)
    try:
        row = conn.execute(
            """
            SELECT feedback_type, feedback_value, evaluation_id, notes, evidence_json
            FROM candidate_feedback_events
            WHERE candidate_id = ? AND job_id = ?
            """,
            ["candidate-a", "job-123"],
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "manual_override"
    assert row[1] == "promote"
    assert row[2] == "run-1:job-123"
    assert row[3] == "This is a stronger adjacent match than the current rank implies."

    evidence = json.loads(row[4])
    assert evidence["signal"] == "promote"
    assert evidence["evaluation"]["employer"] == "Example AS"
    assert evidence["evaluation"]["final_decision"] == "REVIEW_HIGH"


def test_record_feedback_allows_missing_evaluation_context(tmp_path):
    db_path = tmp_path / "jobpipe.sqlite"
    conn = connect_primary_db(db_path)
    ensure_candidate(conn, candidate_id="candidate-a")
    conn.commit()
    conn.close()

    result = record_feedback(
        db_path=db_path,
        candidate_id="candidate-a",
        job_id="job-missing",
        signal="bad_recommendation",
    )

    assert result["has_evaluation_context"] is False
    assert result["evaluation_id"] == ""

    conn = connect_primary_db(db_path)
    try:
        row = conn.execute(
            """
            SELECT feedback_type, feedback_value, evaluation_id, evidence_json
            FROM candidate_feedback_events
            WHERE candidate_id = ? AND job_id = ?
            """,
            ["candidate-a", "job-missing"],
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "recommendation_quality"
    assert row[1] == "bad_recommendation"
    assert row[2] == ""

    evidence = json.loads(row[3])
    assert evidence == {"signal": "bad_recommendation"}
