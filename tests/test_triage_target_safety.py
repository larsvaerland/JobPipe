from __future__ import annotations

from textwrap import dedent
from unittest.mock import MagicMock, patch

from jobpipe.model.schema import JobContext, RunMeta, TriageOut
from jobpipe.stages.triage import triage_stage_factory


SAFETY_RULES = {
    "geo_enabled": False,
    "geo_postal_regex": "",
    "geo_allow_remote_regex": "",
    "geo_county_regex": "",
    "hard_no_title_regex": "",
    "target_title_regex": r"(?i)\b(produktleder\w*|product\s+manager|product\s+owner|digitaliseringsleder\w*)\b",
    "very_strong_positive_regex": "",
    "weak_positive_regex": "",
    "weak_anchor_regex": "",
    "never_skip_if_title_matches": True,
    "weak_override_max_skip_confidence": 0.45,
    "weak_override_min_hits": 4,
    "weak_override_min_hits_with_anchor": 2,
}


def _make_ctx(title: str, *, profile_pack: str) -> JobContext:
    return JobContext(
        meta=RunMeta(run_id="test", pipeline_name="test", created_at="2026-04-20T00:00:00Z"),
        job_id="job-1",
        job={"title": title},
        profile_pack=profile_pack,
    )


def _run_trige_skip(title: str, *, profile_pack: str) -> JobContext:
    with patch("jobpipe.stages.triage.build_triage_agent"), patch("jobpipe.stages.triage.run_agent") as mock_run:
        mock_out = MagicMock()
        mock_out.final_output_as.return_value = TriageOut(
            triage_decision="SKIP",
            confidence=0.82,
            explanation="LLM would skip this role.",
            signals=[],
        )
        mock_run.return_value = mock_out

        _, run = triage_stage_factory(
            model="gpt-4.1-nano",
            max_ad_text_chars=2200,
            safety_rules=SAFETY_RULES,
            profile_pack=profile_pack,
            semantic_threshold=0.0,
        )
        return run(_make_ctx(title, profile_pack=profile_pack), "/tmp")


def test_target_title_safety_still_protects_reference_product_profile() -> None:
    reference_profile = dedent(
        """
        ## 0) Candidate snapshot (quick facts)
        - Level: Mid-Senior
        - Positioning: Product and service delivery leader.

        ### Strategic direction (priority signal for triage)
        Prioritize product, service, platform, CRM, transformation, and digital operations roles.

        ## 1) Target roles (TITLE ANCHORS) - keep if close match
        ### Primary targets (highest priority)
        - Product Owner
        - Product Manager
        - Service Owner

        ### Secondary targets
        - Program Manager

        ## 5) Keyword signals (weighted)
        ### Tier A - Role anchors (highest weight)
        - product owner | product manager | service owner | platform lead
        """
    )

    ctx = _run_trige_skip("Produktleder", profile_pack=reference_profile)

    assert ctx.triage is not None
    assert ctx.triage.triage_decision == "REVIEW"
    assert "safety:target_title" in ctx.triage.signals


def test_target_title_safety_does_not_rescue_off_anchor_public_transition_product_title() -> None:
    public_transition_profile = dedent(
        """
        ## 0) Candidate snapshot (quick facts)
        - Level: Mid-Senior
        - Positioning: Public-sector service management and digitalization transition candidate.

        ### Strategic direction (priority signal for triage)
        Prioritize digitalization advisor, service manager, PMO advisor, process owner, and governance roles.

        ## 1) Target roles (TITLE ANCHORS) - keep if close match
        ### Primary targets (highest priority)
        - Digitalization Advisor
        - Service Manager
        - PMO Advisor
        - Process Owner

        ### Secondary targets
        - Program Coordinator
        - Governance Advisor

        ## 5) Keyword signals (weighted)
        ### Tier A - Role anchors (highest weight)
        - digitalization | process owner | service management | governance | pmo | change management
        """
    )

    ctx = _run_trige_skip("Produktleder", profile_pack=public_transition_profile)

    assert ctx.triage is not None
    assert ctx.triage.triage_decision == "SKIP"
    assert "safety:target_title" not in ctx.triage.signals
    assert "candidate_target_title_mismatch" in ctx.triage.signals


def test_target_title_safety_does_not_treat_negative_product_warning_as_positive_support() -> None:
    specialist_profile = dedent(
        """
        ## 0) Candidate snapshot (quick facts)
        - Level: Mid-Level Specialist
        - Positioning: Analytics and systems specialist.

        ### Strategic direction (priority signal for triage)
        Prioritize analytics, systems specialist, BI, reporting, operations analytics, and application specialist roles.
        Avoid over-promoting broad leadership or generic product titles unless the role clearly rewards hands-on systems depth.

        ## 1) Target roles (TITLE ANCHORS) - keep if close match
        ### Primary targets (highest priority)
        - BI Analyst
        - Operations Analyst
        - Application Specialist

        ### Secondary targets
        - Reporting Manager
        - CRM Specialist

        ## 5) Keyword signals (weighted)
        ### Tier A - Role anchors (highest weight)
        - analytics | bi | reporting | dashboarding | systems specialist | application specialist
        """
    )

    ctx = _run_trige_skip("Produktleder", profile_pack=specialist_profile)

    assert ctx.triage is not None
    assert ctx.triage.triage_decision == "SKIP"
    assert "safety:target_title" not in ctx.triage.signals
    assert "candidate_target_title_mismatch" in ctx.triage.signals


def test_target_title_safety_still_protects_public_transition_anchor_titles() -> None:
    public_transition_profile = dedent(
        """
        ## 0) Candidate snapshot (quick facts)
        - Level: Mid-Senior
        - Positioning: Public-sector service management and digitalization transition candidate.

        ### Strategic direction (priority signal for triage)
        Prioritize digitalization advisor, service manager, PMO advisor, process owner, and governance roles.

        ## 1) Target roles (TITLE ANCHORS) - keep if close match
        ### Primary targets (highest priority)
        - Digitalization Advisor
        - Service Manager
        - PMO Advisor
        - Process Owner

        ### Secondary targets
        - Program Coordinator
        - Governance Advisor
        """
    )

    ctx = _run_trige_skip("Digitaliseringsleder", profile_pack=public_transition_profile)

    assert ctx.triage is not None
    assert ctx.triage.triage_decision == "REVIEW"
    assert "safety:target_title" in ctx.triage.signals
