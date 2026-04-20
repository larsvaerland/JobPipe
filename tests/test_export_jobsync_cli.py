from __future__ import annotations

import json

from jobpipe.cli import export_jobsync


def test_export_jobsync_cli_writes_filtered_cases(tmp_path, monkeypatch) -> None:
    def _fake_payload(*args, **kwargs):
        return {
            "generated_at": "2026-04-20T10:00:00Z",
            "jobs": [
                {
                    "job_id": "job-1",
                    "title": "Senior Python Engineer",
                    "employer": "Acme",
                    "work_city": "Oslo",
                    "applicationDue": "2026-04-30",
                    "source_url": "https://example.com/job-1",
                    "application_url": "https://apply.example.com/job-1",
                    "updated_at": "2026-04-20T10:00:00Z",
                    "final_decision": "APPLY",
                    "recommendation_reason": "Strong fit",
                    "selection_assessment": {"selection_risk_level": "medium", "mitigation_moves": ["Name adjacent domain work."]},
                    "job_claims": [{"claim_text": "Python backend delivery"}],
                    "selection_signals": [{"signal_label": "Hands-on Python"}],
                    "decision_table": {"table_reason": "Worth pursuing", "next_moves": ["Tailor CV"]},
                    "job_narrative_assessment": {"motivation_brief": "Good next step"},
                    "generated_documents": [{"kind": "cv", "status": "draft", "storage_path": "documents/job-1/cv.docx", "updated_at": "2026-04-20T11:00:00Z"}],
                    "app_status": "shortlisted",
                    "app_updated_at": "2026-04-20T11:05:00Z",
                },
                {
                    "job_id": "job-2",
                    "title": "Other role",
                    "employer": "Other",
                    "final_decision": "SKIP",
                },
            ],
        }

    monkeypatch.setattr(export_jobsync, "build_payload", _fake_payload)
    out_path = tmp_path / "jobsync_cases.json"

    export_jobsync.main(["--out", str(out_path)])

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["count"] == 1
    assert payload["cases"][0]["job_summary"]["job_id"] == "job-1"
    assert payload["cases"][0]["decision_brief"]["final_decision"] == "APPLY"


def test_export_jobsync_cli_honors_job_id_filter(tmp_path, monkeypatch) -> None:
    def _fake_payload(*args, **kwargs):
        return {
            "generated_at": "2026-04-20T10:00:00Z",
            "jobs": [
                {"job_id": "job-1", "title": "A", "employer": "Acme", "final_decision": "APPLY"},
                {"job_id": "job-2", "title": "B", "employer": "Beta", "final_decision": "APPLY"},
            ],
        }

    monkeypatch.setattr(export_jobsync, "build_payload", _fake_payload)
    out_path = tmp_path / "jobsync_cases.json"

    export_jobsync.main(["--job-id", "job-2", "--out", str(out_path)])

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["count"] == 1
    assert payload["cases"][0]["job_summary"]["job_id"] == "job-2"
