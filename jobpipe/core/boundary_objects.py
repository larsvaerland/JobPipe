from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from jobpipe.core.schema import (
    ApplicationCaseProjection,
    ArtifactPlan,
    AuthoringBrief,
    DecisionBrief,
    OutcomeFeedback,
)


DECISION_BRIEF_VERSION = "jobpipe.decision-brief.v1"
AUTHORING_BRIEF_VERSION = "jobpipe.authoring-brief.v1"
ARTIFACT_PLAN_VERSION = "jobpipe.artifact-plan.v1"
APPLICATION_CASE_PROJECTION_VERSION = "jobpipe.application-case-projection.v1"
OUTCOME_FEEDBACK_VERSION = "jobpipe.outcome-feedback.v1"


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clean_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def build_decision_brief(
    *,
    final_decision: str = "",
    triage_v3_label: str = "",
    fit_score: Optional[int] = None,
    pivot_score: Optional[int] = None,
    advantage_type: str = "",
    advantageous_match_score: Optional[int] = None,
    review_priority: Optional[int] = None,
    positioning_angle: str = "",
    brand_frame: str = "",
    applicant_pool_hypothesis: str = "",
    recruiter_hook: str = "",
    rationale: str = "",
    overlaps: Any = None,
    gaps: Any = None,
    differentiation_signals: Any = None,
    top_value_props: Any = None,
    cv_focus: Any = None,
    cover_letter_angle: str = "",
) -> Dict[str, Any]:
    brief = DecisionBrief(
        schema_version=DECISION_BRIEF_VERSION,
        final_decision=_clean_text(final_decision),
        triage_v3_label=_clean_text(triage_v3_label),
        fit_score=fit_score,
        pivot_score=pivot_score,
        advantage_type=_clean_text(advantage_type),
        advantageous_match_score=advantageous_match_score,
        review_priority=review_priority,
        positioning_angle=_clean_text(positioning_angle),
        brand_frame=_clean_text(brand_frame),
        applicant_pool_hypothesis=_clean_text(applicant_pool_hypothesis),
        recruiter_hook=_clean_text(recruiter_hook),
        rationale=_clean_text(rationale),
        overlaps=_clean_list(overlaps),
        gaps=_clean_list(gaps),
        differentiation_signals=_clean_list(differentiation_signals),
        top_value_props=_clean_list(top_value_props),
        cv_focus=_clean_list(cv_focus),
        cover_letter_angle=_clean_text(cover_letter_angle),
    )
    return brief.model_dump()


def build_artifact_plan(
    *,
    artifact_root: str = "",
    input_snapshot_path: str = "",
    save_targets: Optional[Dict[str, Any]] = None,
    generated_artifacts: Any = None,
) -> Dict[str, Any]:
    plan = ArtifactPlan(
        schema_version=ARTIFACT_PLAN_VERSION,
        artifact_root=_clean_text(artifact_root),
        input_snapshot_path=_clean_text(input_snapshot_path),
        save_targets=save_targets or {},
        generated_artifacts=generated_artifacts if isinstance(generated_artifacts, list) else [],
    )
    return plan.model_dump()


