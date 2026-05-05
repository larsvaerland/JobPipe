from __future__ import annotations

from jobpipe.core.experiment_review_state import (
    build_advantage_signal_calibration_summary,
    build_advantage_shortlist_quality_summary,
    build_experiment_calibration_summary,
    build_experiment_promotion_review_summary,
    build_experiment_variant_review_summary,
    get_experiment_promotion_review,
    get_experiment_variant_review,
    load_experiment_review_state,
    upsert_experiment_promotion_review,
    upsert_experiment_variant_review,
)


def test_build_experiment_calibration_summary_counts_useful_signal_and_reasons() -> None:
    summary = build_experiment_calibration_summary(
        [
            {
                "review_reason": "promoted_from_discard",
                "adjudication": {"verdict": "correct_miss"},
            },
            {
                "review_reason": "promoted_from_discard",
                "adjudication": {"verdict": "promote_rule_candidate"},
            },
            {
                "review_reason": "borderline_baseline_discard",
                "adjudication": {"verdict": "not_useful"},
            },
            {
                "review_reason": "promoted_in_shadow",
                "adjudication": {"verdict": "interesting_but_no"},
            },
            {
                "review_reason": "promoted_from_discard",
                "adjudication": {},
            },
        ]
    )

    assert summary["schema_version"] == "jobpipe.experiment-calibration.v1"
    assert summary["reviewed"] == 4
    assert summary["positive"] == 2
    assert summary["rejected"] == 1
    assert summary["interesting_but_no"] == 1
    assert summary["useful_signal_rate"] == 50.0
    assert summary["top_positive_reasons"] == [{"reason": "promoted_from_discard", "count": 2}]
    assert summary["top_negative_reasons"] == [{"reason": "borderline_baseline_discard", "count": 1}]


def test_build_advantage_signal_calibration_summary_counts_high_vs_lower_signal_and_hooks() -> None:
    summary = build_advantage_signal_calibration_summary(
        [
            {
                "advantageous_match_score": 82,
                "recruiter_hook": "Strong operator-product bridge.",
                "adjudication": {"verdict": "correct_miss"},
            },
            {
                "advantageous_match_score": 78,
                "recruiter_hook": "Strong operator-product bridge.",
                "adjudication": {"verdict": "not_useful"},
            },
            {
                "advantageous_match_score": 58,
                "recruiter_hook": "Broad delivery profile.",
                "adjudication": {"verdict": "promote_rule_candidate"},
            },
            {
                "advantageous_match_score": 44,
                "recruiter_hook": "Weak generic hook.",
                "adjudication": {"verdict": "interesting_but_no"},
            },
            {
                "advantageous_match_score": 75,
                "recruiter_hook": "Pending hook.",
                "adjudication": {},
            },
        ]
    )

    assert summary["schema_version"] == "jobpipe.advantage-signal-calibration.v1"
    assert summary["reviewed"] == 4
    assert summary["high_advantage_reviewed"] == 2
    assert summary["high_advantage_positive"] == 1
    assert summary["high_advantage_useful_rate"] == 50.0
    assert summary["lower_advantage_reviewed"] == 2
    assert summary["lower_advantage_positive"] == 1
    assert summary["lower_advantage_useful_rate"] == 50.0
    assert summary["top_positive_hooks"] == [{"hook": "Strong operator-product bridge.", "count": 1}, {"hook": "Broad delivery profile.", "count": 1}]
    assert summary["top_negative_hooks"] == [{"hook": "Strong operator-product bridge.", "count": 1}]


