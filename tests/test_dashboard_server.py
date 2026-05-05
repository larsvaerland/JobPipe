from __future__ import annotations

import json
from pathlib import Path

from jobpipe.cli.dashboard_server import (
    APPLY_SESSION_VERSION,
    AUTHORING_STATE_VERSION,
    _gen_status,
    _build_pack_payload,
    _build_apply_session_manifest,
    _build_chat_system_prompt,
    _load_authoring_state,
    _load_workspace_context,
    _persist_authoring_state,
    _persist_application_notes,
    _persist_apply_session_manifest,
    _persist_experiment_review,
    _persist_experiment_promotion_review,
    _persist_experiment_variant_review,
    _persist_profile_draft,
    _persist_settings_payload,
    _run_generation,
)
from jobpipe.cli.mark_status import load_state


def test_persist_application_notes_updates_application_state(tmp_path: Path) -> None:
    state_path = tmp_path / "reports" / "application_state.json"

    entry = _persist_application_notes(state_path, "nav_001", "Follow up next week")
    state = load_state(state_path)

    assert entry["notes"] == "Follow up next week"
    assert entry["updated_at"].endswith("Z")
    assert state["applications"]["nav_001"]["notes"] == "Follow up next week"
    assert state["applications"]["nav_001"]["status"] == ""


def test_persist_experiment_review_updates_local_review_state(tmp_path: Path) -> None:
    state_path = tmp_path / "reports" / "experiment_review_state.json"

    entry = _persist_experiment_review(
        state_path,
        experiment_id="shadow_1",
        job_id="nav_001",
        verdict="correct_miss",
        run_id="run_1",
        review_reason="promoted_from_discard",
        review_priority=255,
    )

    stored = json.loads(state_path.read_text(encoding="utf-8"))
    assert entry["verdict"] == "correct_miss"
    assert entry["updated_at"].endswith("Z")
    assert stored["reviews"]["shadow_1::nav_001"]["review_reason"] == "promoted_from_discard"

    cleared = _persist_experiment_review(
        state_path,
        experiment_id="shadow_1",
        job_id="nav_001",
        verdict="",
    )

    stored_after = json.loads(state_path.read_text(encoding="utf-8"))
    assert cleared == {}
    assert stored_after["reviews"] == {}


def test_persist_experiment_variant_review_updates_local_review_state(tmp_path: Path) -> None:
    state_path = tmp_path / "reports" / "experiment_review_state.json"

    entry = _persist_experiment_variant_review(
        state_path,
        experiment_id="shadow_1",
        verdict="worth_promoting",
        candidate_name="triage_v3_threshold_variant",
        kind="shadow_threshold_eval",
    )

    stored = json.loads(state_path.read_text(encoding="utf-8"))
    assert entry["verdict"] == "worth_promoting"
    assert entry["candidate_name"] == "triage_v3_threshold_variant"
    assert stored["variant_reviews"]["shadow_1"]["kind"] == "shadow_threshold_eval"

    cleared = _persist_experiment_variant_review(
        state_path,
        experiment_id="shadow_1",
        verdict="",
    )

    stored_after = json.loads(state_path.read_text(encoding="utf-8"))
    assert cleared == {}
    assert stored_after["variant_reviews"] == {}


def test_persist_experiment_promotion_review_updates_local_review_state(tmp_path: Path) -> None:
    state_path = tmp_path / "reports" / "experiment_review_state.json"

    entry = _persist_experiment_promotion_review(
        state_path,
        experiment_id="shadow_1",
        verdict="accepted_for_promotion",
        candidate_name="triage_v3_threshold_variant",
        kind="shadow_threshold_eval",
    )

    stored = json.loads(state_path.read_text(encoding="utf-8"))
    assert entry["verdict"] == "accepted_for_promotion"
    assert stored["promotion_reviews"]["shadow_1"]["kind"] == "shadow_threshold_eval"

    cleared = _persist_experiment_promotion_review(
        state_path,
        experiment_id="shadow_1",
        verdict="",
    )

    stored_after = json.loads(state_path.read_text(encoding="utf-8"))
    assert cleared == {}
    assert stored_after["promotion_reviews"] == {}


def test_persist_profile_draft_normalizes_values_before_writing(tmp_path: Path) -> None:
    draft_path = tmp_path / "reports" / "profile_builder_state.json"

    clean = _persist_profile_draft(
        draft_path,
        {
            "headline": "Endringsleder | Produkteier",
            "experience_years": 12,
            "summary": None,
        },
    )

    stored = json.loads(draft_path.read_text(encoding="utf-8"))
    assert clean == stored
    assert stored["headline"] == "Endringsleder | Produkteier"
    assert stored["experience_years"] == "12"
    assert "summary" not in stored


