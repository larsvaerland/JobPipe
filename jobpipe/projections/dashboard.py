"""Dashboard projection built from canonical JobPipe state."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from jobpipe.core.candidate_data import load_candidate_profile_json
from jobpipe.core.io import load_env_file
from jobpipe.core.no_score_reason import derive_no_score_reason, format_no_score_reason
from jobpipe.decision import (
    build_candidate_calibration_context,
    build_decision_context,
    build_monitoring_context,
    derive_candidate_calibration_summary,
)
from jobpipe.runtime.paths import application_state_path, primary_db_path

load_env_file(".env")

try:
    import yaml as _yaml

    def _load_thresholds(config_path: Path) -> Dict[str, Any]:
        try:
            raw = _yaml.safe_load(config_path.read_bytes())
            return (raw or {}).get("thresholds", {})
        except Exception:
            return {}
except ImportError:

    def _load_thresholds(config_path: Path) -> Dict[str, Any]:
        return {}


_APP_STATE_PATH = application_state_path()
_PRIMARY_DB_PATH = primary_db_path()
_CONFIG_PATH = Path("./configs/pipeline.v1.yaml")
_DEFAULT_CANDIDATE_ID = (os.environ.get("JOBPIPE_CANDIDATE_ID") or "default").strip() or "default"

_DETAIL_COLS = (
    "triage_explanation",
    "reverse_decision",
    "reverse_confidence",
    "reverse_rationale",
    "recommendation_reason",
    "cv_focus",
    "feedback_flags",
    "description_snip",
)

_ACTIONABLE = {"APPLY_STRONGLY", "APPLY", "REVIEW_HIGH", "REVIEW_LOW"}
_DATA_PLACEHOLDER = "/*__DASHBOARD_DATA__*/"


def _reclassify(fit_score: Any, pivot_score: Any, thresholds: Dict[str, Any]) -> str:
    """Re-apply current YAML thresholds to produce a fresh final_decision."""
    try:
        fit = int(fit_score or 0)
        pivot = int(pivot_score or 0)
    except Exception:
        return "SKIP"

    apply_strong = int(thresholds.get("apply_strong_fit", 78))
    apply_fit = int(thresholds.get("apply_fit", 67))
    pivot_boost = int(thresholds.get("pivot_boost_apply", 78))
    review_min = int(thresholds.get("review_min_fit", 30))
    review_high = int(thresholds.get("review_high_min_fit", 58))

    if fit < review_min:
        return "SKIP"
    if fit < review_high:
        return "REVIEW_LOW"
    if fit >= apply_strong:
        return "APPLY_STRONGLY"
    if fit >= apply_fit:
        return "APPLY"
    return "REVIEW_HIGH" if pivot >= pivot_boost else "REVIEW_LOW"


def _parse_raw_json(val: Any) -> Dict[str, Any]:
    if not val:
        return {}
    try:
        return json.loads(val)
    except Exception:
        return {}


def _extract_detail(row: Dict[str, Any]) -> Dict[str, Any]:
    match = _parse_raw_json(row.get("raw_match_json"))
    pivot = _parse_raw_json(row.get("raw_pivot_json"))
    mod = _parse_raw_json(row.get("raw_moderator_json"))
    return {
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


def _safe_load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _pick(*vals: Any) -> Any:
    for val in vals:
        if val is not None and str(val).strip():
            return val
    return ""


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")


def _enrich_from_input(row: Dict[str, Any], out_dir: Path) -> None:
    """Fill in missing URL/deadline/location fields from per-job 00_input.json."""
    needs_url = not (row.get("application_url") or "").strip() and not (row.get("source_url") or "").strip()
    needs_loc = not (row.get("work_city") or "").strip() and not (row.get("work_county") or "").strip()
    if not needs_url and not needs_loc:
        return

    run_id = row.get("run_id", "")
    job_id = row.get("job_id", "")
    if not run_id or not job_id:
        return

    input_path = out_dir / run_id / job_id / "00_input.json"
    inp = _safe_load_json(input_path)
    if not inp:
        return

    job = inp.get("job", inp) if isinstance(inp.get("job"), dict) else inp

    if needs_url:
        row["application_url"] = _pick(row.get("application_url"), job.get("applicationUrl"))
        row["source_url"] = _pick(row.get("source_url"), job.get("sourceurl"), job.get("link"))
        row["applicationDue"] = _pick(row.get("applicationDue"), job.get("applicationDue"))
        due = str(row.get("applicationDue") or "")
        if "T" in due:
            row["applicationDue"] = due[:10]

    if needs_loc:
        row["work_city"] = _pick(
            row.get("work_city"),
            job.get("work_city"),
            job.get("municipal"),
            job.get("municipalName"),
        )
        row["work_county"] = _pick(
            row.get("work_county"),
            job.get("work_county"),
            job.get("county"),
        )


def _load_app_state(state_path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return data.get("applications", {})
    except Exception:
        return {}


def _load_app_state_from_db(db_path: Path, candidate_id: str) -> Dict[str, Any]:
    if not db_path.exists():
        return {}

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        summary_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT job_id, current_stage, current_outcome, effective_status,
                       last_event_at, notes_latest, updated_at
                FROM application_summary
                WHERE candidate_id = ?
                """,
                [candidate_id],
            )
        ]
        event_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT job_id, event_type, event_at, source, notes, metadata_json, created_at
                FROM application_events
                WHERE candidate_id = ?
                ORDER BY event_at DESC, created_at DESC
                """,
                [candidate_id],
            )
        ]
        conn.close()
    except Exception:
        return {}

    latest_event_by_job: Dict[str, Dict[str, Any]] = {}
    for row in event_rows:
        job_id = str(row.get("job_id") or "").strip()
        if job_id and job_id not in latest_event_by_job:
            latest_event_by_job[job_id] = row

    out: Dict[str, Any] = {}
    for row in summary_rows:
        job_id = str(row.get("job_id") or "").strip()
        if not job_id:
            continue

        latest = latest_event_by_job.get(job_id, {})
        try:
            metadata = json.loads(latest.get("metadata_json") or "{}")
        except Exception:
            metadata = {}

        stages = metadata.get("stages", [])
        if not isinstance(stages, list):
            stages = []

        outcome = str(row.get("current_outcome") or metadata.get("outcome") or "").strip()
        out[job_id] = {
            "status": str(row.get("effective_status") or metadata.get("effective_status") or "").strip(),
            "stages": stages,
            "outcome": outcome,
            "updated_at": str(row.get("updated_at") or row.get("last_event_at") or "").strip(),
            "source": str(latest.get("source") or "").strip(),
            "notes": str(row.get("notes_latest") or latest.get("notes") or "").strip(),
            "email_subject": str(metadata.get("email_subject") or "").strip(),
            "email_date": str(metadata.get("email_date") or "").strip(),
        }

    return out


def _load_app_state_merged(
    state_path: Optional[Path],
    db_path: Optional[Path],
    candidate_id: str,
) -> Dict[str, Any]:
    merged = _load_app_state_from_db(db_path or _PRIMARY_DB_PATH, candidate_id)
    sidecar = _load_app_state(state_path or _APP_STATE_PATH)
    for job_id, entry in sidecar.items():
        merged.setdefault(job_id, entry)
    return merged


def _load_generated_documents_from_db(
    db_path: Path,
    candidate_id: str,
) -> Dict[str, List[Dict[str, Any]]]:
    if not db_path.exists():
        return {}

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT job_id, kind, producer, status, storage_path, preview_text,
                       created_at, updated_at
                FROM generated_documents
                WHERE candidate_id = ?
                ORDER BY updated_at DESC, created_at DESC
                """,
                [candidate_id],
            )
        ]
        conn.close()
    except Exception:
        return {}

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        job_id = str(row.get("job_id") or "").strip()
        if not job_id:
            continue
        grouped.setdefault(job_id, []).append(
            {
                "kind": str(row.get("kind") or "").strip(),
                "producer": str(row.get("producer") or "").strip(),
                "status": str(row.get("status") or "").strip(),
                "storage_path": str(row.get("storage_path") or "").strip(),
                "preview_text": str(row.get("preview_text") or "").strip(),
                "created_at": str(row.get("created_at") or "").strip(),
                "updated_at": str(row.get("updated_at") or "").strip(),
            }
        )
    return grouped


