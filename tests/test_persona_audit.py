from __future__ import annotations

import json
from pathlib import Path

from jobpipe.cli.persona_audit import (
    _persona_summary,
    choose_audit_slice,
    load_rerunnable_jobs_by_id,
    reconstruct_audit_job_input,
    run_persona_matrix,
)
from jobpipe.core.primary_db import connect_primary_db, upsert_job_replay_input


def test_reconstruct_audit_job_input_uses_catalog_and_metadata_fields() -> None:
    row = {
        "job_id": "nav_123",
        "title": "Senior Product Manager",
        "employer": "Example AS",
        "work_city": "",
        "work_county": "",
        "work_postalCode": "",
        "applicationDue": "2026-05-01T00:00:00",
        "source_url": "https://arbeidsplassen.nav.no/stillinger/stilling/nav_123",
        "application_url": "https://example.com/apply",
        "description_text": "Plain text description",
        "description_html": "<p>HTML description</p>",
        "sector": "Privat",
        "job_metadata_json": (
            '{"_canonical_source_name":"nav_sheet",'
            '"workLocations_json":"[{'
            '\\"city\\":\\"Oslo\\",'
            '\\"postalCode\\":\\"0150\\",'
            '\\"county\\":\\"OSLO\\"'
            '}]"'
            "}"
        ),
    }

    job = reconstruct_audit_job_input(row)

    assert job["job_id"] == "nav_123"
    assert job["title"] == "Senior Product Manager"
    assert job["employer_name"] == "Example AS"
    assert job["work_city"] == "Oslo"
    assert job["work_postalCode"] == "0150"
    assert job["source"] == "nav_sheet"
    assert job["parse_method"] == "audit_baseline"
    assert job["reconstructed_from_audit_baseline"] is True


def test_choose_audit_slice_balances_decision_buckets() -> None:
    jobs_by_id = {
        f"job_{idx}": {
            "job_id": f"job_{idx}",
            "title": f"Job {idx}",
            "employer_name": f"Employer {idx}",
            "sourceurl": f"https://example{idx}.com/jobs/{idx}",
            "applicationUrl": "",
            "source": "audit_baseline",
        }
        for idx in range(1, 10)
    }
    evaluation_rows = [
        {"job_id": "job_1", "final_decision": "APPLY", "final_confidence": 0.91, "fit_score": 82, "pivot_score": 55, "updated_at": "2026-04-17T10:00:00Z"},
        {"job_id": "job_2", "final_decision": "APPLY_STRONGLY", "final_confidence": 0.88, "fit_score": 79, "pivot_score": 48, "updated_at": "2026-04-17T09:00:00Z"},
        {"job_id": "job_3", "final_decision": "REVIEW_HIGH", "final_confidence": 0.77, "fit_score": 63, "pivot_score": 71, "updated_at": "2026-04-17T08:00:00Z"},
        {"job_id": "job_4", "final_decision": "REVIEW_LOW", "final_confidence": 0.71, "fit_score": 51, "pivot_score": 68, "updated_at": "2026-04-17T07:00:00Z"},
        {"job_id": "job_5", "final_decision": "SKIP", "final_confidence": 0.95, "fit_score": 12, "pivot_score": 20, "updated_at": "2026-04-17T06:00:00Z"},
        {"job_id": "job_6", "final_decision": "SKIP", "final_confidence": 0.84, "fit_score": 18, "pivot_score": 28, "updated_at": "2026-04-17T05:00:00Z"},
    ]

    selected = choose_audit_slice(evaluation_rows, jobs_by_id, jobs_per_bucket=2)

    assert [job["job_id"] for job in selected] == [
        "job_1",
        "job_2",
        "job_3",
        "job_4",
        "job_5",
        "job_6",
    ]


def test_load_rerunnable_jobs_by_id_uses_replay_inputs_when_catalog_row_is_missing(tmp_path) -> None:
    db_path = tmp_path / "jobpipe.sqlite"
    conn = connect_primary_db(db_path)
    try:
        upsert_job_replay_input(
            conn,
            {
                "job_id": "job-replay",
                "source_name": "nav_sheet",
                "source_job_key": "job-replay",
                "source_url": "https://example.test/job-replay",
                "application_url": "",
                "title": "Replay Job",
                "employer": "Replay AS",
                "work_city": "Oslo",
                "work_county": "Oslo",
                "work_postalCode": "0001",
                "applicationDue": "2026-05-01",
                "description_text": "Replay payload",
                "description_html": "<p>Replay payload</p>",
                "input_payload_json": {
                    "job_id": "job-replay",
                    "title": "Replay Job",
                    "employer_name": "Replay AS",
                    "source": "nav_sheet",
                    "sourceurl": "https://example.test/job-replay",
                    "applicationDue": "2026-05-01",
                },
                "input_hash": "hash",
                "captured_from_run_id": "run-1",
                "captured_at": "2026-04-17T10:00:00Z",
                "updated_at": "2026-04-17T10:05:00Z",
            },
        )
        conn.commit()
    finally:
        conn.close()

    jobs_by_id, catalog_job_count, replay_only_jobs = load_rerunnable_jobs_by_id(db_path)

    assert catalog_job_count == 0
    assert replay_only_jobs == 1
    assert jobs_by_id["job-replay"]["title"] == "Replay Job"
    assert jobs_by_id["job-replay"]["source"] == "nav_sheet"