def build_authoring_brief(
    *,
    artifact_kind: str,
    objective: str = "",
    handoff_brief: str = "",
    launch_url: str = "",
    seed_text: str = "",
    inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    brief = AuthoringBrief(
        schema_version=AUTHORING_BRIEF_VERSION,
        artifact_kind=artifact_kind,  # validated by model
        objective=_clean_text(objective),
        handoff_brief=_clean_text(handoff_brief),
        launch_url=_clean_text(launch_url),
        seed_text=_clean_text(seed_text),
        inputs=inputs or {},
    )
    return brief.model_dump()


def build_application_case_projection(
    *,
    external_source: str,
    external_id: str,
    run_id: str = "",
    status: str = "",
    updated_at: str = "",
    job_summary: Optional[Dict[str, Any]] = None,
    decision_brief: Dict[str, Any],
    artifact_plan: Dict[str, Any],
) -> Dict[str, Any]:
    projection = ApplicationCaseProjection(
        schema_version=APPLICATION_CASE_PROJECTION_VERSION,
        external_source=_clean_text(external_source),
        external_id=_clean_text(external_id),
        run_id=_clean_text(run_id),
        status=_clean_text(status),
        updated_at=_clean_text(updated_at),
        job_summary=job_summary or {},
        decision_brief=DecisionBrief.model_validate(decision_brief),
        artifact_plan=ArtifactPlan.model_validate(artifact_plan),
    )
    return projection.model_dump()


def build_outcome_feedback(
    *,
    external_source: str,
    external_id: str,
    run_id: str = "",
    final_decision: str = "",
    shared_status: str = "",
    outcome_label: str = "",
    outcome_source: str = "",
    app_notes: str = "",
    updated_at: str = "",
    artifact_refs_used: Any = None,
    decision_brief: Dict[str, Any],
    application_case_projection: Dict[str, Any],
) -> Dict[str, Any]:
    feedback = OutcomeFeedback(
        schema_version=OUTCOME_FEEDBACK_VERSION,
        external_source=_clean_text(external_source),
        external_id=_clean_text(external_id),
        run_id=_clean_text(run_id),
        final_decision=_clean_text(final_decision),
        shared_status=_clean_text(shared_status),
        outcome_label=_clean_text(outcome_label),
        outcome_source=_clean_text(outcome_source),
        app_notes=_clean_text(app_notes),
        updated_at=_clean_text(updated_at),
        artifact_refs_used=artifact_refs_used if isinstance(artifact_refs_used, list) else [],
        decision_brief=DecisionBrief.model_validate(decision_brief),
        application_case_projection=ApplicationCaseProjection.model_validate(application_case_projection),
    )
    return feedback.model_dump()


def build_decision_brief_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    detail = row.get("detail")
    if not isinstance(detail, dict):
        detail = {}
    return build_decision_brief(
        final_decision=row.get("final_decision") or "",
        triage_v3_label=row.get("triage_v3_label") or detail.get("triage_v3_label") or "",
        fit_score=row.get("fit_score"),
        pivot_score=row.get("pivot_score"),
        advantage_type=row.get("advantage_type") or detail.get("advantage_type") or "",
        advantageous_match_score=row.get("advantageous_match_score") or detail.get("advantageous_match_score"),
        review_priority=row.get("advantage_review_priority") or detail.get("advantage_review_priority"),
        positioning_angle=row.get("narrative_positioning_angle") or detail.get("narrative_positioning_angle") or "",
        brand_frame=row.get("narrative_brand_frame") or detail.get("narrative_brand_frame") or "",
        applicant_pool_hypothesis=detail.get("applicant_pool_hypothesis") or "",
        recruiter_hook=detail.get("recruiter_hook") or "",
        rationale=row.get("recommendation_reason") or row.get("triage_explanation") or "",
        overlaps=detail.get("overlaps") or [],
        gaps=detail.get("gaps") or [],
        differentiation_signals=detail.get("differentiation_signals") or [],
        top_value_props=detail.get("top_value_props") or [],
        cv_focus=detail.get("cv_focus_mod") or [],
        cover_letter_angle=detail.get("cover_letter_angle") or "",
    )


def build_case_job_summary_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": _clean_text(row.get("title")),
        "company": _clean_text(row.get("employer")),
        "location": _clean_text(row.get("location")),
        "job_source": _clean_text(row.get("job_source") or "jobpipe"),
        "source_url": _clean_text(row.get("source_url")),
        "application_url": _clean_text(row.get("application_url")),
        "application_due": _clean_text(row.get("applicationDue")),
        "description_snippet": _clean_text(row.get("description_snip")),
    }


def build_case_job_summary(
    *,
    title: str = "",
    company: str = "",
    location: str = "",
    job_source: str = "jobpipe",
    source_url: str = "",
    application_url: str = "",
    application_due: str = "",
    description_snippet: str = "",
) -> Dict[str, Any]:
    return {
        "title": _clean_text(title),
        "company": _clean_text(company),
        "location": _clean_text(location),
        "job_source": _clean_text(job_source),
        "source_url": _clean_text(source_url),
        "application_url": _clean_text(application_url),
        "application_due": _clean_text(application_due),
        "description_snippet": _clean_text(description_snippet),
    }


def build_artifact_plan_from_job_dir(
    *,
    job_dir: Path,
    save_targets: Optional[Dict[str, Any]] = None,
    generated_artifacts: Any = None,
) -> Dict[str, Any]:
    input_snapshot_path = job_dir / "00_input.json"
    return build_artifact_plan(
        artifact_root=str(job_dir),
        input_snapshot_path=str(input_snapshot_path),
        save_targets=save_targets or {},
        generated_artifacts=generated_artifacts,
    )
