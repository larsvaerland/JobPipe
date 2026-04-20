from __future__ import annotations

from jobpipe.projections import (
    build_resume_import_projection,
    build_tailored_cv_plan,
    build_tailored_cv_projection,
)


def _sample_row() -> dict:
    return {
        "job_id": "job-rr-1",
        "run_id": "run-123",
        "title": "Senior Product Owner",
        "employer": "Example Co",
        "sector": "SaaS",
        "description_snip": "Needs product strategy, platform delivery, and stakeholder management.",
        "recommendation_reason": "Strong fit for platform ownership.",
        "cv_focus": ["Platform leadership", "Product strategy"],
        "detail": {
            "overlaps": ["Product leadership", "Platform delivery"],
            "gaps": ["Marketplace exposure"],
            "hard_blockers": [],
            "match_notes": "Strong fit.",
        },
        "final_decision": "APPLY",
    }


def _sample_resume() -> dict:
    return {
        "basics": {"name": "Lars"},
        "work": [
            {
                "name": "Example SaaS",
                "position": "Senior Product Manager",
                "summary": "Led product strategy and platform delivery.",
                "highlights": [
                    "Led roadmap prioritization across platform teams and stakeholders.",
                    "Improved delivery predictability by 25% through workflow changes.",
                ],
            }
        ],
        "projects": [
            {
                "name": "Platform migration",
                "description": "Coordinated rollout and vendor alignment for a platform migration.",
            }
        ],
        "education": [{"institution": "BI", "area": "Management", "studyType": "Bachelor"}],
        "skills": [{"name": "Product strategy"}],
    }


def test_build_resume_import_projection_maps_resume_json() -> None:
    projection = build_resume_import_projection(_sample_resume(), candidate_id="candidate-a", resume_source_id="resume-1")
    assert projection.candidate_id == "candidate-a"
    assert projection.resume_source_id == "resume-1"
    assert len(projection.work) == 1
    assert projection.metadata["work_count"] == 1


def test_build_tailored_cv_plan_and_projection_use_existing_decision_semantics() -> None:
    row = _sample_row()
    resume_json = _sample_resume()
    profile_pack = "Product-facing operator looking for clear ownership and visible value creation."

    plan = build_tailored_cv_plan(
        row,
        profile_pack=profile_pack,
        resume_json=resume_json,
        candidate_id="candidate-a",
    )
    projection = build_tailored_cv_projection(
        row,
        plan,
        profile_pack=profile_pack,
        resume_json=resume_json,
        candidate_id="candidate-a",
    )

    assert plan.job_id == "job-rr-1"
    assert plan.variant_strategy == "balanced"
    assert plan.selected_evidence_unit_ids
    assert "summary" in plan.selected_section_order
    assert plan.claim_targets
    assert projection.summary_text
    assert projection.selected_bullets
    assert projection.provenance["job_id"] == "job-rr-1"