def test_build_apply_session_manifest_exposes_launch_urls_and_save_targets(tmp_path: Path) -> None:
    job_dir = tmp_path / "out_runs" / "run_1" / "nav_123"
    job_dir.mkdir(parents=True)
    (job_dir / "cover_letter_draft.txt").write_text("Kort utkast", encoding="utf-8")
    (job_dir / "10_tailored_resume.pdf").write_bytes(b"%PDF-test")

    manifest = _build_apply_session_manifest(
        job_id="nav_123",
        job_dir=job_dir,
        job={
            "title": "Produktleder",
            "employer_name": "Avinor",
            "work_city": "Oslo",
            "work_county": "Oslo",
            "applicationDue": "2026-05-01",
            "sourceurl": "https://example.test/ad",
            "applicationUrl": "https://example.test/apply",
        },
        pack={
            "positioning_headline": "Sterk brobygger mellom produkt og drift",
            "cover_letter_angle": "Knytt erfaring med operativ digitalisering til rollen.",
            "top_value_props": ["Produktledelse", "Tverrfaglig samhandling"],
            "evidence_map": ["Produktbehov -> leveranser"],
            "gap_mitigations": ["Oversett relevant erfaring tydelig"],
            "cv_highlights": ["Ledet produktteam"],
            "cover_letter_text": "Ferdig søknadsutkast",
            "interview_prep": ["Hvordan prioriterer du i et komplekst backlog?"],
        },
        match={
            "fit_score": 84,
            "overlaps": ["Produktledelse"],
            "gaps": ["Ingen luftfartsbakgrunn"],
        },
        pivot={
            "pivot_score": 62,
            "pivot_type": "adjacent",
            "potential_risk": "low",
        },
        moderator={
            "final_decision": "APPLY_STRONGLY",
            "cv_focus": ["Produktansvar", "Gjennomføring"],
        },
        cover_letter_draft="Kort utkast",
        reactive_resume_base_url="http://localhost:3000",
        document_workspace_base_url="https://docs.example.test/workspace",
    )

    assert manifest["sessionVersion"] == APPLY_SESSION_VERSION
    assert manifest["saveback"]["registrationEndpoint"] == "/api/authoring/nav_123"
    assert manifest["authoringState"]["schemaVersion"] == AUTHORING_STATE_VERSION
    assert manifest["job"]["title"] == "Produktleder"
    assert manifest["job"]["applicationUrl"] == "https://example.test/apply"
    assert manifest["launch"]["openUrls"] == [
        {"label": "job_ad", "url": "https://example.test/ad"},
        {"label": "application_portal", "url": "https://example.test/apply"},
    ]
    assert manifest["saveTargets"]["cover_letter_draft_txt"]["exists"] is True
    assert manifest["saveTargets"]["tailored_resume_pdf"]["exists"] is True
    assert manifest["saveTargets"]["cover_letter_docx"]["exists"] is False
    assert manifest["decisionBrief"]["schema_version"] == "jobpipe.decision-brief.v1"
    assert manifest["decisionBrief"]["final_decision"] == "APPLY_STRONGLY"
    assert manifest["decisionBrief"]["fit_score"] == 84
    assert manifest["authoringBriefs"]["resume"]["schema_version"] == "jobpipe.authoring-brief.v1"
    assert manifest["authoringBriefs"]["resume"]["artifact_kind"] == "resume"
    assert manifest["authoringBriefs"]["coverLetter"]["seed_text"] == "Kort utkast"
    assert manifest["artifactPlan"]["schema_version"] == "jobpipe.artifact-plan.v1"
    assert manifest["artifactPlan"]["save_targets"]["tailored_resume_pdf"]["exists"] is True
    assert manifest["jobSummary"]["title"] == "Produktleder"
    assert manifest["jobSummary"]["company"] == "Avinor"
    assert manifest["job"]["title"] == manifest["jobSummary"]["title"]
    assert manifest["job"]["employer"] == manifest["jobSummary"]["company"]
    assert manifest["job"]["applicationUrl"] == manifest["jobSummary"]["application_url"]
    assert manifest["analysis"]["pivotScore"] == 62
    assert manifest["analysis"]["finalDecision"] == manifest["decisionBrief"]["final_decision"]
    assert manifest["analysis"]["topValueProps"] == manifest["decisionBrief"]["top_value_props"]
    assert manifest["analysis"]["cvFocus"] == manifest["decisionBrief"]["cv_focus"]
    assert manifest["authoring"]["resume"]["saveTargets"]["pdf"].endswith("10_tailored_resume.pdf")
    assert manifest["authoring"]["resume"]["status"] == "external_planned"
    assert manifest["authoring"]["resume"]["launchUrl"] == "http://localhost:3000"
    assert "Tailor a resume variant for: Produktleder @ Avinor" in manifest["authoring"]["resume"]["handoffBrief"]
    assert manifest["authoring"]["coverLetter"]["seedText"] == "Kort utkast"
    assert manifest["authoring"]["coverLetter"]["launchUrl"] == "https://docs.example.test/workspace"
    assert "Draft a tailored cover letter for: Produktleder @ Avinor" in manifest["authoring"]["coverLetter"]["handoffBrief"]
    assert manifest["authoring"]["screeningAnswers"]["launchUrl"] == "https://docs.example.test/workspace"
    assert "Prepare screening-answer material for: Produktleder @ Avinor" in manifest["authoring"]["screeningAnswers"]["handoffBrief"]
    assert manifest["authoring"]["resume"]["saveTargets"]["pdf"] == manifest["artifactPlan"]["save_targets"]["tailored_resume_pdf"]["path"]
    assert manifest["authoring"]["coverLetter"]["saveTargets"]["docx"] == manifest["artifactPlan"]["save_targets"]["cover_letter_docx"]["path"]
    assert manifest["saveTargets"] == manifest["artifactPlan"]["save_targets"]


