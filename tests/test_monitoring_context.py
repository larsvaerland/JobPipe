from __future__ import annotations

from jobpipe.decision import build_decision_context, build_monitoring_context
from jobpipe.decision.monitoring import derive_watchlists


def test_build_monitoring_context_suggests_watchlists_for_monitorable_role() -> None:
    job = {
        "job_id": "job-1",
        "run_id": "run-1",
        "run_seen_at": "2026-04-17T08:00:00Z",
        "updated_at": "2026-04-17T08:05:00Z",
        "title": "Senior Product Manager",
        "employer": "Example AS",
        "sector": "SaaS",
        "work_city": "Oslo",
        "source_url": "https://example.test/job-1",
        "fit_score": 81,
        "pivot_score": 68,
        "final_decision": "APPLY",
        "recommendation_reason": "Strong product and platform overlap.",
        "description_snip": "Platform delivery and roadmap ownership.",
        "detail": {
            "overlaps": ["Product strategy", "Platform delivery"],
            "gaps": [],
            "hard_blockers": [],
            "match_notes": "Strong fit.",
        },
    }

    context = build_monitoring_context(
        job,
        candidate_id="candidate-a",
        decision_context=build_decision_context(job),
    )

    watch_types = {watch.watch_type for watch in context.watchlists}
    change_types = {event.change_type for event in context.change_events}

    assert "job" in watch_types
    assert "employer" in watch_types
    assert "role_family" in watch_types
    assert "new_job" in change_types


def test_build_monitoring_context_detects_deadline_and_selection_changes() -> None:
    job = {
        "job_id": "job-2",
        "run_id": "run-new",
        "run_seen_at": "2026-04-17T08:00:00Z",
        "updated_at": "2026-04-17T08:05:00Z",
        "title": "Principal Product Lead",
        "employer": "Example AS",
        "sector": "SaaS",
        "work_city": "Oslo",
        "applicationDue": "2026-05-01",
        "source_url": "https://example.test/job-2",
        "fit_score": 78,
        "pivot_score": 52,
        "final_decision": "APPLY",
        "recommendation_reason": "Current fit is stronger than last pass.",
        "description_snip": "Product leadership and platform delivery.",
        "detail": {
            "overlaps": ["Product leadership"],
            "gaps": ["Marketplace exposure"],
            "hard_blockers": [],
            "match_notes": "Improved fit.",
        },
    }
    run_history = [
        {
            "job_id": "job-2",
            "run_id": "run-old",
            "run_mtime": 10.0,
            "seen_at": "2026-04-15T08:00:00Z",
            "final_decision": "REVIEW_LOW",
            "fit_score": 58,
            "pivot_score": 35,
            "applicationDue": "2026-04-24",
            "title": "Principal Product Lead",
            "employer": "Example AS",
            "work_city": "Oslo",
            "work_county": "Oslo",
            "source_url": "https://example.test/job-2",
            "application_url": "",
        },
        {
            "job_id": "job-2",
            "run_id": "run-new",
            "run_mtime": 20.0,
            "seen_at": "2026-04-17T08:00:00Z",
            "final_decision": "APPLY",
            "fit_score": 78,
            "pivot_score": 52,
            "applicationDue": "2026-05-01",
            "title": "Principal Product Lead",
            "employer": "Example AS",
            "work_city": "Oslo",
            "work_county": "Oslo",
            "source_url": "https://example.test/job-2",
            "application_url": "",
        },
    ]

    context = build_monitoring_context(
        job,
        candidate_id="candidate-a",
        decision_context=build_decision_context(job),
        run_history=run_history,
    )

    change_types = {event.change_type for event in context.change_events}

    assert "selection_logic_changed" in change_types
    assert "deadline_changed" in change_types


def test_build_monitoring_context_surfaces_application_status_change() -> None:
    job = {
        "job_id": "job-3",
        "run_id": "run-1",
        "run_seen_at": "2026-04-17T08:00:00Z",
        "updated_at": "2026-04-17T08:05:00Z",
        "title": "Program Manager",
        "employer": "Example AS",
        "fit_score": 72,
        "pivot_score": 44,
        "final_decision": "REVIEW_HIGH",
        "description_snip": "Program delivery and stakeholder management.",
        "detail": {
            "overlaps": ["Delivery"],
            "gaps": [],
            "hard_blockers": [],
            "match_notes": "Viable fit.",
        },
    }

    context = build_monitoring_context(
        job,
        candidate_id="candidate-a",
        decision_context=build_decision_context(job),
        app_entry={
            "status": "interview",
            "outcome": "",
            "updated_at": "2026-04-18T09:00:00Z",
            "source": "gmail",
        },
    )

    status_events = [event for event in context.change_events if event.change_type == "status_changed"]
    assert status_events
    assert status_events[0].materiality == "high"


def test_derive_watchlists_assigns_materiality_and_dedups_source_feed() -> None:
    pursue_job = {
        "job_id": "job-pursue",
        "title": "Senior Product Manager",
        "employer": "Acme AS",
        "sector": "SaaS",
        "work_city": "Oslo",
        "source_url": "https://example.test/pursue",
        "fit_score": 85,
        "pivot_score": 72,
        "final_decision": "APPLY_STRONGLY",
        "recommendation_reason": "Strong product overlap.",
        "description_snip": "Product and platform roadmap ownership.",
        "detail": {"overlaps": ["Product strategy"], "gaps": [], "hard_blockers": [], "match_notes": "Strong."},
    }
    review_job = {
        "job_id": "job-review",
        "title": "Program Manager",
        "employer": "Beta AS",
        "sector": "Public Sector",
        "work_city": "Oslo",
        "source_url": "https://example.test/review",
        "fit_score": 64,
        "pivot_score": 48,
        "final_decision": "REVIEW_HIGH",
        "recommendation_reason": "Program delivery overlap.",
        "description_snip": "Program delivery and stakeholder management.",
        "detail": {"overlaps": ["Delivery"], "gaps": [], "hard_blockers": [], "match_notes": "Viable."},
    }

    pursue_ctx = build_decision_context(pursue_job)
    review_ctx = build_decision_context(review_job)
    monitor_ctx = review_ctx.model_copy(
        update={
            "decision_table": review_ctx.decision_table.model_copy(update={"act_now": "monitor"})
        }
    )

    pursue_watches = derive_watchlists(pursue_job, candidate_id="candidate-a", decision_context=pursue_ctx)
    review_watches = derive_watchlists(review_job, candidate_id="candidate-a", decision_context=review_ctx)
    monitor_watches = derive_watchlists(review_job, candidate_id="candidate-a", decision_context=monitor_ctx)

    pursue_by_type = {watch.watch_type: watch for watch in pursue_watches}
    review_types = {watch.watch_type for watch in review_watches}
    monitor_types = {watch.watch_type for watch in monitor_watches}

    # Pursue-now gets a high-materiality job watch and a medium-materiality employer watch.
    assert pursue_by_type["job"].materiality == "high"
    assert pursue_by_type["employer"].materiality == "medium"
    # Role-family watches are always background noise (low materiality).
    assert all(
        watch.materiality == "low"
        for watch in pursue_watches
        if watch.watch_type == "role_family"
    )
    # Review-then-pursue no longer emits a source_feed watch (background-only signal).
    assert "source_feed" not in review_types
    # True monitor mode still keeps the background source-feed watch.
    assert "source_feed" in monitor_types
    # Review-then-pursue keeps at most one role_family watch so monitoring stays bounded.
    assert sum(1 for watch in review_watches if watch.watch_type == "role_family") <= 1
