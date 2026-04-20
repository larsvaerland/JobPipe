from __future__ import annotations

import json
from pathlib import Path

from jobpipe.cli.sync_mailbox_leads import run_mailbox_lead_intake
from jobpipe.core.lead_intake import LEAD_CONNECTOR_VERSION, append_leads


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_append_leads_marks_shared_connector_metadata(tmp_path: Path) -> None:
    out_path = tmp_path / "jobs_delta.jsonl"
    leads = append_leads(
        out_path,
        [
            {
                "job_id": "finn_123",
                "title": "Produktleder",
                "source": "finn_suggestion",
                "suggested_at": "2026-04-18",
            }
        ],
        intake_channel="mailbox_recommendation",
        connector_source="gmail_suggestion_queue",
    )

    assert len(leads) == 1
    stored = json.loads(out_path.read_text(encoding="utf-8").strip())
    assert stored["lead_connector_version"] == LEAD_CONNECTOR_VERSION
    assert stored["lead_intake_channel"] == "mailbox_recommendation"
    assert stored["lead_connector_source"] == "gmail_suggestion_queue"
    assert stored["lead_received_at"] == "2026-04-18"


def test_run_mailbox_lead_intake_skips_when_disabled(tmp_path: Path, monkeypatch) -> None:
    _write_json(
        tmp_path / "reports" / "settings_state.json",
        {
            "integrations": {
                "gmail": {
                    "status_detection_enabled": True,
                    "lead_intake_enabled": False,
                }
            }
        },
    )

    called = {"scan": False, "process": False}

    def fake_scan_suggestions(**_: object) -> int:
        called["scan"] = True
        return 0

    def fake_process_suggested_queue(**_: object) -> dict:
        called["process"] = True
        return {"status": "ok", "fetched": 0, "remaining": 0}

    monkeypatch.setattr("jobpipe.cli.sync_mailbox_leads._scan_suggestions", fake_scan_suggestions)
    monkeypatch.setattr("jobpipe.cli.sync_mailbox_leads._process_suggested_queue", fake_process_suggested_queue)

    result = run_mailbox_lead_intake(data_root=str(tmp_path))

    assert result["status"] == "disabled"
    assert called["scan"] is False
    assert called["process"] is False


def test_run_mailbox_lead_intake_uses_settings_gate_and_shared_flow(tmp_path: Path, monkeypatch) -> None:
    _write_json(
        tmp_path / "reports" / "settings_state.json",
        {
            "integrations": {
                "gmail": {
                    "status_detection_enabled": False,
                    "lead_intake_enabled": True,
                }
            }
        },
    )

    seen = {"scan": None, "process": None}

    def fake_scan_suggestions(**kwargs: object) -> int:
        seen["scan"] = kwargs
        return 3

    def fake_process_suggested_queue(**kwargs: object) -> dict:
        seen["process"] = kwargs
        return {"status": "ok", "fetched": 2, "failed": 1, "remaining": 4, "linkedin_pending": 5}

    monkeypatch.setattr("jobpipe.cli.sync_mailbox_leads._scan_suggestions", fake_scan_suggestions)
    monkeypatch.setattr("jobpipe.cli.sync_mailbox_leads._process_suggested_queue", fake_process_suggested_queue)

    result = run_mailbox_lead_intake(data_root=str(tmp_path), dry_run=True)

    assert result == {
        "status": "ok",
        "queued": 3,
        "fetched": 2,
        "failed": 1,
        "remaining": 4,
        "linkedin_pending": 5,
    }
    assert seen["scan"]["suggested_path"] == tmp_path / "reports" / "suggested_jobs.jsonl"
    assert seen["process"]["out_path"] == tmp_path / "reports" / "leads_connector.jsonl"
    assert seen["process"]["dry_run"] is True