def test_build_apply_session_manifest_prefers_projection_boundary_objects_when_provided(tmp_path: Path) -> None:
    job_dir = tmp_path / "out_runs" / "run_1" / "nav_124"
    job_dir.mkdir(parents=True)

    manifest = _build_apply_session_manifest(
        job_id="nav_124",
        job_dir=job_dir,
        job={
            "title": "Gammel tittel",
            "employer_name": "Gammel arbeidsgiver",
            "work_city": "Bergen",
            "work_county": "Vestland",
            "applicationDue": "2026-05-01",
            "sourceurl": "https://example.test/old-ad",
            "applicationUrl": "https://example.test/old-apply",
        },
        pack={
            "positioning_headline": "Gammelt fokus",
            "cover_letter_angle": "Gammel vinkel",
            "top_value_props": ["Gammelt poeng"],
        },
        match={"fit_score": 61, "overlaps": ["Gammel overlap"], "gaps": ["Gammelt gap"]},
        pivot={"pivot_score": 44},
        moderator={"final_decision": "REVIEW_LOW", "cv_focus": ["Gammelt fokus"]},
        cover_letter_draft="",
        decision_brief_override={
            "schema_version": "jobpipe.decision-brief.v1",
            "final_decision": "APPLY_STRONGLY",
            "fit_score": 91,
            "pivot_score": 63,
            "overlaps": ["Ny overlap"],
            "gaps": ["Nytt gap"],
            "top_value_props": ["Nytt poeng"],
            "cv_focus": ["Nytt fokus"],
            "cover_letter_angle": "Ny vinkel",
        },
        job_summary_override={
            "title": "Ny tittel",
            "company": "Ny arbeidsgiver",
            "location": "Oslo, Oslo",
            "job_source": "nav",
            "source_url": "https://example.test/new-ad",
            "application_url": "https://example.test/new-apply",
            "application_due": "2026-06-02",
            "description_snippet": "Kort oppsummering.",
        },
    )

    assert manifest["decisionBrief"]["final_decision"] == "APPLY_STRONGLY"
    assert manifest["decisionBrief"]["fit_score"] == 91
    assert manifest["analysis"]["finalDecision"] == "APPLY_STRONGLY"
    assert manifest["analysis"]["fitScore"] == 91
    assert manifest["analysis"]["topValueProps"] == ["Nytt poeng"]
    assert manifest["analysis"]["cvFocus"] == ["Nytt fokus"]
    assert manifest["jobSummary"]["title"] == "Ny tittel"
    assert manifest["jobSummary"]["company"] == "Ny arbeidsgiver"
    assert manifest["job"]["title"] == "Ny tittel"
    assert manifest["job"]["employer"] == "Ny arbeidsgiver"
    assert manifest["job"]["applicationUrl"] == "https://example.test/new-apply"
    assert manifest["launch"]["openUrls"] == [
        {"label": "job_ad", "url": "https://example.test/new-ad"},
        {"label": "application_portal", "url": "https://example.test/new-apply"},
    ]


