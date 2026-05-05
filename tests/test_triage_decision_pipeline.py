from __future__ import annotations

from pathlib import Path

from jobpipe.core.runner import PipelineRunner, Stage
from jobpipe.core.schema import (
    FeatureScore,
    HardGates,
    JobContext,
    RunMeta,
    TriageAmbiguityV3,
    TriageDecisionV3,
    TriageFeatures,
    TriageOut,
)
from jobpipe.stages.triage_ambiguity_v3 import triage_ambiguity_v3_stage_factory
from jobpipe.stages.triage_decision_v3 import triage_decision_v3_stage_factory


def _feature(score: int, confidence: int = 80) -> FeatureScore:
    return FeatureScore(score=score, confidence=confidence, reason="test", evidence_spans=[])


def _ctx() -> JobContext:
    ctx = JobContext(
        meta=RunMeta(run_id="test", pipeline_name="test", created_at="2026-01-01T00:00:00Z"),
        job_id="job-1",
        job={"title": "Produkteier"},
        profile_pack="",
    )
    ctx.triage = TriageOut(triage_decision="REVIEW", confidence=0.8, explanation="ok", signals=[], hard_gates=HardGates())
    ctx.triage_features = TriageFeatures(
        core_tech_alignment=_feature(58),
        legacy_burden=_feature(56),
        role_specificity=_feature(54),
        requirement_density=_feature(50),
        geospatial_friction=_feature(24),
        remote_veracity=_feature(82),
        autonomy_level=_feature(48),
        stakeholder_complexity=_feature(46),
        operating_fit=_feature(50),
    )
    return ctx


def test_triage_decision_stage_sets_ctx() -> None:
    should_run, run = triage_decision_v3_stage_factory()
    ctx = _ctx()
    assert should_run(ctx) is True
    result = run(ctx, "/tmp")
    assert result.triage_decision_v3 is not None
    assert result.triage_decision_v3.needs_ambiguity_pass is True


def test_triage_ambiguity_stage_resolves_borderline_review() -> None:
    ctx = _ctx()
    ctx.triage_decision_v3 = TriageDecisionV3(
        label="review",
        weighted_score=55.0,
        confidence=58,
        needs_ambiguity_pass=True,
        blockers=[],
        boosts=[],
        summary="review from weighted feature aggregation.",
    )
    should_run, run = triage_ambiguity_v3_stage_factory()
    assert should_run(ctx) is True
    result = run(ctx, "/tmp")
    assert result.triage_ambiguity_v3 is not None
    assert result.triage_ambiguity_v3.final_decision.needs_ambiguity_pass is False
    assert result.triage_ambiguity_v3.resolved_label == "review"


def test_pipeline_runner_writes_numbered_decision_and_ambiguity_artifacts(tmp_path: Path) -> None:
    decision_should, decision_run = triage_decision_v3_stage_factory()
    ambiguity_should, ambiguity_run = triage_ambiguity_v3_stage_factory()
    runner = PipelineRunner(
        [
            Stage(name="triage_decision_v3", run=decision_run, should_run=decision_should, ctx_model=TriageDecisionV3),
            Stage(name="triage_ambiguity_v3", run=ambiguity_run, should_run=ambiguity_should, ctx_model=TriageAmbiguityV3),
        ]
    )
    runner.run_job(_ctx(), str(tmp_path))

    matches = sorted(path.name for path in tmp_path.glob("*_triage_*v3.json"))
    assert matches == ["01_triage_decision_v3.json", "02_triage_ambiguity_v3.json"]
