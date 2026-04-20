from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from .models import (
    CalibrationPattern,
    CandidateCalibrationContext,
    CandidateCalibrationSummary,
    JobCalibrationAssessment,
)

_ROLE_FAMILY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("product", ("product", "owner", "roadmap", "backlog", "plattform", "platform")),
    ("project_delivery", ("project", "program", "delivery", "implementation", "rollout")),
    ("operations", ("operations", "drift", "service", "process", "support", "improvement")),
    ("transformation", ("transform", "change", "transition", "moderniz", "reorgan")),
    ("analytics", ("analytics", "analysis", "reporting", "insight", "data")),
    ("leadership", ("lead", "manager", "principal", "director", "head")),
)

_POSITIVE_FEEDBACK = {"good_recommendation", "promote", "good_fit"}
_NEGATIVE_FEEDBACK = {"bad_recommendation", "demote", "bad_fit"}
_POSITIVE_OUTCOME_MARKERS = ("interview", "offer", "accepted", "hired")
_NEGATIVE_OUTCOME_MARKERS = ("rejected", "declined", "withdrawn")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _job_text(job: Mapping[str, Any]) -> str:
    parts = [
        _clean_text(job.get("title")),
        _clean_text(job.get("employer")),
        _clean_text(job.get("sector")),
        _clean_text(job.get("description_snip")),
        _clean_text(job.get("recommendation_reason")),
    ]
    detail = job.get("detail")
    if isinstance(detail, Mapping):
        parts.extend(str(item).strip() for item in detail.get("overlaps", []) or [] if str(item).strip())
        parts.extend(str(item).strip() for item in detail.get("gaps", []) or [] if str(item).strip())
        parts.append(_clean_text(detail.get("match_notes")))
    return " ".join(part for part in parts if part)


def _role_family_tags(job: Mapping[str, Any]) -> list[str]:
    lowered = _job_text(job).lower()
    tags: list[str] = []
    for tag, needles in _ROLE_FAMILY_PATTERNS:
        if any(needle in lowered for needle in needles):
            tags.append(tag)
    if not tags:
        title = _clean_text(job.get("title"))
        if title:
            tags.append(_slug(title))
    return tags[:2]


def _source_host(job: Mapping[str, Any]) -> str:
    raw = _clean_text(job.get("source_url") or job.get("application_url"))
    if not raw:
        return ""
    try:
        return (urlparse(raw).hostname or "").lower()
    except Exception:
        return ""


def _pattern_polarity(net_score: int) -> str:
    if net_score >= 2:
        return "supports"
    if net_score <= -2:
        return "caution"
    if net_score == 0:
        return "neutral"
    return "mixed"


def _feedback_direction(event: Mapping[str, Any]) -> str:
    value = _clean_text(event.get("feedback_value")).lower()
    if value in _POSITIVE_FEEDBACK:
        return "positive"
    if value in _NEGATIVE_FEEDBACK:
        return "negative"
    return "neutral"


def _outcome_direction(entry: Mapping[str, Any]) -> str:
    status = _clean_text(entry.get("status")).lower()
    outcome = _clean_text(entry.get("outcome")).lower()
    label = f"{status} {outcome}".strip()
    if any(marker in label for marker in _POSITIVE_OUTCOME_MARKERS):
        return "positive"
    if any(marker in label for marker in _NEGATIVE_OUTCOME_MARKERS):
        return "negative"
    return "neutral"