def test_build_pack_payload_prefers_projection_boundary_objects_when_present(tmp_path: Path) -> None:
    job_dir = tmp_path / "out_runs" / "run_1" / "nav_125"
    job_dir.mkdir(parents=True)

    payload = _build_pack_payload(
        job_id="nav_125",
        ctx={
            "job_dir": job_dir,
            "job": {
                "title": "Gammel tittel",
                "employer_name": "Gammel arbeidsgiver",
                "applicationDue": "2026-05-01",
                "sourceurl": "https://example.test/old-ad-pack",
                "applicationUrl": "https://example.test/old-apply-pack",
                "description": "Gammel beskrivelse",
            },
            "pack": {
                "positioning_headline": "Sterk retning",
                "top_value_props": ["Fra pack"],
                "cover_letter_angle": "Fra pack",
            },
            "match": {
                "fit_score": 61,
                "overlaps": ["Fra match"],
                "gaps": ["Fra gap"],
            },
            "pivot": {"pivot_score": 44},
            "moderator": {"final_decision": "REVIEW_LOW", "cv_focus": ["Fra moderator"]},
            "detail_projection": {
                "decision_brief": {
                    "schema_version": "jobpipe.decision-brief.v1",
                    "final_decision": "APPLY",
                    "fit_score": 87,
                    "pivot_score": 52,
                    "overlaps": ["Fra projection overlap"],
                    "gaps": ["Fra projection gap"],
                    "top_value_props": ["Fra projection value"],
                    "cv_focus": ["Fra projection focus"],
                    "cover_letter_angle": "Fra projection angle",
                },
                "application_case_projection": {
                    "job_summary": {
                        "title": "Ny tittel",
                        "company": "Ny arbeidsgiver",
                        "source_url": "https://example.test/new-ad-pack",
                        "application_url": "https://example.test/new-apply-pack",
                        "application_due": "2026-06-03",
                        "description_snippet": "Projection-sammendrag",
                    }
                },
            },
            "has_docx": True,
            "cover_letter_draft": "Kort utkast",
        },
    )

    assert payload["job"]["title"] == "Ny tittel"
    assert payload["job"]["employer"] == "Ny arbeidsgiver"
    assert payload["job"]["source_url"] == "https://example.test/new-ad-pack"
    assert payload["job"]["application_url"] == "https://example.test/new-apply-pack"
    assert payload["job"]["deadline"] == "2026-06-03"
    assert payload["job"]["description_snip"] == "Projection-sammendrag"
    assert payload["jobSummary"]["title"] == "Ny tittel"
    assert payload["decisionBrief"]["final_decision"] == "APPLY"
    assert payload["decisionBrief"]["fit_score"] == 87
    assert payload["overlaps"] == ["Fra projection overlap"]
    assert payload["gaps"] == ["Fra projection gap"]
    assert payload["pack"]["positioning_headline"] == "Sterk retning"
    assert payload["has_docx"] is True
    assert payload["cover_letter_draft"] == "Kort utkast"


def test_persist_apply_session_manifest_writes_json_file(tmp_path: Path) -> None:
    job_dir = tmp_path / "out_runs" / "run_1" / "nav_456"
    job_dir.mkdir(parents=True)

    manifest = {"sessionVersion": APPLY_SESSION_VERSION, "jobId": "nav_456", "generatedAt": "2026-04-18T10:00:00Z"}
    stored = _persist_apply_session_manifest(job_dir, manifest)

    saved = json.loads((job_dir / "apply_session.json").read_text(encoding="utf-8"))
    assert stored == manifest
    assert saved == manifest


def test_load_authoring_state_defaults_to_deterministic_export_targets(tmp_path: Path) -> None:
    job_dir = tmp_path / "out_runs" / "run_1" / "nav_999"
    job_dir.mkdir(parents=True)

    state = _load_authoring_state(job_dir, "nav_999")

    assert state["schemaVersion"] == AUTHORING_STATE_VERSION
    assert state["jobId"] == "nav_999"
    assert state["resume"]["exportRef"] == ""
    assert state["resume"]["exportFormat"] == "pdf"
    assert state["resume"]["exportPdfPath"].endswith("10_tailored_resume.pdf")
    assert state["resume"]["exportJsonPath"].endswith("10_tailored_resume.json")
    assert state["coverLetter"]["exportDocxPath"].endswith("08_cover_letter.docx")
    assert state["screeningAnswers"]["exportDocxPath"].endswith("09_screening_answers.docx")


