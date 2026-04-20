from __future__ import annotations

from typing import Any, Dict

from jobpipe.core.schema import HardGates, JobContext, ModeratorOut
from jobpipe.core.triage_v3 import aggregate_triage_decision
from jobpipe.stages.triage_features import build_triage_features, persist_triage_features
from jobpipe.stages.triage_decision_v3 import persist_triage_decision_v3
from jobpipe.stages.triage_ambiguity_v3 import persist_triage_ambiguity_v3


def _clamp01(x) -> float:
    try:
        x = float(x)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, x))


def moderate_stage_factory(thresholds: Dict[str, Any]):
    """
    Deterministisk moderatorlogikk.

    Regler (som du ba om):
    - hvis fit < review_min_fit  -> SKIP (uansett pivot)
    - hvis fit < review_high_min_fit -> REVIEW_LOW (selv om pivot er høy)
    """

    thr = thresholds or {}

    # eksisterende terskler (fallbacks)
    apply_strong_fit = int(thr.get("apply_strong_fit", 78))
    apply_fit = int(thr.get("apply_fit", 66))
    pivot_boost_apply = int(thr.get("pivot_boost_apply", 72))

    # NYE "gate"-terskler
    review_min_fit = int(thr.get("review_min_fit", 25))
    review_high_min_fit = int(thr.get("review_high_min_fit", 52))

    def should_run(ctx: JobContext) -> bool:
        return True

    def run(ctx: JobContext, job_dir: str) -> JobContext:
        fit = int((ctx.profile_match.fit_score if ctx.profile_match else 0) or 0)
        pivot = int((ctx.pivot.pivot_score if ctx.pivot else 0) or 0)

        # 1) hard gate
        if fit < review_min_fit:
            final = "SKIP"
        # 2) mid gate: alltid REVIEW_LOW
        elif fit < review_high_min_fit:
            final = "REVIEW_LOW"
        else:
            # 3) normal logikk videre
            if fit >= apply_strong_fit:
                final = "APPLY_STRONGLY"
            elif fit >= apply_fit:
                final = "APPLY"
            else:
                final = "REVIEW_HIGH" if pivot >= pivot_boost_apply else "REVIEW_LOW"

        # enkel, stabil confidence
        conf = 0.40 + 0.45 * _clamp01(fit / 100.0) + 0.15 * _clamp01(pivot / 100.0)
        conf = round(float(_clamp01(conf)), 2)

        if ctx.triage_features is None:
            ctx.triage_features = build_triage_features(ctx)
            persist_triage_features(job_dir, ctx.triage_features)

        hard_gates = ctx.triage.hard_gates if ctx.triage and ctx.triage.hard_gates else HardGates()
        if ctx.triage_decision_v3 is None:
            ctx.triage_decision_v3 = aggregate_triage_decision(ctx.triage_features, hard_gates)
            persist_triage_decision_v3(job_dir, ctx.triage_decision_v3)
        if ctx.triage_ambiguity_v3 is not None:
            triage_decision_v3 = ctx.triage_ambiguity_v3.final_decision
        else:
            triage_decision_v3 = ctx.triage_decision_v3
            if triage_decision_v3.needs_ambiguity_pass is False and ctx.triage_ambiguity_v3:
                persist_triage_ambiguity_v3(job_dir, ctx.triage_ambiguity_v3)

        ctx.moderator = ModeratorOut(
            final_decision=final,
            confidence=conf,
            recommendation_reason=f"fit={fit}, pivot={pivot}",
            cv_focus=[],
            feedback_flags=[],
            triage_decision_v3=triage_decision_v3,
        )
        return ctx

    return should_run, run
