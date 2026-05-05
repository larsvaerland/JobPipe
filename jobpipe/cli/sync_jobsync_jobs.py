from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from jobpipe.cli.export_dashboard import build_payload
from jobpipe.core.boundary_objects import (
    build_application_case_projection,
    build_artifact_plan,
    build_case_job_summary,
    build_decision_brief_from_row,
)
from jobpipe.core.jobsync import (
    APPLICATION_PACKET_VERSION,
    build_connector_envelope,
    load_jobsync_settings,
    post_jobsync_json,
    resolve_jobsync_user_email,
    write_jobsync_outbox,
)
from jobpipe.core.paths import bootstrap_private_data, get_jobpipe_paths


DEFAULT_DECISIONS = ("APPLY", "APPLY_STRONGLY")


def _parse_decisions(raw: str) -> List[str]:
    values = [part.strip().upper() for part in str(raw or "").split(",")]
    return [value for value in values if value]


def _location_text(row: Dict[str, Any]) -> str:
    parts = [str(row.get("work_city") or "").strip(), str(row.get("work_county") or "").strip()]
    return ", ".join(part for part in parts if part)


def _artifacts_path(data_root: Path, row: Dict[str, Any]) -> str:
    run_id = str(row.get("run_id") or "").strip()
    job_id = str(row.get("job_id") or "").strip()
    if not run_id or not job_id:
        return ""
    return str(data_root / "out_runs" / run_id / job_id)


def _input_snapshot_path(data_root: Path, row: Dict[str, Any]) -> str:
    artifacts = _artifacts_path(data_root, row)
    if not artifacts:
        return ""
    return str(Path(artifacts) / "00_input.json")


def _packet_analysis(row: Dict[str, Any]) -> Dict[str, Any]:
    detail = row.get("detail")
    if not isinstance(detail, dict):
        detail = {}
    return {
        "jobpipeStatus": str(row.get("app_status") or ""),
        "decision": str(row.get("final_decision") or ""),
        "fitScore": row.get("fit_score"),
        "pivotScore": row.get("pivot_score"),
        "rationale": str(row.get("recommendation_reason") or row.get("triage_explanation") or ""),
        "overlaps": list(detail.get("overlaps") or []),
        "gaps": list(detail.get("gaps") or []),
        "hardBlockers": list(detail.get("hard_blockers") or []),
        "matchNotes": str(detail.get("match_notes") or ""),
        "pivotType": str(detail.get("pivot_type") or ""),
        "pivotRisk": str(detail.get("pivot_risk") or ""),
        "pivotWhy": list(detail.get("pivot_why") or []),
    }


def _packet_drafting(row: Dict[str, Any]) -> Dict[str, Any]:
    detail = row.get("detail")
    if not isinstance(detail, dict):
        detail = {}
    return {
        "packReady": bool(row.get("pack_ready")),
        "packGeneratedAt": str(row.get("pack_generated_at") or ""),
        "packHasCoverLetter": bool(row.get("pack_has_cover_letter")),
        "packDocxReady": bool(row.get("pack_docx_ready")),
        "packHighlightCount": row.get("pack_highlight_count"),
        "cvFocus": str(row.get("cv_focus") or ""),
        "feedbackFlags": str(row.get("feedback_flags") or ""),
        "moderatorCvFocus": list(detail.get("cv_focus_mod") or []),
        "moderatorFeedbackFlags": list(detail.get("feedback_flags_mod") or []),
    }


def _build_application_packet(
    row: Dict[str, Any],
    *,
    decision_brief: Dict[str, Any],
    artifact_plan: Dict[str, Any],
    case_projection: Dict[str, Any],
) -> Dict[str, Any]:
    job_summary = case_projection.get("job_summary", {}) if isinstance(case_projection, dict) else {}
    if not isinstance(job_summary, dict):
        job_summary = {}
    return {
        "packetVersion": APPLICATION_PACKET_VERSION,
        "createdAt": str(row.get("updated_at") or ""),
        "artifactsPath": str(artifact_plan.get("artifact_root") or ""),
        "inputSnapshotPath": str(artifact_plan.get("input_snapshot_path") or ""),
        "job": {
            "title": str(job_summary.get("title") or ""),
            "company": str(job_summary.get("company") or ""),
            "location": str(job_summary.get("location") or ""),
            "jobSource": str(job_summary.get("job_source") or "jobpipe"),
            "sourceUrl": str(job_summary.get("source_url") or ""),
            "applicationUrl": str(job_summary.get("application_url") or ""),
            "applicationDue": str(job_summary.get("application_due") or ""),
            "descriptionSnippet": str(job_summary.get("description_snippet") or ""),
        },
        "analysis": {
            **_packet_analysis(row),
            "decision": str(decision_brief.get("final_decision") or ""),
            "fitScore": decision_brief.get("fit_score"),
            "pivotScore": decision_brief.get("pivot_score"),
            "rationale": str(decision_brief.get("rationale") or ""),
            "overlaps": list(decision_brief.get("overlaps") or []),
            "gaps": list(decision_brief.get("gaps") or []),
        },
        "drafting": _packet_drafting(row),
        "generatedArtifacts": list(artifact_plan.get("generated_artifacts") or []),
    }