def test_persist_authoring_state_merges_manual_refs_and_sanitizes_artifacts(tmp_path: Path) -> None:
    job_dir = tmp_path / "out_runs" / "run_1" / "nav_321"
    job_dir.mkdir(parents=True)

    stored = _persist_authoring_state(
        job_dir,
        "nav_321",
        {
            "resume": {
                "variantRef": " rr:resume-123 ",
                "variantLabel": " Tailored Bane NOR ",
                "sourceUrl": " http://localhost:3000/resumes/123 ",
                "exportRef": " rr-export-123 ",
                "exportLabel": " Tailored Resume PDF ",
                "exportUrl": " http://localhost:3000/exports/123.pdf ",
                "exportFormat": " PDF ",
                "artifactRefs": [
                    {
                        "kind": "resume_pdf",
                        "label": " PDF export ",
                        "path": " C:/Users/example/JobpipeData/out_runs/run_1/nav_321/10_tailored_resume.pdf ",
                    },
                    "skip-me",
                ],
            },
            "coverLetter": {
                "documentRef": " word-doc-77 ",
                "documentLabel": " Cover letter draft ",
                "sourceUrl": " https://docs.example.test/cover-letter ",
                "exportRef": " cover-export-77 ",
                "exportLabel": " Final cover letter DOCX ",
                "exportUrl": " https://docs.example.test/export/cover-letter ",
                "exportFormat": " DOCX ",
            },
            "screeningAnswers": {
                "documentRef": " screening-doc-77 ",
                "documentLabel": " Screening answers draft ",
                "sourceUrl": " https://docs.example.test/screening ",
                "exportRef": " screening-export-77 ",
                "exportLabel": " Final screening answers DOCX ",
                "exportUrl": " https://docs.example.test/export/screening ",
            },
        },
    )

    assert stored["updatedAt"].endswith("Z")
    assert stored["resume"]["variantRef"] == "rr:resume-123"
    assert stored["resume"]["variantLabel"] == "Tailored Bane NOR"
    assert stored["resume"]["sourceUrl"] == "http://localhost:3000/resumes/123"
    assert stored["resume"]["exportRef"] == "rr-export-123"
    assert stored["resume"]["exportLabel"] == "Tailored Resume PDF"
    assert stored["resume"]["exportUrl"] == "http://localhost:3000/exports/123.pdf"
    assert stored["resume"]["exportFormat"] == "PDF"
    assert stored["resume"]["exportedAt"].endswith("Z")
    assert stored["resume"]["artifactRefs"] == [
        {
            "kind": "resume_pdf",
            "label": "PDF export",
            "path": "C:/Users/example/JobpipeData/out_runs/run_1/nav_321/10_tailored_resume.pdf",
            "url": "",
        }
    ]
    assert stored["coverLetter"]["documentRef"] == "word-doc-77"
    assert stored["coverLetter"]["documentLabel"] == "Cover letter draft"
    assert stored["coverLetter"]["sourceUrl"] == "https://docs.example.test/cover-letter"
    assert stored["coverLetter"]["exportRef"] == "cover-export-77"
    assert stored["coverLetter"]["exportLabel"] == "Final cover letter DOCX"
    assert stored["coverLetter"]["exportUrl"] == "https://docs.example.test/export/cover-letter"
    assert stored["coverLetter"]["exportFormat"] == "DOCX"
    assert stored["coverLetter"]["exportedAt"].endswith("Z")
    assert stored["screeningAnswers"]["documentRef"] == "screening-doc-77"
    assert stored["screeningAnswers"]["documentLabel"] == "Screening answers draft"
    assert stored["screeningAnswers"]["sourceUrl"] == "https://docs.example.test/screening"
    assert stored["screeningAnswers"]["exportRef"] == "screening-export-77"
    assert stored["screeningAnswers"]["exportLabel"] == "Final screening answers DOCX"
    assert stored["screeningAnswers"]["exportUrl"] == "https://docs.example.test/export/screening"
    assert stored["screeningAnswers"]["exportFormat"] == "docx"
    assert stored["screeningAnswers"]["exportedAt"].endswith("Z")

    manifest = _build_apply_session_manifest(
        job_id="nav_321",
        job_dir=job_dir,
        job={"title": "Produktleder", "employer_name": "Bane NOR"},
        pack={},
        match={},
        pivot={},
        moderator={},
        cover_letter_draft="",
        authoring_state=stored,
    )

    assert manifest["authoring"]["resume"]["status"] == "export_registered"
    assert manifest["authoring"]["coverLetter"]["status"] == "export_registered"
    assert manifest["authoring"]["screeningAnswers"]["status"] == "export_registered"
    assert manifest["authoringState"]["resume"]["variantRef"] == "rr:resume-123"
    assert manifest["authoringState"]["resume"]["exportRef"] == "rr-export-123"
    assert manifest["authoringState"]["coverLetter"]["exportRef"] == "cover-export-77"
    assert manifest["authoringState"]["screeningAnswers"]["exportRef"] == "screening-export-77"


