"""Export ledger.sqlite to a self-contained dashboard HTML file.

Builds the canonical dashboard payload, including:
- actionable-job enrichment from per-job 00_input.json files when the ledger
  still lacks URLs/deadlines/location fields
- a tracked-source profile payload from profile_pack.md and resume.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jobpipe.cli.mark_status import load_state as load_application_state
from jobpipe.cli.mark_status import normalize_shared_status
from jobpipe.core.automation_state import build_automation_payload
from jobpipe.core.boundary_objects import (
    build_application_case_projection,
    build_artifact_plan,
    build_case_job_summary,
    build_decision_brief,
)
from jobpipe.core.config import load_raw_config
from jobpipe.core.experiment_review_state import (
    build_advantage_signal_calibration_summary,
    build_advantage_shortlist_quality_summary,
    build_experiment_calibration_summary,
    build_experiment_promotion_review_summary,
    build_experiment_review_summary,
    build_experiment_variant_review_summary,
    get_experiment_promotion_review,
    get_experiment_review,
    get_experiment_variant_review,
    load_experiment_review_state,
)
from jobpipe.core.experiments import load_latest_shadow_review_queue
from jobpipe.core.experiments import load_experiment_detail
from jobpipe.core.experiments import load_recent_shadow_experiment_summaries
from jobpipe.core.outcome_feedback import (
    build_outcome_feedback_state,
    build_outcome_ranking_guidance,
    build_outcomes_dashboard_payload,
    persist_outcome_feedback_state,
)
from jobpipe.core.paths import JobPipePaths, bootstrap_private_data, get_jobpipe_paths
from jobpipe.core.profile_layer import build_profile_dashboard_payload
from jobpipe.core.projection_store import (
    apply_input_enrichment_projection,
    apply_detail_projection,
    build_detail_projection,
    build_input_enrichment_projection,
    build_job_projection_bundle,
    get_job_projection_bundle,
    load_projection_store,
    persist_projection_store,
    set_job_projection_bundle,
)
from jobpipe.core.settings_state import build_settings_payload

_PAYLOAD_SCHEMA_VERSION = "jobpipe.dashboard.v2"
_PAYLOAD_SOFT_BUDGET_BYTES = 16 * 1024 * 1024
_PAYLOAD_EVENT_HARD_CAP = 10_000
_PAYLOAD_EVENT_MIN_ROWS = 2_000
_PAYLOAD_EVENT_PRUNE_STEP = 500


def _load_config_raw(config_path: Path, overlays: Optional[List[str]] = None) -> Dict[str, Any]:
    try:
        return load_raw_config(config_path, overlays=overlays or [])
    except Exception:
        return {}


def _load_thresholds(config_path: Path, overlays: Optional[List[str]] = None) -> Dict[str, Any]:
    thresholds = _load_config_raw(config_path, overlays=overlays).get("thresholds", {})
    return thresholds if isinstance(thresholds, dict) else {}


def _build_config_snapshot(config_path: Path, overlays: Optional[List[str]] = None) -> Dict[str, Any]:
    raw = _load_config_raw(config_path, overlays=overlays)
    if not raw:
        return {}
    models = raw.get("models", {})
    stages = raw.get("stages", [])
    thresholds = raw.get("thresholds", {})
    safety_rules = raw.get("safety_rules", {})
    return {
        "pipeline_name": raw.get("pipeline_name", "jobpipe"),
        "models": models if isinstance(models, dict) else {},
        "stages": stages if isinstance(stages, list) else [],
        "thresholds": thresholds if isinstance(thresholds, dict) else {},
        "safety_rules": safety_rules if isinstance(safety_rules, dict) else {},
        "config_name": config_path.name,
        "overlay_count": len(overlays or []),
    }


def _reclassify(fit_score, pivot_score, thr: Dict[str, Any]) -> str:
    """Re-apply current YAML thresholds to produce a fresh final_decision.
    Mirrors the logic in moderate.py exactly."""
    try:
        fit = int(fit_score or 0)
        pivot = int(pivot_score or 0)
    except Exception:
        return "SKIP"

    apply_strong = int(thr.get("apply_strong_fit", 78))
    apply_fit    = int(thr.get("apply_fit", 67))
    pivot_boost  = int(thr.get("pivot_boost_apply", 78))
    review_min   = int(thr.get("review_min_fit", 30))
    review_high  = int(thr.get("review_high_min_fit", 58))

    if fit < review_min:
        return "SKIP"
    if fit < review_high:
        return "REVIEW_LOW"
    if fit >= apply_strong:
        return "APPLY_STRONGLY"
    if fit >= apply_fit:
        return "APPLY"
    return "REVIEW_HIGH" if pivot >= pivot_boost else "REVIEW_LOW"

_DETAIL_COLS = (
    "triage_explanation", "reverse_decision", "reverse_confidence",
    "reverse_rationale", "recommendation_reason", "cv_focus",
    "feedback_flags", "description_snip",
)

_ACTIONABLE = {"APPLY_STRONGLY", "APPLY", "REVIEW_HIGH", "REVIEW_LOW"}
_DATA_PLACEHOLDER = "/*__DASHBOARD_DATA__*/"
_DEFAULT_PATHS = get_jobpipe_paths()


def _find_latest_suffix_artifact(job_dir: Path, suffix: str) -> Optional[Path]:
    matches = sorted(job_dir.glob(f"*{suffix}"))
    return matches[-1] if matches else None


def _default_paths():
    return get_jobpipe_paths()


def _resolve_paths_for_payload(
    *,
    state_path: Optional[Path],
    profile_path: Optional[Path],
    resume_path: Optional[Path],
    profile_draft_path: Optional[Path],
    settings_path: Optional[Path],
) -> JobPipePaths:
    repo_root = _DEFAULT_PATHS.repo_root
    candidates = [settings_path, state_path, profile_draft_path, resume_path]
    for candidate in candidates:
        if not candidate:
            continue
        return JobPipePaths(repo_root=repo_root, data_root=candidate.parent.parent)
    if profile_path:
        return JobPipePaths(repo_root=repo_root, data_root=profile_path.parent)
    return _default_paths()


def _rows_as_dicts(conn: sqlite3.Connection, sql: str) -> List[Dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql)]


def _json_size_bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))


def _prune_events(
    events: List[Dict[str, Any]],
    payload_base: Dict[str, Any],
    budget_bytes: int,
    max_event_rows: int,
    min_event_rows: int,
) -> tuple[List[Dict[str, Any]], int]:
    kept = list(events)
    pruned = 0

    if max_event_rows > 0 and len(kept) > max_event_rows:
        pruned += len(kept) - max_event_rows
        kept = kept[-max_event_rows:]

    base_size = _json_size_bytes(payload_base)
    while (
        kept
        and len(kept) > min_event_rows
        and (base_size + _json_size_bytes(kept)) > budget_bytes
    ):
        drop = min(_PAYLOAD_EVENT_PRUNE_STEP, len(kept) - min_event_rows)
        if drop <= 0:
            break
        kept = kept[drop:]
        pruned += drop

    return kept, pruned


def _attach_payload_meta(
    payload: Dict[str, Any],
    *,
    budget_bytes: int,
    event_rows_before: int,
    event_rows_after: int,
    pruned_event_count: int,
    max_event_rows: int,
    min_event_rows: int,
) -> None:
    meta = {
        "budget_bytes": int(budget_bytes),
        "budget_mb": round(int(budget_bytes) / 1024 / 1024, 3),
        "event_rows_before": int(event_rows_before),
        "event_rows_after": int(event_rows_after),
        "pruned_event_count": int(pruned_event_count),
        "max_event_rows": int(max_event_rows),
        "min_event_rows": int(min_event_rows),
        "size_bytes": 0,
        "size_mb": 0.0,
        "budget_state": "ok",
    }
    payload["payload_meta"] = meta
    for _ in range(2):
        size_bytes = _json_size_bytes(payload)
        meta["size_bytes"] = size_bytes
        meta["size_mb"] = round(size_bytes / 1024 / 1024, 3)
        meta["budget_state"] = "ok" if size_bytes <= budget_bytes else "over"


def _parse_raw_json(val: Any) -> Dict[str, Any]:
    if not val:
        return {}
    try:
        return json.loads(val)
    except Exception:
        return {}


def _extract_detail(row: Dict[str, Any]) -> Dict[str, Any]:
    triage_features = _parse_raw_json(row.get("raw_triage_features_json"))
    triage_decision_v3 = _parse_raw_json(row.get("raw_triage_decision_v3_json"))
    triage_ambiguity_v3 = _parse_raw_json(row.get("raw_triage_ambiguity_v3_json"))
    advantage = _parse_raw_json(row.get("raw_advantage_assessment_v3_json"))
    narrative = _parse_raw_json(row.get("raw_narrative_strategy_v3_json"))
    match = _parse_raw_json(row.get("raw_match_json"))
    pivot = _parse_raw_json(row.get("raw_pivot_json"))
    mod = _parse_raw_json(row.get("raw_moderator_json"))
    detail = {
        "triage_v3_label": triage_decision_v3.get("label", ""),
        "triage_v3_weighted_score": triage_decision_v3.get("weighted_score"),
        "triage_v3_needs_ambiguity": triage_decision_v3.get("needs_ambiguity_pass", False),
        "triage_v3_blockers": triage_decision_v3.get("blockers", []),
        "triage_v3_boosts": triage_decision_v3.get("boosts", []),
        "triage_ambiguity_label": triage_ambiguity_v3.get("resolved_label", ""),
        "triage_ambiguity_reason": triage_ambiguity_v3.get("resolution_reason", ""),
        "advantage_type": advantage.get("advantage_type", ""),
        "advantage_signals": advantage.get("advantage_signals", []),
        "objection_signals": advantage.get("objection_signals", []),
        "neutralizing_evidence": advantage.get("neutralizing_evidence", []),
        "differentiation_signals": advantage.get("differentiation_signals", []),
        "advantageous_match_score": advantage.get("advantageous_match_score"),
        "applicant_pool_hypothesis": advantage.get("applicant_pool_hypothesis", ""),
        "recruiter_hook": advantage.get("recruiter_hook", ""),
        "review_priority": advantage.get("review_priority"),
        "narrative_positioning_angle": narrative.get("positioning_angle", ""),
        "narrative_brand_frame": narrative.get("brand_frame", ""),
        "narrative_why_me_now": narrative.get("why_me_now", ""),
        "narrative_value_props": narrative.get("top_value_props", []),
        "narrative_objections": narrative.get("objections_to_handle", []),
        "narrative_cv_focus_order": narrative.get("cv_focus_order", []),
        "cover_letter_strategy": narrative.get("cover_letter_strategy", ""),
        "triage_features": triage_features,
        "overlaps": match.get("overlaps", []),
        "gaps": match.get("gaps", []),
        "hard_blockers": match.get("hard_blockers", []),
        "match_notes": match.get("notes", ""),
        "pivot_type": pivot.get("pivot_type", ""),
        "pivot_risk": pivot.get("potential_risk", ""),
        "pivot_why": pivot.get("why_it_matters", []),
        "cv_focus_mod": mod.get("cv_focus", []),
        "feedback_flags_mod": mod.get("feedback_flags", []),
    }
    detail["decision_brief"] = build_decision_brief(
        final_decision=row.get("final_decision") or "",
        triage_v3_label=detail["triage_v3_label"],
        fit_score=row.get("fit_score"),
        pivot_score=row.get("pivot_score"),
        advantage_type=detail["advantage_type"],
        advantageous_match_score=detail["advantageous_match_score"],
        review_priority=detail["review_priority"],
        positioning_angle=detail["narrative_positioning_angle"],
        brand_frame=detail["narrative_brand_frame"],
        applicant_pool_hypothesis=detail["applicant_pool_hypothesis"],
        recruiter_hook=detail["recruiter_hook"],
        rationale=row.get("recommendation_reason") or row.get("triage_explanation") or "",
        overlaps=detail["overlaps"],
        gaps=detail["gaps"],
        differentiation_signals=detail["differentiation_signals"],
        top_value_props=detail["narrative_value_props"],
        cv_focus=detail["cv_focus_mod"],
        cover_letter_angle=detail["cover_letter_strategy"],
    )
    detail["application_case_projection"] = build_application_case_projection(
        external_source="jobpipe",
        external_id=str(row.get("job_id") or ""),
        run_id=str(row.get("run_id") or ""),
        status=str(row.get("app_status") or ""),
        updated_at=str(row.get("updated_at") or ""),
        job_summary=build_case_job_summary(
            title=str(row.get("title") or ""),
            company=str(row.get("employer") or ""),
            location=", ".join(
                part for part in [str(row.get("work_city") or "").strip(), str(row.get("work_county") or "").strip()] if part
            ),
            job_source=str(row.get("job_source") or "jobpipe"),
            source_url=str(row.get("source_url") or ""),
            application_url=str(row.get("application_url") or ""),
            application_due=str(row.get("applicationDue") or ""),
            description_snippet=str(row.get("description_snip") or ""),
        ),
        decision_brief=detail["decision_brief"],
        artifact_plan=build_artifact_plan(),
    )
    return detail


def _safe_load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _pick(*vals: Any) -> Any:
    for v in vals:
        if v is not None and str(v).strip():
            return v
    return ""


def _job_dir(row: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    run_id = str(row.get("run_id") or "").strip()
    job_id = str(row.get("job_id") or "").strip()
    if not run_id or not job_id:
        return None
    return out_dir / run_id / job_id


def _normalize_due(value: Any) -> str:
    due = str(value or "").strip()
    if not due:
        return ""
    if "T" in due:
        return due[:10]
    return due


def _derive_no_score_reason_label(row: Dict[str, Any]) -> str:
    reason = str(row.get("skip_reason") or "").strip()
    labels = {
        "geo": "filtered by location rules before scoring",
        "hard_no": "filtered by title rules before scoring",
        "semantic": "filtered by semantic pre-filter before scoring",
        "triage_llm": "filtered by AI triage before deeper scoring",
        "fit_floor": "fit score landed below the review floor",
        "moderate": "moderator thresholds kept this role below the action queue",
        "passed": "",
    }
    if reason in labels:
        return labels[reason]
    if row.get("fit_score") is None and row.get("final_decision") == "SKIP":
        return "filtered before deeper scoring"
    return ""


def _parse_json_array(value: Any) -> List[Dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _collect_generated_documents(row: Dict[str, Any], out_dir: Path) -> List[Dict[str, Any]]:
    persisted = _parse_json_array(row.get("generated_documents_json"))
    if persisted:
        return persisted

    job_dir = _job_dir(row, out_dir)
    if not job_dir or not job_dir.exists():
        return []

    docs: List[Dict[str, Any]] = []
    candidates = []
    pack_path = _find_latest_suffix_artifact(job_dir, "_application_pack.json")
    if pack_path:
        candidates.append((pack_path, "application_pack_json", "saved"))
    docx_path = _find_latest_suffix_artifact(job_dir, "_cv_highlights.docx")
    if docx_path:
        candidates.append((docx_path, "cv_highlights_docx", "draft"))
    candidates.extend(
        [
            (job_dir / "application_pack_draft.json", "application_pack_json", "draft"),
            (job_dir / "cover_letter_draft.txt", "cover_letter_text", "draft"),
        ]
    )
    for path, kind, status in candidates:
        if not path.exists():
            continue
        docs.append(
            {
                "kind": kind,
                "status": status,
                "storage_path": str(path.resolve()),
            }
        )
    return docs


def _apply_threshold_view(row: Dict[str, Any], thr: Dict[str, Any]) -> None:
    if row.get("fit_score") is None or not thr:
        return
    final_decision = _reclassify(row.get("fit_score"), row.get("pivot_score"), thr)
    row["final_decision"] = final_decision
    review_min = int(thr.get("review_min_fit", 30))
    if final_decision == "SKIP":
        row["skip_reason"] = "fit_floor" if int(row.get("fit_score") or 0) < review_min else "moderate"
    else:
        row["skip_reason"] = "passed"


def _enrich_from_input(row: Dict[str, Any], out_dir: Path) -> None:
    """Fill in missing URL/deadline/location fields from per-job 00_input.json."""
    needs_employer = not (row.get("employer") or "").strip()
    needs_normalized_title = not (row.get("normalized_title") or "").strip()
    needs_application_url = not (row.get("application_url") or "").strip()
    needs_source_url = not (row.get("source_url") or "").strip()
    needs_due = not (row.get("applicationDue") or "").strip()
    needs_city = not (row.get("work_city") or "").strip()
    needs_county = not (row.get("work_county") or "").strip()
    needs_postal = not (row.get("work_postalCode") or "").strip()
    needs_job_source = not (row.get("job_source") or "").strip()
    if (
        not needs_employer
        and not needs_normalized_title
        and not needs_application_url
        and not needs_source_url
        and not needs_due
        and not needs_city
        and not needs_county
        and not needs_postal
        and not needs_job_source
    ):
        return

    job_dir = _job_dir(row, out_dir)
    if not job_dir:
        return

    input_path = job_dir / "00_input.json"
    inp = _safe_load_json(input_path)
    if not inp:
        return

    # The input file can have the job data at root level or nested under "job"
    job = inp.get("job", inp) if isinstance(inp.get("job"), dict) else inp

    if needs_employer:
        row["employer"] = _pick(
            row.get("employer"),
            job.get("employer_name"),
            job.get("employer"),
            job.get("company"),
        )
    if needs_normalized_title:
        row["normalized_title"] = _pick(
            row.get("normalized_title"),
            job.get("normalized_title"),
            row.get("title"),
            job.get("title"),
        )
    if needs_application_url:
        row["application_url"] = _pick(row.get("application_url"), job.get("applicationUrl"))
    if needs_source_url:
        row["source_url"] = _pick(row.get("source_url"), job.get("sourceurl"), job.get("link"))
    if needs_due:
        row["applicationDue"] = _pick(row.get("applicationDue"), job.get("applicationDue"))
    row["applicationDue"] = _normalize_due(row.get("applicationDue"))

    if needs_city:
        row["work_city"] = _pick(
            row.get("work_city"),
            job.get("work_city"),
            job.get("municipal"),
            job.get("municipalName"),
        )
    if needs_county:
        row["work_county"] = _pick(
            row.get("work_county"),
            job.get("work_county"),
            job.get("county"),
        )
    if needs_postal:
        row["work_postalCode"] = _pick(
            row.get("work_postalCode"),
            job.get("work_postalCode"),
            job.get("postalCode"),
        )
    if needs_job_source:
        row["job_source"] = _pick(
            row.get("job_source"),
            job.get("source"),
            job.get("job_source"),
        )


def _load_app_state(state_path: Path) -> Dict[str, Any]:
    """Load application_state.json sidecar. Returns empty dict if missing."""
    try:
        data = load_application_state(state_path)
        return data.get("applications", {})
    except Exception:
        return {}


def _build_profile_payload(
    paths: JobPipePaths,
    profile_path: Path,
    resume_path: Path,
    profile_draft_path: Path,
) -> Dict[str, Any]:
    return build_profile_dashboard_payload(
        profile_path,
        resume_path,
        profile_draft_path,
        projection_path=paths.profile_layer_state_path,
    )


def _extract_experiment_advantage_context(job: Dict[str, Any]) -> Dict[str, Any]:
    detail = job.get("detail")
    if not isinstance(detail, dict):
        detail = {}
    brief = detail.get("decision_brief")
    if not isinstance(brief, dict):
        brief = {}
    advantageous_match_score = brief.get("advantageous_match_score")
    try:
        advantageous_match_score_int = int(advantageous_match_score)
    except Exception:
        advantageous_match_score_int = 0
    review_priority = brief.get("review_priority")
    try:
        review_priority_int = int(review_priority)
    except Exception:
        review_priority_int = 0
    recruiter_hook = str(brief.get("recruiter_hook") or "").strip()
    applicant_pool_hypothesis = str(brief.get("applicant_pool_hypothesis") or "").strip()
    return {
        "advantageous_match_score": advantageous_match_score_int,
        "advantage_review_priority": review_priority_int,
        "recruiter_hook": recruiter_hook,
        "applicant_pool_hypothesis": applicant_pool_hypothesis,
    }


def _enrich_experiment_review_item(
    item: Dict[str, Any],
    *,
    experiment_id: str,
    review_state: Dict[str, Any],
    job_index: Dict[tuple[str, str], Dict[str, Any]],
) -> Dict[str, Any]:
    enriched = dict(item)
    enriched["experiment_id"] = experiment_id
    job = job_index.get((str(item.get("run_id") or ""), str(item.get("job_id") or "")))
    if job:
        enriched["title"] = str(job.get("title") or "")
        enriched["employer"] = str(job.get("employer") or "")
        enriched["final_decision"] = str(job.get("final_decision") or "")
        enriched["app_status"] = str(job.get("app_status") or "")
        enriched["job_source"] = str(job.get("job_source") or "")
        enriched.update(_extract_experiment_advantage_context(job))
    enriched["adjudication"] = get_experiment_review(
        review_state,
        experiment_id=experiment_id,
        job_id=str(item.get("job_id") or ""),
    )
    return enriched


def _sort_experiment_review_queue(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sorted_items = list(items)
    sorted_items.sort(
        key=lambda item: (
            -int(item.get("review_priority") or 0),
            -int(item.get("advantageous_match_score") or 0),
            -int(item.get("advantage_review_priority") or 0),
            -float(item.get("candidate_weighted_score") or 0.0),
            str(item.get("job_id") or ""),
        )
    )
    return sorted_items


def _build_advantage_signal_recommendation(summary: Dict[str, Any]) -> Dict[str, Any]:
    reviewed = int(summary.get("reviewed") or 0)
    high_reviewed = int(summary.get("high_advantage_reviewed") or 0)
    high_rate = float(summary.get("high_advantage_useful_rate") or 0.0)
    lower_rate = float(summary.get("lower_advantage_useful_rate") or 0.0)
    delta = round(high_rate - lower_rate, 1)

    if reviewed <= 0:
        status = "no_signal"
        confidence = "low"
        explanation = "No reviewed advantageous-match sample is available yet."
        recommended_action = "Keep advantageous-match in observation mode."
    elif high_reviewed < 2:
        status = "insufficient_signal"
        confidence = "low"
        explanation = "Too few high-advantage reviewed items to trust the pattern yet."
        recommended_action = "Collect more reviewed high-advantage cases before promoting the signal."
    elif reviewed < 4:
        status = "watch"
        confidence = "low"
        explanation = "The early advantageous-match pattern looks usable, but the reviewed sample is still thin."
        recommended_action = "Keep using the signal in shadow ordering and continue reviewing items."
    elif high_rate >= 60.0 and delta >= 15.0:
        status = "promising"
        confidence = "high" if reviewed >= 8 and high_reviewed >= 4 else "medium"
        explanation = "High advantageous-match cases are outperforming lower-score cases in reviewed shadow samples."
        recommended_action = "Use this signal to guide more shadow ordering and promotion review."
    elif high_rate >= lower_rate:
        status = "mixed"
        confidence = "medium" if reviewed >= 6 else "low"
        explanation = "The advantageous-match signal is not hurting, but it is not yet clearly separating the best cases."
        recommended_action = "Keep the signal visible, but do not promote it into live ranking yet."
    else:
        status = "weak"
        confidence = "medium" if reviewed >= 6 else "low"
        explanation = "High advantageous-match cases are not outperforming lower-score cases in reviewed shadow samples."
        recommended_action = "Treat this signal as descriptive only until calibration improves."

    return {
        "schema_version": "jobpipe.advantage-signal-recommendation.v1",
        "status": status,
        "confidence": confidence,
        "reviewed": reviewed,
        "high_advantage_reviewed": high_reviewed,
        "delta_useful_rate": delta,
        "summary": explanation,
        "recommended_action": recommended_action,
    }


def _classify_variant_advantage_fit(
    item: Dict[str, Any],
    recommendation: Dict[str, Any],
) -> Dict[str, str]:
    avg_score = float(item.get("avg_advantageous_match_score") or 0.0)
    high_count = int(item.get("high_advantage_count") or 0)
    reviewed = int(item.get("reviewed") or 0)
    useful_rate = float(item.get("useful_signal_rate") or 0.0)
    signal_status = str(recommendation.get("status") or "")

    if avg_score < 55.0:
        fit = "weak"
        note = "Little advantageous differentiation in the reviewed shadow sample."
    elif reviewed > 0 and useful_rate < 50.0:
        fit = "contested"
        note = "Strong advantageous framing exists, but reviewed human signal is not supporting it yet."
    elif avg_score >= 70.0 and high_count > 0 and signal_status in {"promising", "watch", "mixed"}:
        fit = "strong"
        note = "This candidate lines up well with the current advantageous-match pattern."
    elif avg_score >= 55.0 and signal_status in {"promising", "watch", "mixed"}:
        fit = "adjacent"
        note = "There is some advantageous edge here, but it is not dominant yet."
    else:
        fit = "tentative"
        note = "The advantageous profile looks interesting, but calibration is still too thin."

    return {
        "fit": fit,
        "note": note,
    }


def _build_advantage_promotion_readiness(
    item: Dict[str, Any],
    recommendation: Dict[str, Any],
) -> Dict[str, str]:
    signal_status = str(recommendation.get("status") or "")
    fit = str((item.get("advantage_signal_fit") or {}).get("fit") or "")
    useful_rate = float(item.get("useful_signal_rate") or 0.0)
    reviewed = int(item.get("reviewed") or 0)

    if fit == "contested":
        status = "hold_for_human_review"
        summary = "Human-reviewed signal is still pushing back on this advantageous framing."
        action = "Keep the candidate in shadow review and inspect why the advantageous case is not landing."
    elif signal_status == "promising" and fit == "strong" and reviewed > 0 and useful_rate >= 50.0:
        status = "ready_for_patch_review"
        summary = "This candidate lines up with the strongest current advantageous-match pattern."
        action = "Review the proposed patch/config delta manually; still do not auto-apply it."
    elif signal_status in {"watch", "mixed"} and fit in {"strong", "adjacent"}:
        status = "needs_more_shadow_review"
        summary = "The candidate looks directionally good, but the advantageous signal is not mature enough yet."
        action = "Keep collecting reviewed shadow cases before promoting beyond manual patch review."
    elif signal_status in {"insufficient_signal", "no_signal"}:
        status = "waiting_for_signal"
        summary = "There is not enough advantageous calibration data to trust promotion readiness yet."
        action = "Accumulate more reviewed advantageous-match cases first."
    else:
        status = "hold_weak_advantage_signal"
        summary = "The current advantageous signal is too weak to support promotion confidence."
        action = "Treat this as an interesting shadow candidate, not a promotion-ready one."

    return {
        "schema_version": "jobpipe.advantage-promotion-readiness.v1",
        "status": status,
        "summary": summary,
        "recommended_action": action,
    }


def _classify_variant_outcome_handoff_fit(
    item: Dict[str, Any],
    handoff: Dict[str, Any],
) -> Dict[str, str]:
    suggested_experiment = str(handoff.get("suggested_experiment") or "")
    ready_for_shadow = bool(handoff.get("ready_for_shadow"))
    kind = str(item.get("kind") or "")

    if suggested_experiment == "collect_more_outcomes" or not suggested_experiment:
        fit = "waiting"
        note = "The outcome loop is still collecting signal, so no current shadow candidate is outcome-backed yet."
    elif suggested_experiment == "shadow_threshold_recheck":
        if kind == "shadow_threshold_eval":
            fit = "aligned" if ready_for_shadow else "watch"
            note = (
                "This threshold candidate matches the current outcome-driven shadow follow-up."
                if ready_for_shadow
                else "This threshold candidate matches the likely next outcome-driven shadow direction, but the loop is not ready yet."
            )
        else:
            fit = "indirect"
            note = "The outcome loop currently points to threshold recheck first, so this candidate is secondary."
    elif suggested_experiment == "shadow_artifact_capture_review":
        fit = "indirect"
        note = "The outcome loop is pointing toward artifact-capture review, not this shadow candidate family."
    else:
        fit = "unknown"
        note = "The outcome loop suggests a different follow-up path than this shadow candidate."

    return {
        "schema_version": "jobpipe.outcome-shadow-fit.v1",
        "fit": fit,
        "note": note,
    }


def _build_promotion_outcome_status(item: Dict[str, Any]) -> Dict[str, str]:
    outcome_fit = item.get("outcome_shadow_fit") if isinstance(item, dict) else {}
    if not isinstance(outcome_fit, dict):
        outcome_fit = {}
    fit = str(outcome_fit.get("fit") or "")

    if fit == "aligned":
        status = "outcome_backed"
        summary = "This promotion candidate is supported by the current outcome-driven shadow direction."
    elif fit == "waiting":
        status = "waiting_for_outcomes"
        summary = "This promotion candidate may still be promising, but the outcome loop has not produced enough signal yet."
    else:
        status = "not_outcome_backed_yet"
        summary = "This promotion candidate is still shadow-valid, but it is not directly backed by the current outcome loop."

    return {
        "schema_version": "jobpipe.promotion-outcome-status.v1",
        "status": status,
        "summary": summary,
    }


def _build_experiments_payload(
    paths: JobPipePaths,
    jobs: List[Dict[str, Any]],
    outcome_shadow_handoff: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = load_latest_shadow_review_queue(paths.experiment_runs_path, max_items=10)
    review_state = load_experiment_review_state(paths.experiment_review_state_path)
    outcome_shadow_handoff = (
        dict(outcome_shadow_handoff)
        if isinstance(outcome_shadow_handoff, dict)
        else {}
    )
    experiment_id = str((payload.get("latest_shadow_eval") or {}).get("experiment_id") or "")
    job_index = {
        (str(job.get("run_id") or ""), str(job.get("job_id") or "")): job
        for job in jobs
        if str(job.get("run_id") or "") and str(job.get("job_id") or "")
    }
    enriched_queue: List[Dict[str, Any]] = []
    for item in payload.get("review_queue", []):
        if not isinstance(item, dict):
            continue
        enriched_queue.append(
            _enrich_experiment_review_item(
                item,
                experiment_id=experiment_id,
                review_state=review_state,
                job_index=job_index,
            )
        )
    payload["review_queue"] = _sort_experiment_review_queue(enriched_queue)
    payload["adjudication_summary"] = build_experiment_review_summary(enriched_queue)
    payload["calibration_summary"] = build_experiment_calibration_summary(enriched_queue)
    recent_runs = load_recent_shadow_experiment_summaries(paths.experiment_runs_path, max_runs=5)
    all_recent_review_items: List[Dict[str, Any]] = []
    variant_comparison: List[Dict[str, Any]] = []
    variant_verdict_rank = {
        "worth_promoting": 2,
        "needs_more_review": 1,
        "reject_variant": -1,
    }
    for run in recent_runs:
        experiment_run_id = str(run.get("experiment_id") or "")
        detail = load_experiment_detail(run.get("detail_path"))
        review_items = detail.get("review_sample", []) if isinstance(detail, dict) else []
        if not isinstance(review_items, list):
            review_items = []
        enriched_variant_queue: List[Dict[str, Any]] = []
        for item in review_items:
            if not isinstance(item, dict):
                continue
            enriched_variant_queue.append(
                _enrich_experiment_review_item(
                    item,
                    experiment_id=experiment_run_id,
                    review_state=review_state,
                    job_index=job_index,
                )
            )
        enriched_variant_queue = _sort_experiment_review_queue(enriched_variant_queue)
        all_recent_review_items.extend(enriched_variant_queue)
        calibration = build_experiment_calibration_summary(enriched_variant_queue)
        advantage_scores = [
            int(item.get("advantageous_match_score") or 0)
            for item in enriched_variant_queue
            if int(item.get("advantageous_match_score") or 0) > 0
        ]
        recruiter_hooks: List[str] = []
        for item in enriched_variant_queue:
            hook = str(item.get("recruiter_hook") or "").strip()
            if hook and hook not in recruiter_hooks:
                recruiter_hooks.append(hook)
            if len(recruiter_hooks) >= 2:
                break
        candidate = run.get("candidate", {})
        variant_review = get_experiment_variant_review(
            review_state,
            experiment_id=experiment_run_id,
        )
        variant_comparison.append(
            {
                "experiment_id": experiment_run_id,
                "kind": str(run.get("kind") or ""),
                "created_at": str(run.get("created_at") or ""),
                "baseline": dict(run.get("baseline") or {}),
                "candidate": dict(run.get("candidate") or {}),
                "candidate_name": str(candidate.get("name") or ""),
                "sample_size": int(run.get("sample_size") or 0),
                "changed_count": int(run.get("changed_count") or 0),
                "upgrade_count": int(run.get("upgrade_count") or 0),
                "review_sample_count": int(run.get("review_sample_count") or 0),
                "reviewed": int(calibration.get("reviewed") or 0),
                "positive": int(calibration.get("positive") or 0),
                "rejected": int(calibration.get("rejected") or 0),
                "useful_signal_rate": float(calibration.get("useful_signal_rate") or 0.0),
                "avg_advantageous_match_score": round(sum(advantage_scores) / len(advantage_scores), 1)
                if advantage_scores
                else 0.0,
                "high_advantage_count": sum(1 for score in advantage_scores if score >= 70),
                "top_recruiter_hooks": recruiter_hooks,
                "top_positive_reasons": calibration.get("top_positive_reasons", []),
                "top_negative_reasons": calibration.get("top_negative_reasons", []),
                "summary": str(run.get("summary") or ""),
                "variant_review": variant_review,
            }
        )
    advantage_calibration_summary = build_advantage_signal_calibration_summary(all_recent_review_items)
    advantage_signal_recommendation = _build_advantage_signal_recommendation(advantage_calibration_summary)

    for item in variant_comparison:
        item["advantage_signal_fit"] = _classify_variant_advantage_fit(
            item,
            advantage_signal_recommendation,
        )
        item["outcome_shadow_fit"] = _classify_variant_outcome_handoff_fit(
            item,
            outcome_shadow_handoff,
        )

    outcome_ranking_guidance = build_outcome_ranking_guidance(variant_comparison)
    outcome_fit_rank = {
        "aligned": 3,
        "watch": 2,
        "indirect": 1,
        "waiting": 0,
        "unknown": -1,
    }

    variant_comparison.sort(
        key=lambda item: (
            -variant_verdict_rank.get(str((item.get("variant_review") or {}).get("verdict") or ""), 0),
            -outcome_fit_rank.get(str((item.get("outcome_shadow_fit") or {}).get("fit") or ""), 0),
            -(1 if item.get("reviewed", 0) > 0 else 0),
            -float(item.get("useful_signal_rate", 0.0)),
            -float(item.get("avg_advantageous_match_score", 0.0)),
            -int(item.get("high_advantage_count", 0)),
            -int(item.get("positive", 0)),
            -int(item.get("upgrade_count", 0)),
            str(item.get("created_at") or ""),
        )
    )
    payload["variant_comparison"] = variant_comparison
    payload["variant_review_summary"] = build_experiment_variant_review_summary(variant_comparison)
    promotion_candidates: List[Dict[str, Any]] = []
    promotion_review_rank = {
        "accepted_for_promotion": 2,
        "deferred_promotion": 1,
        "rejected_promotion": -1,
    }
    promotion_outcome_rank = {
        "outcome_backed": 2,
        "waiting_for_outcomes": 1,
        "not_outcome_backed_yet": 0,
    }
    promotion_readiness_rank = {
        "ready_for_patch_review": 3,
        "needs_more_shadow_review": 2,
        "waiting_for_signal": 1,
        "hold_for_human_review": 0,
        "hold_weak_advantage_signal": -1,
    }
    for item in variant_comparison:
        variant_review = item.get("variant_review", {})
        if str((variant_review or {}).get("verdict") or "") != "worth_promoting":
            continue
        baseline = dict(item.get("baseline") or {})
        candidate = dict(item.get("candidate") or {})
        feature_delta_rows: List[Dict[str, Any]] = []
        baseline_weights = baseline.get("feature_weights", {})
        if not isinstance(baseline_weights, dict):
            baseline_weights = {}
        candidate_weights = candidate.get("feature_weights", {})
        if not isinstance(candidate_weights, dict):
            candidate_weights = {}
        for feature_name in sorted(set(baseline_weights) | set(candidate_weights)):
            baseline_value = float(baseline_weights.get(feature_name) or 0.0)
            candidate_value = float(candidate_weights.get(feature_name) or 0.0)
            if round(candidate_value - baseline_value, 6) == 0:
                continue
            feature_delta_rows.append(
                {
                    "feature": str(feature_name),
                    "from": baseline_value,
                    "to": candidate_value,
                    "delta": round(candidate_value - baseline_value, 3),
                }
            )
        review_from = baseline.get("review_threshold")
        shortlist_from = baseline.get("shortlist_threshold")
        review_to = candidate.get("review_threshold")
        shortlist_to = candidate.get("shortlist_threshold")
        recommended_config_delta = {
            "review_threshold": {
                "from": float(review_from) if review_from is not None else None,
                "to": float(review_to) if review_to is not None else None,
                "delta": round(float(review_to) - float(review_from), 3)
                if review_from is not None and review_to is not None
                else None,
            },
            "shortlist_threshold": {
                "from": float(shortlist_from) if shortlist_from is not None else None,
                "to": float(shortlist_to) if shortlist_to is not None else None,
                "delta": round(float(shortlist_to) - float(shortlist_from), 3)
                if shortlist_from is not None and shortlist_to is not None
                else None,
            },
            "feature_weights": feature_delta_rows,
        }
        threshold_patch_lines = [
            "thresholds:",
            "  # Proposed triage_v3 shadow candidate. Not auto-wired into live runtime yet.",
        ]
        if review_to is not None:
            threshold_patch_lines.append(f"  triage_v3_review_threshold: {float(review_to):g}")
        if shortlist_to is not None:
            threshold_patch_lines.append(f"  triage_v3_shortlist_threshold: {float(shortlist_to):g}")
        threshold_patch = "\n".join(threshold_patch_lines)

        feature_weight_patch = ""
        if feature_delta_rows:
            merged_weights = {
                str(name): float(candidate_weights.get(name) or 0.0)
                for name in sorted(set(baseline_weights) | set(candidate_weights))
            }
            ordered_items = ",\n".join(
                f'    "{name}": {value:g},'
                for name, value in merged_weights.items()
            )
            feature_weight_patch = "TRIAGE_FEATURE_WEIGHTS = {\n" + ordered_items + "\n}"

        patch_recommendation = {
            "target_config_path": str(paths.default_config_path),
            "thresholds_overlay_yaml": threshold_patch,
            "requires_code_change": bool(feature_weight_patch),
            "target_weights_path": str(paths.repo_root / "jobpipe" / "core" / "triage_v3.py") if feature_weight_patch else "",
            "feature_weights_python_patch": feature_weight_patch,
        }
        promotion_readiness = _build_advantage_promotion_readiness(
            item,
            advantage_signal_recommendation,
        )
        promotion_candidates.append(
            {
                "experiment_id": item.get("experiment_id"),
                "kind": item.get("kind"),
                "created_at": item.get("created_at"),
                "candidate_name": item.get("candidate_name"),
                "summary": item.get("summary"),
                "variant_review": variant_review,
                "useful_signal_rate": item.get("useful_signal_rate", 0.0),
                "reviewed": item.get("reviewed", 0),
                "positive": item.get("positive", 0),
                "rejected": item.get("rejected", 0),
                "upgrade_count": item.get("upgrade_count", 0),
                "changed_count": item.get("changed_count", 0),
                "avg_advantageous_match_score": item.get("avg_advantageous_match_score", 0.0),
                "high_advantage_count": item.get("high_advantage_count", 0),
                "top_recruiter_hooks": list(item.get("top_recruiter_hooks") or []),
                "advantage_signal_fit": dict(item.get("advantage_signal_fit") or {}),
                "outcome_shadow_fit": dict(item.get("outcome_shadow_fit") or {}),
                "promotion_outcome_status": _build_promotion_outcome_status(item),
                "promotion_readiness": promotion_readiness,
                "recommended_config_delta": recommended_config_delta,
                "patch_recommendation": patch_recommendation,
                "promotion_review": get_experiment_promotion_review(
                    review_state,
                    experiment_id=str(item.get("experiment_id") or ""),
                ),
            }
        )
    promotion_candidates.sort(
        key=lambda item: (
            -promotion_review_rank.get(str((item.get("promotion_review") or {}).get("verdict") or ""), 0),
            -promotion_outcome_rank.get(str((item.get("promotion_outcome_status") or {}).get("status") or ""), 0),
            -promotion_readiness_rank.get(str((item.get("promotion_readiness") or {}).get("status") or ""), 0),
            -float(item.get("useful_signal_rate", 0.0)),
            -float(item.get("avg_advantageous_match_score", 0.0)),
            -int(item.get("high_advantage_count", 0)),
            -int(item.get("upgrade_count", 0)),
            str(item.get("created_at") or ""),
        )
    )
    payload["promotion_candidates"] = promotion_candidates
    payload["promotion_summary"] = {
        "count": len(promotion_candidates),
        "has_feature_weight_candidate": any(
            bool((candidate.get("recommended_config_delta") or {}).get("feature_weights"))
            for candidate in promotion_candidates
        ),
        "outcome_backed_count": sum(
            1
            for candidate in promotion_candidates
            if str((candidate.get("promotion_outcome_status") or {}).get("status") or "") == "outcome_backed"
        ),
        "waiting_for_outcomes_count": sum(
            1
            for candidate in promotion_candidates
            if str((candidate.get("promotion_outcome_status") or {}).get("status") or "") == "waiting_for_outcomes"
        ),
        "not_outcome_backed_yet_count": sum(
            1
            for candidate in promotion_candidates
            if str((candidate.get("promotion_outcome_status") or {}).get("status") or "") == "not_outcome_backed_yet"
        ),
    }
    payload["promotion_readiness_summary"] = {
        "ready_for_patch_review": sum(
            1
            for candidate in promotion_candidates
            if str((candidate.get("promotion_readiness") or {}).get("status") or "") == "ready_for_patch_review"
        ),
        "needs_more_shadow_review": sum(
            1
            for candidate in promotion_candidates
            if str((candidate.get("promotion_readiness") or {}).get("status") or "") == "needs_more_shadow_review"
        ),
        "waiting_for_signal": sum(
            1
            for candidate in promotion_candidates
            if str((candidate.get("promotion_readiness") or {}).get("status") or "") == "waiting_for_signal"
        ),
        "hold_for_human_review": sum(
            1
            for candidate in promotion_candidates
            if str((candidate.get("promotion_readiness") or {}).get("status") or "") == "hold_for_human_review"
        ),
        "hold_weak_advantage_signal": sum(
            1
            for candidate in promotion_candidates
            if str((candidate.get("promotion_readiness") or {}).get("status") or "") == "hold_weak_advantage_signal"
        ),
    }
    payload["promotion_review_summary"] = build_experiment_promotion_review_summary(promotion_candidates)
    payload["outcome_shadow_summary"] = {
        "aligned": sum(
            1
            for item in variant_comparison
            if str((item.get("outcome_shadow_fit") or {}).get("fit") or "") == "aligned"
        ),
        "indirect": sum(
            1
            for item in variant_comparison
            if str((item.get("outcome_shadow_fit") or {}).get("fit") or "") == "indirect"
        ),
        "waiting": sum(
            1
            for item in variant_comparison
            if str((item.get("outcome_shadow_fit") or {}).get("fit") or "") == "waiting"
        ),
        "watch": sum(
            1
            for item in variant_comparison
            if str((item.get("outcome_shadow_fit") or {}).get("fit") or "") == "watch"
        ),
    }
    payload["outcome_ranking_guidance"] = outcome_ranking_guidance
    payload["advantage_calibration_summary"] = advantage_calibration_summary
    payload["advantage_shortlist_quality_summary"] = build_advantage_shortlist_quality_summary(variant_comparison)
    payload["advantage_signal_recommendation"] = advantage_signal_recommendation
    if variant_comparison:
        payload["leading_variant"] = variant_comparison[0]
        if promotion_candidates and payload["leading_variant"].get("experiment_id") == promotion_candidates[0].get("experiment_id"):
            payload["leading_variant"]["promotion_readiness"] = dict(promotion_candidates[0].get("promotion_readiness") or {})
            payload["leading_variant"]["promotion_outcome_status"] = dict(promotion_candidates[0].get("promotion_outcome_status") or {})
    return payload


def _build_outcome_shadow_handoff(outcomes: Dict[str, Any]) -> Dict[str, Any]:
    recommendation = outcomes.get("recommendation") if isinstance(outcomes, dict) else {}
    shadow_followup = outcomes.get("shadow_followup") if isinstance(outcomes, dict) else {}
    if not isinstance(recommendation, dict):
        recommendation = {}
    if not isinstance(shadow_followup, dict):
        shadow_followup = {}

    suggested_experiment = str(shadow_followup.get("suggested_experiment") or "")
    ready_for_shadow = bool(shadow_followup.get("ready_for_shadow"))
    if ready_for_shadow:
        status = "ready_for_shadow"
    elif suggested_experiment == "collect_more_outcomes":
        status = "collect_more_outcomes"
    else:
        status = "hold_for_review"

    return {
        "schema_version": "jobpipe.outcome-shadow-handoff.v1",
        "status": status,
        "suggested_experiment": suggested_experiment,
        "ready_for_shadow": ready_for_shadow,
        "confidence": str(shadow_followup.get("confidence") or ""),
        "rationale": str(shadow_followup.get("rationale") or ""),
        "recommended_next_action": str(recommendation.get("recommended_next_action") or ""),
        "decision_signal": str(recommendation.get("decision_signal") or ""),
        "artifact_signal": str(recommendation.get("artifact_signal") or ""),
    }


def build_payload(
    sqlite_path: Path,
    out_dir: Path,
    state_path: Optional[Path] = None,
    config_path: Optional[Path] = None,
    config_overlays: Optional[List[str]] = None,
    profile_path: Optional[Path] = None,
    resume_path: Optional[Path] = None,
    profile_draft_path: Optional[Path] = None,
    settings_path: Optional[Path] = None,
    payload_budget_bytes: int = _PAYLOAD_SOFT_BUDGET_BYTES,
    max_event_rows: int = _PAYLOAD_EVENT_HARD_CAP,
    min_event_rows: int = _PAYLOAD_EVENT_MIN_ROWS,
) -> Dict[str, Any]:
    paths = _resolve_paths_for_payload(
        state_path=state_path,
        profile_path=profile_path,
        resume_path=resume_path,
        profile_draft_path=profile_draft_path,
        settings_path=settings_path,
    )
    app_state = _load_app_state(state_path or paths.application_state_path)
    config_path = config_path or paths.default_config_path
    resume_source = resume_path or paths.resume_json_path
    resume_fixed_source = (
        paths.resume_fixed_json_path if resume_path is None else resume_source.with_name("resume_fixed.json")
    )
    if not resume_source.exists() and resume_fixed_source.exists():
        resume_source = resume_fixed_source
    profile = _build_profile_payload(
        paths,
        profile_path or paths.profile_pack_path,
        resume_source,
        profile_draft_path or paths.profile_builder_state_path,
    )
    settings = build_settings_payload(
        paths=paths,
        profile=profile,
        settings_path=settings_path or paths.settings_state_path,
    )
    automations = build_automation_payload(
        paths,
        state_path=paths.automation_state_path,
    )
    thresholds = _load_thresholds(config_path, overlays=config_overlays)
    config_snapshot = _build_config_snapshot(config_path, overlays=config_overlays)
    projection_store = load_projection_store(paths.projection_store_path)
    conn = sqlite3.connect(str(sqlite_path))

    jobs_raw = _rows_as_dicts(conn, """
        SELECT job_id, title, employer, work_city, work_county, work_postalCode,
               applicationDue, source_url, application_url,
               job_source, job_status, suggested_by_platform, normalized_title,
               occ_level1, occ_level2, cat_type, cat_code, cat_name, cat_score,
               triage_decision, triage_confidence, triage_explanation, triage_signals,
               reverse_decision, reverse_confidence, reverse_rationale,
               fit_score, pivot_score,
               triage_v3_label, triage_v3_weighted_score, triage_v3_confidence,
               triage_v3_needs_ambiguity, triage_ambiguity_label, triage_ambiguity_reason,
               advantage_type, advantage_review_priority,
               narrative_positioning_angle, narrative_brand_frame,
               final_decision, final_confidence, recommendation_reason,
               cv_focus, feedback_flags,
               pack_ready, pack_generated_at, pack_has_cover_letter,
               pack_highlight_count, pack_docx_ready, generated_documents_json,
               description_snip,
               skip_reason,
               run_id, run_seen_at, updated_at, closed_at,
               raw_triage_features_json, raw_triage_decision_v3_json,
               raw_triage_ambiguity_v3_json, raw_advantage_assessment_v3_json,
               raw_narrative_strategy_v3_json,
               raw_match_json, raw_pivot_json, raw_moderator_json
        FROM ledger
        ORDER BY
            CASE final_decision
                WHEN 'APPLY_STRONGLY' THEN 0
                WHEN 'APPLY' THEN 1
                WHEN 'REVIEW_HIGH' THEN 2
                WHEN 'REVIEW_LOW' THEN 3
                ELSE 4
            END,
            fit_score DESC NULLS LAST
    """)

    jobs = []
    for row in jobs_raw:
        # Re-apply current YAML thresholds so the dashboard always reflects
        # the latest config — even for jobs scored under older threshold values.
        _apply_threshold_view(row, thresholds)

        is_actionable = row.get("final_decision") in _ACTIONABLE

        if is_actionable:
            row["detail"] = _extract_detail(row)
            bundle = get_job_projection_bundle(
                projection_store,
                run_id=str(row.get("run_id") or ""),
                job_id=str(row.get("job_id") or ""),
            )
            apply_detail_projection(row["detail"], bundle.get("detail_projection", {}))
            apply_input_enrichment_projection(row, bundle.get("input_enrichment", {}))
            row["applicationDue"] = _normalize_due(row.get("applicationDue"))
            _enrich_from_input(row, out_dir)
            set_job_projection_bundle(
                projection_store,
                run_id=str(row.get("run_id") or ""),
                job_id=str(row.get("job_id") or ""),
                bundle=build_job_projection_bundle(
                    input_enrichment=build_input_enrichment_projection(row),
                    detail_projection=build_detail_projection(
                        decision_brief=row["detail"].get("decision_brief"),
                        application_case_projection=row["detail"].get("application_case_projection"),
                        updated_at=str(row.get("updated_at") or ""),
                    ),
                ),
            )
        else:
            for col in _DETAIL_COLS:
                row.pop(col, None)
            row["detail"] = None

        for k in (
            "raw_triage_features_json",
            "raw_triage_decision_v3_json",
            "raw_triage_ambiguity_v3_json",
            "raw_advantage_assessment_v3_json",
            "raw_narrative_strategy_v3_json",
            "raw_match_json",
            "raw_pivot_json",
            "raw_moderator_json",
        ):
            row.pop(k, None)

        row["suggested_by_platform"] = bool(row.get("suggested_by_platform"))
        row["pack_ready"] = bool(row.get("pack_ready"))
        row["pack_has_cover_letter"] = bool(row.get("pack_has_cover_letter"))
        row["pack_docx_ready"] = bool(row.get("pack_docx_ready"))
        row["no_score_reason_label"] = _derive_no_score_reason_label(row)
        row["generated_documents"] = _collect_generated_documents(row, out_dir)
        row["applicationDue"] = _normalize_due(row.get("applicationDue"))
        row.pop("generated_documents_json", None)

        # Merge application tracking state
        app_entry = app_state.get(row.get("job_id", ""), {})
        row["app_status"] = normalize_shared_status(app_entry)
        row["app_stages"] = json.dumps(app_entry.get("stages", []), ensure_ascii=False)
        row["app_outcome"] = app_entry.get("outcome") or ""
        row["app_updated_at"] = app_entry.get("updated_at", "")
        row["app_source"] = app_entry.get("source", "")
        row["app_notes"] = app_entry.get("notes", "")

        jobs.append(row)

    events = _rows_as_dicts(conn, """
        SELECT run_id, job_id, run_mtime, seen_at,
               job_source, job_status, skip_reason,
               final_decision, triage_decision, triage_confidence,
               fit_score, pivot_score
        FROM events
        ORDER BY run_mtime
    """)

    conn.close()
    persist_projection_store(paths.projection_store_path, projection_store)
    outcome_feedback_state = build_outcome_feedback_state(jobs)
    persist_outcome_feedback_state(paths.outcome_feedback_state_path, outcome_feedback_state)
    outcomes = build_outcomes_dashboard_payload(outcome_feedback_state)
    outcome_shadow_handoff = _build_outcome_shadow_handoff(outcomes)
    experiments = _build_experiments_payload(
        paths,
        jobs,
        outcome_shadow_handoff=outcome_shadow_handoff,
    )
    experiments["outcome_shadow_handoff"] = outcome_shadow_handoff

    payload = {
        "schema_version": _PAYLOAD_SCHEMA_VERSION,
        "jobs": jobs,
        "events": events,
        "experiments": experiments,
        "outcomes": outcomes,
        "profile": profile,
        "settings": settings,
        "automations": automations,
        "thresholds": thresholds,
        "config_snapshot": config_snapshot,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    pruned_events, pruned_event_count = _prune_events(
        payload["events"],
        {k: v for k, v in payload.items() if k != "events"},
        budget_bytes=payload_budget_bytes,
        max_event_rows=max_event_rows,
        min_event_rows=min_event_rows,
    )
    payload["events"] = pruned_events
    _attach_payload_meta(
        payload,
        budget_bytes=payload_budget_bytes,
        event_rows_before=len(events),
        event_rows_after=len(pruned_events),
        pruned_event_count=pruned_event_count,
        max_event_rows=max_event_rows,
        min_event_rows=min_event_rows,
    )
    return payload


def render_dashboard_html(payload: Dict[str, Any], template_path: Path, head_injection: str = "") -> str:
    template = template_path.read_text(encoding="utf-8")
    data_json = json.dumps(payload, ensure_ascii=False, default=str)
    if _DATA_PLACEHOLDER not in template:
        raise RuntimeError(
            f"Template {template_path} is missing the data placeholder: {_DATA_PLACEHOLDER}"
        )
    html = template.replace(_DATA_PLACEHOLDER, data_json)
    if head_injection:
        if "</head>" not in html:
            raise RuntimeError(f"Template {template_path} is missing </head> for head injection")
        html = html.replace("</head>", head_injection + "\n</head>", 1)
    return html


def build_dashboard_html(
    sqlite_path: Path,
    out_dir: Path,
    template_path: Path,
    state_path: Optional[Path] = None,
    config_path: Optional[Path] = None,
    config_overlays: Optional[List[str]] = None,
    profile_path: Optional[Path] = None,
    resume_path: Optional[Path] = None,
    profile_draft_path: Optional[Path] = None,
    settings_path: Optional[Path] = None,
    head_injection: str = "",
) -> tuple[str, Dict[str, Any]]:
    payload = build_payload(
        sqlite_path,
        out_dir,
        state_path=state_path,
        config_path=config_path,
        config_overlays=config_overlays,
        profile_path=profile_path,
        resume_path=resume_path,
        profile_draft_path=profile_draft_path,
        settings_path=settings_path,
    )
    html = render_dashboard_html(payload, template_path, head_injection=head_injection)
    return html, payload


def export(sqlite_path: Path, out_dir: Path, template_path: Path, out_path: Path,
           state_path: Optional[Path] = None, config_path: Optional[Path] = None,
           config_overlays: Optional[List[str]] = None,
           profile_path: Optional[Path] = None,
           resume_path: Optional[Path] = None,
           profile_draft_path: Optional[Path] = None,
           settings_path: Optional[Path] = None) -> None:
    html, payload = build_dashboard_html(
        sqlite_path,
        out_dir,
        template_path,
        state_path=state_path,
        config_path=config_path,
        config_overlays=config_overlays,
        profile_path=profile_path,
        resume_path=resume_path,
        profile_draft_path=profile_draft_path,
        settings_path=settings_path,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    n_action = sum(1 for j in payload["jobs"] if j.get("final_decision") in _ACTIONABLE)
    n_urls = sum(1 for j in payload["jobs"]
                 if j.get("final_decision") in _ACTIONABLE
                 and (j.get("application_url") or j.get("source_url")))
    n_tracked = sum(1 for j in payload["jobs"] if j.get("app_status"))
    print(f"Dashboard exported: {out_path}")
    print(f"  {len(payload['jobs'])} jobs ({n_action} actionable, {n_urls} with URLs), {len(payload['events'])} events")
    if n_tracked:
        print(f"  {n_tracked} jobs with application status tracked")
    meta = payload.get("payload_meta") or {}
    if meta:
        print(
            "  payload: "
            f"{meta.get('size_mb', 0)} MB, "
            f"events {meta.get('event_rows_after', 0)}/{meta.get('event_rows_before', 0)} "
            f"(pruned {meta.get('pruned_event_count', 0)})"
        )
        if meta.get("budget_state") != "ok":
            print("  warning: payload is still above the soft budget after event pruning")


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Build a self-contained dashboard HTML from ledger SQLite.")
    ap.add_argument(
        "--data-root",
        default="",
        help=f"JobPipe user data root (default: {_DEFAULT_PATHS.data_root})",
    )
    ap.add_argument(
        "--sqlite",
        default="",
        help=f"Path to ledger.sqlite (default: {_DEFAULT_PATHS.ledger_sqlite_path})",
    )
    ap.add_argument(
        "--out-runs",
        default="",
        help=f"Path to out_runs directory (default: {_DEFAULT_PATHS.out_runs_dir})",
    )
    ap.add_argument(
        "--template",
        default="",
        help=f"HTML template path (default: {_DEFAULT_PATHS.dashboard_template_path})",
    )
    ap.add_argument(
        "--out",
        default="",
        help=f"Output HTML path (default: {_DEFAULT_PATHS.dashboard_export_path})",
    )
    ap.add_argument(
        "--app-state",
        default="",
        help=f"Path to application_state.json (default: {_DEFAULT_PATHS.application_state_path})",
    )
    ap.add_argument(
        "--config",
        default="",
        help=f"Pipeline config YAML (default: {_DEFAULT_PATHS.default_config_path})",
    )
    ap.add_argument("--config-overlay", action="append", default=[], help="Optional config overlay YAML. Can be passed multiple times.")
    args = ap.parse_args(argv)
    paths = get_jobpipe_paths(args.data_root or None)
    bootstrap_private_data(paths, include_artifacts=True)
    export(
        Path(args.sqlite) if args.sqlite else paths.ledger_sqlite_path,
        Path(args.out_runs) if args.out_runs else paths.out_runs_dir,
        Path(args.template) if args.template else paths.dashboard_template_path,
        Path(args.out) if args.out else paths.dashboard_export_path,
        state_path=Path(args.app_state) if args.app_state else paths.application_state_path,
        config_path=Path(args.config) if args.config else paths.default_config_path,
        config_overlays=args.config_overlay,
        profile_path=paths.profile_pack_path,
        resume_path=paths.resume_json_path,
        profile_draft_path=paths.profile_builder_state_path,
        settings_path=paths.settings_state_path,
    )


if __name__ == "__main__":
    main()