def _load_feedback_events_from_db(
    db_path: Path,
    candidate_id: str,
) -> List[Dict[str, Any]]:
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT feedback_event_id, candidate_id, job_id, evaluation_id, feedback_type,
                       feedback_value, source, notes, evidence_json, created_at
                FROM candidate_feedback_events
                WHERE candidate_id = ?
                ORDER BY created_at DESC, job_id ASC
                """,
                [candidate_id],
            )
        ]
        conn.close()
    except Exception:
        return []

    for row in rows:
        try:
            row["evidence_json"] = json.loads(row.get("evidence_json") or "{}")
        except Exception:
            row["evidence_json"] = {}
    return rows


def _load_calibration_settings_from_db(
    db_path: Path,
    candidate_id: str,
) -> List[Dict[str, Any]]:
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT candidate_id, scope, setting_key, value_json, updated_at
                FROM candidate_calibration_settings
                WHERE candidate_id = ?
                ORDER BY updated_at DESC, scope ASC, setting_key ASC
                """,
                [candidate_id],
            )
        ]
        conn.close()
    except Exception:
        return []

    for row in rows:
        try:
            row["value_json"] = json.loads(row.get("value_json") or "{}")
        except Exception:
            row["value_json"] = {}
    return rows


def _load_jobs_and_events_from_primary_db(
    db_path: Path,
    candidate_id: str,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not db_path.exists():
        return [], []

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        jobs = [
            dict(r)
            for r in conn.execute(
                """
                SELECT job_id, title, employer, work_city, work_county, work_postalCode,
                       applicationDue, source_url, application_url,
                       triage_decision, triage_confidence, triage_explanation, triage_signals,
                       reverse_decision, reverse_confidence, reverse_rationale,
                       fit_score, pivot_score,
                       final_decision, final_confidence, recommendation_reason,
                       cv_focus, feedback_flags, description_snip,
                       skip_reason,
                       run_id, run_seen_at, updated_at,
                       raw_match_json, raw_pivot_json, raw_moderator_json
                FROM job_evaluations
                WHERE candidate_id = ?
                ORDER BY
                    CASE final_decision
                        WHEN 'APPLY_STRONGLY' THEN 0
                        WHEN 'APPLY' THEN 1
                        WHEN 'REVIEW_HIGH' THEN 2
                        WHEN 'REVIEW_LOW' THEN 3
                        ELSE 4
                    END,
                    CASE WHEN fit_score IS NULL THEN 1 ELSE 0 END,
                    fit_score DESC
                """,
                [candidate_id],
            )
        ]
        events = [
            dict(r)
            for r in conn.execute(
                """
                SELECT run_id, job_id, run_mtime, seen_at,
                       final_decision, triage_decision, triage_confidence,
                       fit_score, pivot_score, applicationDue,
                       title, employer, work_city, work_county,
                       source_url, application_url
                FROM job_run_events
                WHERE candidate_id = ?
                ORDER BY run_mtime
                """,
                [candidate_id],
            )
        ]
        conn.close()
    except Exception:
        return [], []

    return jobs, events


def _load_promoted_decision_state_from_db(
    db_path: Path,
    candidate_id: str,
) -> Dict[str, Any]:
    empty = {
        "claims_by_job": {},
        "signals_by_job": {},
        "selection_assessments_by_job": {},
        "decision_tables_by_job": {},
        "job_narrative_assessments_by_job": {},
        "watchlists": [],
        "change_events_by_job": {},
        "watchlist_count": 0,
        "watchlist_count_by_materiality": {"high": 0, "medium": 0, "low": 0},
        "change_event_count": 0,
        "high_materiality_change_events": 0,
        "state_available": False,
    }
    if not db_path.exists():
        return empty

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        claims = [
            dict(r)
            for r in conn.execute(
                """
                SELECT job_id, claim_type, claim_strength, claim_subject_type,
                       normalized_key, normalized_label, claim_text, source_basis,
                       source_section, evidence_span, confidence_score, importance_score,
                       claim_json
                FROM job_claims
                ORDER BY job_id ASC, importance_score DESC, updated_at DESC
                """
            )
        ]
        signals = [
            dict(r)
            for r in conn.execute(
                """
                SELECT job_id, signal_type, signal_label, selection_stage, signal_strength,
                       normalized_key, evidence_required, confidence_score, importance_score,
                       source_basis, signal_json
                FROM job_selection_signals
                ORDER BY job_id ASC, importance_score DESC, updated_at DESC
                """
            )
        ]
        selection_assessments = [
            dict(r)
            for r in conn.execute(
                """
                SELECT candidate_id, job_id, structural_pass, screenability_score,
                       title_continuity_score, domain_continuity_score,
                       ambiguity_risk_score, evidence_burden_score, selection_risk_level,
                       likely_rejection_vectors_json, mitigation_moves_json,
                       assessment_reason, assessment_json
                FROM job_selection_assessments
                WHERE candidate_id = ?
                """,
                [candidate_id],
            )
        ]
        decision_tables = [
            dict(r)
            for r in conn.execute(
                """
                SELECT candidate_id, job_id, can_do_level, can_do_score, can_do_reason,
                       can_do_supporting_points_json, can_do_risk_points_json,
                       can_get_level, can_get_score, can_get_reason,
                       can_get_supporting_points_json, can_get_risk_points_json,
                       should_want_level, should_want_score, should_want_reason,
                       should_want_supporting_points_json, should_want_risk_points_json,
                       can_explain_level, can_explain_score, can_explain_reason,
                       can_explain_supporting_points_json, can_explain_risk_points_json,
                       act_now, confidence_score, table_reason, next_moves_json, decision_table_json
                FROM job_decision_tables
                WHERE candidate_id = ?
                """,
                [candidate_id],
            )
        ]
        narrative_assessments = [
            dict(r)
            for r in conn.execute(
                """
                SELECT candidate_id, job_id, direction_fit_score, motivation_fit_score,
                       pivot_credibility_score, story_strength_score,
                       misalignment_flags_json, assessment_reason, motivation_brief,
                       assessment_json
                FROM job_narrative_assessments
                WHERE candidate_id = ?
                """,
                [candidate_id],
            )
        ]
        watchlists = [
            dict(r)
            for r in conn.execute(
                """
                SELECT watchlist_id, candidate_id, watch_type, watch_key, watch_label,
                       watch_config_json, is_active, materiality
                FROM watchlists
                WHERE candidate_id = ? AND is_active = 1
                ORDER BY watch_type ASC, watch_label ASC, watch_key ASC
                """,
                [candidate_id],
            )
        ]
        change_events = [
            dict(r)
            for r in conn.execute(
                """
                SELECT change_event_id, candidate_id, watchlist_id, job_id, change_type,
                       change_summary, change_json, materiality, detected_at, reviewed_at
                FROM change_events
                WHERE candidate_id = ?
                ORDER BY detected_at DESC, updated_at DESC
                """,
                [candidate_id],
            )
        ]
        conn.close()
    except Exception:
        return empty

    claims_by_job: Dict[str, List[Dict[str, Any]]] = {}
    for row in claims:
        job_id = _clean_text(row.get("job_id"))
        if not job_id:
            continue
        try:
            claim_json = json.loads(row.get("claim_json") or "{}")
        except Exception:
            claim_json = {}
        claims_by_job.setdefault(job_id, []).append(
            {
                "claim_type": _clean_text(row.get("claim_type")),
                "claim_strength": _clean_text(row.get("claim_strength")),
                "claim_subject_type": _clean_text(row.get("claim_subject_type")),
                "normalized_key": _clean_text(row.get("normalized_key")),
                "normalized_label": _clean_text(row.get("normalized_label")),
                "claim_text": _clean_text(row.get("claim_text")),
                "source_basis": _clean_text(row.get("source_basis")),
                "source_section": _clean_text(row.get("source_section")),
                "evidence_span": _clean_text(row.get("evidence_span")),
                "confidence_score": row.get("confidence_score"),
                "importance_score": row.get("importance_score"),
                "claim_json": claim_json,
            }
        )

    signals_by_job: Dict[str, List[Dict[str, Any]]] = {}
    for row in signals:
        job_id = _clean_text(row.get("job_id"))
        if not job_id:
            continue
        try:
            signal_json = json.loads(row.get("signal_json") or "{}")
        except Exception:
            signal_json = {}
        signals_by_job.setdefault(job_id, []).append(
            {
                "signal_type": _clean_text(row.get("signal_type")),
                "signal_label": _clean_text(row.get("signal_label")),
                "selection_stage": _clean_text(row.get("selection_stage")),
                "signal_strength": _clean_text(row.get("signal_strength")),
                "normalized_key": _clean_text(row.get("normalized_key")),
                "evidence_required": _clean_text(row.get("evidence_required")),
                "confidence_score": row.get("confidence_score"),
                "importance_score": row.get("importance_score"),
                "source_basis": _clean_text(row.get("source_basis")),
                "signal_json": signal_json,
            }
        )

    selection_assessments_by_job: Dict[str, Dict[str, Any]] = {}
    for row in selection_assessments:
        job_id = _clean_text(row.get("job_id"))
        if not job_id:
            continue
        try:
            likely_rejection_vectors = json.loads(row.get("likely_rejection_vectors_json") or "[]")
        except Exception:
            likely_rejection_vectors = []
        try:
            mitigation_moves = json.loads(row.get("mitigation_moves_json") or "[]")
        except Exception:
            mitigation_moves = []
        try:
            assessment_json = json.loads(row.get("assessment_json") or "{}")
        except Exception:
            assessment_json = {}
        selection_assessments_by_job[job_id] = {
            "structural_pass": bool(row.get("structural_pass")),
            "screenability_score": row.get("screenability_score"),
            "title_continuity_score": row.get("title_continuity_score"),
            "domain_continuity_score": row.get("domain_continuity_score"),
            "ambiguity_risk_score": row.get("ambiguity_risk_score"),
            "evidence_burden_score": row.get("evidence_burden_score"),
            "selection_risk_level": _clean_text(row.get("selection_risk_level")),
            "likely_rejection_vectors": likely_rejection_vectors if isinstance(likely_rejection_vectors, list) else [],
            "mitigation_moves": mitigation_moves if isinstance(mitigation_moves, list) else [],
            "assessment_reason": _clean_text(row.get("assessment_reason")),
            "assessment_json": assessment_json,
        }

    decision_tables_by_job: Dict[str, Dict[str, Any]] = {}
    for row in decision_tables:
        job_id = _clean_text(row.get("job_id"))
        if not job_id:
            continue
        try:
            decision_table_json = json.loads(row.get("decision_table_json") or "{}")
        except Exception:
            decision_table_json = {}
        if isinstance(decision_table_json, dict) and decision_table_json.get("can_do"):
            decision_tables_by_job[job_id] = decision_table_json
            continue

        def _dim(prefix: str) -> Dict[str, Any]:
            try:
                supporting_points = json.loads(row.get(f"{prefix}_supporting_points_json") or "[]")
            except Exception:
                supporting_points = []
            try:
                risk_points = json.loads(row.get(f"{prefix}_risk_points_json") or "[]")
            except Exception:
                risk_points = []
            return {
                "dimension_key": prefix,
                "level": _clean_text(row.get(f"{prefix}_level")),
                "score": row.get(f"{prefix}_score"),
                "reason": _clean_text(row.get(f"{prefix}_reason")),
                "supporting_points": supporting_points if isinstance(supporting_points, list) else [],
                "risk_points": risk_points if isinstance(risk_points, list) else [],
            }

        try:
            next_moves = json.loads(row.get("next_moves_json") or "[]")
        except Exception:
            next_moves = []
        decision_tables_by_job[job_id] = {
            "can_do": _dim("can_do"),
            "can_get": _dim("can_get"),
            "should_want": _dim("should_want"),
            "can_explain": _dim("can_explain"),
            "act_now": _clean_text(row.get("act_now")),
            "confidence_score": row.get("confidence_score"),
            "table_reason": _clean_text(row.get("table_reason")),
            "next_moves": next_moves if isinstance(next_moves, list) else [],
            "decision_table_json": {},
        }

    job_narrative_assessments_by_job: Dict[str, Dict[str, Any]] = {}
    for row in narrative_assessments:
        job_id = _clean_text(row.get("job_id"))
        if not job_id:
            continue
        try:
            misalignment_flags = json.loads(row.get("misalignment_flags_json") or "[]")
        except Exception:
            misalignment_flags = []
        try:
            assessment_json = json.loads(row.get("assessment_json") or "{}")
        except Exception:
            assessment_json = {}
        job_narrative_assessments_by_job[job_id] = {
            "direction_fit_score": row.get("direction_fit_score"),
            "motivation_fit_score": row.get("motivation_fit_score"),
            "pivot_credibility_score": row.get("pivot_credibility_score"),
            "story_strength_score": row.get("story_strength_score"),
            "misalignment_flags": misalignment_flags if isinstance(misalignment_flags, list) else [],
            "assessment_reason": _clean_text(row.get("assessment_reason")),
            "motivation_brief": _clean_text(row.get("motivation_brief")),
            "assessment_json": assessment_json,
        }

    normalized_watchlists: List[Dict[str, Any]] = []
    watchlist_materiality_counts = {"high": 0, "medium": 0, "low": 0}
    for row in watchlists:
        try:
            watch_config_json = json.loads(row.get("watch_config_json") or "{}")
        except Exception:
            watch_config_json = {}
        materiality = _clean_text(row.get("materiality")) or "low"
        if materiality not in watchlist_materiality_counts:
            materiality = "low"
        watchlist_materiality_counts[materiality] += 1
        normalized_watchlists.append(
            {
                "watchlist_id": _clean_text(row.get("watchlist_id")),
                "candidate_id": _clean_text(row.get("candidate_id")),
                "watch_type": _clean_text(row.get("watch_type")),
                "watch_key": _clean_text(row.get("watch_key")),
                "watch_label": _clean_text(row.get("watch_label")),
                "watch_config_json": watch_config_json,
                "is_active": bool(row.get("is_active")),
                "materiality": materiality,
            }
        )

    change_events_by_job: Dict[str, List[Dict[str, Any]]] = {}
    high_materiality_change_events = 0
    for row in change_events:
        try:
            change_json = json.loads(row.get("change_json") or "{}")
        except Exception:
            change_json = {}
        normalized = {
            "change_event_id": _clean_text(row.get("change_event_id")),
            "candidate_id": _clean_text(row.get("candidate_id")),
            "watchlist_id": _clean_text(row.get("watchlist_id")),
            "job_id": _clean_text(row.get("job_id")),
            "change_type": _clean_text(row.get("change_type")),
            "change_summary": _clean_text(row.get("change_summary")),
            "change_json": change_json,
            "materiality": _clean_text(row.get("materiality")),
            "detected_at": _clean_text(row.get("detected_at")),
            "reviewed_at": _clean_text(row.get("reviewed_at")),
        }
        if normalized["materiality"] == "high":
            high_materiality_change_events += 1
        change_events_by_job.setdefault(normalized["job_id"], []).append(normalized)

    state_available = any(
        (
            claims_by_job,
            signals_by_job,
            selection_assessments_by_job,
            decision_tables_by_job,
            normalized_watchlists,
            change_events,
            job_narrative_assessments_by_job,
        )
    )

    return {
        "claims_by_job": claims_by_job,
        "signals_by_job": signals_by_job,
        "selection_assessments_by_job": selection_assessments_by_job,
        "decision_tables_by_job": decision_tables_by_job,
        "job_narrative_assessments_by_job": job_narrative_assessments_by_job,
        "watchlists": normalized_watchlists,
        "change_events_by_job": change_events_by_job,
        "watchlist_count": len(normalized_watchlists),
        "watchlist_count_by_materiality": watchlist_materiality_counts,
        "change_event_count": len(change_events),
        "high_materiality_change_events": high_materiality_change_events,
        "state_available": state_available,
    }


def _watchlist_matches_job(watch: Dict[str, Any], row: Dict[str, Any]) -> bool:
    watch_type = _clean_text(watch.get("watch_type"))
    watch_key = _clean_text(watch.get("watch_key"))
    watch_config = watch.get("watch_config_json")
    if not isinstance(watch_config, dict):
        watch_config = {}

    job_id = _clean_text(row.get("job_id"))
    employer = _clean_text(row.get("employer"))
    employer_slug = _slug(employer)
    source_host = ""
    source_url = _clean_text(row.get("source_url") or row.get("application_url"))
    if source_url:
        try:
            source_host = (urlparse(source_url).hostname or "").lower()
        except Exception:
            source_host = ""
    text_blob = " ".join(
        part for part in (
            _clean_text(row.get("title")),
            _clean_text(row.get("sector")),
            _clean_text(row.get("work_city")),
            _clean_text(row.get("work_county")),
            _clean_text(row.get("description_snip")),
            _clean_text(row.get("recommendation_reason")),
        ) if part
    ).lower()

    if watch_type == "job":
        return watch_key == job_id or _clean_text(watch_config.get("job_id")) == job_id
    if watch_type == "employer":
        config_employer = _clean_text(watch_config.get("employer"))
        return watch_key == employer_slug or config_employer.lower() == employer.lower()
    if watch_type == "source_feed":
        return bool(source_host and watch_key.lower() == source_host)
    if watch_type == "role_family":
        return watch_key.replace("_", " ").lower() in text_blob
    if watch_type == "search_pattern":
        role_family = _clean_text(watch_config.get("role_family")).replace("_", " ").lower()
        location_or_domain = _clean_text(watch_config.get("location_or_domain")).lower()
        role_match = not role_family or role_family in text_blob
        scope_match = not location_or_domain or location_or_domain in text_blob
        return role_match and scope_match
    return False


def _watchlists_for_job(watchlists: List[Dict[str, Any]], row: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [watch for watch in watchlists if _watchlist_matches_job(watch, row)]


def _load_operational_db_counts(
    db_path: Path,
    candidate_id: str,
) -> Dict[str, Any]:
    if not db_path.exists():
        return {
            "catalog_jobs": 0,
            "source_records": 0,
            "pipeline_runs": 0,
            "suggestion_total": 0,
            "suggestion_platform_counts": {},
            "suggestion_status_counts": {},
        }

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        catalog_jobs = int(conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])
        source_records = int(conn.execute("SELECT COUNT(*) FROM job_source_records").fetchone()[0])
        pipeline_runs = int(
            conn.execute(
                "SELECT COUNT(*) FROM pipeline_runs WHERE candidate_id = ?",
                [candidate_id],
            ).fetchone()[0]
        )
        suggestion_platform_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT platform, COUNT(*) AS count
                FROM suggestion_leads
                WHERE candidate_id = ?
                GROUP BY platform
                ORDER BY count DESC, platform ASC
                """,
                [candidate_id],
            )
        ]
        suggestion_status_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM suggestion_leads
                WHERE candidate_id = ?
                GROUP BY status
                ORDER BY count DESC, status ASC
                """,
                [candidate_id],
            )
        ]
        conn.close()
    except Exception:
        return {
            "catalog_jobs": 0,
            "source_records": 0,
            "pipeline_runs": 0,
            "suggestion_total": 0,
            "suggestion_platform_counts": {},
            "suggestion_status_counts": {},
        }

    suggestion_platform_counts = {
        str(row.get("platform") or "").strip(): int(row.get("count") or 0)
        for row in suggestion_platform_rows
        if str(row.get("platform") or "").strip()
    }
    suggestion_status_counts = {
        str(row.get("status") or "").strip(): int(row.get("count") or 0)
        for row in suggestion_status_rows
        if str(row.get("status") or "").strip()
    }

    return {
        "catalog_jobs": catalog_jobs,
        "source_records": source_records,
        "pipeline_runs": pipeline_runs,
        "suggestion_total": sum(suggestion_status_counts.values()),
        "suggestion_platform_counts": suggestion_platform_counts,
        "suggestion_status_counts": suggestion_status_counts,
    }


