from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

EXPERIMENT_REVIEW_STATE_VERSION = "jobpipe.experiment-review.v1"
ALLOWED_EXPERIMENT_VERDICTS = {
    "correct_miss",
    "not_useful",
    "interesting_but_no",
    "promote_rule_candidate",
}
ALLOWED_VARIANT_VERDICTS = {
    "worth_promoting",
    "needs_more_review",
    "reject_variant",
}
ALLOWED_PROMOTION_VERDICTS = {
    "accepted_for_promotion",
    "deferred_promotion",
    "rejected_promotion",
}


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _empty_state() -> Dict[str, Any]:
    return {
        "schema_version": EXPERIMENT_REVIEW_STATE_VERSION,
        "updated_at": "",
        "reviews": {},
        "variant_reviews": {},
        "promotion_reviews": {},
    }


def _review_key(experiment_id: str, job_id: str) -> str:
    return f"{experiment_id}::{job_id}"


def _variant_review_key(experiment_id: str) -> str:
    return str(experiment_id or "").strip()


def _promotion_review_key(experiment_id: str) -> str:
    return str(experiment_id or "").strip()


def load_experiment_review_state(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_state()
    if not isinstance(raw, dict):
        return _empty_state()
    reviews = raw.get("reviews", {})
    if not isinstance(reviews, dict):
        reviews = {}
    variant_reviews = raw.get("variant_reviews", {})
    if not isinstance(variant_reviews, dict):
        variant_reviews = {}
    promotion_reviews = raw.get("promotion_reviews", {})
    if not isinstance(promotion_reviews, dict):
        promotion_reviews = {}
    return {
        "schema_version": str(raw.get("schema_version") or EXPERIMENT_REVIEW_STATE_VERSION),
        "updated_at": str(raw.get("updated_at") or ""),
        "reviews": {str(key): value for key, value in reviews.items() if isinstance(value, dict)},
        "variant_reviews": {
            str(key): value
            for key, value in variant_reviews.items()
            if isinstance(value, dict)
        },
        "promotion_reviews": {
            str(key): value
            for key, value in promotion_reviews.items()
            if isinstance(value, dict)
        },
    }


def persist_experiment_review_state(path: Path, state: Dict[str, Any]) -> Dict[str, Any]:
    clean = {
        "schema_version": EXPERIMENT_REVIEW_STATE_VERSION,
        "updated_at": _utc_now_z(),
        "reviews": {
            str(key): value
            for key, value in dict(state.get("reviews", {})).items()
            if isinstance(value, dict)
        },
        "variant_reviews": {
            str(key): value
            for key, value in dict(state.get("variant_reviews", {})).items()
            if isinstance(value, dict)
        },
        "promotion_reviews": {
            str(key): value
            for key, value in dict(state.get("promotion_reviews", {})).items()
            if isinstance(value, dict)
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return clean


def upsert_experiment_review(
    path: Path,
    *,
    experiment_id: str,
    job_id: str,
    verdict: str,
    note: str = "",
    run_id: str = "",
    review_reason: str = "",
    review_priority: int | None = None,
) -> Dict[str, Any]:
    state = load_experiment_review_state(path)
    reviews = dict(state.get("reviews", {}))
    key = _review_key(experiment_id, job_id)
    verdict_clean = str(verdict or "").strip()
    note_clean = str(note or "").strip()

    if not verdict_clean:
        reviews.pop(key, None)
        state["reviews"] = reviews
        persist_experiment_review_state(path, state)
        return {}

    if verdict_clean not in ALLOWED_EXPERIMENT_VERDICTS:
        raise ValueError(f"Unsupported experiment verdict: {verdict_clean}")

    entry = {
        "experiment_id": str(experiment_id or "").strip(),
        "job_id": str(job_id or "").strip(),
        "run_id": str(run_id or "").strip(),
        "verdict": verdict_clean,
        "note": note_clean,
        "review_reason": str(review_reason or "").strip(),
        "review_priority": int(review_priority or 0),
        "updated_at": _utc_now_z(),
    }
    reviews[key] = entry
    state["reviews"] = reviews
    persist_experiment_review_state(path, state)
    return entry


def get_experiment_review(
    state: Dict[str, Any],
    *,
    experiment_id: str,
    job_id: str,
) -> Dict[str, Any]:
    reviews = state.get("reviews", {})
    if not isinstance(reviews, dict):
        return {}
    entry = reviews.get(_review_key(experiment_id, job_id), {})
    return entry if isinstance(entry, dict) else {}


def upsert_experiment_variant_review(
    path: Path,
    *,
    experiment_id: str,
    verdict: str,
    note: str = "",
    candidate_name: str = "",
    kind: str = "",
) -> Dict[str, Any]:
    state = load_experiment_review_state(path)
    variant_reviews = dict(state.get("variant_reviews", {}))
    key = _variant_review_key(experiment_id)
    verdict_clean = str(verdict or "").strip()
    note_clean = str(note or "").strip()

    if not key:
        raise ValueError("experiment_id required")

    if not verdict_clean:
        variant_reviews.pop(key, None)
        state["variant_reviews"] = variant_reviews
        persist_experiment_review_state(path, state)
        return {}

    if verdict_clean not in ALLOWED_VARIANT_VERDICTS:
        raise ValueError(f"Unsupported experiment variant verdict: {verdict_clean}")

    entry = {
        "experiment_id": key,
        "verdict": verdict_clean,
        "note": note_clean,
        "candidate_name": str(candidate_name or "").strip(),
        "kind": str(kind or "").strip(),
        "updated_at": _utc_now_z(),
    }
    variant_reviews[key] = entry
    state["variant_reviews"] = variant_reviews
    persist_experiment_review_state(path, state)
    return entry


def get_experiment_variant_review(
    state: Dict[str, Any],
    *,
    experiment_id: str,
) -> Dict[str, Any]:
    variant_reviews = state.get("variant_reviews", {})
    if not isinstance(variant_reviews, dict):
        return {}
    entry = variant_reviews.get(_variant_review_key(experiment_id), {})
    return entry if isinstance(entry, dict) else {}


def upsert_experiment_promotion_review(
    path: Path,
    *,
    experiment_id: str,
    verdict: str,
    note: str = "",
    candidate_name: str = "",
    kind: str = "",
) -> Dict[str, Any]:
    state = load_experiment_review_state(path)
    promotion_reviews = dict(state.get("promotion_reviews", {}))
    key = _promotion_review_key(experiment_id)
    verdict_clean = str(verdict or "").strip()
    note_clean = str(note or "").strip()

    if not key:
        raise ValueError("experiment_id required")

    if not verdict_clean:
        promotion_reviews.pop(key, None)
        state["promotion_reviews"] = promotion_reviews
        persist_experiment_review_state(path, state)
        return {}

    if verdict_clean not in ALLOWED_PROMOTION_VERDICTS:
        raise ValueError(f"Unsupported experiment promotion verdict: {verdict_clean}")

    entry = {
        "experiment_id": key,
        "verdict": verdict_clean,
        "note": note_clean,
        "candidate_name": str(candidate_name or "").strip(),
        "kind": str(kind or "").strip(),
        "updated_at": _utc_now_z(),
    }
    promotion_reviews[key] = entry
    state["promotion_reviews"] = promotion_reviews
    persist_experiment_review_state(path, state)
    return entry


def get_experiment_promotion_review(
    state: Dict[str, Any],
    *,
    experiment_id: str,
) -> Dict[str, Any]:
    promotion_reviews = state.get("promotion_reviews", {})
    if not isinstance(promotion_reviews, dict):
        return {}
    entry = promotion_reviews.get(_promotion_review_key(experiment_id), {})
    return entry if isinstance(entry, dict) else {}


def build_experiment_review_summary(items: List[Dict[str, Any]]) -> Dict[str, int]:
    summary = {
        "reviewed": 0,
        "pending": 0,
        "correct_miss": 0,
        "not_useful": 0,
        "interesting_but_no": 0,
        "promote_rule_candidate": 0,
    }
    for item in items:
        adjudication = item.get("adjudication", {})
        if not isinstance(adjudication, dict) or not adjudication.get("verdict"):
            summary["pending"] += 1
            continue
        summary["reviewed"] += 1
        verdict = str(adjudication.get("verdict") or "")
        if verdict in summary:
            summary[verdict] += 1
    return summary


def build_experiment_calibration_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    reviewed_items: List[Dict[str, Any]] = []
    positive_reason_counts: Dict[str, int] = {}
    negative_reason_counts: Dict[str, int] = {}

    for item in items:
        adjudication = item.get("adjudication", {})
        if not isinstance(adjudication, dict):
            continue
        verdict = str(adjudication.get("verdict") or "").strip()
        if not verdict:
            continue
        reviewed_items.append(item)
        review_reason = str(item.get("review_reason") or "").strip()
        if verdict in {"correct_miss", "promote_rule_candidate"} and review_reason:
            positive_reason_counts[review_reason] = positive_reason_counts.get(review_reason, 0) + 1
        elif verdict == "not_useful" and review_reason:
            negative_reason_counts[review_reason] = negative_reason_counts.get(review_reason, 0) + 1

    reviewed = len(reviewed_items)
    positive = sum(
        1
        for item in reviewed_items
        if str((item.get("adjudication") or {}).get("verdict") or "") in {"correct_miss", "promote_rule_candidate"}
    )
    rejected = sum(
        1
        for item in reviewed_items
        if str((item.get("adjudication") or {}).get("verdict") or "") == "not_useful"
    )
    interesting = sum(
        1
        for item in reviewed_items
        if str((item.get("adjudication") or {}).get("verdict") or "") == "interesting_but_no"
    )

    def _top_reasons(counts: Dict[str, int]) -> List[Dict[str, Any]]:
        return [
            {"reason": reason, "count": count}
            for reason, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:3]
        ]

    return {
        "schema_version": "jobpipe.experiment-calibration.v1",
        "reviewed": reviewed,
        "positive": positive,
        "rejected": rejected,
        "interesting_but_no": interesting,
        "useful_signal_rate": round((positive / reviewed) * 100, 1) if reviewed else 0.0,
        "top_positive_reasons": _top_reasons(positive_reason_counts),
        "top_negative_reasons": _top_reasons(negative_reason_counts),
    }


def build_advantage_signal_calibration_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    reviewed_items: List[Dict[str, Any]] = []
    positive_hook_counts: Dict[str, int] = {}
    negative_hook_counts: Dict[str, int] = {}

    for item in items:
        adjudication = item.get("adjudication", {})
        if not isinstance(adjudication, dict):
            continue
        verdict = str(adjudication.get("verdict") or "").strip()
        if not verdict:
            continue
        reviewed_items.append(item)
        hook = str(item.get("recruiter_hook") or "").strip()
        if verdict in {"correct_miss", "promote_rule_candidate"} and hook:
            positive_hook_counts[hook] = positive_hook_counts.get(hook, 0) + 1
        elif verdict == "not_useful" and hook:
            negative_hook_counts[hook] = negative_hook_counts.get(hook, 0) + 1

    def _subset_summary(predicate) -> tuple[int, int]:
        subset = [item for item in reviewed_items if predicate(item)]
        positives = sum(
            1
            for item in subset
            if str((item.get("adjudication") or {}).get("verdict") or "") in {"correct_miss", "promote_rule_candidate"}
        )
        return len(subset), positives

    def _score(item: Dict[str, Any]) -> int:
        try:
            return int(item.get("advantageous_match_score") or 0)
        except Exception:
            return 0

    high_reviewed, high_positive = _subset_summary(lambda item: _score(item) >= 70)
    lower_reviewed, lower_positive = _subset_summary(lambda item: 0 < _score(item) < 70)

    def _top_hooks(counts: Dict[str, int]) -> List[Dict[str, Any]]:
        return [
            {"hook": hook, "count": count}
            for hook, count in sorted(counts.items(), key=lambda item: -item[1])[:3]
        ]

    return {
        "schema_version": "jobpipe.advantage-signal-calibration.v1",
        "reviewed": len(reviewed_items),
        "high_advantage_reviewed": high_reviewed,
        "high_advantage_positive": high_positive,
        "high_advantage_useful_rate": round((high_positive / high_reviewed) * 100, 1) if high_reviewed else 0.0,
        "lower_advantage_reviewed": lower_reviewed,
        "lower_advantage_positive": lower_positive,
        "lower_advantage_useful_rate": round((lower_positive / lower_reviewed) * 100, 1) if lower_reviewed else 0.0,
        "top_positive_hooks": _top_hooks(positive_hook_counts),
        "top_negative_hooks": _top_hooks(negative_hook_counts),
    }


def build_advantage_shortlist_quality_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    def _avg_score(item: Dict[str, Any]) -> float:
        try:
            return float(item.get("avg_advantageous_match_score") or 0.0)
        except Exception:
            return 0.0

    reviewed_variants = [
        item
        for item in items
        if int(item.get("reviewed") or 0) > 0 and _avg_score(item) > 0.0
    ]

    def _subset_summary(predicate) -> Dict[str, Any]:
        subset = [item for item in reviewed_variants if predicate(item)]
        worth_promoting = sum(
            1
            for item in subset
            if str((item.get("variant_review") or {}).get("verdict") or "") == "worth_promoting"
        )
        rejected = sum(
            1
            for item in subset
            if str((item.get("variant_review") or {}).get("verdict") or "") == "reject_variant"
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
            "worth_promoting_rate": round((worth_promoting / len(subset)) * 100, 1) if subset else 0.0,
            "rejected": rejected,
            "rejected_rate": round((rejected / len(subset)) * 100, 1) if subset else 0.0,
        }

    high = _subset_summary(lambda item: _avg_score(item) >= 70.0)
    lower = _subset_summary(lambda item: 0.0 < _avg_score(item) < 70.0)
    delta_useful_rate = round(high["avg_useful_signal_rate"] - lower["avg_useful_signal_rate"], 1)
    delta_worth_promoting_rate = round(high["worth_promoting_rate"] - lower["worth_promoting_rate"], 1)

    if not reviewed_variants or high["count"] == 0:
        status = "no_signal"
        confidence = "low"
        summary = "No reviewed shadow variants currently show a strong advantageous-match profile."
        recommended_action = "Keep advantageous-match visible in shadow mode until reviewed variants accumulate."
    elif lower["count"] == 0:
        status = "thin_sample"
        confidence = "low"
        summary = "Only high-advantage reviewed variants are available, so shortlist-quality comparison is still one-sided."
        recommended_action = "Collect at least one reviewed lower-advantage variant before judging shortlist quality."
    elif delta_useful_rate >= 10.0 and delta_worth_promoting_rate >= 0.0:
        status = "improving"
        confidence = "medium" if min(high["count"], lower["count"]) >= 2 else "low"
        summary = "Higher-advantage shadow variants are producing better reviewed shortlist quality than lower-advantage ones."
        recommended_action = "Keep the signal in shadow ordering and promotion review while the sample grows."
    elif delta_useful_rate >= 0.0 or delta_worth_promoting_rate > 0.0:
        status = "mixed"
        confidence = "medium" if len(reviewed_variants) >= 4 else "low"
        summary = "Higher-advantage variants are directionally better, but the shortlist-quality edge is still thin."
        recommended_action = "Continue comparing reviewed variants before promoting the signal any further."
    else:
        status = "not_improving"
        confidence = "medium" if len(reviewed_variants) >= 4 else "low"
        summary = "Higher-advantage shadow variants are not yet producing better reviewed shortlist quality."
        recommended_action = "Treat advantageous-match as descriptive only until shortlist quality improves."

    return {
        "schema_version": "jobpipe.advantage-shortlist-quality.v1",
        "reviewed_variants": len(reviewed_variants),
        "high_advantage_variants": high["count"],
        "high_advantage_avg_useful_rate": high["avg_useful_signal_rate"],
        "high_advantage_worth_promoting": high["worth_promoting"],
        "high_advantage_worth_promoting_rate": high["worth_promoting_rate"],
        "lower_advantage_variants": lower["count"],
        "lower_advantage_avg_useful_rate": lower["avg_useful_signal_rate"],
        "lower_advantage_worth_promoting": lower["worth_promoting"],
        "lower_advantage_worth_promoting_rate": lower["worth_promoting_rate"],
        "quality_delta_useful_rate": delta_useful_rate,
        "quality_delta_worth_promoting_rate": delta_worth_promoting_rate,
        "status": status,
        "confidence": confidence,
        "summary": summary,
        "recommended_action": recommended_action,
    }


def build_experiment_variant_review_summary(items: List[Dict[str, Any]]) -> Dict[str, int]:
    summary = {
        "reviewed": 0,
        "pending": 0,
        "worth_promoting": 0,
        "needs_more_review": 0,
        "reject_variant": 0,
    }
    for item in items:
        variant_review = item.get("variant_review", {})
        if not isinstance(variant_review, dict) or not variant_review.get("verdict"):
            summary["pending"] += 1
            continue
        summary["reviewed"] += 1
        verdict = str(variant_review.get("verdict") or "")
        if verdict in summary:
            summary[verdict] += 1
    return summary


def build_experiment_promotion_review_summary(items: List[Dict[str, Any]]) -> Dict[str, int]:
    summary = {
        "reviewed": 0,
        "pending": 0,
        "accepted_for_promotion": 0,
        "deferred_promotion": 0,
        "rejected_promotion": 0,
    }
    for item in items:
        promotion_review = item.get("promotion_review", {})
        if not isinstance(promotion_review, dict) or not promotion_review.get("verdict"):
            summary["pending"] += 1
            continue
        summary["reviewed"] += 1
        verdict = str(promotion_review.get("verdict") or "")
        if verdict in summary:
            summary[verdict] += 1
    return summary
