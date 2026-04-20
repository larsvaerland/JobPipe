from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from jobpipe.core.intake_pipe import (
    CONNECTOR_LEADS,
    POLICY_FULL_FEED,
    prepare_connector_record,
)

LEAD_CONNECTOR_VERSION = "jobpipe.lead-intake.v1"


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def prepare_lead_record(
    job: Dict[str, Any],
    *,
    intake_channel: str,
    connector_source: str,
    pretriage_policy: str = POLICY_FULL_FEED,
) -> Dict[str, Any]:
    clean = prepare_connector_record(
        job,
        connector_name=CONNECTOR_LEADS,
        connector_source=connector_source,
        intake_channel=intake_channel,
        pretriage_policy=pretriage_policy,
    )
    clean["lead_connector_version"] = LEAD_CONNECTOR_VERSION
    clean["lead_intake_channel"] = _clean_text(intake_channel)
    clean["lead_connector_source"] = _clean_text(connector_source)
    clean["lead_received_at"] = (
        _clean_text(clean.get("lead_received_at"))
        or _clean_text(clean.get("suggested_at"))
        or _clean_text(clean.get("captured_at"))
        or _utc_now_z()
    )
    return clean


def append_leads(
    out_path: Path,
    jobs: Iterable[Dict[str, Any]],
    *,
    intake_channel: str,
    connector_source: str,
    pretriage_policy: str = POLICY_FULL_FEED,
) -> List[Dict[str, Any]]:
    prepared = [
        prepare_lead_record(
            job,
            intake_channel=intake_channel,
            connector_source=connector_source,
            pretriage_policy=pretriage_policy,
        )
        for job in jobs
    ]
    if not prepared:
        return []

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "a", encoding="utf-8") as handle:
        for job in prepared:
            handle.write(json.dumps(job, ensure_ascii=False) + "\n")
    return prepared
