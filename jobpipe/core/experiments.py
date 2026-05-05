from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from jobpipe.core.schema import HardGates, TriageFeatures
from jobpipe.core.triage_v3 import (
    REVIEW_THRESHOLD,
    SHORTLIST_THRESHOLD,
    TRIAGE_FEATURE_WEIGHTS,
    aggregate_triage_decision,
    resolve_triage_ambiguity,
)


EXPERIMENT_RUN_VERSION = "jobpipe.experiment-run.v1"
SAFE_EXPERIMENT_RULES = [
    "shadow_only",
    "no_live_shortlist_suppression",
    "compare_against_baseline",
]

TRIAGE_LABEL_RANK = {"discard": 0, "review": 1, "shortlist": 2}


def utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _shadow_run_sort_key(run: Dict[str, Any]) -> tuple[str, str]:
    return (str(run.get("created_at") or ""), str(run.get("experiment_id") or ""))


def load_experiment_runs(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return raw if isinstance(raw, list) else []


def persist_experiment_runs(path: Path, runs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = [run for run in runs if isinstance(run, dict)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def append_experiment_run(path: Path, run: Dict[str, Any]) -> List[Dict[str, Any]]:
    runs = load_experiment_runs(path)
    runs.insert(0, run)
    return persist_experiment_runs(path, runs)


def persist_experiment_detail(path: Path, run: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")


def load_experiment_detail(path: Path | str | None) -> Dict[str, Any]:
    if not path:
        return {}
    try:
        candidate = Path(path)
        raw = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def load_latest_shadow_review_queue(
    index_path: Path,
    *,
    max_items: int = 10,
) -> Dict[str, Any]:
    runs = load_experiment_runs(index_path)
    completed_shadow_runs = sorted(
        [
            run
            for run in runs
            if isinstance(run, dict)
            and str(run.get("kind") or "").startswith("shadow_")
            and str(run.get("status") or "") == "completed"
        ],
        key=_shadow_run_sort_key,
        reverse=True,
    )
    latest: Optional[Dict[str, Any]] = completed_shadow_runs[0] if completed_shadow_runs else None
    if not latest:
        return {
            "schema_version": "jobpipe.experiments-dashboard.v1",
            "latest_shadow_eval": {},
            "review_queue": [],
        }

    latest_summary = {
        "experiment_id": str(latest.get("experiment_id") or ""),
        "kind": str(latest.get("kind") or ""),
        "created_at": str(latest.get("created_at") or ""),
        "sample_size": int(latest.get("sample_size") or 0),
        "changed_count": int(latest.get("changed_count") or 0),
        "upgrade_count": int(latest.get("upgrade_count") or 0),
        "downgrade_count": int(latest.get("downgrade_count") or 0),
        "review_sample_count": int(latest.get("review_sample_count") or 0),
        "summary": str(latest.get("summary") or ""),
    }
    detail = load_experiment_detail(latest.get("detail_path"))
    review_queue = detail.get("review_sample", []) if isinstance(detail, dict) else []
    if not isinstance(review_queue, list):
        review_queue = []
    review_queue = [item for item in review_queue if isinstance(item, dict)]
    if max_items > 0:
        review_queue = review_queue[:max_items]
    return {
        "schema_version": "jobpipe.experiments-dashboard.v1",
        "latest_shadow_eval": latest_summary,
        "review_queue": review_queue,
    }


def load_recent_shadow_experiment_summaries(
    index_path: Path,
    *,
    max_runs: int = 5,
) -> List[Dict[str, Any]]:
    runs = load_experiment_runs(index_path)
    summaries: List[Dict[str, Any]] = []
    completed_shadow_runs = sorted(
        [
            run
            for run in runs
            if isinstance(run, dict)
            and str(run.get("kind") or "").startswith("shadow_")
            and str(run.get("status") or "") == "completed"
        ],
        key=_shadow_run_sort_key,
        reverse=True,
    )
    for run in completed_shadow_runs:
        summaries.append(
            {
                "experiment_id": str(run.get("experiment_id") or ""),
                "kind": str(run.get("kind") or ""),
                "created_at": str(run.get("created_at") or ""),
                "sample_size": int(run.get("sample_size") or 0),
                "changed_count": int(run.get("changed_count") or 0),
                "upgrade_count": int(run.get("upgrade_count") or 0),
                "downgrade_count": int(run.get("downgrade_count") or 0),
                "review_sample_count": int(run.get("review_sample_count") or 0),
                "summary": str(run.get("summary") or ""),
                "baseline": dict(run.get("baseline") or {}) if isinstance(run.get("baseline"), dict) else {},
                "candidate": dict(run.get("candidate") or {}) if isinstance(run.get("candidate"), dict) else {},
                "detail_path": str(run.get("detail_path") or ""),
            }
        )
        if max_runs > 0 and len(summaries) >= max_runs:
            break
    return summaries


def build_threshold_shadow_run(
    *,
    experiment_id: str | None = None,
    review_threshold: float,
    shortlist_threshold: float,
    samples: List[Dict[str, Any]],
    review_sample_max: int = 10,
    feature_weights: Optional[Dict[str, float]] = None,
    candidate_name: str = "triage_v3_threshold_variant",
) -> Dict[str, Any]:
    upgrade_count = sum(1 for sample in samples if sample.get("direction") == "upgrade")
    downgrade_count = sum(1 for sample in samples if sample.get("direction") == "downgrade")
    changed_count = sum(1 for sample in samples if sample.get("changed"))
    review_sample = build_false_negative_review_sample(
        samples,
        review_threshold=review_threshold,
        max_items=review_sample_max,
    )
    normalized_weights = (
        {str(name): float(value) for name, value in (feature_weights or {}).items()}
        if feature_weights
        else {}
    )
    kind = "shadow_feature_weight_eval" if normalized_weights else "shadow_threshold_eval"
    return {
        "schema_version": EXPERIMENT_RUN_VERSION,
        "experiment_id": experiment_id or f"shadow_triage_{uuid4().hex[:12]}",
        "kind": kind,
        "status": "completed",
        "safe_rules": list(SAFE_EXPERIMENT_RULES),
        "baseline": {
            "name": "triage_v3_default",
            "review_threshold": REVIEW_THRESHOLD,
            "shortlist_threshold": SHORTLIST_THRESHOLD,
            "feature_weights": dict(TRIAGE_FEATURE_WEIGHTS),
        },
        "candidate": {
            "name": candidate_name,
            "review_threshold": float(review_threshold),
            "shortlist_threshold": float(shortlist_threshold),
            "feature_weights": normalized_weights,
        },
        "sample_size": len(samples),
        "changed_count": changed_count,
        "upgrade_count": upgrade_count,
        "downgrade_count": downgrade_count,
        "review_sample_count": len(review_sample),
        "review_sample_max": int(review_sample_max),
        "created_at": utc_now_z(),
        "summary": (
            f"Shadow triage eval over {len(samples)} jobs; "
            f"{changed_count} label changes, {upgrade_count} upgrades, {downgrade_count} downgrades."
        ),
        "samples": samples,
        "review_sample": review_sample,
    }


def build_false_negative_review_sample(
    samples: Iterable[Dict[str, Any]],
    *,
    review_threshold: float,
    max_items: int = 10,
) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for sample in samples:
        baseline_label = str(sample.get("baseline_label") or "discard")
        candidate_label = str(sample.get("candidate_label") or baseline_label)
        baseline_rank = TRIAGE_LABEL_RANK.get(baseline_label, 0)
        candidate_rank = TRIAGE_LABEL_RANK.get(candidate_label, baseline_rank)
        baseline_score = float(sample.get("baseline_weighted_score") or 0.0)
        candidate_score = float(sample.get("candidate_weighted_score") or baseline_score)
        baseline_ambiguity = bool(sample.get("baseline_needs_ambiguity"))
        candidate_ambiguity = bool(sample.get("candidate_needs_ambiguity"))
        changed = bool(sample.get("changed"))
        direction = str(sample.get("direction") or "unchanged")

        review_reason = ""
        review_priority = 0

        if direction == "upgrade" and baseline_rank == 0 and candidate_rank >= 1:
            review_reason = "promoted_from_discard"
            review_priority = 220 + (candidate_rank * 20)
        elif direction == "upgrade":
            review_reason = "promoted_in_shadow"
            review_priority = 160 + (candidate_rank * 20) - (baseline_rank * 5)
        elif (
            baseline_label == "discard"
            and baseline_ambiguity
            and baseline_score >= max(0.0, review_threshold - 3.0)
        ):
            review_reason = "borderline_baseline_discard"
            review_priority = 100 - int(abs(review_threshold - baseline_score) * 10)
        else:
            continue

        if baseline_ambiguity or candidate_ambiguity:
            review_priority += 10
        if changed:
            review_priority += 5

        candidate = dict(sample)
        candidate["review_reason"] = review_reason
        candidate["review_priority"] = review_priority
        candidate["score_delta"] = round(candidate_score - baseline_score, 1)
        ranked.append(candidate)

    ranked.sort(
        key=lambda sample: (
            -int(sample.get("review_priority", 0)),
            -float(sample.get("candidate_weighted_score") or 0.0),
            str(sample.get("job_id") or ""),
        )
    )
    if max_items <= 0:
        return ranked
    return ranked[:max_items]


def compare_threshold_shadow_sample(
    *,
    run_id: str,
    job_id: str,
    features: TriageFeatures,
    hard_gates: HardGates,
    baseline_label: str = "",
    baseline_weighted_score: float | None = None,
    review_threshold: float,
    shortlist_threshold: float,
    feature_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    baseline_first_pass = aggregate_triage_decision(features, hard_gates)
    baseline_final = resolve_triage_ambiguity(features, baseline_first_pass).final_decision
    candidate_first_pass = aggregate_triage_decision(
        features,
        hard_gates,
        feature_weights=feature_weights,
        review_threshold=review_threshold,
        shortlist_threshold=shortlist_threshold,
    )
    candidate_final = resolve_triage_ambiguity(features, candidate_first_pass).final_decision

    effective_baseline_label = baseline_label or baseline_final.label
    effective_baseline_score = (
        float(baseline_weighted_score)
        if baseline_weighted_score is not None
        else float(baseline_first_pass.weighted_score)
    )
    changed = effective_baseline_label != candidate_final.label

    baseline_rank = TRIAGE_LABEL_RANK.get(effective_baseline_label, 0)
    candidate_rank = TRIAGE_LABEL_RANK.get(candidate_final.label, 0)
    if candidate_rank > baseline_rank:
        direction = "upgrade"
    elif candidate_rank < baseline_rank:
        direction = "downgrade"
    else:
        direction = "unchanged"

    return {
        "run_id": run_id,
        "job_id": job_id,
        "baseline_label": effective_baseline_label,
        "baseline_weighted_score": effective_baseline_score,
        "candidate_label": candidate_final.label,
        "candidate_weighted_score": float(candidate_first_pass.weighted_score),
        "changed": changed,
        "direction": direction,
        "baseline_needs_ambiguity": baseline_first_pass.needs_ambiguity_pass,
        "candidate_needs_ambiguity": candidate_first_pass.needs_ambiguity_pass,
    }
