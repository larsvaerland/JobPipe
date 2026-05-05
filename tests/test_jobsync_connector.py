from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from jobpipe.core.jobsync import JobSyncSettings, build_connector_envelope, post_jobsync_json, write_jobsync_outbox
from jobpipe.core.jobsync_authoring import build_authoring_sync_record
from jobpipe.core.paths import get_jobpipe_paths
from jobpipe.cli.sync_jobsync_jobs import _build_import_record


def test_build_connector_envelope_is_versioned() -> None:
    envelope = build_connector_envelope(
        "curated_jobs_import",
        "lars@example.test",
        {"jobs": [{"externalId": "nav_1"}]},
    )

    assert envelope["contractVersion"] == "jobpipe.jobsync.v1"
    assert envelope["producer"] == "jobpipe"
    assert envelope["kind"] == "curated_jobs_import"
    assert envelope["userEmail"] == "lars@example.test"
    assert envelope["jobs"][0]["externalId"] == "nav_1"


def test_write_jobsync_outbox_writes_json_payload(tmp_path) -> None:
    paths = get_jobpipe_paths(data_root=tmp_path, repo=tmp_path)
    envelope = build_connector_envelope(
        "application_status_sync",
        "lars@example.test",
        {"events": [{"externalId": "nav_1", "status": "draft"}]},
    )

    outbox_path = write_jobsync_outbox(paths, "application_status_sync", envelope)

    saved = json.loads(outbox_path.read_text(encoding="utf-8"))
    assert saved["kind"] == "application_status_sync"
    assert saved["events"][0]["status"] == "draft"


