from __future__ import annotations

from typing import Any, Iterable, Mapping

from jobpipe.model import (
    JobSyncApplicationCaseProjection,
    JobSyncDecisionBrief,
    JobSyncDocumentRef,
    JobSyncJobSummary,
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _list_of_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return []


def _location_label(row: Mapping[str, Any]) -> str:
    parts = [
        _clean(row.get("work_city")),
        _clean(row.get("work_county")),
    ]
    return ", ".join(part for part in parts if part)


def _top_claims(row: Mapping[str, Any], *, max_items: int = 3) -> list[str]:
    claims = row.get("job_claims")
    if not isinstance(claims, list):
        return []
    items: list[str] = []
    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        text = _clean(claim.get("normalized_label")) or _clean(claim.get("claim_text"))
        if text:
            items.append(text)
        if len(items) >= max_items:
            break
    return items


def _top_selection_signals(row: Mapping[str, Any], *, max_items: int = 3) -> list[str]:
    signals = row.get("selection_signals")
    if not isinstance(signals, list):
        return []
    items: list[str] = []
    for signal in signals:
        if not isinstance(signal, Mapping):
            continue
        label = _clean(signal.get("signal_label")) or _clean(signal.get("normalized_key"))
        if label:
            items.append(label)
        if len(items) >= max_items:
            break
    return items


def _top_mitigation_moves(row: Mapping[str, Any], *, max_items: int = 3) -> list[str]:
    selection_assessment = row.get("selection_assessment")
    if not isinstance(selection_assessment, Mapping):
        return []
    return _list_of_strings(selection_assessment.get("mitigation_moves"))[:max_items]


def _top_evidence_units(row: Mapping[str, Any], *, max_items: int = 4) -> list[str]:
    detail = row.get("detail")
    if isinstance(detail, Mapping):
        cv_focus = _list_of_strings(detail.get("cv_focus_mod"))
        if cv_focus:
            return cv_focus[:max_items]
        overlaps = _list_of_strings(detail.get("overlaps"))
        if overlaps:
            return overlaps[:max_items]

    cv_focus = row.get("cv_focus")
    if isinstance(cv_focus, str):
        return [part.strip() for part in cv_focus.split("|") if part.strip()][:max_items]
    return _list_of_strings(cv_focus)[:max_items]


def _decision_table_summary(row: Mapping[str, Any]) -> str:
    decision_table = row.get("decision_table")
    if not isinstance(decision_table, Mapping):
        return ""

    parts: list[str] = []
    for key in ("can_do", "can_get", "should_want", "can_explain"):
        dimension = decision_table.get(key)
        if not isinstance(dimension, Mapping):
            continue
        level = _clean(dimension.get("level"))
        score = dimension.get("score")
        if level:
            if score is None:
                parts.append(f"{key}:{level}")
            else:
                parts.append(f"{key}:{level} {score}")
    return " | ".join(parts)


def _next_action_hint(row: Mapping[str, Any]) -> str:
    current_status = _clean(row.get("app_status"))
    final_decision = _clean(row.get("final_decision"))
    if current_status in {"interview", "second_interview"}:
        return "Prepare interview follow-up and keep document refs current."
    if current_status == "applied":
        return "Track response timing and keep notes updated."
    if final_decision in {"APPLY_STRONGLY", "APPLY"}:
        return "Review decision brief and prepare application materials."
    if final_decision in {"REVIEW_HIGH", "REVIEW_LOW"}:
        return "Review decision risks before promoting this case."
    return "Keep under monitoring until the case becomes actionable."


def build_jobsync_job_summary(row: Mapping[str, Any]) -> JobSyncJobSummary:
    return JobSyncJobSummary(
        job_id=_clean(row.get("job_id")),
        title=_clean(row.get("title")),
        employer=_clean(row.get("employer")),
        location=_location_label(row),
        application_due=_clean(row.get("applicationDue")),
        source_url=_clean(row.get("source_url")),
        application_url=_clean(row.get("application_url")),
        updated_at=_clean(row.get("updated_at")) or _clean(row.get("run_seen_at")),
    )


def build_jobsync_decision_brief(row: Mapping[str, Any]) -> JobSyncDecisionBrief:
    selection_assessment = row.get("selection_assessment")
    narrative_assessment = row.get("job_narrative_assessment")
    return JobSyncDecisionBrief(
        final_decision=_clean(row.get("final_decision")),
        recommendation_reason=_clean(row.get("recommendation_reason")),
        decision_table_summary=_decision_table_summary(row),
        selection_risk_level=(
            _clean(selection_assessment.get("selection_risk_level"))
            if isinstance(selection_assessment, Mapping)
            else ""
        ),
        top_claims=_top_claims(row),
        top_selection_signals=_top_selection_signals(row),
        top_mitigation_moves=_top_mitigation_moves(row),
        top_evidence_units=_top_evidence_units(row),
        narrative_motivation_brief=(
            _clean(narrative_assessment.get("motivation_brief"))
            if isinstance(narrative_assessment, Mapping)
            else ""
        ),
    )


def build_jobsync_document_refs(row: Mapping[str, Any]) -> list[JobSyncDocumentRef]:
    refs: list[JobSyncDocumentRef] = []
    generated_documents = row.get("generated_documents")
    if not isinstance(generated_documents, list):
        return refs
    for document in generated_documents:
        if not isinstance(document, Mapping):
            continue
        refs.append(
            JobSyncDocumentRef(
                document_id=_clean(document.get("document_id")),
                kind=_clean(document.get("kind")),
                status=_clean(document.get("status")),
                storage_path=_clean(document.get("storage_path")),
                updated_at=_clean(document.get("updated_at")) or _clean(document.get("created_at")),
            )
        )
    return refs


def build_jobsync_application_case_projection(
    row: Mapping[str, Any],
) -> JobSyncApplicationCaseProjection:
    return JobSyncApplicationCaseProjection(
        job_summary=build_jobsync_job_summary(row),
        decision_brief=build_jobsync_decision_brief(row),
        document_refs=build_jobsync_document_refs(row),
        current_application_status=_clean(row.get("app_status")),
        last_application_event_at=_clean(row.get("app_updated_at")),
        next_action_hint=_next_action_hint(row),
    )


def build_jobsync_application_case_projections(
    rows: Iterable[Mapping[str, Any]],
) -> list[JobSyncApplicationCaseProjection]:
    return [build_jobsync_application_case_projection(row) for row in rows]


__all__ = [
    "build_jobsync_application_case_projection",
    "build_jobsync_application_case_projections",
    "build_jobsync_decision_brief",
    "build_jobsync_document_refs",
    "build_jobsync_job_summary",
]
