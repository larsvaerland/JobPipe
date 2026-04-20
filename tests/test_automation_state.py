from __future__ import annotations

import json
from pathlib import Path

from jobpipe.core.automation_state import (
    AUTOMATION_SCHEMA_VERSION,
    append_automation_run,
    build_automation_payload,
    update_automation_run,
)
from jobpipe.core.paths import JobPipePaths


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_build_automation_payload_counts_staging_and_recent_runs(tmp_path: Path) -> None:
    paths = JobPipePaths(repo_root=tmp_path, data_root=tmp_path)
    _write_jsonl(paths.nav_connector_path, [{"job_id": "nav_1"}, {"job_id": "nav_2"}])
    _write_jsonl(paths.leads_connector_path, [{"job_id": "lead_1"}])
    _write_jsonl(paths.jobs_delta_path, [{"job_id": "merged_1"}, {"job_id": "merged_2"}, {"job_id": "merged_3"}])

    append_automation_run(
        paths.automation_state_path,
        {
            "run_id": "run_001",
            "action_key": "nav_refresh",
            "label": "Refresh NAV connector",
            "category": "connector",
            "status": "running",
            "started_at": "2026-04-18T10:00:00Z",
            "finished_at": "",
            "exit_code": None,
            "summary": "Run started.",
            "log_excerpt": "",
        },
    )
    update_automation_run(
        paths.automation_state_path,
        "run_001",
        {
            "status": "succeeded",
            "finished_at": "2026-04-18T10:02:00Z",
            "exit_code": 0,
            "summary": "Connector refreshed.",
            "log_excerpt": "Connector refreshed.",
        },
    )

    payload = build_automation_payload(paths)

    assert payload["schema_version"] == AUTOMATION_SCHEMA_VERSION
    assert payload["connector_counts"]["nav_connector_rows"] == 2
    assert payload["connector_counts"]["lead_connector_rows"] == 1
    assert payload["connector_counts"]["merged_queue_rows"] == 3
    assert payload["summary"]["running"] == 0
    assert payload["summary"]["succeeded"] == 1
    assert payload["summary"]["failed"] == 0
    assert payload["summary"]["last_run_at"] == "2026-04-18T10:02:00Z"
    assert payload["recent_runs"][0]["summary"] == "Connector refreshed."
    assert payload["scheduled_flow"]["schema_version"] == "jobpipe.scheduled-run-control.v1"
    assert payload["scheduled_flow"]["summary"]["status"] == "never_run"


def test_automation_run_history_keeps_most_recent_entry_first(tmp_path: Path) -> None:
    paths = JobPipePaths(repo_root=tmp_path, data_root=tmp_path)

    append_automation_run(
        paths.automation_state_path,
        {
            "run_id": "older",
            "action_key": "merge_connectors",
            "label": "Rebuild merged queue",
            "category": "pipeline",
            "status": "failed",
            "started_at": "2026-04-18T09:00:00Z",
            "finished_at": "2026-04-18T09:01:00Z",
            "exit_code": 1,
            "summary": "Queue rebuild failed.",
            "log_excerpt": "Queue rebuild failed.",
        },
    )
    append_automation_run(
        paths.automation_state_path,
        {
            "run_id": "newer",
            "action_key": "export_dashboard",
            "label": "Rebuild dashboard export",
            "category": "control_plane",
            "status": "succeeded",
            "started_at": "2026-04-18T10:00:00Z",
            "finished_at": "2026-04-18T10:01:00Z",
            "exit_code": 0,
            "summary": "Dashboard rebuilt.",
            "log_excerpt": "Dashboard rebuilt.",
        },
    )

    payload = build_automation_payload(paths)

    assert [run["run_id"] for run in payload["recent_runs"]] == ["newer", "older"]
    assert payload["summary"]["failed"] == 1
    assert payload["summary"]["succeeded"] == 1
    assert {action["key"] for action in payload["actions"]} >= {"scheduled_full_run", "nav_refresh", "export_dashboard"}
