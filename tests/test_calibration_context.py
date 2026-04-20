from __future__ import annotations

from jobpipe.decision import (
    build_candidate_calibration_context,
    derive_candidate_calibration_summary,
)


def _known_jobs() -> list[dict]:
    return [
        {
            "job_id": "job-product",
            "title": "Senior Product Manager",
            "employer": "Example AS",
            "sector": "SaaS",
            "source_url": "https://example.test/job-product",
            "description_snip": "Product strategy and platform delivery.",
        },
        {
            "job_id": "job-ops",
            "title": "Operations Manager",
            "employer": "Ops AS",
            "sector": "Operations",
            "source_url": "https://ops.test/job-ops",
            "description_snip": "Operations improvement and service delivery.",
        },
    ]


def test_derive_candidate_calibration_summary_surfaces_patterns_and_counts() -> None:
    summary = derive_candidate_calibration_summary(
        feedback_events=[
            {
                "job_id": "job-product",
                "feedback_type": "manual_override",
                "feedback_value": "promote",
                "evidence_json": {},
            },
            {
                "job_id": "job-ops",
                "feedback_type": "recommendation_quality",
                "feedback_value": "bad_recommendation",
                "evidence_json": {},
            },
        ],
        application_state=[
            {"job_id": "job-product", "status": "interview", "outcome": ""},
            {"job_id": "job-ops", "status": "rejected", "outcome": ""},
        ],
        known_jobs=_known_jobs(),
        calibration_settings=[
            {"scope": "ranking", "setting_key": "apply_floor", "value_json": {"value": 0.7}},
        ],
    )

    assert summary.total_feedback_events == 2
    assert summary.positive_feedback_events == 1
    assert summary.negative_feedback_events == 1
    assert summary.manual_promotions == 1
    assert summary.rejection_outcomes == 1
    assert "ranking:apply_floor" in summary.active_setting_keys
    assert summary.role_family_patterns
    assert summary.summary_reason


def test_build_candidate_calibration_context_supports_matching_positive_history() -> None:
    job = {
        "job_id": "job-current",
        "title": "Principal Product Lead",
        "employer": "Future AS",
        "sector": "SaaS",
        "source_url": "https://example.test/job-current",
        "description_snip": "Product leadership and platform delivery.",
    }

    context = build_candidate_calibration_context(
        job,
        feedback_events=[
            {
                "job_id": "job-product",
                "feedback_type": "fit_judgment",
                "feedback_value": "good_fit",
                "evidence_json": {},
            }
        ],
        application_state=[
            {"job_id": "job-product", "status": "interview", "outcome": ""},
        ],
        known_jobs=_known_jobs(),
    )

    assert context.job_calibration_assessment.polarity in {"supports", "mixed"}
    assert context.job_calibration_assessment.support_score >= context.job_calibration_assessment.risk_score
    assert context.job_calibration_assessment.supporting_patterns


def test_build_candidate_calibration_context_flags_direct_negative_feedback() -> None:
    job = {
        "job_id": "job-current",
        "title": "Operations Manager",
        "employer": "Ops AS",
        "sector": "Operations",
        "source_url": "https://ops.test/job-current",
        "description_snip": "Operations improvement and service delivery.",
    }

    context = build_candidate_calibration_context(
        job,
        feedback_events=[
            {
                "job_id": "job-current",
                "feedback_type": "manual_override",
                "feedback_value": "demote",
                "evidence_json": {},
            }
        ],
        known_jobs=[job],
    )

    assert context.job_calibration_assessment.direct_feedback_signals == ["demote"]
    assert context.job_calibration_assessment.risk_score > context.job_calibration_assessment.support_score
    assert context.job_calibration_assessment.polarity in {"caution", "mixed"}
