from __future__ import annotations

import json

from jobpipe.cli import export_reactive_resume_plan


def test_export_reactive_resume_plan_cli_writes_plan(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        export_reactive_resume_plan,
        "build_payload",
        lambda *args, **kwargs: {
            "jobs": [
                {
                    "job_id": "job-rr-1",
                    "run_id": "run-123",
                    "title": "Senior Product Owner",
                    "employer": "Example Co",
                    "sector": "SaaS",
                    "description_snip": "Needs product strategy and delivery.",
                    "recommendation_reason": "Strong fit.",
                    "cv_focus": ["Platform leadership"],
                    "detail": {"overlaps": ["Product leadership"], "gaps": [], "hard_blockers": [], "match_notes": "Strong fit."},
                    "final_decision": "APPLY",
                }
            ]
        },
    )
    monkeypatch.setattr(
        export_reactive_resume_plan,
        "load_candidate_profile_pack",
        lambda *args, **kwargs: "Looking for clear ownership and visible value creation.",
    )
    monkeypatch.setattr(
        export_reactive_resume_plan,
        "load_candidate_resume_json",
        lambda *args, **kwargs: {
            "work": [
                {
                    "name": "Example SaaS",
                    "position": "Senior Product Manager",
                    "summary": "Led product strategy and delivery.",
                    "highlights": ["Led roadmap prioritization."],
                }
            ],
            "projects": [],
            "education": [],
            "skills": [],
        },
    )

    out_path = tmp_path / "reactive_resume_job-rr-1.json"
    export_reactive_resume_plan.main(["job-rr-1", "--out", str(out_path)])

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["job_id"] == "job-rr-1"
    assert payload["tailored_cv_plan"]["selected_evidence_unit_ids"]
    assert payload["tailored_cv_projection"]["selected_bullets"]
