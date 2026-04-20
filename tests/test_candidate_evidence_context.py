from __future__ import annotations

from jobpipe.decision import build_candidate_evidence_context, derive_candidate_evidence_units


def test_derive_candidate_evidence_units_from_resume_json() -> None:
    units = derive_candidate_evidence_units(
        {
            "work": [
                {
                    "name": "Example SaaS",
                    "position": "Senior Product Manager",
                    "summary": "Led cross-functional product and platform work.",
                    "highlights": [
                        "Led roadmap prioritization across platform teams and stakeholders.",
                        "Improved delivery predictability by 25% through workflow changes.",
                    ],
                }
            ],
            "projects": [
                {
                    "name": "Platform migration",
                    "description": "Coordinated rollout and supplier alignment for a new platform.",
                }
            ],
            "education": [
                {
                    "institution": "BI",
                    "area": "Management",
                    "studyType": "Bachelor",
                }
            ],
        },
        candidate_id="candidate-a",
    )

    assert len(units) >= 4
    assert any(unit.source_type == "work_highlight" for unit in units)
    assert any(unit.source_type == "project_case" for unit in units)
    assert any(unit.source_type == "education" for unit in units)
    assert any("product" in unit.role_family_tags for unit in units if unit.source_type == "work_highlight")
    assert any("delivery_execution" in unit.capability_tags for unit in units)


def test_build_candidate_evidence_context_selects_relevant_units_for_job() -> None:
    context = build_candidate_evidence_context(
        {
            "title": "Principal Product Lead",
            "sector": "SaaS",
            "description_snip": "Needs product strategy, platform delivery, and stakeholder management.",
            "detail": {
                "overlaps": ["Product leadership", "Platform delivery"],
                "gaps": [],
                "hard_blockers": [],
                "match_notes": "Strong product/platform overlap.",
            },
        },
        {
            "work": [
                {
                    "name": "Example SaaS",
                    "position": "Senior Product Manager",
                    "summary": "Led product strategy and platform roadmap work.",
                    "highlights": [
                        "Led roadmap prioritization across platform teams and stakeholders.",
                        "Improved delivery predictability by 25% through workflow changes.",
                    ],
                },
                {
                    "name": "Regional Health Org",
                    "position": "Operations Manager",
                    "summary": "Ran service operations and vendor coordination.",
                    "highlights": [
                        "Managed supplier handoffs and support queues.",
                    ],
                },
            ],
            "projects": [],
            "education": [],
        },
        candidate_id="candidate-a",
        focus_terms=["Platform leadership", "Product strategy"],
        limit=3,
    )

    assert len(context.candidate_evidence_units) >= 3
    assert 1 <= len(context.selected_evidence_units) <= 3
    top = context.selected_evidence_units[0]
    assert top.canonical_text
    assert top.relevance_score >= 40
    assert top.matched_role_family_tags or top.matched_capability_tags or top.targeted_terms