def test_persist_settings_payload_writes_sanitized_local_state(tmp_path: Path) -> None:
    settings_path = tmp_path / "reports" / "settings_state.json"

    clean = _persist_settings_payload(
        settings_path,
        {
            "targeting": {
                "primary_roles_text": "Produktleder\nTjenesteeier",
                "domain_focus_text": "Offentlig sektor\nDigitalisering",
            },
            "integrations": {
                "jobsync": {"enabled": "true", "base_url": "http://localhost:3737"},
                "document_workspace": {"enabled": 1, "base_url": "https://docs.example.test/workspace"},
                "gmail": {"status_detection_enabled": 1, "lead_intake_enabled": 0},
            },
        },
    )

    stored = json.loads(settings_path.read_text(encoding="utf-8"))
    assert clean == stored
    assert stored["targeting"]["primary_roles_text"] == "Produktleder\nTjenesteeier"
    assert stored["targeting"]["domain_focus_text"] == "Offentlig sektor\nDigitalisering"
    assert stored["integrations"]["jobsync"]["enabled"] is True
    assert stored["integrations"]["jobsync"]["base_url"] == "http://localhost:3737"
    assert stored["integrations"]["document_workspace"]["enabled"] is True
    assert stored["integrations"]["document_workspace"]["base_url"] == "https://docs.example.test/workspace"
    assert stored["integrations"]["gmail"]["status_detection_enabled"] is True
    assert stored["integrations"]["gmail"]["lead_intake_enabled"] is False
    assert stored["updated_at"].endswith("Z")


def test_load_workspace_context_falls_back_to_projection_store_when_input_missing(tmp_path: Path) -> None:
    from jobpipe.cli import dashboard_server as server_mod
    from jobpipe.core.paths import get_jobpipe_paths
    from jobpipe.core.projection_store import persist_projection_store

    paths = get_jobpipe_paths(data_root=tmp_path, repo=tmp_path)
    paths.ensure_data_dirs()
    original_paths = server_mod.PATHS

    try:
        server_mod._apply_paths(paths)
        job_dir = paths.out_runs_dir / "run_proj" / "nav_proj_ctx"
        job_dir.mkdir(parents=True)
        (job_dir / "08_application_pack.json").write_text("{}", encoding="utf-8")
        (job_dir / "03_profile_match.json").write_text('{"fit_score": 80}', encoding="utf-8")
        (job_dir / "04_pivot.json").write_text('{"pivot_score": 61}', encoding="utf-8")
        (job_dir / "07_moderator.json").write_text('{"final_decision": "APPLY"}', encoding="utf-8")

        persist_projection_store(
            paths.projection_store_path,
            {
                "inputEnrichment": {
                    "run_proj::nav_proj_ctx": {
                        "employer": "Avinor",
                        "normalized_title": "produktleder",
                        "application_url": "https://example.test/apply_ctx",
                        "source_url": "https://example.test/nav_ctx",
                        "applicationDue": "2026-05-12",
                        "work_city": "Oslo",
                        "work_county": "Oslo",
                        "work_postalCode": "0150",
                        "job_source": "nav",
                    }
                },
                "detailProjections": {
                    "run_proj::nav_proj_ctx": {
                        "application_case_projection": {
                            "job_summary": {
                                "title": "Produktleder",
                                "company": "Avinor",
                                "location": "Oslo, Oslo",
                                "job_source": "nav",
                                "source_url": "https://example.test/nav_ctx",
                                "application_url": "https://example.test/apply_ctx",
                                "application_due": "2026-05-12",
                                "description_snippet": "Own roadmap and delivery.",
                            }
                        }
                    }
                },
            },
        )

        ctx = _load_workspace_context("nav_proj_ctx")

        assert ctx is not None
        assert ctx["job"]["title"] == "Produktleder"
        assert ctx["job"]["employer_name"] == "Avinor"
        assert ctx["job"]["applicationUrl"] == "https://example.test/apply_ctx"
        assert ctx["job"]["sourceurl"] == "https://example.test/nav_ctx"
        assert ctx["job"]["work_city"] == "Oslo"
        assert ctx["job"]["source"] == "nav"
    finally:
        server_mod._apply_paths(original_paths)


