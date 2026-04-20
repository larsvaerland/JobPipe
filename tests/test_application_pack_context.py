from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from jobpipe.core.paths import JOBPIPE_DATA_ROOT_ENV
from jobpipe.core.schema import (
    AdvantageAssessmentV3,
    JobContext,
    JobParse,
    ModeratorOut,
    NarrativeStrategyV3,
    PivotOut,
    ProfileMatchOut,
    RunMeta,
)
from jobpipe.stages.application_pack import _build_application_pack_payload


def _write_profile_sources(data_root: Path) -> None:
    (data_root / "reports").mkdir(parents=True, exist_ok=True)
    (data_root / "profile_pack.md").write_text(
        dedent(
            """
            # PROFILE_PACK

            ## 0) Candidate snapshot
            - Base: Arendal
            - Languages: Norwegian + English
            - Level: Senior IC / lead
            - Positioning: Builds digital services across tech, business, and operations.

            ### Strategic direction
            Long-term goal is strategic service ownership with clear business value.

            ## 1) Target roles
            ### Primary targets
            - Produktleder
            - Tjenesteeier

            ### Secondary targets
            - CRM-ansvarlig

            ### Stepping-stone roles
            - Teamleder IT

            ## 2) Must-haves
            ### Location (OK if any)
            - Agder
            - Oslo
            Remote/Hybrid: always OK

            ## 7b) Market positioning context
            Motivation language core: "Jeg er motivert av roller der jeg kan forbedre digitale tjenester."
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (data_root / "reports" / "resume.json").write_text(
        json.dumps(
            {
                "basics": {"name": "Lars Værland", "label": "Produkteier"},
                "work": [
                    {
                        "name": "Avinor",
                        "position": "Produktleder",
                        "startDate": "2024-01-01",
                        "endDate": "2025-01-01",
                        "summary": "Ledet produktutvikling og digital tjenesteforbedring.",
                        "highlights": ["Ledet produktteam", "Drevet digitalisering"],
                    }
                ],
                "projects": [
                    {"name": "CRM-program", "description": "Forbedret kundereiser og systemstøtte."}
                ],
                "skills": [
                    {"name": "Produkt", "keywords": ["Prioritering", "Backlog"]},
                    {"name": "ServiceNow", "keywords": ["ITSM", "Forvaltning"]},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_application_pack_payload_uses_derived_authoring_context(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(JOBPIPE_DATA_ROOT_ENV, str(tmp_path))
    _write_profile_sources(tmp_path)

    ctx = JobContext(
        meta=RunMeta(run_id="run_1", pipeline_name="jobpipe", created_at="2026-04-19T00:00:00Z"),
        job_id="nav_123",
        job={
            "title": "Produktleder",
            "employer_name": "Avinor",
            "sector": "Aviation",
            "applicationDue": "2026-05-01",
            "sourceurl": "https://example.test/job",
        },
        profile_pack="legacy profile text",
        parsed=JobParse(
            role_summary="Produktleder med tydelig eierskap.",
            responsibilities=["Lede produktarbeid"],
            requirements_must=["Produktledelse"],
            requirements_nice=["ServiceNow"],
        ),
        profile_match=ProfileMatchOut(
            fit_score=82,
            match_level="strong",
            overlaps=["Produktledelse", "ServiceNow"],
            gaps=[],
            hard_blockers=[],
            notes="Sterk match.",
        ),
        pivot=PivotOut(
            pivot_score=64,
            pivot_type="adjacent",
            potential_risk="low",
            why_it_matters=["Tydelig eierskap"],
        ),
        advantage_assessment_v3=AdvantageAssessmentV3(
            advantage_type="strong_fit",
            advantage_signals=["Produktledelse", "ServiceNow"],
            objection_signals=["offentlig sektor"],
            neutralizing_evidence=["Ledet produktteam"],
            stretch_level="low",
            review_priority=81,
            confidence=78,
            summary="Strong fit with a minor domain objection.",
        ),
        narrative_strategy_v3=NarrativeStrategyV3(
            positioning_angle="Direkte relevant produktledelse som kan levere raskt i rollen.",
            brand_frame="Brobygger mellom produkt og drift",
            why_me_now="Har allerede erfaring som matcher kjernen i rollen.",
            top_value_props=["Produktledelse", "ServiceNow"],
            objections_to_handle=["offentlig sektor"],
            cv_focus_order=["ownership", "delivery", "ServiceNow"],
            cover_letter_strategy="Åpne med relevant eierskap og underbygg med leveranser.",
            confidence=79,
            summary="Narrative strategy for Produktleder.",
        ),
        moderator=ModeratorOut(
            final_decision="APPLY",
            confidence=0.88,
            recommendation_reason="Strong fit",
            cv_focus=["ownership", "delivery"],
            feedback_flags=[],
        ),
    )

    payload = _build_application_pack_payload(ctx)

    assert "profile_pack" not in payload
    assert "resume_work" not in payload
    assert "resume_projects" not in payload
    assert payload["authoring_context"]["schema_version"] == "jobpipe.profile-layer.v1"
    assert payload["authoring_context"]["profile_snapshot"]["target_roles"][0] == "Produktleder"
    assert payload["authoring_context"]["authoring_profile"]["strongest_storylines"]
    assert payload["authoring_context"]["role_records"][0]["company"] == "Avinor"
    assert payload["authoring_context"]["selected_evidence_atoms"][0]["text"] == "Ledet produktteam"
    assert payload["advantage_assessment"]["advantage_type"] == "strong_fit"
    assert payload["narrative_strategy"]["brand_frame"] == "Brobygger mellom produkt og drift"
    assert payload["narrative_strategy"]["cv_focus_order"][0] == "ownership"
