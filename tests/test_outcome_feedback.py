from __future__ import annotations

from jobpipe.core.outcome_feedback import (
    build_outcome_feedback_state,
    build_outcome_ranking_guidance,
    build_outcomes_dashboard_payload,
    load_outcome_feedback_state,
    persist_outcome_feedback_state,
)


def test_build_outcome_feedback_state_links_decision_context_artifacts_and_status() -> None:
    state = build_outcome_feedback_state(
        [
            {
                "job_id": "nav_outcome_1",
                "run_id": "run_outcome",
                "final_decision": "APPLY",
                "app_status": "interview",
                "app_outcome": "",
                "app_source": "manual",
                "app_notes": "Good first call.",
                "app_updated_at": "2026-04-19T20:00:00Z",
                "generated_documents": [
                    {
                        "kind": "cover_letter_text",
                        "status": "draft",
                        "storage_path": "C:/Users/example/JobpipeData/out_runs/run_outcome/nav_outcome_1/cover_letter_draft.txt",
                    }
                ],
                "detail": {
                    "decision_brief": {
                        "schema_version": "jobpipe.decision-brief.v1",
                        "final_decision": "APPLY",
                        "fit_score": 79,
                        "pivot_score": 52,
                    },
                    "application_case_projection": {
                        "schema_version": "jobpipe.application-case-projection.v1",
                        "external_source": "jobpipe",
                        "external_id": "nav_outcome_1",
                        "run_id": "run_outcome",
                        "status": "interview",
                        "updated_at": "2026-04-19T20:00:00Z",
                        "job_summary": {
                            "title": "Produktleder",
                            "company": "Vy",
                        },
                        "decision_brief": {
                            "schema_version": "jobpipe.decision-brief.v1",
                            "final_decision": "APPLY",
                        },
                        "artifact_plan": {
                            "schema_version": "jobpipe.artifact-plan.v1",
                            "artifact_root": "C:/Users/example/JobpipeData/out_runs/run_outcome/nav_outcome_1",
                            "input_snapshot_path": "C:/Users/example/JobpipeData/out_runs/run_outcome/nav_outcome_1/00_input.json",
                            "save_targets": {},
                            "generated_artifacts": [],
                        },
                    },
                },
            }
        ]
    )

    entry = state["outcomes"]["run_outcome::nav_outcome_1"]
    assert state["schema_version"] == "jobpipe.outcome-feedback-state.v1"
    assert entry["schema_version"] == "jobpipe.outcome-feedback.v1"
    assert entry["shared_status"] == "interview"
    assert entry["outcome_label"] == "interview"
    assert entry["artifact_refs_used"][0]["kind"] == "cover_letter_text"
    assert entry["decision_brief"]["fit_score"] == 79
    assert entry["application_case_projection"]["job_summary"]["title"] == "Produktleder"