def test_build_import_record_emits_application_packet_and_new_target_status(tmp_path) -> None:
    paths = get_jobpipe_paths(data_root=tmp_path, repo=tmp_path)
    row = {
        "job_id": "nav_42",
        "run_id": "run_1",
        "title": "Senior Produktleder",
        "employer": "Acme",
        "work_city": "Oslo",
        "work_county": "Oslo",
        "source_url": "https://example.test/job",
        "application_url": "https://example.test/apply",
        "description_snip": "Own roadmap and delivery.",
        "job_source": "nav",
        "app_status": "draft",
        "final_decision": "APPLY",
        "fit_score": 78,
        "pivot_score": 64,
        "recommendation_reason": "Strong ownership fit.",
        "updated_at": "2026-04-18T12:00:00Z",
        "pack_ready": True,
        "pack_generated_at": "2026-04-18T12:05:00Z",
        "pack_has_cover_letter": True,
        "pack_docx_ready": True,
        "pack_highlight_count": 4,
        "generated_documents": [
            {
                "kind": "application_pack_json",
                "status": "saved",
                "storage_path": "C:/data/run_1/nav_42/06_application_pack.json",
            }
        ],
        "triage_v3_label": "shortlist",
        "detail": {
            "overlaps": ["product leadership"],
            "gaps": ["public-sector domain"],
            "hard_blockers": [],
            "match_notes": "Good strategic fit.",
            "pivot_type": "adjacent",
            "pivot_risk": "low",
            "pivot_why": ["Cross-functional scope"],
            "cv_focus_mod": ["ownership"],
            "feedback_flags_mod": [],
            "advantage_type": "strong_fit",
            "advantage_review_priority": 82,
            "narrative_positioning_angle": "Direkte relevant produktledelse for komplekse leveranser.",
            "narrative_brand_frame": "Brobygger mellom produkt og drift",
        },
    }

    record = _build_import_record(paths, row)

    assert record["status"] == "new"
    assert record["jobpipeStatus"] == "draft"
    assert record["title"] == record["applicationCaseProjection"]["job_summary"]["title"]
    assert record["company"] == record["applicationCaseProjection"]["job_summary"]["company"]
    assert record["location"] == record["applicationCaseProjection"]["job_summary"]["location"]
    assert record["jobUrl"] == record["applicationCaseProjection"]["job_summary"]["source_url"]
    assert record["applicationUrl"] == record["applicationCaseProjection"]["job_summary"]["application_url"]
    assert record["description"] == record["applicationCaseProjection"]["job_summary"]["description_snippet"]
    assert record["jobSource"] == record["applicationCaseProjection"]["job_summary"]["job_source"]
    assert record["decision"] == record["decisionBrief"]["final_decision"]
    assert record["fitScore"] == record["decisionBrief"]["fit_score"]
    assert record["pivotScore"] == record["decisionBrief"]["pivot_score"]
    assert record["triageExplanation"] == record["decisionBrief"]["rationale"]
    assert record["artifactsPath"] == record["artifactPlan"]["artifact_root"]
    assert record["updatedAt"] == record["applicationCaseProjection"]["updated_at"]
    assert record["applicationPacket"]["packetVersion"] == "jobpipe.application-packet.v1"
    assert record["applicationPacket"]["job"]["title"] == "Senior Produktleder"
    assert record["applicationPacket"]["job"]["title"] == record["applicationCaseProjection"]["job_summary"]["title"]
    assert record["applicationPacket"]["job"]["company"] == record["applicationCaseProjection"]["job_summary"]["company"]
    assert record["applicationPacket"]["analysis"]["gaps"] == ["public-sector domain"]
    assert record["applicationPacket"]["analysis"]["decision"] == record["decisionBrief"]["final_decision"]
    assert record["applicationPacket"]["analysis"]["fitScore"] == record["decisionBrief"]["fit_score"]
    assert record["applicationPacket"]["analysis"]["rationale"] == record["decisionBrief"]["rationale"]
    assert record["applicationPacket"]["drafting"]["packReady"] is True
    assert record["applicationPacket"]["generatedArtifacts"][0]["kind"] == "application_pack_json"
    assert record["applicationPacket"]["generatedArtifacts"] == record["artifactPlan"]["generated_artifacts"]
    assert record["applicationPacket"]["inputSnapshotPath"] == record["artifactPlan"]["input_snapshot_path"]
    assert record["applicationPacket"]["artifactsPath"] == record["artifactPlan"]["artifact_root"]
    assert record["decisionBrief"]["schema_version"] == "jobpipe.decision-brief.v1"
    assert record["decisionBrief"]["triage_v3_label"] == "shortlist"
    assert record["decisionBrief"]["advantage_type"] == "strong_fit"
    assert record["decisionBrief"]["positioning_angle"] == "Direkte relevant produktledelse for komplekse leveranser."
    assert record["artifactPlan"]["schema_version"] == "jobpipe.artifact-plan.v1"
    assert record["artifactPlan"]["artifact_root"].endswith("out_runs\\run_1\\nav_42")
    assert record["applicationCaseProjection"]["schema_version"] == "jobpipe.application-case-projection.v1"
    assert record["applicationCaseProjection"]["job_summary"]["title"] == "Senior Produktleder"
    assert record["applicationCaseProjection"]["decision_brief"]["brand_frame"] == "Brobygger mellom produkt og drift"


