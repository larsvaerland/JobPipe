from __future__ import annotations

from typing import Any, Dict, Callable, Tuple

from jobpipe.core.profile_pack import parse_profile_pack
from jobpipe.decision import derive_selection_assessment
from jobpipe.model.schema import JobContext, ModeratorOut

_SCOPE_CAUTION_TERMS = ("early", "junior", "coordinator", "associate", "specialist", "operations")
_PRODUCT_FAMILY_TERMS = ("product", "produkt")


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
    - svake REVIEW_LOW-kandidater kan demoteres hvis kandidatprofilen gjør
      bred produktledelse tydelig off-anchor og screeningsrisikoen er svært høy
    """

    thr = thresholds or {}

    # eksisterende terskler (fallbacks)
    apply_strong_fit = int(thr.get("apply_strong_fit", 78))
    apply_fit = int(thr.get("apply_fit", 66))
    pivot_boost_apply = int(thr.get("pivot_boost_apply", 72))

    # NYE "gate"-terskler
    review_min_fit = int(thr.get("review_min_fit", 25))              # <- løsere gate (justér i yaml)
    review_high_min_fit = int(thr.get("review_high_min_fit", 52))    # <- under denne blir det alltid REVIEW_LOW

    def _profile_text(candidate_profile: dict[str, Any]) -> str:
        snapshot = candidate_profile.get("snapshot") or {}
        return " ".join(
            str(part).strip()
            for part in (
                snapshot.get("level"),
                snapshot.get("positioning"),
                candidate_profile.get("strategic_direction"),
            )
            if str(part).strip()
        ).lower()

    def _profile_list(candidate_profile: dict[str, Any], *path: str) -> list[str]:
        current: Any = candidate_profile
        for key in path:
            if not isinstance(current, dict):
                return []
            current = current.get(key)
        if not isinstance(current, list):
            return []
        return [str(value).strip() for value in current if str(value).strip()]

    def _supports_broad_product_scope(candidate_profile: dict[str, Any]) -> bool:
        targets = [
            *_profile_list(candidate_profile, "target_roles", "primary"),
            *_profile_list(candidate_profile, "target_roles", "secondary"),
        ]
        for target in targets:
            normalized = target.lower()
            if not any(term in normalized for term in _PRODUCT_FAMILY_TERMS):
                continue
            if any(term in normalized for term in _SCOPE_CAUTION_TERMS):
                continue
            return True
        return False

    def _candidate_risk_demotes_review(ctx: JobContext, fit: int, pivot: int) -> bool:
        profile_pack = str(ctx.profile_pack or "").strip()
        if not profile_pack:
            return False

        candidate_profile = parse_profile_pack(profile_pack)
        if not candidate_profile:
            return False

        title = str(ctx.job.get("normalized_title") or ctx.job.get("title") or "").strip()
        if not title:
            return False

        assessment = derive_selection_assessment(
            {
                "title": title,
                "sector": str(ctx.job.get("sector") or "").strip(),
                "fit_score": fit,
                "pivot_score": pivot,
                "triage_signals": list(getattr(ctx.triage, "signals", []) or []),
                "detail": {
                    "hard_blockers": list(getattr(ctx.profile_match, "hard_blockers", []) or []),
                },
            },
            candidate_profile=candidate_profile,
        )

        candidate_flags = assessment.assessment_json.get("candidate_profile_flags", {})
        profile_text = _profile_text(candidate_profile)
        return (
            bool(candidate_flags.get("product_leadership_off_anchor"))
            and any(term in profile_text for term in _SCOPE_CAUTION_TERMS)
            and not _supports_broad_product_scope(candidate_profile)
            and assessment.selection_risk_level == "very_high"
        )

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

        candidate_risk_demoted = False
        if final == "REVIEW_LOW" and _candidate_risk_demotes_review(ctx, fit, pivot):
            final = "SKIP"
            candidate_risk_demoted = True

        # enkel, stabil confidence
        conf = 0.40 + 0.45 * _clamp01(fit / 100.0) + 0.15 * _clamp01(pivot / 100.0)
        conf = round(float(_clamp01(conf)), 2)

        reason = f"fit={fit}, pivot={pivot}"
        if candidate_risk_demoted:
            reason += ", candidate_risk=off_anchor_product_leadership_scope"

        ctx.moderator = ModeratorOut(
            final_decision=final,
            confidence=conf,
            recommendation_reason=reason,
            cv_focus=[],
            feedback_flags=[],
        )
        return ctx

    return should_run, run