def test_load_workspace_context_reuses_detail_projection_when_stage_json_missing(tmp_path: Path) -> None:
    from jobpipe.cli import dashboard_server as server_mod
    from jobpipe.core.paths import get_jobpipe_paths
    from jobpipe.core.projection_store import persist_projection_store

    paths = get_jobpipe_paths(data_root=tmp_path, repo=tmp_path)
    paths.ensure_data_dirs()
    original_paths = server_mod.PATHS

    try:
        server_mod._apply_paths(paths)
        job_dir = paths.out_runs_dir / "run_proj2" / "nav_proj_ctx2"
        job_dir.mkdir(parents=True)

        persist_projection_store(
            paths.projection_store_path,
            {
                "inputEnrichment": {
                    "run_proj2::nav_proj_ctx2": {
                        "employer": "Entur",
                        "normalized_title": "produktsjef",
                        "application_url": "https://example.test/apply_ctx2",
                        "source_url": "https://example.test/nav_ctx2",
                        "applicationDue": "2026-06-01",
                        "work_city": "Oslo",
                        "work_county": "Oslo",
                        "job_source": "nav",
                    }
                },
                "detailProjections": {
                    "run_proj2::nav_proj_ctx2": {
                        "decision_brief": {
                            "schema_version": "jobpipe.decision-brief.v1",
                            "final_decision": "APPLY_STRONGLY",
                            "fit_score": 88,
                            "pivot_score": 54,
                            "positioning_angle": "Koble produktledelse til mobilitet og offentlig samhandling.",
                            "overlaps": ["Produktledelse", "Tverrfaglig samhandling"],
                            "gaps": ["Ingen direkte mobilitetsbakgrunn"],
                            "top_value_props": ["Sterk produktstyring", "Operativ gjennomføring"],
                            "cv_focus": ["Produktansvar", "Gjennomføring"],
                            "cover_letter_angle": "Vis hvordan erfaring fra komplekse tjenesteforløp passer rollen.",
                            "rationale": "Sterk match mot rollen med håndterbare domenegap.",
                        },
                        "application_case_projection": {
                            "job_summary": {
                                "title": "Produktsjef",
                                "company": "Entur",
                                "location": "Oslo, Oslo",
                                "job_source": "nav",
                                "source_url": "https://example.test/nav_ctx2",
                                "application_url": "https://example.test/apply_ctx2",
                                "application_due": "2026-06-01",
                            }
                        },
                    }
                },
            },
        )

        ctx = _load_workspace_context("nav_proj_ctx2")

        assert ctx is not None
        assert ctx["pack"]["positioning_headline"] == "Koble produktledelse til mobilitet og offentlig samhandling."
        assert ctx["pack"]["top_value_props"] == ["Sterk produktstyring", "Operativ gjennomføring"]
        assert ctx["pack"]["cover_letter_angle"] == "Vis hvordan erfaring fra komplekse tjenesteforløp passer rollen."
        assert ctx["match"]["fit_score"] == 88
        assert ctx["match"]["overlaps"] == ["Produktledelse", "Tverrfaglig samhandling"]
        assert ctx["pivot"]["pivot_score"] == 54
        assert ctx["moderator"]["final_decision"] == "APPLY_STRONGLY"
        assert ctx["moderator"]["cv_focus"] == ["Produktansvar", "Gjennomføring"]
    finally:
        server_mod._apply_paths(original_paths)


def test_build_chat_system_prompt_uses_projection_aware_workspace_context(tmp_path: Path) -> None:
    from jobpipe.cli import dashboard_server as server_mod
    from jobpipe.core.paths import get_jobpipe_paths
    from jobpipe.core.projection_store import persist_projection_store

    paths = get_jobpipe_paths(data_root=tmp_path, repo=tmp_path)
    paths.ensure_data_dirs()
    original_paths = server_mod.PATHS

    try:
        server_mod._apply_paths(paths)
        job_dir = paths.out_runs_dir / "run_proj3" / "nav_proj_ctx3"
        job_dir.mkdir(parents=True)

        persist_projection_store(
            paths.projection_store_path,
            {
                "inputEnrichment": {
                    "run_proj3::nav_proj_ctx3": {
                        "employer": "Vy",
                        "application_url": "https://example.test/apply_ctx3",
                        "source_url": "https://example.test/nav_ctx3",
                    }
                },
                "detailProjections": {
                    "run_proj3::nav_proj_ctx3": {
                        "decision_brief": {
                            "schema_version": "jobpipe.decision-brief.v1",
                            "positioning_angle": "Vis hvordan produktledelse og tjenesteflyt passer kollektivdomenet.",
                            "top_value_props": ["Produktstrategi", "Tverrfaglig levering"],
                            "overlaps": ["Produktledelse", "Offentlig sektor"],
                            "gaps": ["Ingen direkte kollektivbakgrunn"],
                            "cover_letter_angle": "Koble tjenesteflyt og operativ levering til rollen.",
                        },
                        "application_case_projection": {
                            "job_summary": {
                                "title": "Produktleder",
                                "company": "Vy",
                                "source_url": "https://example.test/nav_ctx3",
                                "application_url": "https://example.test/apply_ctx3",
                            }
                        },
                    }
                },
            },
        )

        prompt = _build_chat_system_prompt("nav_proj_ctx3")

        assert "**Stilling:** Produktleder @ Vy" in prompt
        assert "**Posisjoneringsoverskrift:** Vis hvordan produktledelse og tjenesteflyt passer kollektivdomenet." in prompt
        assert "**Søknadsvinkel (AI-generert):** Koble tjenesteflyt og operativ levering til rollen." in prompt
        assert "**Toppverdier:**" in prompt
        assert "Produktstrategi" in prompt
        assert "**Overlaps:** Produktledelse, Offentlig sektor" in prompt
        assert "**Gaps:** Ingen direkte kollektivbakgrunn" in prompt
    finally:
        server_mod._apply_paths(original_paths)