def _build_import_record(paths, row: Dict[str, Any]) -> Dict[str, Any]:
    decision_brief = build_decision_brief_from_row(row)
    artifact_plan = build_artifact_plan(
        artifact_root=_artifacts_path(paths.data_root, row),
        input_snapshot_path=_input_snapshot_path(paths.data_root, row),
        generated_artifacts=list(row.get("generated_documents") or []),
    )
    case_projection = build_application_case_projection(
        external_source="jobpipe",
        external_id=str(row.get("job_id") or ""),
        run_id=str(row.get("run_id") or ""),
        status="new",
        updated_at=str(row.get("updated_at") or ""),
        job_summary=build_case_job_summary(
            title=str(row.get("title") or ""),
            company=str(row.get("employer") or ""),
            location=_location_text(row),
            job_source=str(row.get("job_source") or "jobpipe"),
            source_url=str(row.get("source_url") or ""),
            application_url=str(row.get("application_url") or ""),
            application_due=str(row.get("applicationDue") or ""),
            description_snippet=str(row.get("description_snip") or ""),
        ),
        decision_brief=decision_brief,
        artifact_plan=artifact_plan,
    )
    job_summary = case_projection.get("job_summary", {}) if isinstance(case_projection, dict) else {}
    if not isinstance(job_summary, dict):
        job_summary = {}
    return {
        "externalSource": "jobpipe",
        "externalId": str(row.get("job_id") or ""),
        "runId": str(row.get("run_id") or ""),
        "title": str(job_summary.get("title") or ""),
        "company": str(job_summary.get("company") or ""),
        "location": str(job_summary.get("location") or ""),
        "jobUrl": str(job_summary.get("source_url") or ""),
        "applicationUrl": str(job_summary.get("application_url") or ""),
        "description": str(job_summary.get("description_snippet") or ""),
        "jobSource": str(job_summary.get("job_source") or "jobpipe"),
        "status": "new",
        "jobpipeStatus": str(row.get("app_status") or ""),
        "decision": str(decision_brief.get("final_decision") or ""),
        "fitScore": decision_brief.get("fit_score"),
        "pivotScore": decision_brief.get("pivot_score"),
        "triageExplanation": str(decision_brief.get("rationale") or ""),
        "artifactsPath": str(artifact_plan.get("artifact_root") or ""),
        "packReady": bool(row.get("pack_ready")),
        "packDocxReady": bool(row.get("pack_docx_ready")),
        "updatedAt": str(case_projection.get("updated_at") or row.get("updated_at") or ""),
        "decisionBrief": decision_brief,
        "artifactPlan": artifact_plan,
        "applicationCaseProjection": case_projection,
        "applicationPacket": _build_application_packet(
            row,
            decision_brief=decision_brief,
            artifact_plan=artifact_plan,
            case_projection=case_projection,
        ),
    }


def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Sync curated JobPipe jobs into JobSync.")
    ap.add_argument("--data-root", default="", help="JobPipe user data root")
    ap.add_argument("--user-email", default="", help="Override JobSync target user email")
    ap.add_argument(
        "--decisions",
        default=",".join(DEFAULT_DECISIONS),
        help="Comma-separated final decisions to import",
    )
    ap.add_argument("--max", type=int, default=0, help="Maximum number of jobs to send")
    ap.add_argument("--emit-outbox", action="store_true", help="Write the connector envelope to the local outbox")
    ap.add_argument("--outbox-only", action="store_true", help="Write the connector envelope only, without POSTing")
    ap.add_argument("--dry-run", action="store_true", help="Preview payload only")
    args = ap.parse_args(argv)

    paths = get_jobpipe_paths(args.data_root or None)
    bootstrap_private_data(paths, include_artifacts=False)
    user_email = resolve_jobsync_user_email(paths, args.user_email)

    payload = build_payload(
        sqlite_path=paths.ledger_sqlite_path,
        out_dir=paths.out_runs_dir,
        state_path=paths.application_state_path,
        config_path=paths.default_config_path,
        profile_path=paths.profile_pack_path,
        resume_path=paths.resume_json_path,
        profile_draft_path=paths.profile_builder_state_path,
    )

    decisions = set(_parse_decisions(args.decisions))
    rows = [row for row in payload.get("jobs", []) if str(row.get("final_decision") or "") in decisions]
    if args.max > 0:
        rows = rows[: args.max]

    jobs = [_build_import_record(paths, row) for row in rows]
    envelope = build_connector_envelope("curated_jobs_import", user_email, {"jobs": jobs})

    if args.dry_run:
        print(json.dumps(envelope, ensure_ascii=False, indent=2))
        print(f"\n[DRY RUN] Prepared {len(jobs)} curated jobs for JobSync import.")
        return

    if not jobs:
        print("No curated jobs matched the selected decisions.")
        return

    if args.emit_outbox or args.outbox_only:
        outbox_path = write_jobsync_outbox(paths, "curated_jobs_import", envelope)
        print(f"[OK] Wrote connector envelope to {outbox_path}")
        if args.outbox_only:
            return

    settings = load_jobsync_settings(paths)
    response = post_jobsync_json(
        settings,
        settings.jobs_import_path,
        envelope,
    )
    print(
        f"[OK] Imported {int(response.get('created', 0))} created / "
        f"{int(response.get('updated', 0))} updated jobs into JobSync."
    )


if __name__ == "__main__":
    main()