def _known_job_index(known_jobs: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for job in known_jobs:
        job_id = _clean_text(job.get("job_id"))
        if job_id and job_id not in index:
            index[job_id] = job
    return index


def _feedback_job_context(event: Mapping[str, Any], job_index: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any]:
    job_id = _clean_text(event.get("job_id"))
    if job_id and job_id in job_index:
        return job_index[job_id]
    evidence_json = event.get("evidence_json")
    if isinstance(evidence_json, Mapping):
        evaluation = evidence_json.get("evaluation")
        if isinstance(evaluation, Mapping):
            return {
                "job_id": job_id,
                "title": evaluation.get("title"),
                "employer": evaluation.get("employer"),
                "source_url": evaluation.get("source_url"),
                "application_url": evaluation.get("application_url"),
            }
    return {"job_id": job_id}


def _pattern_list(
    pattern_type: str,
    support_counts: Counter[str],
    risk_counts: Counter[str],
    evidence_sources: Mapping[str, set[str]],
    *,
    limit: int = 4,
) -> list[CalibrationPattern]:
    keys = sorted(set(support_counts) | set(risk_counts))
    patterns: list[CalibrationPattern] = []
    for key in keys:
        if not key:
            continue
        support = int(support_counts.get(key, 0))
        risk = int(risk_counts.get(key, 0))
        net = support - risk
        patterns.append(
            CalibrationPattern(
                pattern_type=pattern_type,
                pattern_key=key,
                pattern_label=key.replace("_", " "),
                support_count=support,
                risk_count=risk,
                net_score=net,
                polarity=_pattern_polarity(net),
                evidence_sources=sorted(evidence_sources.get(key, set())),
            )
        )
    patterns.sort(key=lambda pattern: (abs(pattern.net_score), pattern.support_count + pattern.risk_count), reverse=True)
    return patterns[:limit]


def derive_candidate_calibration_summary(
    *,
    feedback_events: Iterable[Mapping[str, Any]] = (),
    application_state: Iterable[Mapping[str, Any]] = (),
    known_jobs: Iterable[Mapping[str, Any]] = (),
    calibration_settings: Iterable[Mapping[str, Any]] = (),
) -> CandidateCalibrationSummary:
    job_index = _known_job_index(known_jobs)
    positive_feedback = 0
    negative_feedback = 0
    manual_promotions = 0
    manual_demotions = 0
    interview_or_better = 0
    rejection_outcomes = 0

    role_support: Counter[str] = Counter()
    role_risk: Counter[str] = Counter()
    role_sources: dict[str, set[str]] = defaultdict(set)
    source_support: Counter[str] = Counter()
    source_risk: Counter[str] = Counter()
    source_sources: dict[str, set[str]] = defaultdict(set)

    for event in feedback_events:
        direction = _feedback_direction(event)
        if direction == "neutral":
            continue
        if direction == "positive":
            positive_feedback += 1
        elif direction == "negative":
            negative_feedback += 1

        feedback_value = _clean_text(event.get("feedback_value")).lower()
        if feedback_value == "promote":
            manual_promotions += 1
        elif feedback_value == "demote":
            manual_demotions += 1

        job = _feedback_job_context(event, job_index)
        role_tags = _role_family_tags(job)
        host = _source_host(job)
        source_label = f"feedback:{feedback_value or _clean_text(event.get('feedback_type')).lower()}"

        for tag in role_tags:
            if direction == "positive":
                role_support[tag] += 1
            else:
                role_risk[tag] += 1
            role_sources[tag].add(source_label)

        if host:
            if direction == "positive":
                source_support[host] += 1
            else:
                source_risk[host] += 1
            source_sources[host].add(source_label)

    for entry in application_state:
        direction = _outcome_direction(entry)
        if direction == "neutral":
            continue
        if direction == "positive":
            interview_or_better += 1
        else:
            rejection_outcomes += 1

        job_id = _clean_text(entry.get("job_id"))
        job = job_index.get(job_id, {"job_id": job_id})
        role_tags = _role_family_tags(job)
        host = _source_host(job)
        status_label = _clean_text(entry.get("outcome") or entry.get("status")).lower() or "status"
        source_label = f"application:{status_label}"

        for tag in role_tags:
            if direction == "positive":
                role_support[tag] += 1
            else:
                role_risk[tag] += 1
            role_sources[tag].add(source_label)

        if host:
            if direction == "positive":
                source_support[host] += 1
            else:
                source_risk[host] += 1
            source_sources[host].add(source_label)

    active_setting_keys: list[str] = []
    for row in calibration_settings:
        scope = _clean_text(row.get("scope"))
        key = _clean_text(row.get("setting_key"))
        if scope and key:
            active_setting_keys.append(f"{scope}:{key}")
    active_setting_keys = sorted(set(active_setting_keys))

    role_patterns = _pattern_list("role_family", role_support, role_risk, role_sources)
    source_patterns = _pattern_list("source_host", source_support, source_risk, source_sources)

    reasons: list[str] = []
    if positive_feedback or negative_feedback:
        reasons.append(
            f"Feedback history currently contains {positive_feedback} positive and {negative_feedback} negative recommendation signals."
        )
    if interview_or_better or rejection_outcomes:
        reasons.append(
            f"Application outcomes currently show {interview_or_better} interview-or-better results and {rejection_outcomes} negative terminal outcomes."
        )
    if active_setting_keys:
        reasons.append(f"{len(active_setting_keys)} explicit local calibration settings are active.")
    if not reasons:
        reasons.append("No meaningful local calibration history exists yet, so the current view is still mostly neutral.")

    return CandidateCalibrationSummary(
        total_feedback_events=positive_feedback + negative_feedback,
        positive_feedback_events=positive_feedback,
        negative_feedback_events=negative_feedback,
        manual_promotions=manual_promotions,
        manual_demotions=manual_demotions,
        interview_or_better_outcomes=interview_or_better,
        rejection_outcomes=rejection_outcomes,
        active_setting_keys=active_setting_keys,
        role_family_patterns=role_patterns,
        source_patterns=source_patterns,
        summary_reason=" ".join(reasons),
    )


def derive_job_calibration_assessment(
    job: Mapping[str, Any],
    *,
    calibration_summary: CandidateCalibrationSummary,
    feedback_events: Iterable[Mapping[str, Any]] = (),
) -> JobCalibrationAssessment:
    role_tags = _role_family_tags(job)
    host = _source_host(job)
    job_id = _clean_text(job.get("job_id"))

    direct_feedback_signals: list[str] = []
    support_score = 20
    risk_score = 20
    supporting_patterns: list[str] = []
    caution_patterns: list[str] = []

    for event in feedback_events:
        if _clean_text(event.get("job_id")) != job_id:
            continue
        value = _clean_text(event.get("feedback_value")).lower()
        if not value:
            continue
        direct_feedback_signals.append(value)
        if value in _POSITIVE_FEEDBACK:
            support_score += 30
        elif value in _NEGATIVE_FEEDBACK:
            risk_score += 35

    role_pattern_map = {pattern.pattern_key: pattern for pattern in calibration_summary.role_family_patterns}
    for tag in role_tags:
        pattern = role_pattern_map.get(tag)
        if not pattern:
            continue
        if pattern.net_score > 0:
            support_score += min(pattern.net_score * 12, 25)
            supporting_patterns.append(
                f"Role-family history for {_clean_text(pattern.pattern_label)} trends positive ({pattern.support_count}:{pattern.risk_count})."
            )
        elif pattern.net_score < 0:
            risk_score += min(abs(pattern.net_score) * 12, 25)
            caution_patterns.append(
                f"Role-family history for {_clean_text(pattern.pattern_label)} trends negative ({pattern.support_count}:{pattern.risk_count})."
            )

    if host:
        source_pattern_map = {pattern.pattern_key: pattern for pattern in calibration_summary.source_patterns}
        pattern = source_pattern_map.get(host)
        if pattern:
            if pattern.net_score > 0:
                support_score += min(pattern.net_score * 8, 18)
                supporting_patterns.append(
                    f"Source history for {host} trends positive ({pattern.support_count}:{pattern.risk_count})."
                )
            elif pattern.net_score < 0:
                risk_score += min(abs(pattern.net_score) * 8, 18)
                caution_patterns.append(
                    f"Source history for {host} trends negative ({pattern.support_count}:{pattern.risk_count})."
                )

    support_score = max(0, min(100, int(round(support_score))))
    risk_score = max(0, min(100, int(round(risk_score))))
    delta = support_score - risk_score
    if risk_score >= 60 and delta <= -10:
        polarity = "caution"
    elif support_score >= 60 and delta >= 10:
        polarity = "supports"
    elif supporting_patterns or caution_patterns or direct_feedback_signals:
        polarity = "mixed"
    else:
        polarity = "neutral"

    if direct_feedback_signals:
        reason = f"Direct feedback exists for this job: {', '.join(sorted(set(direct_feedback_signals)))}."
    elif polarity == "supports":
        reason = "Local feedback and outcome history modestly support this job family or source."
    elif polarity == "caution":
        reason = "Local feedback and outcome history suggest caution for this job family or source."
    elif polarity == "mixed":
        reason = "Local feedback history is mixed, so calibration support is informative but not decisive."
    else:
        reason = "There is little local calibration history for this job yet."

    return JobCalibrationAssessment(
        support_score=support_score,
        risk_score=risk_score,
        polarity=polarity,
        direct_feedback_signals=sorted(set(direct_feedback_signals)),
        supporting_patterns=supporting_patterns[:3],
        caution_patterns=caution_patterns[:3],
        assessment_reason=reason,
    )


def build_candidate_calibration_context(
    job: Mapping[str, Any],
    *,
    feedback_events: Iterable[Mapping[str, Any]] = (),
    application_state: Iterable[Mapping[str, Any]] = (),
    known_jobs: Iterable[Mapping[str, Any]] = (),
    calibration_settings: Iterable[Mapping[str, Any]] = (),
) -> CandidateCalibrationContext:
    summary = derive_candidate_calibration_summary(
        feedback_events=feedback_events,
        application_state=application_state,
        known_jobs=known_jobs,
        calibration_settings=calibration_settings,
    )
    assessment = derive_job_calibration_assessment(
        job,
        calibration_summary=summary,
        feedback_events=feedback_events,
    )
    return CandidateCalibrationContext(
        calibration_summary=summary,
        job_calibration_assessment=assessment,
    )


__all__ = [
    "build_candidate_calibration_context",
    "derive_candidate_calibration_summary",
    "derive_job_calibration_assessment",
]