def test_run_generation_uses_projection_backed_workspace_context_when_input_missing(tmp_path: Path, monkeypatch) -> None:
    from jobpipe.cli import dashboard_server as server_mod
    from jobpipe.core.paths import get_jobpipe_paths
    from jobpipe.core.projection_store import persist_projection_store
    from jobpipe.core.schema import ApplicationPackOut
    import jobpipe.core.config as config_mod
    import jobpipe.core.io as io_mod
    import jobpipe.stages.application_pack as application_pack_mod

    paths = get_jobpipe_paths(data_root=tmp_path, repo=tmp_path)
    paths.ensure_data_dirs()
    original_paths = server_mod.PATHS
    captured: dict[str, object] = {}

    class DummyCfg:
        models = {"application_pack": "fake-model"}
        stages = ["triage", "reverse_triage", "parsed", "profile_match", "pivot", "moderator", "application_pack"]

    def fake_load_config(*args, **kwargs):
        return DummyCfg()

    def fake_load_env_file(*args, **kwargs):
        return None

    def fake_load_profile_pack(*args, **kwargs):
        return "profiltekst"

    def fake_factory(model: str):
        def should_run(ctx):
            return bool(ctx.moderator and ctx.moderator.final_decision in ("APPLY", "APPLY_STRONGLY"))

        def run(ctx, job_dir: str):
            captured["job"] = dict(ctx.job)
            captured["moderator"] = ctx.moderator.model_dump() if ctx.moderator else {}
            ctx.application_pack = ApplicationPackOut(
                positioning_headline="Projection headline",
                top_value_props=["Verdi 1", "Verdi 2"],
                evidence_map=[],
                gap_mitigations=[],
                cover_letter_angle="Projection angle",
                cover_letter_text="Kort brev",
                interview_prep=[],
                cv_highlights=[],
            )
            return ctx

        return should_run, run

    try:
        server_mod._apply_paths(paths)
        monkeypatch.setattr(config_mod, "load_config", fake_load_config)
        monkeypatch.setattr(io_mod, "load_env_file", fake_load_env_file)
        monkeypatch.setattr(io_mod, "load_profile_pack", fake_load_profile_pack)
        monkeypatch.setattr(application_pack_mod, "application_pack_stage_factory", fake_factory)

        job_dir = paths.out_runs_dir / "run_proj4" / "nav_proj_ctx4"
        job_dir.mkdir(parents=True)

        persist_projection_store(
            paths.projection_store_path,
            {
                "inputEnrichment": {
                    "run_proj4::nav_proj_ctx4": {
                        "employer": "Bane NOR",
                        "normalized_title": "produktleder",
                        "application_url": "https://example.test/apply_ctx4",
                        "source_url": "https://example.test/nav_ctx4",
                        "applicationDue": "2026-06-15",
                        "work_city": "Oslo",
                        "work_county": "Oslo",
                        "job_source": "nav",
                    }
                },
                "detailProjections": {
                    "run_proj4::nav_proj_ctx4": {
                        "decision_brief": {
                            "schema_version": "jobpipe.decision-brief.v1",
                            "final_decision": "APPLY",
                            "fit_score": 81,
                            "pivot_score": 50,
                            "rationale": "Sterk nok match.",
                        },
                        "application_case_projection": {
                            "job_summary": {
                                "title": "Produktleder",
                                "company": "Bane NOR",
                                "location": "Oslo, Oslo",
                                "job_source": "nav",
                                "source_url": "https://example.test/nav_ctx4",
                                "application_url": "https://example.test/apply_ctx4",
                                "application_due": "2026-06-15",
                                "description_snippet": "Led produktforbedringer.",
                            }
                        },
                    }
                },
            },
        )

        _gen_status.pop("nav_proj_ctx4", None)
        _run_generation("nav_proj_ctx4")

        generated_path = job_dir / "07_application_pack.json"
        assert _gen_status["nav_proj_ctx4"] == "done"
        assert captured["job"]["title"] == "Produktleder"
        assert captured["job"]["employer_name"] == "Bane NOR"
        assert captured["moderator"]["final_decision"] == "APPLY"
        assert generated_path.exists()
        saved = json.loads(generated_path.read_text(encoding="utf-8"))
        assert saved["positioning_headline"] == "Projection headline"
    finally:
        server_mod._apply_paths(original_paths)
        _gen_status.pop("nav_proj_ctx4", None)
