from __future__ import annotations

from textwrap import dedent

from jobpipe.core.profile_pack import parse_profile_pack
from jobpipe.decision import build_decision_context, derive_job_claims


def test_derive_job_claims_extracts_role_location_and_text_patterns() -> None:
    claims = derive_job_claims(
        {
            "title": "Senior Product Manager",
            "sector": "Public Sector",
            "work_city": "Oslo",
            "work_postalCode": "0001",
            "description_snip": "Norsk språk er viktig. Bachelor degree preferred. Salesforce experience is useful.",
        }
    )

    claim_types = {claim.claim_type for claim in claims}
    labels = {claim.normalized_label for claim in claims}

    assert "role_summary" in claim_types
    assert "location_requirement" in claim_types
    assert "domain_requirement" in claim_types
    assert "language_requirement" in claim_types
    assert "credential_requirement" in claim_types
    assert "tool_requirement" in claim_types
    assert "Senior Product Manager" in labels


def test_build_decision_context_flags_selection_risk_and_mitigations() -> None:
    context = build_decision_context(
        {
            "title": "Principal Product Lead",
            "sector": "Banking",
            "work_city": "Oslo",
            "fit_score": 64,
            "pivot_score": 42,
            "triage_signals": "platform_suggested",
            "description_snip": "Bachelor required. Norwegian language required. Hybrid setup.",
            "detail": {
                "hard_blockers": ["No direct banking experience"],
                "overlaps": ["Product leadership"],
                "gaps": ["Banking domain"],
                "match_notes": "Adjacent fit, but process likely rigid.",
            },
        }
    )

    assert any(signal.normalized_key == "credential_gate" for signal in context.selection_signals)
    assert any(signal.normalized_key == "title_continuity_pressure" for signal in context.selection_signals)
    assert context.selection_assessment.selection_risk_level in {"high", "very_high"}
    assert context.selection_assessment.structural_pass is False
    assert context.selection_assessment.screenability_score < 70
    assert any("title" in move.lower() or "degree" in move.lower() or "location" in move.lower() for move in context.selection_assessment.mitigation_moves)
    assert context.decision_table.can_get.level == "weak"
    assert context.decision_table.should_want.level in {"fragile", "weak"}
    assert context.decision_table.act_now == "skip"
    assert context.decision_table.next_moves


def test_build_decision_context_includes_actionable_decision_table() -> None:
    context = build_decision_context(
        {
            "title": "Senior Product Manager",
            "sector": "SaaS",
            "work_city": "Oslo",
            "fit_score": 83,
            "pivot_score": 72,
            "final_decision": "APPLY",
            "triage_explanation": "Strong overlap in product leadership and platform delivery.",
            "recommendation_reason": "Role aligns with current ownership scope and delivery evidence.",
            "description_snip": "English is fine. Hybrid setup. Jira and SQL experience help.",
            "detail": {
                "hard_blockers": [],
                "overlaps": ["Product leadership", "Platform delivery"],
                "gaps": ["B2C marketplace exposure"],
                "match_notes": "Strong core fit.",
            },
        }
    )

    assert context.decision_table.can_do.level in {"strong", "viable"}
    assert context.decision_table.can_get.level in {"strong", "viable"}
    assert context.decision_table.should_want.level in {"strong", "viable"}
    assert context.decision_table.can_explain.level in {"strong", "viable"}
    assert context.decision_table.act_now == "pursue_now"
    assert context.decision_table.confidence_score >= 0.6


def test_build_decision_context_penalizes_leadership_scope_for_specialist_profile() -> None:
    specialist_profile = parse_profile_pack(
        dedent(
            """
        ## 0) Candidate snapshot (quick facts)
        - Level: Mid-Level Specialist
        - Positioning: Analytics and systems specialist with strong reporting and tool ownership.

        ### Strategic direction (priority signal for triage)
        Prioritize analytics, systems specialist, BI, reporting, and application specialist roles.
        Avoid over-promoting broad leadership or generic product titles unless the role clearly rewards hands-on systems depth.

        ## 1) Target roles (TITLE ANCHORS) - keep if close match
        ### Primary targets (highest priority)
        - BI Analyst
        - Operations Analyst
        - Application Specialist

        ### Secondary targets
        - Reporting Manager

        ### Hard NO (even as stepping stone)
        - Generic people manager

        ## 6) Negative keywords (noise signals)
        - sales
        - cashier
        """
        )
    )
    job = {
        "title": "Head of Product",
        "sector": "SaaS",
        "fit_score": 66,
        "pivot_score": 58,
        "final_decision": "REVIEW_HIGH",
        "recommendation_reason": "Broad product leadership overlap.",
        "description_snip": "Own strategy, roadmap, and cross-functional stakeholder leadership.",
        "detail": {
            "overlaps": ["Cross-functional delivery"],
            "gaps": ["Direct product leadership"],
            "hard_blockers": [],
            "match_notes": "Interesting adjacent role, but broad scope.",
        },
    }

    baseline = build_decision_context(job)
    specialist = build_decision_context(job, candidate_profile=specialist_profile)

    signal_keys = {signal.normalized_key for signal in specialist.selection_signals}
    assert "candidate_scope_mismatch" in signal_keys
    assert specialist.selection_assessment.screenability_score < baseline.selection_assessment.screenability_score
    assert specialist.selection_assessment.ambiguity_risk_score > baseline.selection_assessment.ambiguity_risk_score
    assert specialist.decision_table.can_get.score < baseline.decision_table.can_get.score


def test_build_decision_context_boosts_primary_target_alignment() -> None:
    specialist_profile = parse_profile_pack(
        dedent(
            """
        ## 0) Candidate snapshot (quick facts)
        - Level: Mid-Level Specialist
        - Positioning: Analytics and systems specialist.

        ### Strategic direction (priority signal for triage)
        Prioritize analytics, BI, reporting, and systems specialist roles.

        ## 1) Target roles (TITLE ANCHORS) - keep if close match
        ### Primary targets (highest priority)
        - BI Analyst
        - Operations Analyst
        """
        )
    )
    job = {
        "title": "BI Analyst",
        "sector": "SaaS",
        "fit_score": 62,
        "pivot_score": 55,
        "final_decision": "REVIEW_HIGH",
        "recommendation_reason": "Reporting and analytics overlap.",
        "description_snip": "Build dashboards, reporting, and analytics routines.",
        "detail": {
            "overlaps": ["Reporting", "Dashboards"],
            "gaps": [],
            "hard_blockers": [],
            "match_notes": "Close role-family fit.",
        },
    }

    context = build_decision_context(job, candidate_profile=specialist_profile)

    signal_keys = {signal.normalized_key for signal in context.selection_signals}
    assert "candidate_primary_target_alignment" in signal_keys
    assert context.selection_assessment.title_continuity_score >= 70
    assert context.selection_assessment.screenability_score >= 70
