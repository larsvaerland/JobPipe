from __future__ import annotations

from unittest.mock import MagicMock, patch

from jobpipe.core.schema import JobContext, JobParse, PivotOut, ProfileMatchOut, ReverseTriageOut, RunMeta, TriageOut
from jobpipe.stages.pivot import pivot_stage_factory
from jobpipe.stages.reverse_triage import reverse_triage_stage_factory


def _ctx() -> JobContext:
    return JobContext(
        meta=RunMeta(run_id="test", pipeline_name="test", created_at="2026-01-01T00:00:00Z"),
        job_id="job-1",
        job={
            "title": "Produktleder",
            "employer_name": "Avinor",
            "description_html": "Strategisk produktrolle med eierskap og tjenesteutvikling.",
        },
        profile_pack="RAW PROFILE PACK SHOULD NOT BE FORWARDED",
    )


def test_pivot_stage_uses_derived_context_not_profile_pack_excerpt() -> None:
    ctx = _ctx()
    ctx.parsed = JobParse(
        role_summary="Produktrolle",
        responsibilities=["Eie tjeneste"],
        requirements_must=["Produktledelse"],
        requirements_nice=[],
        domain_tags=["offentlig sektor"],
        tools_tech=["Jira"],
        red_flags=[],
    )
    ctx.profile_match = ProfileMatchOut(
        fit_score=74,
        match_level="strong",
        overlaps=["Produktledelse"],
        gaps=[],
        hard_blockers=[],
        notes="Strong overlap",
    )

    should_run, run = pivot_stage_factory(model="gpt-4.1-mini")
    assert should_run(ctx) is True

    with patch("jobpipe.stages.pivot.run_agent") as mock_run:
        mock_result = MagicMock()
        mock_result.final_output_as.return_value = PivotOut(
            pivot_score=71,
            pivot_type="styring",
            potential_risk="low",
            why_it_matters=["Relevant scope"],
        )
        mock_run.return_value = mock_result

        run(ctx, job_dir="/tmp/test")

        input_text = mock_run.call_args.args[1]
        assert "pivot_context" in input_text
        assert "profile_pack_excerpt" not in input_text
        assert "RAW PROFILE PACK SHOULD NOT BE FORWARDED" not in input_text


def test_reverse_triage_stage_uses_derived_context_not_profile_pack_excerpt() -> None:
    ctx = _ctx()
    ctx.triage = TriageOut(
        triage_decision="SKIP",
        confidence=0.62,
        explanation="Borderline skip",
        signals=["sim:0.31"],
    )

    should_run, run = reverse_triage_stage_factory(
        model="gpt-4.1-mini",
        max_ad_text_chars=1200,
        min_conf=0.7,
        skip_above=1.0,
    )
    assert should_run(ctx) is True

    with patch("jobpipe.stages.reverse_triage.run_agent") as mock_run:
        mock_result = MagicMock()
        mock_result.final_output_as.return_value = ReverseTriageOut(
            reverse_decision="SKIP_CONFIRMED",
            confidence=0.81,
            rationale="Still out of scope",
            reasoning_flags=["confirmed"],
        )
        mock_run.return_value = mock_result

        run(ctx, job_dir="/tmp/test")

        input_text = mock_run.call_args.args[1]
        assert "reverse_triage_context" in input_text
        assert "profile_pack_excerpt" not in input_text
        assert "RAW PROFILE PACK SHOULD NOT BE FORWARDED" not in input_text
