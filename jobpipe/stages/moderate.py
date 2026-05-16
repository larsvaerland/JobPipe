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

        # ── v3-veto guard (added 2026-05-16, Cognia FP) ─────────────────────
        # The deterministic fit/pivot moderator above was producing APPLY_STRONGLY
        # for cases the v3 stack had already classified as "discard" + "weak_case"
        # (e.g. construction-site lead scoring 81 because keyword overlap on
        # "leder"/"prosjekt" inflated fit_score, while v3 had every other signal
        # screaming weak match). Veto so v3 disagreement caps the decision.
        veto_reason = None
        adv = ctx.advantage_assessment_v3
        v3_label = getattr(triage_decision_v3, "label", None)
        if v3_label == "discard":
            veto_reason = "v3_discard"
        elif adv is not None and adv.advantage_type == "weak_case" and fit < 85:
            veto_reason = "advantage_weak_case"
        if veto_reason:
            # Strong vote-against: never promote past REVIEW_LOW. SKIP only when
            # the moderator already wanted it (don't downgrade a moderator
            # REVIEW_LOW to SKIP — keep the chance of a human review).
            if final in ("APPLY_STRONGLY", "APPLY", "REVIEW_HIGH"):
                final = "REVIEW_LOW"

        ctx.moderator = ModeratorOut(
            final_decision=final,
            confidence=conf,
            recommendation_reason=(
                f"fit={fit}, pivot={pivot}"
                + (f", veto={veto_reason}" if veto_reason else "")
            ),
            cv_focus=[],
            feedback_flags=([veto_reason] if veto_reason else []),
            triage_decision_v3=triage_decision_v3,
        )
        return ctx

    return should_run, run