def test_post_jobsync_json_posts_expected_headers_and_payload() -> None:
    captured: dict[str, object] = {}

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            captured["path"] = self.path
            captured["token"] = self.headers.get("X-JobPipe-Token")
            captured["content_type"] = self.headers.get("Content-Type")
            captured["payload"] = json.loads(body.decode("utf-8"))

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"created":1,"updated":0}')

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        settings = JobSyncSettings(
            base_url=f"http://127.0.0.1:{server.server_port}",
            token="secret-token",
            user_email="lars@example.test",
            timeout_seconds=5.0,
        )
        payload = build_connector_envelope(
            "curated_jobs_import",
            "lars@example.test",
            {"jobs": [{"externalId": "nav_42", "status": "new"}]},
        )

        response = post_jobsync_json(settings, "/api/integrations/jobpipe/jobs", payload)

        assert response == {"created": 1, "updated": 0}
        assert captured["path"] == "/api/integrations/jobpipe/jobs"
        assert captured["token"] == "secret-token"
        assert captured["content_type"] == "application/json"
        posted = captured["payload"]
        assert isinstance(posted, dict)
        assert posted["kind"] == "curated_jobs_import"
        assert posted["jobs"][0]["status"] == "new"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_build_authoring_sync_record_emits_clean_authoring_refs() -> None:
    record = build_authoring_sync_record(
        "nav_42",
        {
            "jobId": "nav_42",
            "updatedAt": "2026-04-18T22:50:00Z",
            "resume": {
                "variantRef": " rr:resume-42 ",
                "variantLabel": " Tailored Resume ",
                "sourceUrl": " http://localhost:3000/resumes/42 ",
                "exportRef": " rr-export-42 ",
                "exportLabel": " Resume PDF ",
                "exportUrl": " http://localhost:3000/exports/42.pdf ",
                "exportFormat": " pdf ",
                "exportedAt": " 2026-04-18T23:05:00Z ",
                "exportPdfPath": " C:/tmp/10_tailored_resume.pdf ",
                "artifactRefs": [
                    {
                        "kind": "resume_pdf",
                        "label": " Final PDF ",
                        "path": " C:/tmp/10_tailored_resume.pdf ",
                    }
                ],
            },
            "coverLetter": {
                "documentRef": " doc-42 ",
                "documentLabel": " Cover Letter ",
                "sourceUrl": " https://docs.example.test/doc-42 ",
                "exportRef": " cover-export-42 ",
                "exportLabel": " Final cover letter DOCX ",
                "exportUrl": " https://docs.example.test/export/doc-42 ",
                "exportFormat": " docx ",
                "exportedAt": " 2026-04-18T23:06:00Z ",
                "exportDocxPath": " C:/tmp/08_cover_letter.docx ",
            },
            "screeningAnswers": {
                "documentRef": " q-42 ",
                "documentLabel": " Screening answers ",
                "sourceUrl": " https://docs.example.test/q-42 ",
                "exportRef": " screening-export-42 ",
                "exportLabel": " Screening answers DOCX ",
                "exportUrl": " https://docs.example.test/export/q-42 ",
                "exportFormat": " docx ",
                "exportedAt": " 2026-04-18T23:07:00Z ",
                "exportDocxPath": " C:/tmp/09_screening_answers.docx ",
            },
        },
    )

    assert record["externalSource"] == "jobpipe"
    assert record["externalId"] == "nav_42"
    assert record["authoringState"]["resume"]["variantRef"] == "rr:resume-42"
    assert record["authoringState"]["resume"]["exportRef"] == "rr-export-42"
    assert record["authoringState"]["resume"]["exportLabel"] == "Resume PDF"
    assert record["authoringState"]["resume"]["exportUrl"] == "http://localhost:3000/exports/42.pdf"
    assert record["authoringState"]["resume"]["exportFormat"] == "pdf"
    assert record["authoringState"]["resume"]["exportedAt"] == "2026-04-18T23:05:00Z"
    assert record["authoringState"]["resume"]["artifactRefs"] == [
        {
            "kind": "resume_pdf",
            "label": "Final PDF",
            "path": "C:/tmp/10_tailored_resume.pdf",
            "url": "",
        }
    ]
    assert record["authoringState"]["coverLetter"]["documentRef"] == "doc-42"
    assert record["authoringState"]["coverLetter"]["documentLabel"] == "Cover Letter"
    assert record["authoringState"]["coverLetter"]["exportRef"] == "cover-export-42"
    assert record["authoringState"]["coverLetter"]["exportLabel"] == "Final cover letter DOCX"
    assert record["authoringState"]["coverLetter"]["exportUrl"] == "https://docs.example.test/export/doc-42"
    assert record["authoringState"]["coverLetter"]["exportFormat"] == "docx"
    assert record["authoringState"]["coverLetter"]["exportedAt"] == "2026-04-18T23:06:00Z"
    assert record["authoringState"]["screeningAnswers"]["documentRef"] == "q-42"
    assert record["authoringState"]["screeningAnswers"]["documentLabel"] == "Screening answers"
    assert record["authoringState"]["screeningAnswers"]["exportRef"] == "screening-export-42"
    assert record["authoringState"]["screeningAnswers"]["exportLabel"] == "Screening answers DOCX"
    assert record["authoringState"]["screeningAnswers"]["exportUrl"] == "https://docs.example.test/export/q-42"
    assert record["authoringState"]["screeningAnswers"]["exportFormat"] == "docx"
    assert record["authoringState"]["screeningAnswers"]["exportedAt"] == "2026-04-18T23:07:00Z"