def build_payload(
    out_dir: Path,
    state_path: Optional[Path] = None,
    primary_db_path_: Optional[Path] = None,
    candidate_id: str = _DEFAULT_CANDIDATE_ID,
    *,
    config_path: Path = _CONFIG_PATH,
) -> Dict[str, Any]:
    app_state = _load_app_state_merged(
        state_path=state_path,
        db_path=primary_db_path_ or _PRIMARY_DB_PATH,
        candidate_id=candidate_id,
    )
    generated_docs = _load_generated_documents_from_db(primary_db_path_ or _PRIMARY_DB_PATH, candidate_id)
    feedback_events = _load_feedback_events_from_db(primary_db_path_ or _PRIMARY_DB_PATH, candidate_id)
    calibration_settings = _load_calibration_settings_from_db(primary_db_path_ or _PRIMARY_DB_PATH, candidate_id)
    thresholds = _load_thresholds(config_path)
    jobs_raw, events = _load_jobs_and_events_from_primary_db(primary_db_path_ or _PRIMARY_DB_PATH, candidate_id)
    persisted_state = _load_promoted_decision_state_from_db(primary_db_path_ or _PRIMARY_DB_PATH, candidate_id)
    db_counts = _load_operational_db_counts(primary_db_path_ or _PRIMARY_DB_PATH, candidate_id)

    events_by_job: Dict[str, List[Dict[str, Any]]] = {}
    for event in events:
        job_id = str(event.get("job_id") or "").strip()
        if not job_id:
            continue
        events_by_job.setdefault(job_id, []).append(event)

    application_entries = [{"job_id": job_id, **entry} for job_id, entry in app_state.items()]
    calibration_summary = derive_candidate_calibration_summary(
        feedback_events=feedback_events,
        application_state=application_entries,
        known_jobs=jobs_raw,
        calibration_settings=calibration_settings,
    )
    candidate_profile = load_candidate_profile_json(candidate_id=candidate_id, db_path=primary_db_path_ or _PRIMARY_DB_PATH)

    jobs = []
    for row in jobs_raw:
        if not str(row.get("final_decision") or "").strip() and row.get("fit_score") is not None and thresholds:
            row["final_decision"] = _reclassify(row.get("fit_score"), row.get("pivot_score"), thresholds)

        is_actionable = row.get("final_decision") in _ACTIONABLE
        if is_actionable:
            row["detail"] = _extract_detail(row)
            _enrich_from_input(row, out_dir)
        else:
            for col in _DETAIL_COLS:
                row.pop(col, None)
            row["detail"] = None

        for key in ("raw_match_json", "raw_pivot_json", "raw_moderator_json"):
            row.pop(key, None)

        app_entry = app_state.get(row.get("job_id", ""), {})
        row["app_status"] = app_entry.get("status", "")
        row["app_stages"] = json.dumps(app_entry.get("stages", []), ensure_ascii=False)
        row["app_outcome"] = app_entry.get("outcome") or ""
        row["app_updated_at"] = app_entry.get("updated_at", "")
        row["app_source"] = app_entry.get("source", "")
        row["app_notes"] = app_entry.get("notes", "")
        row["generated_documents"] = generated_docs.get(row.get("job_id", ""), [])
        row["no_score_reason"] = derive_no_score_reason(row)
        row["no_score_reason_label"] = format_no_score_reason(row["no_score_reason"])

        job_id = str(row.get("job_id") or "").strip()
        decision_context = None
        if not (
            persisted_state["claims_by_job"].get(job_id)
            and persisted_state["signals_by_job"].get(job_id)
            and persisted_state["selection_assessments_by_job"].get(job_id)
            and persisted_state["decision_tables_by_job"].get(job_id)
        ):
            decision_context = build_decision_context(row, candidate_profile=candidate_profile)

        monitoring_context = None
        if not persisted_state["state_available"]:
            monitoring_context = build_monitoring_context(
                row,
                candidate_id=candidate_id,
                decision_context=decision_context or build_decision_context(row, candidate_profile=candidate_profile),
                run_history=events_by_job.get(job_id, []),
                app_entry=app_entry,
            )
        calibration_context = build_candidate_calibration_context(
            row,
            feedback_events=feedback_events,
            application_state=application_entries,
            known_jobs=jobs_raw,
            calibration_settings=calibration_settings,
        )

        row["job_claims"] = persisted_state["claims_by_job"].get(job_id) or [
            claim.model_dump(mode="json") for claim in (decision_context.job_claims if decision_context else [])
        ]
        row["selection_signals"] = persisted_state["signals_by_job"].get(job_id) or [
            signal.model_dump(mode="json") for signal in (decision_context.selection_signals if decision_context else [])
        ]
        row["selection_assessment"] = persisted_state["selection_assessments_by_job"].get(job_id) or (
            decision_context.selection_assessment.model_dump(mode="json") if decision_context else {}
        )
        row["decision_table"] = persisted_state["decision_tables_by_job"].get(job_id) or (
            decision_context.decision_table.model_dump(mode="json") if decision_context else {}
        )
        row["watchlists"] = (
            _watchlists_for_job(persisted_state["watchlists"], row)
            if persisted_state["state_available"]
            else [watch.model_dump(mode="json") for watch in monitoring_context.watchlists]
        )
        row["change_events"] = (
            persisted_state["change_events_by_job"].get(job_id, [])
            if persisted_state["state_available"]
            else [event.model_dump(mode="json") for event in monitoring_context.change_events]
        )
        if persisted_state["job_narrative_assessments_by_job"].get(job_id):
            row["job_narrative_assessment"] = persisted_state["job_narrative_assessments_by_job"][job_id]
        row["job_calibration_assessment"] = calibration_context.job_calibration_assessment.model_dump(mode="json")

        jobs.append(row)

    app_status_counts: Dict[str, int] = {}
    for entry in app_state.values():
        status = str(entry.get("status") or "").strip()
        if not status:
            continue
        app_status_counts[status] = app_status_counts.get(status, 0) + 1

    actionable_jobs = sum(1 for row in jobs if row.get("final_decision") in _ACTIONABLE)
    jobs_with_apply_url = sum(
        1 for row in jobs if row.get("final_decision") in _ACTIONABLE and (row.get("application_url") or row.get("source_url"))
    )
    if persisted_state["state_available"]:
        watchlist_count = persisted_state["watchlist_count"]
        watchlist_count_by_materiality = persisted_state.get(
            "watchlist_count_by_materiality", {"high": 0, "medium": 0, "low": 0}
        )
        change_event_count = persisted_state["change_event_count"]
        high_materiality_change_events = persisted_state["high_materiality_change_events"]
    else:
        watchlist_count = sum(len(row.get("watchlists", [])) for row in jobs)
        watchlist_count_by_materiality = {"high": 0, "medium": 0, "low": 0}
        for row in jobs:
            for watch in row.get("watchlists", []):
                materiality = str(watch.get("materiality") or "").strip() or "low"
                if materiality not in watchlist_count_by_materiality:
                    materiality = "low"
                watchlist_count_by_materiality[materiality] += 1
        change_event_count = sum(len(row.get("change_events", [])) for row in jobs)
        high_materiality_change_events = sum(
            1
            for row in jobs
            for event in row.get("change_events", [])
            if str(event.get("materiality") or "").strip() == "high"
        )

    return {
        "jobs": jobs,
        "events": events,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "evaluated_jobs": len(jobs),
            "actionable_jobs": actionable_jobs,
            "jobs_with_apply_url": jobs_with_apply_url,
            "tracked_applications": sum(app_status_counts.values()),
            "application_status_counts": app_status_counts,
            "watchlist_count": watchlist_count,
            "watchlist_count_by_materiality": watchlist_count_by_materiality,
            "change_event_count": change_event_count,
            "high_materiality_change_events": high_materiality_change_events,
            "calibration_summary": calibration_summary.model_dump(mode="json"),
            **db_counts,
        },
    }


