from __future__ import annotations

import sqlite3

from jobpipe.core.evaluation_state import load_job_catalog, load_processed_job_ids
from jobpipe.core.primary_db import connect_primary_db, ensure_candidate, upsert_job_evaluation


def test_load_job_catalog_prefers_primary_db(tmp_path):
    db_path = tmp_path / "jobpipe.sqlite"
    ledger_path = tmp_path / "ledger.sqlite"

    conn = connect_primary_db(db_path)
    ensure_candidate(conn, candidate_id="candidate-a")
    upsert_job_evaluation(
        conn,
        {
            "candidate_id": "candidate-a",
            "job_id": "job-db",
            "run_id": "run-1",
            "run_mtime": 1713260000.0,
            "run_seen_at": "2026-04-17T10:00:00Z",
            "title": "Primary DB Job",
            "employer": "Example AS",
            "sector": "",
            "work_city": "Oslo",
            "work_county": "",
            "work_postalCode": "",
            "applicationDue": "",
            "source_url": "",
            "application_url": "",
            "triage_decision": "APPLY",
            "triage_confidence": 0.9,
            "triage_explanation": "",
            "triage_signals": "",
            "reverse_decision": "",
            "reverse_confidence": None,
            "reverse_rationale": "",
            "fit_score": 80,
            "pivot_score": 30,
            "final_decision": "APPLY",
            "final_confidence": 0.88,
            "recommendation_reason": "",
            "cv_focus": "",
            "feedback_flags": "",
            "description_snip": "",
            "skip_reason": "passed",
            "raw_index_json": "{}",
            "raw_match_json": "{}",
            "raw_pivot_json": "{}",
            "raw_moderator_json": "{}",
            "closed_at": "",
            "updated_at": "2026-04-17T10:05:00Z",
        },
    )
    conn.commit()
    conn.close()

    ledger = sqlite3.connect(str(ledger_path))
    ledger.execute(
        "CREATE TABLE ledger (job_id TEXT, title TEXT, employer TEXT, work_city TEXT, final_decision TEXT)"
    )
    ledger.execute(
        "INSERT INTO ledger (job_id, title, employer, work_city, final_decision) VALUES (?, ?, ?, ?, ?)",
        ["job-ledger", "Ledger Job", "Fallback AS", "Bergen", "REVIEW_HIGH"],
    )
    ledger.commit()
    ledger.close()

    rows = load_job_catalog(
        primary_db_path=db_path,
        candidate_id="candidate-a",
        ledger_path=ledger_path,
    )

    assert [row["job_id"] for row in rows] == ["job-db"]
    assert rows[0]["title"] == "Primary DB Job"
    assert load_processed_job_ids(
        primary_db_path=db_path,
        candidate_id="candidate-a",
        ledger_path=ledger_path,
    ) == {"job-db"}


def test_load_job_catalog_falls_back_to_ledger(tmp_path):
    ledger_path = tmp_path / "ledger.sqlite"

    ledger = sqlite3.connect(str(ledger_path))
    ledger.execute(
        "CREATE TABLE ledger (job_id TEXT, title TEXT, employer TEXT, work_city TEXT, final_decision TEXT)"
    )
    ledger.execute(
        "INSERT INTO ledger (job_id, title, employer, work_city, final_decision) VALUES (?, ?, ?, ?, ?)",
        ["job-ledger", "Ledger Job", "Fallback AS", "Bergen", "REVIEW_HIGH"],
    )
    ledger.commit()
    ledger.close()

    rows = load_job_catalog(
        primary_db_path=tmp_path / "missing.sqlite",
        candidate_id="candidate-a",
        ledger_path=ledger_path,
    )

    assert [row["job_id"] for row in rows] == ["job-ledger"]
    assert rows[0]["title"] == "Ledger Job"
    assert load_processed_job_ids(
        primary_db_path=tmp_path / "missing.sqlite",
        candidate_id="candidate-a",
        ledger_path=ledger_path,
    ) == {"job-ledger"}
