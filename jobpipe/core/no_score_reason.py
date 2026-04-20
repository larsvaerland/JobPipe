from __future__ import annotations

from typing import Any, Mapping


_LABELS = {
    "geo_filtered_before_scoring": "filtered by location rules before scoring",
    "hard_no_title_before_scoring": "filtered by hard title rules before scoring",
    "semantic_filter_before_scoring": "filtered by semantic screening before scoring",
    "triage_skip_before_scoring": "skipped at triage before fit and pivot scoring",
    "score_not_available": "score details were not preserved for this evaluation",
}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def derive_no_score_reason(row: Mapping[str, Any]) -> str:
    fit_score = row.get("fit_score")
    pivot_score = row.get("pivot_score")
    if fit_score is not None or pivot_score is not None:
        return ""

    skip_reason = _clean_text(row.get("skip_reason"))
    triage_decision = _clean_text(row.get("triage_decision")).upper()

    if skip_reason == "geo":
        return "geo_filtered_before_scoring"
    if skip_reason == "hard_no":
        return "hard_no_title_before_scoring"
    if skip_reason == "semantic":
        return "semantic_filter_before_scoring"
    if skip_reason == "triage_llm" or triage_decision == "SKIP":
        return "triage_skip_before_scoring"
    return "score_not_available"


def format_no_score_reason(reason: str) -> str:
    key = _clean_text(reason)
    if not key:
        return ""
    return _LABELS.get(key, key.replace("_", " "))