def test_run_persona_matrix_keeps_dashboard_app_state_isolated(tmp_path, monkeypatch) -> None:
    audit_root = tmp_path / "audit"
    baseline_dir = audit_root / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)

    (baseline_dir / "pipeline.v1.yaml").write_text("version: 1\n", encoding="utf-8")
    (baseline_dir / "jobs_corpus.audit_slice.jsonl").write_text(
        json.dumps(
            {
                "job_id": "job-1",
                "title": "Example Role",
                "employer_name": "Example AS",
                "description_text": "Example",
                "source": "audit_baseline",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    empty_app_state_path = baseline_dir / "empty_application_state.json"
    empty_app_state_path.write_text(json.dumps({"applications": {}, "updated_at": "2026-04-17T00:00:00Z"}), encoding="utf-8")

    manifest_path = baseline_dir / "personas.manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "personas": [
                    {
                        "persona_id": "persona_test",
                        "label": "Test Persona",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    repo_root_path = tmp_path / "repo"
    persona_source_dir = repo_root_path / "tests" / "fixtures" / "personas" / "persona_test"
    persona_source_dir.mkdir(parents=True, exist_ok=True)
    (persona_source_dir / "profile_pack.md").write_text("# Profile\n", encoding="utf-8")
    (persona_source_dir / "resume.json").write_text("{}", encoding="utf-8")

    recorded_commands: list[list[str]] = []
    build_payload_calls: list[dict[str, Path | str | None]] = []

    def fake_run_command(command: list[str], *, cwd: Path, log_path: Path) -> None:
        recorded_commands.append(command)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("", encoding="utf-8")

    def fake_copy_catalog_tables(source_db: Path, target_db: Path) -> None:
        target_db.parent.mkdir(parents=True, exist_ok=True)
        connect_primary_db(target_db).close()

    def fake_build_payload(out_dir: Path, *, state_path: Path | None = None, primary_db_path_: Path | None = None, candidate_id: str = "", config_path: Path | None = None) -> dict[str, object]:
        build_payload_calls.append(
            {
                "out_dir": out_dir,
                "state_path": state_path,
                "db_path": primary_db_path_,
                "candidate_id": candidate_id,
                "config_path": config_path,
            }
        )
        return {
            "generated_at": "2026-04-17T00:00:00Z",
            "jobs": [
                {
                    "job_id": "job-1",
                    "title": "Example Role",
                    "employer": "Example AS",
                    "final_decision": "SKIP",
                    "fit_score": 12,
                    "pivot_score": 5,
                }
            ],
            "summary": {
                "tracked_applications": 0,
                "application_status_counts": {},
            },
        }

    monkeypatch.setattr("jobpipe.cli.persona_audit._run_command", fake_run_command)
    monkeypatch.setattr("jobpipe.cli.persona_audit._copy_catalog_tables", fake_copy_catalog_tables)
    monkeypatch.setattr("jobpipe.cli.persona_audit.build_payload", fake_build_payload)

    result = run_persona_matrix(
        audit_root=audit_root,
        live_db=tmp_path / "live.sqlite",
        python_exe=Path("python"),
        repo_root_path=repo_root_path,
    )

    export_command = next(cmd for cmd in recorded_commands if "jobpipe.cli.export_dashboard" in cmd)
    assert "--app-state" in export_command
    assert export_command[export_command.index("--app-state") + 1] == str(empty_app_state_path)

    assert build_payload_calls[0]["state_path"] == empty_app_state_path
    assert result["persona_count"] == 1
    assert result["personas"][0]["summary"]["tracked_applications"] == 0


def test_persona_summary_preserves_no_score_reason_fields() -> None:
    summary = _persona_summary(
        {
            "generated_at": "2026-04-17T00:00:00Z",
            "summary": {},
            "jobs": [
                {
                    "job_id": "job-1",
                    "title": "Staff Software Engineer",
                    "employer": "Example AS",
                    "final_decision": "SKIP",
                    "fit_score": None,
                    "pivot_score": None,
                    "no_score_reason": "triage_skip_before_scoring",
                    "no_score_reason_label": "skipped at triage before fit and pivot scoring",
                }
            ],
        },
        persona_id="persona_test",
        persona_label="Test Persona",
    )

    assert summary["top_skip"][0]["no_score_reason"] == "triage_skip_before_scoring"
    assert summary["top_skip"][0]["no_score_reason_label"] == "skipped at triage before fit and pivot scoring"
