from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from jobpipe.core.boundary_objects import build_outcome_feedback

OUTCOME_FEEDBACK_STATE_VERSION = "jobpipe.outcome-feedback-state.v1"
OUTCOMES_DASHBOARD_VERSION = "jobpipe.outcomes-dashboard.v1"
OUTCOME_FEEDBACK_AUDIT_VERSION = "jobpipe.outcome-feedback-audit.v1"
OUTCOME_FEEDBACK_CALIBRATION_VERSION = "jobpipe.outcome-feedback-calibration.v1"
OUTCOME_FEEDBACK_RECOMMENDATION_VERSION = "jobpipe.outcome-feedback-recommendation.v1"
OUTCOME_FEEDBACK_SHADOW_FOLLOWUP_VERSION = "jobpipe.outcome-feedback-shadow-followup.v1"
OUTCOME_FEEDBACK_RANKING_GUIDANCE_VERSION = "jobpipe.outcome-ranking-guidance.v1"

_PROGRESSED_STATUSES = {
    "interview",
    "second_interview",
    "final_interview",
    "offer",
    "accepted",
}
_CLOSED_STATUSES = {
    "dismissed",
    "rejected",
}
_APPLY_LIKE_DECISIONS = {"APPLY", "APPLY_STRONGLY"}


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _feedback_key(run_id: str, job_id: str) -> str:
    return f"{run_id}::{job_id}" if run_id else str(job_id or "").strip()


def _empty_state() -> Dict[str, Any]:
    return {
        "schema_version": OUTCOME_FEEDBACK_STATE_VERSION,
        "updated_at": "",
        "outcomes": {},
    }