def test_build_advantage_shortlist_quality_summary_compares_reviewed_variant_quality() -> None:
    summary = build_advantage_shortlist_quality_summary(
        [
            {
                "reviewed": 2,
                "useful_signal_rate": 75.0,
                "avg_advantageous_match_score": 78.0,
                "variant_review": {"verdict": "worth_promoting"},
            },
            {
                "reviewed": 1,
                "useful_signal_rate": 30.0,
                "avg_advantageous_match_score": 61.0,
                "variant_review": {"verdict": "reject_variant"},
            },
            {
                "reviewed": 1,
                "useful_signal_rate": 55.0,
                "avg_advantageous_match_score": 74.0,
                "variant_review": {"verdict": "needs_more_review"},
            },
        ]
    )

    assert summary["schema_version"] == "jobpipe.advantage-shortlist-quality.v1"
    assert summary["reviewed_variants"] == 3
    assert summary["high_advantage_variants"] == 2
    assert summary["high_advantage_avg_useful_rate"] == 65.0
    assert summary["high_advantage_worth_promoting"] == 1
    assert summary["high_advantage_worth_promoting_rate"] == 50.0
    assert summary["lower_advantage_variants"] == 1
    assert summary["lower_advantage_avg_useful_rate"] == 30.0
    assert summary["lower_advantage_worth_promoting_rate"] == 0.0
    assert summary["quality_delta_useful_rate"] == 35.0
    assert summary["quality_delta_worth_promoting_rate"] == 50.0
    assert summary["status"] == "improving"
    assert summary["confidence"] == "low"


def test_upsert_experiment_variant_review_roundtrip(tmp_path: Path) -> None:
    state_path = tmp_path / "reports" / "experiment_review_state.json"

    entry = upsert_experiment_variant_review(
        state_path,
        experiment_id="shadow_latest",
        verdict="worth_promoting",
        candidate_name="triage_v3_threshold_variant",
        kind="shadow_threshold_eval",
    )

    state = load_experiment_review_state(state_path)
    assert entry["verdict"] == "worth_promoting"
    assert get_experiment_variant_review(state, experiment_id="shadow_latest")["candidate_name"] == "triage_v3_threshold_variant"

    cleared = upsert_experiment_variant_review(
        state_path,
        experiment_id="shadow_latest",
        verdict="",
    )
    assert cleared == {}
    assert get_experiment_variant_review(load_experiment_review_state(state_path), experiment_id="shadow_latest") == {}


def test_build_experiment_variant_review_summary_counts_variant_verdicts() -> None:
    summary = build_experiment_variant_review_summary(
        [
            {"variant_review": {"verdict": "worth_promoting"}},
            {"variant_review": {"verdict": "needs_more_review"}},
            {"variant_review": {"verdict": "reject_variant"}},
            {"variant_review": {}},
        ]
    )

    assert summary == {
        "reviewed": 3,
        "pending": 1,
        "worth_promoting": 1,
        "needs_more_review": 1,
        "reject_variant": 1,
    }


def test_upsert_experiment_promotion_review_roundtrip(tmp_path: Path) -> None:
    state_path = tmp_path / "reports" / "experiment_review_state.json"

    entry = upsert_experiment_promotion_review(
        state_path,
        experiment_id="shadow_latest",
        verdict="accepted_for_promotion",
        candidate_name="triage_v3_threshold_variant",
        kind="shadow_threshold_eval",
    )

    state = load_experiment_review_state(state_path)
    assert entry["verdict"] == "accepted_for_promotion"
    assert get_experiment_promotion_review(state, experiment_id="shadow_latest")["candidate_name"] == "triage_v3_threshold_variant"

    cleared = upsert_experiment_promotion_review(
        state_path,
        experiment_id="shadow_latest",
        verdict="",
    )
    assert cleared == {}
    assert get_experiment_promotion_review(load_experiment_review_state(state_path), experiment_id="shadow_latest") == {}


def test_build_experiment_promotion_review_summary_counts_promotion_verdicts() -> None:
    summary = build_experiment_promotion_review_summary(
        [
            {"promotion_review": {"verdict": "accepted_for_promotion"}},
            {"promotion_review": {"verdict": "deferred_promotion"}},
            {"promotion_review": {"verdict": "rejected_promotion"}},
            {"promotion_review": {}},
        ]
    )

    assert summary == {
        "reviewed": 3,
        "pending": 1,
        "accepted_for_promotion": 1,
        "deferred_promotion": 1,
        "rejected_promotion": 1,
    }