def test_outcomes_dashboard_payload_summarizes_recent_feedback_and_persists(tmp_path) -> None:
    state_path = tmp_path / "reports" / "outcome_feedback_state.json"
    state = {
        "schema_version": "jobpipe.outcome-feedback-state.v1",
        "updated_at": "2026-04-19T20:00:00Z",
        "outcomes": {
            "run_a::job_1": {
                "schema_version": "jobpipe.outcome-feedback.v1",
                "external_source": "jobpipe",
                "external_id": "job_1",
                "run_id": "run_a",
                "final_decision": "APPLY",
                "shared_status": "interview",
                "outcome_label": "interview",
                "outcome_source": "manual",
                "app_notes": "",
                "updated_at": "2026-04-19T20:00:00Z",
                "artifact_refs_used": [{"kind": "resume_pdf"}],
                "decision_brief": {"schema_version": "jobpipe.decision-brief.v1", "final_decision": "APPLY"},
                "application_case_projection": {
                    "schema_version": "jobpipe.application-case-projection.v1",
                    "external_source": "jobpipe",
                    "external_id": "job_1",
                    "decision_brief": {"schema_version": "jobpipe.decision-brief.v1", "final_decision": "APPLY"},
                    "artifact_plan": {"schema_version": "jobpipe.artifact-plan.v1"},
                },
            },
            "run_b::job_2": {
                "schema_version": "jobpipe.outcome-feedback.v1",
                "external_source": "jobpipe",
                "external_id": "job_2",
                "run_id": "run_b",
                "final_decision": "REVIEW_HIGH",
                "shared_status": "dismissed",
                "outcome_label": "dismissed",
                "outcome_source": "manual",
                "app_notes": "",
                "updated_at": "2026-04-18T20:00:00Z",
                "artifact_refs_used": [],
                "decision_brief": {"schema_version": "jobpipe.decision-brief.v1", "final_decision": "REVIEW_HIGH"},
                "application_case_projection": {
                    "schema_version": "jobpipe.application-case-projection.v1",
                    "external_source": "jobpipe",
                    "external_id": "job_2",
                    "decision_brief": {"schema_version": "jobpipe.decision-brief.v1", "final_decision": "REVIEW_HIGH"},
                    "artifact_plan": {"schema_version": "jobpipe.artifact-plan.v1"},
                },
            },
        },
    }

    persist_outcome_feedback_state(state_path, state)
    stored = load_outcome_feedback_state(state_path)
    payload = build_outcomes_dashboard_payload(stored)

    assert payload["schema_version"] == "jobpipe.outcomes-dashboard.v1"
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["artifact_linked"] == 1
    assert payload["summary"]["by_status"]["interview"] == 1
    assert payload["summary"]["by_status"]["dismissed"] == 1
    assert payload["audit_summary"]["schema_version"] == "jobpipe.outcome-feedback-audit.v1"
    assert payload["audit_summary"]["tracked_total"] == 2
    assert payload["audit_summary"]["artifact_linked_total"] == 1
    assert payload["audit_summary"]["decision_status_matrix"]["APPLY"]["interview"] == 1
    assert payload["audit_summary"]["decision_status_matrix"]["REVIEW_HIGH"]["dismissed"] == 1
    assert payload["audit_summary"]["apply_path_summary"]["apply_like_total"] == 1
    assert payload["audit_summary"]["apply_path_summary"]["progressed_count"] == 1
    assert payload["audit_summary"]["artifact_effect_summary"]["progressed_with_artifacts"] == 1
    assert payload["audit_summary"]["artifact_effect_summary"]["closed_without_artifacts"] == 1
    assert payload["calibration_summary"]["schema_version"] == "jobpipe.outcome-feedback-calibration.v1"
    assert payload["calibration_summary"]["tracked_total"] == 2
    assert payload["calibration_summary"]["apply_like_total"] == 1
    assert payload["calibration_summary"]["apply_like_progressed"] == 1
    assert payload["calibration_summary"]["apply_like_progression_rate"] == 100.0
    assert payload["calibration_summary"]["non_apply_total"] == 1
    assert payload["calibration_summary"]["non_apply_progressed"] == 0
    assert payload["calibration_summary"]["artifact_linked_total"] == 1
    assert payload["calibration_summary"]["artifact_linked_progressed"] == 1
    assert payload["calibration_summary"]["no_artifact_progression_rate"] == 0.0
    assert payload["recommendation"]["schema_version"] == "jobpipe.outcome-feedback-recommendation.v1"
    assert payload["recommendation"]["decision_signal"] == "insufficient_signal"
    assert payload["recommendation"]["artifact_signal"] == "insufficient_signal"
    assert payload["recommendation"]["confidence"] == "low"
    assert payload["recommendation"]["recommended_next_action"] == "collect_more_outcomes"
    assert payload["shadow_followup"]["schema_version"] == "jobpipe.outcome-feedback-shadow-followup.v1"
    assert payload["shadow_followup"]["suggested_experiment"] == "collect_more_outcomes"
    assert payload["shadow_followup"]["ready_for_shadow"] is False
    assert payload["shadow_followup"]["confidence"] == "low"
    assert payload["recent_feedback"][0]["external_id"] == "job_1"


def test_build_outcome_ranking_guidance_compares_supported_vs_non_supported_variants() -> None:
    summary = build_outcome_ranking_guidance(
        [
            {
                "reviewed": 2,
                "useful_signal_rate": 80.0,
                "variant_review": {"verdict": "worth_promoting"},
                "outcome_shadow_fit": {"fit": "aligned"},
            },
            {
                "reviewed": 1,
                "useful_signal_rate": 25.0,
                "variant_review": {"verdict": "reject_variant"},
                "outcome_shadow_fit": {"fit": "indirect"},
            },
            {
                "reviewed": 1,
                "useful_signal_rate": 55.0,
                "variant_review": {"verdict": "needs_more_review"},
                "outcome_shadow_fit": {"fit": "watch"},
            },
        ]
    )

    assert summary["schema_version"] == "jobpipe.outcome-ranking-guidance.v1"
    assert summary["reviewed_variants"] == 3
    assert summary["supported_variants"] == 2
    assert summary["supported_avg_useful_rate"] == 67.5
    assert summary["supported_worth_promoting_rate"] == 50.0
    assert summary["non_supported_variants"] == 1
    assert summary["non_supported_avg_useful_rate"] == 25.0
    assert summary["quality_delta_useful_rate"] == 42.5
    assert summary["status"] == "supports_ranking_review"
    assert summary["confidence"] == "low"