def load_outcome_feedback_state(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_state()
    if not isinstance(raw, dict):
        return _empty_state()
    outcomes = raw.get("outcomes", {})
    if not isinstance(outcomes, dict):
        outcomes = {}
    return {
        "schema_version": str(raw.get("schema_version") or OUTCOME_FEEDBACK_STATE_VERSION),
        "updated_at": str(raw.get("updated_at") or ""),
        "outcomes": {
            str(key): value
            for key, value in outcomes.items()
            if isinstance(value, dict)
        },
    }


def persist_outcome_feedback_state(path: Path, state: Dict[str, Any]) -> Dict[str, Any]:
    clean = {
        "schema_version": OUTCOME_FEEDBACK_STATE_VERSION,
        "updated_at": _utc_now_z(),
        "outcomes": {
            str(key): value
            for key, value in dict(state.get("outcomes", {})).items()
            if isinstance(value, dict)
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return clean


def _derive_outcome_label(job: Dict[str, Any]) -> str:
    shared_status = str(job.get("app_status") or "").strip()
    explicit_outcome = str(job.get("app_outcome") or "").strip()
    if explicit_outcome:
        return explicit_outcome
    return shared_status


def _derive_outcome_updated_at(job: Dict[str, Any]) -> str:
    for key in ("app_updated_at", "updated_at", "run_seen_at"):
        value = str(job.get(key) or "").strip()
        if value:
            return value
    return ""


def _clean_artifact_refs(job: Dict[str, Any]) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    for item in list(job.get("generated_documents") or [])[:8]:
        if not isinstance(item, dict):
            continue
        refs.append(
            {
                "kind": str(item.get("kind") or "").strip(),
                "status": str(item.get("status") or "").strip(),
                "storage_path": str(item.get("storage_path") or "").strip(),
            }
        )
    return refs


def build_outcome_feedback_entry(job: Dict[str, Any]) -> Dict[str, Any]:
    detail = job.get("detail") if isinstance(job.get("detail"), dict) else {}
    decision_brief = detail.get("decision_brief") if isinstance(detail.get("decision_brief"), dict) else {}
    application_case_projection = (
        detail.get("application_case_projection")
        if isinstance(detail.get("application_case_projection"), dict)
        else {}
    )
    return build_outcome_feedback(
        external_source="jobpipe",
        external_id=str(job.get("job_id") or ""),
        run_id=str(job.get("run_id") or ""),
        final_decision=str(job.get("final_decision") or ""),
        shared_status=str(job.get("app_status") or ""),
        outcome_label=_derive_outcome_label(job),
        outcome_source=str(job.get("app_source") or ""),
        app_notes=str(job.get("app_notes") or ""),
        updated_at=_derive_outcome_updated_at(job),
        artifact_refs_used=_clean_artifact_refs(job),
        decision_brief=decision_brief,
        application_case_projection=application_case_projection,
    )


def build_outcome_feedback_state(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    outcomes: Dict[str, Dict[str, Any]] = {}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if not str(job.get("job_id") or "").strip():
            continue
        if not isinstance(job.get("detail"), dict):
            continue
        if not any(
            [
                str(job.get("app_status") or "").strip(),
                str(job.get("app_outcome") or "").strip(),
                str(job.get("app_notes") or "").strip(),
                list(job.get("generated_documents") or []),
            ]
        ):
            continue
        key = _feedback_key(str(job.get("run_id") or ""), str(job.get("job_id") or ""))
        outcomes[key] = build_outcome_feedback_entry(job)
    return {
        "schema_version": OUTCOME_FEEDBACK_STATE_VERSION,
        "updated_at": _utc_now_z(),
        "outcomes": outcomes,
    }


def build_outcome_feedback_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    outcomes = state.get("outcomes", {})
    if not isinstance(outcomes, dict):
        outcomes = {}
    entries = [value for value in outcomes.values() if isinstance(value, dict)]
    by_status: Dict[str, int] = {}
    artifact_linked = 0
    for entry in entries:
        status = str(entry.get("shared_status") or "").strip() or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        if list(entry.get("artifact_refs_used") or []):
            artifact_linked += 1
    return {
        "schema_version": "jobpipe.outcome-feedback-summary.v1",
        "total": len(entries),
        "artifact_linked": artifact_linked,
        "by_status": by_status,
    }


def _normalized_entry_status(entry: Dict[str, Any]) -> str:
    status = str(entry.get("shared_status") or "").strip()
    if status:
        return status
    fallback = str(entry.get("outcome_label") or "").strip()
    return fallback or "unknown"


def build_outcome_feedback_audit_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    outcomes = state.get("outcomes", {})
    if not isinstance(outcomes, dict):
        outcomes = {}
    entries = [value for value in outcomes.values() if isinstance(value, dict)]

    decision_status_matrix: Dict[str, Dict[str, int]] = {}
    by_final_decision: Dict[str, int] = {}
    progressed_with_artifacts = 0
    progressed_without_artifacts = 0
    closed_with_artifacts = 0
    closed_without_artifacts = 0
    apply_like_total = 0
    apply_like_applied = 0
    apply_like_progressed = 0
    apply_like_closed = 0

    for entry in entries:
        final_decision = str(entry.get("final_decision") or "").strip() or "unknown"
        status = _normalized_entry_status(entry)
        artifact_refs = list(entry.get("artifact_refs_used") or [])
        has_artifacts = bool(artifact_refs)

        by_final_decision[final_decision] = by_final_decision.get(final_decision, 0) + 1
        decision_bucket = decision_status_matrix.setdefault(final_decision, {})
        decision_bucket[status] = decision_bucket.get(status, 0) + 1

        if status in _PROGRESSED_STATUSES:
            if has_artifacts:
                progressed_with_artifacts += 1
            else:
                progressed_without_artifacts += 1
        elif status in _CLOSED_STATUSES:
            if has_artifacts:
                closed_with_artifacts += 1
            else:
                closed_without_artifacts += 1

        if final_decision in {"APPLY", "APPLY_STRONGLY"}:
            apply_like_total += 1
            if status == "applied":
                apply_like_applied += 1
            elif status in _PROGRESSED_STATUSES:
                apply_like_progressed += 1
            elif status in _CLOSED_STATUSES:
                apply_like_closed += 1

    return {
        "schema_version": OUTCOME_FEEDBACK_AUDIT_VERSION,
        "tracked_total": len(entries),
        "artifact_linked_total": sum(
            1 for entry in entries if list(entry.get("artifact_refs_used") or [])
        ),
        "by_final_decision": by_final_decision,
        "decision_status_matrix": decision_status_matrix,
        "apply_path_summary": {
            "apply_like_total": apply_like_total,
            "applied_count": apply_like_applied,
            "progressed_count": apply_like_progressed,
            "closed_count": apply_like_closed,
        },
        "artifact_effect_summary": {
            "progressed_with_artifacts": progressed_with_artifacts,
            "progressed_without_artifacts": progressed_without_artifacts,
            "closed_with_artifacts": closed_with_artifacts,
            "closed_without_artifacts": closed_without_artifacts,
        },
    }


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 1)


def build_outcome_feedback_calibration_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    outcomes = state.get("outcomes", {})
    if not isinstance(outcomes, dict):
        outcomes = {}
    entries = [value for value in outcomes.values() if isinstance(value, dict)]

    apply_like_total = 0
    apply_like_progressed = 0
    non_apply_total = 0
    non_apply_progressed = 0
    artifact_linked_total = 0
    artifact_linked_progressed = 0
    no_artifact_total = 0
    no_artifact_progressed = 0

    for entry in entries:
        final_decision = str(entry.get("final_decision") or "").strip() or "unknown"
        status = _normalized_entry_status(entry)
        has_artifacts = bool(list(entry.get("artifact_refs_used") or []))
        progressed = status in _PROGRESSED_STATUSES

        if final_decision in _APPLY_LIKE_DECISIONS:
            apply_like_total += 1
            if progressed:
                apply_like_progressed += 1
        else:
            non_apply_total += 1
            if progressed:
                non_apply_progressed += 1

        if has_artifacts:
            artifact_linked_total += 1
            if progressed:
                artifact_linked_progressed += 1
        else:
            no_artifact_total += 1
            if progressed:
                no_artifact_progressed += 1

    return {
        "schema_version": OUTCOME_FEEDBACK_CALIBRATION_VERSION,
        "tracked_total": len(entries),
        "apply_like_total": apply_like_total,
        "apply_like_progressed": apply_like_progressed,
        "apply_like_progression_rate": _percent(apply_like_progressed, apply_like_total),
        "non_apply_total": non_apply_total,
        "non_apply_progressed": non_apply_progressed,
        "non_apply_progression_rate": _percent(non_apply_progressed, non_apply_total),
        "artifact_linked_total": artifact_linked_total,
        "artifact_linked_progressed": artifact_linked_progressed,
        "artifact_linked_progression_rate": _percent(
            artifact_linked_progressed,
            artifact_linked_total,
        ),
        "no_artifact_total": no_artifact_total,
        "no_artifact_progressed": no_artifact_progressed,
        "no_artifact_progression_rate": _percent(
            no_artifact_progressed,
            no_artifact_total,
        ),
    }


def build_outcome_feedback_recommendation(
    calibration_summary: Dict[str, Any],
) -> Dict[str, Any]:
    apply_like_total = int(calibration_summary.get("apply_like_total") or 0)
    non_apply_total = int(calibration_summary.get("non_apply_total") or 0)
    artifact_linked_total = int(calibration_summary.get("artifact_linked_total") or 0)
    no_artifact_total = int(calibration_summary.get("no_artifact_total") or 0)
    apply_like_rate = float(calibration_summary.get("apply_like_progression_rate") or 0.0)
    non_apply_rate = float(calibration_summary.get("non_apply_progression_rate") or 0.0)
    artifact_rate = float(calibration_summary.get("artifact_linked_progression_rate") or 0.0)
    no_artifact_rate = float(calibration_summary.get("no_artifact_progression_rate") or 0.0)

    if apply_like_total + non_apply_total < 3:
        decision_signal = "insufficient_signal"
        decision_note = "Too few tracked outcomes to compare recommendation classes yet."
    elif apply_like_rate >= non_apply_rate + 20.0:
        decision_signal = "reinforce_apply_bias"
        decision_note = "Apply-like decisions are progressing materially better than the rest of the tracked set."
    elif non_apply_rate >= apply_like_rate + 20.0:
        decision_signal = "review_apply_thresholds"
        decision_note = "Non-apply outcomes are progressing better than apply-like ones in the tracked set."
    else:
        decision_signal = "mixed_signal"
        decision_note = "Recommendation classes are too close to justify a ranking change yet."

    if artifact_linked_total < 2 and no_artifact_total < 2:
        artifact_signal = "insufficient_signal"
        artifact_note = "Too few tracked artifact-linked cases to compare artifact contribution yet."
    elif artifact_rate >= no_artifact_rate + 20.0:
        artifact_signal = "artifacts_associated_with_progress"
        artifact_note = "Tracked cases with linked artifacts are progressing better than cases without artifacts."
    elif no_artifact_rate >= artifact_rate + 20.0:
        artifact_signal = "artifact_effect_unclear"
        artifact_note = "Linked artifacts are not yet outperforming cases without artifacts."
    else:
        artifact_signal = "mixed_signal"
        artifact_note = "Artifact-linked and non-artifact cases are too close to call."

    strong_samples = sum(
        1
        for value in (apply_like_total, non_apply_total, artifact_linked_total, no_artifact_total)
        if value >= 3
    )
    confidence = "high" if strong_samples >= 3 else "medium" if strong_samples >= 1 else "low"

    if decision_signal == "reinforce_apply_bias" and artifact_signal == "artifacts_associated_with_progress":
        recommended_next_action = "use_outcomes_for_shadow_ranking_review"
    elif decision_signal == "review_apply_thresholds":
        recommended_next_action = "prepare_shadow_threshold_recheck"
    else:
        recommended_next_action = "collect_more_outcomes"

    return {
        "schema_version": OUTCOME_FEEDBACK_RECOMMENDATION_VERSION,
        "decision_signal": decision_signal,
        "decision_note": decision_note,
        "artifact_signal": artifact_signal,
        "artifact_note": artifact_note,
        "confidence": confidence,
        "recommended_next_action": recommended_next_action,
    }


def build_outcome_feedback_shadow_followup(
    recommendation: Dict[str, Any],
) -> Dict[str, Any]:
    decision_signal = str(recommendation.get("decision_signal") or "")
    artifact_signal = str(recommendation.get("artifact_signal") or "")
    confidence = str(recommendation.get("confidence") or "low")

    if decision_signal == "review_apply_thresholds":
        suggested_experiment = "shadow_threshold_recheck"
        ready_for_shadow = True
        rationale = "Outcome data suggests reviewing threshold behavior in shadow mode before any live change."
    elif artifact_signal == "artifacts_associated_with_progress":
        suggested_experiment = "shadow_artifact_capture_review"
        ready_for_shadow = True
        rationale = "Outcome data suggests artifact-linked cases may be progressing better and should be reviewed in shadow mode."
    else:
        suggested_experiment = "collect_more_outcomes"
        ready_for_shadow = False
        rationale = "Outcome data is not strong enough yet to justify a new shadow change proposal."

    return {
        "schema_version": OUTCOME_FEEDBACK_SHADOW_FOLLOWUP_VERSION,
        "suggested_experiment": suggested_experiment,
        "ready_for_shadow": ready_for_shadow,
        "confidence": confidence,
        "rationale": rationale,
    }


def build_outcome_ranking_guidance(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    reviewed_items = [
        item
        for item in items
        if isinstance(item, dict) and int(item.get("reviewed") or 0) > 0
    ]

    def _fit(item: Dict[str, Any]) -> str:
        outcome_shadow_fit = item.get("outcome_shadow_fit")
        if not isinstance(outcome_shadow_fit, dict):
            outcome_shadow_fit = {}
        return str(outcome_shadow_fit.get("fit") or "")

    def _subset_summary(subset: List[Dict[str, Any]]) -> Dict[str, Any]:
        worth_promoting = sum(
            1
            for item in subset
            if str((item.get("variant_review") or {}).get("verdict") or "") == "worth_promoting"
        )
        avg_useful_signal_rate = (
            round(sum(float(item.get("useful_signal_rate") or 0.0) for item in subset) / len(subset), 1)
            if subset
            else 0.0
        )
        return {
            "count": len(subset),
            "avg_useful_signal_rate": avg_useful_signal_rate,
            "worth_promoting": worth_promoting,
            "worth_promoting_rate": _percent(worth_promoting, len(subset)),
        }

    supported_items = [item for item in reviewed_items if _fit(item) in {"aligned", "watch"}]
    non_supported_items = [item for item in reviewed_items if _fit(item) in {"indirect", "unknown"}]
    waiting_items = [item for item in reviewed_items if _fit(item) == "waiting"]

    supported_summary = _subset_summary(supported_items)
    non_supported_summary = _subset_summary(non_supported_items)
    delta_useful_rate = round(
        supported_summary["avg_useful_signal_rate"] - non_supported_summary["avg_useful_signal_rate"],
        1,
    )
    delta_worth_promoting_rate = round(
        supported_summary["worth_promoting_rate"] - non_supported_summary["worth_promoting_rate"],
        1,
    )

    if not reviewed_items:
        status = "no_signal"
        confidence = "low"
        summary = "No reviewed shadow variants are available for outcome-guided ranking yet."
        recommended_action = "Keep outcome guidance visible, but do not change shadow ordering."
    elif supported_summary["count"] == 0 and waiting_items:
        status = "waiting_for_outcomes"
        confidence = "low"
        summary = "The current reviewed variants are still waiting for enough outcome evidence to support ranking guidance."
        recommended_action = "Collect more tracked outcomes before treating the loop as a ranking signal."
    elif supported_summary["count"] == 0:
        status = "no_supported_variant"
        confidence = "low"
        summary = "The current outcome loop is not pointing at any reviewed variant strongly enough to guide ranking."
        recommended_action = "Keep outcome guidance descriptive until one reviewed candidate aligns with the loop."
    elif non_supported_summary["count"] == 0:
        status = "one_sided_support"
        confidence = "low"
        summary = "Only outcome-supported reviewed variants are available, so ranking guidance is still one-sided."
        recommended_action = "Compare against at least one non-supported reviewed variant before promoting the signal."
    elif delta_useful_rate >= 10.0 and delta_worth_promoting_rate >= 0.0:
        status = "supports_ranking_review"
        confidence = "medium" if min(supported_summary["count"], non_supported_summary["count"]) >= 2 else "low"
        summary = "Outcome-supported variants are producing better reviewed shadow quality than the non-supported set."
        recommended_action = "Use the outcome loop as a bounded secondary ordering signal in experiment review."
    elif delta_useful_rate >= 0.0 or delta_worth_promoting_rate > 0.0:
        status = "mixed_support"
        confidence = "medium" if len(reviewed_items) >= 4 else "low"
        summary = "Outcome-supported variants are directionally better, but the edge is still thin."
        recommended_action = "Keep the loop visible and continue reviewing before promoting stronger calibration changes."
    else:
        status = "not_supported_yet"
        confidence = "medium" if len(reviewed_items) >= 4 else "low"
        summary = "Outcome-supported variants are not yet outperforming the rest of the reviewed shadow set."
        recommended_action = "Keep outcome guidance descriptive until reviewed quality improves."

    return {
        "schema_version": OUTCOME_FEEDBACK_RANKING_GUIDANCE_VERSION,
        "reviewed_variants": len(reviewed_items),
        "supported_variants": supported_summary["count"],
        "supported_avg_useful_rate": supported_summary["avg_useful_signal_rate"],
        "supported_worth_promoting_rate": supported_summary["worth_promoting_rate"],
        "non_supported_variants": non_supported_summary["count"],
        "non_supported_avg_useful_rate": non_supported_summary["avg_useful_signal_rate"],
        "non_supported_worth_promoting_rate": non_supported_summary["worth_promoting_rate"],
        "waiting_variants": len(waiting_items),
        "quality_delta_useful_rate": delta_useful_rate,
        "quality_delta_worth_promoting_rate": delta_worth_promoting_rate,
        "status": status,
        "confidence": confidence,
        "summary": summary,
        "recommended_action": recommended_action,
    }


def build_outcomes_dashboard_payload(state: Dict[str, Any], *, max_items: int = 8) -> Dict[str, Any]:
    outcomes = state.get("outcomes", {})
    if not isinstance(outcomes, dict):
        outcomes = {}
    entries = [value for value in outcomes.values() if isinstance(value, dict)]
    recent_feedback = sorted(
        entries,
        key=lambda item: str(item.get("updated_at") or ""),
        reverse=True,
    )[:max_items]
    calibration_summary = build_outcome_feedback_calibration_summary(state)
    recommendation = build_outcome_feedback_recommendation(calibration_summary)
    return {
        "schema_version": OUTCOMES_DASHBOARD_VERSION,
        "summary": build_outcome_feedback_summary(state),
        "audit_summary": build_outcome_feedback_audit_summary(state),
        "calibration_summary": calibration_summary,
        "recommendation": recommendation,
        "shadow_followup": build_outcome_feedback_shadow_followup(recommendation),
        "recent_feedback": recent_feedback,
    }