def export(
    out_dir: Path,
    template_path: Path,
    out_path: Path,
    *,
    state_path: Optional[Path] = None,
    primary_db_path_: Optional[Path] = None,
    candidate_id: str = _DEFAULT_CANDIDATE_ID,
    config_path: Path = _CONFIG_PATH,
) -> None:
    payload = build_payload(
        out_dir,
        state_path=state_path,
        primary_db_path_=primary_db_path_,
        candidate_id=candidate_id,
        config_path=config_path,
    )

    template = template_path.read_text(encoding="utf-8")
    data_json = json.dumps(payload, ensure_ascii=False, default=str)
    if _DATA_PLACEHOLDER not in template:
        raise RuntimeError(
            f"Template {template_path} is missing the data placeholder: {_DATA_PLACEHOLDER}"
        )

    html = template.replace(_DATA_PLACEHOLDER, data_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    n_action = sum(1 for job in payload["jobs"] if job.get("final_decision") in _ACTIONABLE)
    n_urls = sum(
        1
        for job in payload["jobs"]
        if job.get("final_decision") in _ACTIONABLE and (job.get("application_url") or job.get("source_url"))
    )
    n_tracked = sum(1 for job in payload["jobs"] if job.get("app_status"))
    print(f"Dashboard exported: {out_path}")
    print(f"  {len(payload['jobs'])} jobs ({n_action} actionable, {n_urls} with URLs), {len(payload['events'])} events")
    if n_tracked:
        print(f"  {n_tracked} jobs with application status tracked")


__all__ = [
    "build_payload",
    "export",
    "_load_app_state_merged",
]
