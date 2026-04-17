from __future__ import annotations

import json

from jobpipe.cli.gap_analysis_report import run_gap_analysis
from jobpipe.core.primary_db import connect_primary_db, ensure_candidate, upsert_job_evaluation


def _seed_eval(
    conn,
    *,
    candidate_id: str,
    job_id: str,
    run_id: str,
    title: str,
    employer: str,
    fit_score: int,
    final_decision: str,
    gaps: list[str],
    hard_blockers: list[str] | None = None,
) -> None:
    upsert_job_evaluation(
        conn,
        {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "run_id": run_id,
            "run_mtime": 1713350000.0,
            "run_seen_at": "2026-04-17T14:00:00Z",
            "title": title,
            "employer": employer,
            "sector": "",
            "work_city": "Oslo",
            "work_county": "Oslo",
            "work_postalCode": "",
            "applicationDue": "",
            "source_url": f"https://example.test/{job_id}",
            "application_url": "",
            "triage_decision": "REVIEW",
            "triage_confidence": 0.7,
            "triage_explanation": "",
            "triage_signals": "",
            "reverse_decision": "",
            "reverse_confidence": None,
            "reverse_rationale": "",
            "fit_score": fit_score,
            "pivot_score": 35,
            "final_decision": final_decision,
            "final_confidence": 0.75,
            "recommendation_reason": "Close fit, but blocked by repeated gaps.",
            "cv_focus": "",
            "feedback_flags": "",
            "description_snip": "",
            "skip_reason": "passed",
            "raw_index_json": "{}",
            "raw_match_json": json.dumps(
                {
                    "overlaps": ["Product leadership"],
                    "gaps": gaps,
                    "hard_blockers": hard_blockers or [],
                    "notes": "",
                },
                ensure_ascii=False,
            ),
            "raw_pivot_json": "{}",
            "raw_moderator_json": "{}",
            "closed_at": "",
            "updated_at": "2026-04-17T14:00:00Z",
        },
    )


def test_gap_analysis_report_persists_gap_state_and_outputs_report(tmp_path):
    db_path = tmp_path / "jobpipe.sqlite"
    out_md = tmp_path / "capability_gap_report.md"
    out_json = tmp_path / "capability_gap_report.json"

    conn = connect_primary_db(db_path)
    ensure_candidate(conn, candidate_id="candidate-a")
    _seed_eval(
        conn,
        candidate_id="candidate-a",
        job_id="job-1",
        run_id="run-1",
        title="Head of Product Operations",
        employer="Example AS",
        fit_score=64,
        final_decision="REVIEW_HIGH",
        gaps=["Manglende erfaring med formell people leadership"],
    )
    _seed_eval(
        conn,
        candidate_id="candidate-a",
        job_id="job-2",
        run_id="run-2",
        title="VP Product Platform",
        employer="Second Example AS",
        fit_score=61,
        final_decision="REVIEW_HIGH",
        gaps=["Ingen dokumentert erfaring med formell people leadership"],
    )
    _seed_eval(
        conn,
        candidate_id="candidate-a",
        job_id="job-3",
        run_id="run-3",
        title="Strategy PM",
        employer="Third Example AS",
        fit_score=47,
        final_decision="REVIEW_LOW",
        gaps=["Manglende erfaring med offentlig anskaffelse"],
    )
    conn.commit()
    conn.close()

    payload = run_gap_analysis(
        db_path=db_path,
        candidate_id="candidate-a",
        out_md=out_md,
        out_json=out_json,
        min_fit=45,
    )

    assert payload["jobs_considered"] == 3
    assert payload["jobs_with_gap_evidence"] == 3
    assert payload["gap_count"] == 2

    leadership_gap = next(g for g in payload["gaps"] if g["gap_key"] == "formell_people_leadership")
    assert leadership_gap["priority"] == "close_now"
    assert leadership_gap["frequency_jobs"] == 2
    assert leadership_gap["time_to_close"] == "high"

    procurement_gap = next(g for g in payload["gaps"] if g["gap_key"] == "offentlig_anskaffelse")
    assert procurement_gap["priority"] in {"monitor", "ignore"}
    assert procurement_gap["frequency_jobs"] == 1

    assert out_md.exists()
    assert out_json.exists()
    assert "Capability Gap Report" in out_md.read_text(encoding="utf-8")

    conn = connect_primary_db(db_path)
    try:
        gap_count = conn.execute(
            "SELECT COUNT(*) FROM capability_gaps WHERE candidate_id = ?",
            ["candidate-a"],
        ).fetchone()[0]
        evidence_count = conn.execute(
            "SELECT COUNT(*) FROM gap_evidence WHERE candidate_id = ?",
            ["candidate-a"],
        ).fetchone()[0]
        close_now_count = conn.execute(
            "SELECT COUNT(*) FROM gap_assessments WHERE candidate_id = ? AND priority = 'close_now'",
            ["candidate-a"],
        ).fetchone()[0]
    finally:
        conn.close()

    assert gap_count == 2
    assert evidence_count == 3
    assert close_now_count == 1
