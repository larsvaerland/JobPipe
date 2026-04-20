from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from .models import ChangeEvent, DecisionContext, MonitoringContext, Watchlist

_ROLE_FAMILY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("product", ("product", "owner", "roadmap", "backlog", "plattform", "platform")),
    ("project_delivery", ("project", "program", "delivery", "implementation", "rollout")),
    ("operations", ("operations", "drift", "service", "process", "support", "improvement")),
    ("transformation", ("transform", "change", "transition", "moderniz", "reorgan")),
    ("analytics", ("analytics", "analysis", "reporting", "insight", "data")),
    ("leadership", ("lead", "manager", "principal", "director", "head")),
)

_ACTIONABLE_DECISIONS = {"APPLY_STRONGLY", "APPLY", "REVIEW_HIGH", "REVIEW_LOW"}
_HIGH_STATUS_MARKERS = ("interview", "offer", "rejected", "declined", "final")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _hash_id(prefix: str, *parts: str) -> str:
    raw = "|".join(parts)
    return f"{prefix}_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _pretty_label(value: str) -> str:
    return value.replace("_", " ").strip()


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
        parts.extend(str(item).strip() for item in detail.get("hard_blockers", []) or [] if str(item).strip())
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


def _feed_host(job: Mapping[str, Any]) -> str:
    raw = _clean_text(job.get("source_url") or job.get("application_url"))
    if not raw:
        return ""
    try:
        return (urlparse(raw).hostname or "").lower()
    except Exception:
        return ""


def _detected_at(job: Mapping[str, Any], app_entry: Mapping[str, Any] | None = None) -> str:
    if app_entry:
        updated = _clean_text(app_entry.get("updated_at"))
        if updated:
            return updated
    return (
        _clean_text(job.get("updated_at"))
        or _clean_text(job.get("run_seen_at"))
        or _clean_text(job.get("seen_at"))
        or datetime.now(timezone.utc).isoformat()
    )


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _watchlist(
    *,
    candidate_id: str,
    watch_type: str,
    watch_key: str,
    watch_label: str,
    watch_config_json: Mapping[str, Any] | None = None,
) -> Watchlist:
    return Watchlist(
        watchlist_id=_hash_id("watch", candidate_id, watch_type, watch_key),
        candidate_id=candidate_id,
        watch_type=watch_type,
        watch_key=watch_key,
        watch_label=watch_label,
        watch_config_json=dict(watch_config_json or {}),
        is_active=True,
    )


def derive_watchlists(
    job: Mapping[str, Any],
    *,
    candidate_id: str = "default",
    decision_context: DecisionContext | None = None,
) -> list[Watchlist]:
    watchlists: list[Watchlist] = []
    seen: set[tuple[str, str]] = set()
    act_now = decision_context.decision_table.act_now if decision_context else ""
    title = _clean_text(job.get("title"))
    employer = _clean_text(job.get("employer"))
    job_id = _clean_text(job.get("job_id"))
    city = _clean_text(job.get("work_city"))
    sector = _clean_text(job.get("sector"))
    role_families = _role_family_tags(job)
    host = _feed_host(job)

    def add_watch(watch: Watchlist) -> None:
        key = (watch.watch_type, watch.watch_key)
        if key in seen:
            return
        seen.add(key)
        watchlists.append(watch)

    if job_id and act_now in {"pursue_now", "review_then_pursue", "monitor"}:
        add_watch(
            _watchlist(
                candidate_id=candidate_id,
                watch_type="job",
                watch_key=job_id,
                watch_label=f"{title or 'Job'} at {employer}".strip(),
                watch_config_json={"job_id": job_id},
            )
        )

    if employer and act_now != "skip":
        add_watch(
            _watchlist(
                candidate_id=candidate_id,
                watch_type="employer",
                watch_key=_slug(employer),
                watch_label=employer,
                watch_config_json={"employer": employer},
            )
        )

    for role_family in role_families:
        if act_now == "skip":
            break
        add_watch(
            _watchlist(
                candidate_id=candidate_id,
                watch_type="role_family",
                watch_key=role_family,
                watch_label=f"{_pretty_label(role_family)} roles",
                watch_config_json={"role_family": role_family},
            )
        )

    if role_families and act_now in {"review_then_pursue", "monitor"}:
        location_or_domain = city or sector
        if location_or_domain:
            role_family = role_families[0]
            add_watch(
                _watchlist(
                    candidate_id=candidate_id,
                    watch_type="search_pattern",
                    watch_key=f"{role_family}:{_slug(location_or_domain)}",
                    watch_label=f"{_pretty_label(role_family)} roles in {location_or_domain}",
                    watch_config_json={
                        "role_family": role_family,
                        "work_city": city,
                        "sector": sector,
                    },
                )
            )

    if host and act_now in {"review_then_pursue", "monitor"}:
        add_watch(
            _watchlist(
                candidate_id=candidate_id,
                watch_type="source_feed",
                watch_key=host,
                watch_label=f"{host} feed",
                watch_config_json={"host": host},
            )
        )

    return watchlists


