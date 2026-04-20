from __future__ import annotations

from jobpipe.decision import build_decision_context, build_monitoring_context


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
