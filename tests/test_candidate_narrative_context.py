from __future__ import annotations

from jobpipe.decision import (
    build_candidate_evidence_context,
    build_candidate_narrative_context,
    build_decision_context,
    derive_candidate_evidence_units,
)


def _resume_json() -> dict:
    return {
        "work": [
            {
                "name": "Example SaaS",
                "position": "Senior Product Manager",
                "summary": "Led product strategy and platform delivery across cross-functional teams.",
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
        "education": [
            {
                "institution": "BI",
                "area": "Management",
                "studyType": "Bachelor",
            }
        ],
    }


def test_build_candidate_narrative_context_derives_profile_and_assessment() -> None:
    job = {
        "title": "Principal Product Lead",
        "sector": "SaaS",
        "description_snip": "Needs product strategy, platform delivery, and stakeholder management.",
        "fit_score": 82,
        "pivot_score": 70,
        "final_decision": "APPLY",
        "recommendation_reason": "Role aligns with current ownership and delivery scope.",
        "detail": {
            "overlaps": ["Product strategy", "Platform delivery"],
            "gaps": ["Marketplace exposure"],
            "hard_blockers": [],
            "match_notes": "Strong core fit.",
        },
    }
    evidence_units = derive_candidate_evidence_units(_resume_json(), candidate_id="candidate-a")
    decision_context = build_decision_context(job)

    selected = build_candidate_evidence_context(
        job,
        _resume_json(),
        candidate_id="candidate-a",
        focus_terms=["Platform leadership", "Product strategy"],
        limit=4,
    ).selected_evidence_units

    context = build_candidate_narrative_context(
        job,
        """
        # Profile
        Looking for product and transformation roles with clearer ownership.
        Prefers structured environments where visible delivery and impact matter.
        """,
        evidence_units,
        selected,
        candidate_id="candidate-a",
        decision_table=decision_context.decision_table,
    )

    assert context.narrative_profile.core_identity
    assert context.narrative_profile.future_direction
    assert context.narrative_profile.motivation_themes
    assert context.narrative_fragments
    assert context.narrative_evidence_links
    assert context.job_narrative_assessment.story_strength_score >= 40
    assert context.job_narrative_assessment.motivation_brief


def test_narrative_assessment_flags_explanation_risk_when_story_is_fragile() -> None:
    job = {
        "title": "Principal Banking Product Lead",
        "sector": "Banking",
        "description_snip": "Requires direct banking experience and Norwegian language.",
        "fit_score": 58,
        "pivot_score": 40,
        "final_decision": "REVIEW_LOW",
        "recommendation_reason": "Adjacent fit, but process looks rigid.",
        "detail": {
            "overlaps": ["Product leadership"],
            "gaps": ["Banking domain"],
            "hard_blockers": ["No direct banking experience"],
            "match_notes": "Substantively plausible, but procedurally fragile.",
        },
    }
    evidence_units = derive_candidate_evidence_units(_resume_json(), candidate_id="candidate-a")
    decision_context = build_decision_context(job)
    selected = build_candidate_evidence_context(
        job,
        _resume_json(),
        candidate_id="candidate-a",
        focus_terms=["Product leadership"],
        limit=3,
    ).selected_evidence_units

    context = build_candidate_narrative_context(
        job,
        "Looking for adjacent product and transformation roles without pretending to be a narrow banking specialist.",
        evidence_units,
        selected,
        candidate_id="candidate-a",
        decision_table=decision_context.decision_table,
    )

    assert context.job_narrative_assessment.misalignment_flags
    assert any("explain" in flag.lower() or "forward-fit" in flag.lower() for flag in context.job_narrative_assessment.misalignment_flags)