def _latest_previous_run(
    job: Mapping[str, Any],
    run_history: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    rows = list(run_history)
    if not rows:
        return None

    current_run_id = _clean_text(job.get("run_id"))
    if current_run_id:
        previous = [row for row in rows if _clean_text(row.get("run_id")) != current_run_id]
        if previous:
            previous.sort(key=lambda row: (_safe_float(row.get("run_mtime")), _clean_text(row.get("seen_at"))))
            return previous[-1]

    rows.sort(key=lambda row: (_safe_float(row.get("run_mtime")), _clean_text(row.get("seen_at"))))
    if len(rows) >= 2:
        return rows[-2]
    return None


def _decision_boundary(decision: str) -> str:
    return "actionable" if decision in _ACTIONABLE_DECISIONS else "non_actionable"


def _status_materiality(status_label: str) -> str:
    lowered = status_label.lower()
    if any(marker in lowered for marker in _HIGH_STATUS_MARKERS):
        return "high"
    if lowered:
        return "medium"
    return "low"


def derive_change_events(
    job: Mapping[str, Any],
    *,
    watchlists: Iterable[Watchlist] = (),
    candidate_id: str = "default",
    decision_context: DecisionContext | None = None,
    run_history: Iterable[Mapping[str, Any]] = (),
    app_entry: Mapping[str, Any] | None = None,
) -> list[ChangeEvent]:
    del watchlists  # watchlists are first-class outputs now; change events stay delta-driven in this slice.

    events: list[ChangeEvent] = []
    detected_at = _detected_at(job, app_entry)
    previous_run = _latest_previous_run(job, run_history)
    title = _clean_text(job.get("title"))
    employer = _clean_text(job.get("employer"))
    job_id = _clean_text(job.get("job_id"))
    current_decision = _clean_text(job.get("final_decision"))
    current_fit = _safe_int(job.get("fit_score"))
    current_pivot = _safe_int(job.get("pivot_score"))
    current_due = _clean_text(job.get("applicationDue"))
    act_now = decision_context.decision_table.act_now if decision_context else ""

    def add_event(
        *,
        change_type: str,
        change_summary: str,
        materiality: str,
        change_json: Mapping[str, Any] | None = None,
    ) -> None:
        events.append(
            ChangeEvent(
                change_event_id=_hash_id(
                    "change",
                    candidate_id,
                    job_id or title or employer or "job",
                    change_type,
                    detected_at,
                    change_summary,
                ),
                candidate_id=candidate_id,
                watchlist_id="",
                job_id=job_id,
                change_type=change_type,
                change_summary=change_summary,
                change_json=dict(change_json or {}),
                materiality=materiality,
                detected_at=detected_at,
                reviewed_at="",
            )
        )

    if previous_run is None:
        materiality = "high" if act_now in {"pursue_now", "review_then_pursue"} else "medium"
        add_event(
            change_type="new_job",
            change_summary=f"New job entered the current pipeline view: {title or 'Unknown role'} at {employer or 'Unknown employer'}.",
            materiality=materiality,
            change_json={
                "title": title,
                "employer": employer,
                "final_decision": current_decision,
                "act_now": act_now,
            },
        )
    else:
        previous_due = _clean_text(previous_run.get("applicationDue"))
        if previous_due != current_due and (previous_due or current_due):
            materiality = "high" if previous_due and current_due else "medium"
            add_event(
                change_type="deadline_changed",
                change_summary=f"Deadline changed from {previous_due or 'missing'} to {current_due or 'missing'}.",
                materiality=materiality,
                change_json={"previous_deadline": previous_due, "current_deadline": current_due},
            )

        previous_decision = _clean_text(previous_run.get("final_decision"))
        previous_fit = _safe_int(previous_run.get("fit_score"))
        previous_pivot = _safe_int(previous_run.get("pivot_score"))
        fit_delta = None if previous_fit is None or current_fit is None else current_fit - previous_fit
        pivot_delta = None if previous_pivot is None or current_pivot is None else current_pivot - previous_pivot

        decision_changed = previous_decision != current_decision and (previous_decision or current_decision)
        fit_changed = fit_delta is not None and abs(fit_delta) >= 8
        pivot_changed = pivot_delta is not None and abs(pivot_delta) >= 10
        if decision_changed or fit_changed or pivot_changed:
            boundary_changed = _decision_boundary(previous_decision) != _decision_boundary(current_decision)
            materiality = "high" if boundary_changed or decision_changed else "medium"
            summary_parts = []
            if decision_changed:
                summary_parts.append(
                    f"Selection outcome moved from {previous_decision or 'unknown'} to {current_decision or 'unknown'}."
                )
            if fit_delta is not None and fit_changed:
                direction = "rose" if fit_delta > 0 else "fell"
                summary_parts.append(f"Fit score {direction} from {previous_fit} to {current_fit}.")
            if pivot_delta is not None and pivot_changed:
                direction = "rose" if pivot_delta > 0 else "fell"
                summary_parts.append(f"Pivot score {direction} from {previous_pivot} to {current_pivot}.")
            add_event(
                change_type="selection_logic_changed",
                change_summary=" ".join(summary_parts),
                materiality=materiality,
                change_json={
                    "previous_decision": previous_decision,
                    "current_decision": current_decision,
                    "previous_fit_score": previous_fit,
                    "current_fit_score": current_fit,
                    "previous_pivot_score": previous_pivot,
                    "current_pivot_score": current_pivot,
                    "act_now": act_now,
                },
            )

        previous_title = _clean_text(previous_run.get("title"))
        previous_employer = _clean_text(previous_run.get("employer"))
        previous_city = _clean_text(previous_run.get("work_city"))
        previous_county = _clean_text(previous_run.get("work_county"))
        previous_source_url = _clean_text(previous_run.get("source_url"))
        current_city = _clean_text(job.get("work_city"))
        current_county = _clean_text(job.get("work_county"))
        current_source_url = _clean_text(job.get("source_url"))
        job_changed_fields: list[str] = []
        if previous_title != title and (previous_title or title):
            job_changed_fields.append("title")
        if previous_employer != employer and (previous_employer or employer):
            job_changed_fields.append("employer")
        if previous_city != current_city and (previous_city or current_city):
            job_changed_fields.append("work_city")
        if previous_county != current_county and (previous_county or current_county):
            job_changed_fields.append("work_county")
        if previous_source_url != current_source_url and (previous_source_url or current_source_url):
            job_changed_fields.append("source_url")
        if job_changed_fields:
            add_event(
                change_type="job_changed",
                change_summary=f"Job metadata changed in: {', '.join(job_changed_fields)}.",
                materiality="medium" if len(job_changed_fields) > 1 else "low",
                change_json={"changed_fields": job_changed_fields},
            )

    status = _clean_text((app_entry or {}).get("status"))
    outcome = _clean_text((app_entry or {}).get("outcome"))
    status_label = outcome or status
    if status_label:
        add_event(
            change_type="status_changed",
            change_summary=f"Application status is now {status_label}.",
            materiality=_status_materiality(status_label),
            change_json={
                "status": status,
                "outcome": outcome,
                "updated_at": _clean_text((app_entry or {}).get("updated_at")),
                "source": _clean_text((app_entry or {}).get("source")),
            },
        )

    return events


def build_monitoring_context(
    job: Mapping[str, Any],
    *,
    candidate_id: str = "default",
    decision_context: DecisionContext | None = None,
    run_history: Iterable[Mapping[str, Any]] = (),
    app_entry: Mapping[str, Any] | None = None,
) -> MonitoringContext:
    watchlists = derive_watchlists(job, candidate_id=candidate_id, decision_context=decision_context)
    change_events = derive_change_events(
        job,
        watchlists=watchlists,
        candidate_id=candidate_id,
        decision_context=decision_context,
        run_history=run_history,
        app_entry=app_entry,
    )
    return MonitoringContext(watchlists=watchlists, change_events=change_events)


__all__ = [
    "build_monitoring_context",
    "derive_change_events",
    "derive_watchlists",
]
