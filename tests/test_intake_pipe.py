from __future__ import annotations

import json
from pathlib import Path

from jobpipe.core.intake_pipe import (
    CONNECTOR_NAV,
    INTAKE_CONNECTOR_VERSION,
    INTAKE_MERGE_VERSION,
    POLICY_FULL_FEED,
    POLICY_SUGGESTED_LEAD,
    merge_connector_records,
    prepare_connector_record,
    prune_connector_records,
    rebuild_intake_queue,
)


def test_merge_prefers_nav_as_canonical_and_backfills_missing_fields() -> None:
    nav = prepare_connector_record(
        {
            "job_id": "nav_1",
            "title": "Produktleder",
            "employer_name": "Acme",
            "source": "nav",
            "work_city": "Oslo",
            "sourceurl": "https://nav.example/job",
        },
        connector_name=CONNECTOR_NAV,
        connector_source="nav",
        intake_channel="sheet",
        pretriage_policy=POLICY_FULL_FEED,
    )
    lead = prepare_connector_record(
        {
            "job_id": "finn_1",
            "title": "Produktleder",
            "employer_name": "Acme",
            "source": "finn_suggestion",
            "work_city": "Oslo",
            "applicationDue": "2026-04-30",
            "applicationUrl": "https://finn.example/apply",
            "suggested_by_platform": True,
        },
        connector_name="suggested_leads",
        connector_source="finn_suggested",
        intake_channel="gmail_recommendation_email",
        pretriage_policy=POLICY_SUGGESTED_LEAD,
    )

    merged = merge_connector_records([nav, lead])

    assert len(merged) == 1
    row = merged[0]
    assert row["job_id"] == "nav_1"
    assert row["source"] == "nav"
    assert row["applicationDue"] == "2026-04-30"
    assert row["applicationUrl"] == "https://finn.example/apply"
    assert row["intake_merge_version"] == INTAKE_MERGE_VERSION
    assert row["intake_connector_version"] == INTAKE_CONNECTOR_VERSION
    assert row["intake_pretriage_policy"] == POLICY_SUGGESTED_LEAD
    assert row["suggested_by_platform"] is True
    assert sorted(row["intake_connector_names"]) == ["nav_feed", "suggested_leads"]
    assert len(row["intake_source_variants"]) == 2


def test_rebuild_and_prune_connector_files(tmp_path: Path) -> None:
    nav_path = tmp_path / "nav_connector.jsonl"
    leads_path = tmp_path / "leads_connector.jsonl"
    delta_path = tmp_path / "jobs_delta.jsonl"

    nav = prepare_connector_record(
        {
            "job_id": "nav_2",
            "title": "Produkteier",
            "employer_name": "Bravo",
            "work_city": "Oslo",
        },
        connector_name=CONNECTOR_NAV,
        connector_source="nav",
        intake_channel="sheet",
        pretriage_policy=POLICY_FULL_FEED,
    )
    lead = prepare_connector_record(
        {
            "job_id": "finn_2",
            "title": "Produkteier",
            "employer_name": "Bravo",
            "work_city": "Oslo",
            "suggested_by_platform": True,
        },
        connector_name="suggested_leads",
        connector_source="finn_suggested",
        intake_channel="gmail_recommendation_email",
        pretriage_policy=POLICY_SUGGESTED_LEAD,
    )

    nav_path.write_text(json.dumps(nav, ensure_ascii=False) + "\n", encoding="utf-8")
    leads_path.write_text(json.dumps(lead, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = rebuild_intake_queue(nav_path=nav_path, leads_path=leads_path, out_path=delta_path)
    assert summary == {"nav_records": 1, "lead_records": 1, "merged_records": 1}

    merged_row = json.loads(delta_path.read_text(encoding="utf-8").strip())
    key = merged_row["intake_dedupe_key"]
    assert key

    assert prune_connector_records(nav_path, [key]) == 1
    assert prune_connector_records(leads_path, [key]) == 1
    assert nav_path.read_text(encoding="utf-8") == ""
    assert leads_path.read_text(encoding="utf-8") == ""
