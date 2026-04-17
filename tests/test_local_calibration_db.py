from __future__ import annotations

import json

from jobpipe.core.primary_db import (
    connect_primary_db,
    ensure_candidate,
    insert_candidate_feedback_event,
    insert_gap_evidence,
    upsert_candidate_calibration_setting,
    upsert_capability_gap,
    upsert_gap_assessment,
)


def test_local_calibration_and_gap_tables_round_trip(tmp_path):
    db_path = tmp_path / "jobpipe.sqlite"

    conn = connect_primary_db(db_path)
    ensure_candidate(conn, candidate_id="candidate-a")

    upsert_candidate_calibration_setting(
        conn,
        {
            "candidate_id": "candidate-a",
            "scope": "ranking",
            "setting_key": "apply_floor",
            "value_json": {"value": 0.72, "reason": "Prefer tighter shortlist"},
            "updated_at": "2026-04-17T12:00:00Z",
        },
    )
    insert_candidate_feedback_event(
        conn,
        {
            "feedback_event_id": "fb_1",
            "candidate_id": "candidate-a",
            "job_id": "job-123",
            "evaluation_id": "run-1:job-123",
            "feedback_type": "recommendation_quality",
            "feedback_value": "good_fit",
            "source": "manual",
            "notes": "This was a realistic recommendation.",
            "evidence_json": {"final_decision": "APPLY", "user_override": False},
            "created_at": "2026-04-17T12:05:00Z",
        },
    )
    upsert_capability_gap(
        conn,
        {
            "gap_id": "gap_1",
            "candidate_id": "candidate-a",
            "gap_key": "formal_people_leadership",
            "label": "Formal people leadership",
            "gap_type": "experience",
            "description": "Repeated blocker in otherwise plausible leadership-adjacent roles.",
            "created_at": "2026-04-17T12:10:00Z",
            "updated_at": "2026-04-17T12:10:00Z",
        },
    )
    insert_gap_evidence(
        conn,
        {
            "gap_evidence_id": "gap_ev_1",
            "candidate_id": "candidate-a",
            "gap_id": "gap_1",
            "job_id": "job-123",
            "evaluation_id": "run-1:job-123",
            "run_id": "run-1",
            "severity": "material_blocker",
            "evidence_source": "raw_match_json.gaps",
            "evidence_text": "No formal people leadership experience.",
            "evidence_json": {"title": "Head of Product Operations"},
            "fit_score": 61,
            "pivot_score": 42,
            "final_decision": "REVIEW_HIGH",
            "created_at": "2026-04-17T12:11:00Z",
        },
    )
    upsert_gap_assessment(
        conn,
        {
            "candidate_id": "candidate-a",
            "gap_id": "gap_1",
            "frequency_score": 0.8,
            "severity_score": 0.9,
            "unlock_score": 0.7,
            "opportunity_quality_score": 0.85,
            "time_to_close": "high",
            "confidence_score": 0.78,
            "priority": "close_now",
            "assessment_json": {
                "jobs_considered": 12,
                "adjacent_blocked_jobs": 5,
                "why": [
                    "Appears repeatedly in leadership-adjacent roles",
                    "Often blocks otherwise plausible recommendations",
                ],
            },
            "updated_at": "2026-04-17T12:12:00Z",
        },
    )
    conn.commit()

    calibration = conn.execute(
        """
        SELECT scope, setting_key, value_json
        FROM candidate_calibration_settings
        WHERE candidate_id = ?
        """,
        ["candidate-a"],
    ).fetchone()
    feedback = conn.execute(
        """
        SELECT feedback_type, feedback_value, evidence_json
        FROM candidate_feedback_events
        WHERE candidate_id = ?
        """,
        ["candidate-a"],
    ).fetchone()
    gap = conn.execute(
        """
        SELECT gap_key, label, gap_type
        FROM capability_gaps
        WHERE candidate_id = ?
        """,
        ["candidate-a"],
    ).fetchone()
    evidence = conn.execute(
        """
        SELECT severity, evidence_source, evidence_json, fit_score, final_decision
        FROM gap_evidence
        WHERE candidate_id = ? AND gap_id = ?
        """,
        ["candidate-a", "gap_1"],
    ).fetchone()
    assessment = conn.execute(
        """
        SELECT priority, time_to_close, assessment_json
        FROM gap_assessments
        WHERE candidate_id = ? AND gap_id = ?
        """,
        ["candidate-a", "gap_1"],
    ).fetchone()
    conn.close()

    assert calibration is not None
    assert calibration[0] == "ranking"
    assert calibration[1] == "apply_floor"
    assert json.loads(calibration[2])["value"] == 0.72

    assert feedback is not None
    assert feedback[0] == "recommendation_quality"
    assert feedback[1] == "good_fit"
    assert json.loads(feedback[2])["final_decision"] == "APPLY"

    assert gap is not None
    assert gap[0] == "formal_people_leadership"
    assert gap[1] == "Formal people leadership"
    assert gap[2] == "experience"

    assert evidence is not None
    assert evidence[0] == "material_blocker"
    assert evidence[1] == "raw_match_json.gaps"
    assert json.loads(evidence[2])["title"] == "Head of Product Operations"
    assert evidence[3] == 61
    assert evidence[4] == "REVIEW_HIGH"

    assert assessment is not None
    assert assessment[0] == "close_now"
    assert assessment[1] == "high"
    assert json.loads(assessment[2])["jobs_considered"] == 12
