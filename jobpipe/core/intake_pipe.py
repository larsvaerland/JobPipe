from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from jobpipe.core.io import stable_job_id

INTAKE_CONNECTOR_VERSION = "jobpipe.intake-connector.v1"
INTAKE_MERGE_VERSION = "jobpipe.intake-merge.v1"

POLICY_FULL_FEED = "full_feed"
POLICY_SUGGESTED_LEAD = "suggested_lead"

CONNECTOR_NAV = "nav_feed"
CONNECTOR_LEADS = "suggested_leads"

CANONICAL_FIELD_CANDIDATES = (
    "title",
    "normalized_title",
    "employer_name",
    "description_html",
    "applicationDue",
    "applicationUrl",
    "sourceurl",
    "link",
    "work_city",
    "work_county",
    "work_postalCode",
    "workLocations_json",
    "sector",
    "source",
)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_text(value: Any) -> str:
    text = _clean_text(value).lower()
    text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _suggested_from_policy(policy: str) -> bool:
    return policy == POLICY_SUGGESTED_LEAD


def _completeness_score(job: Dict[str, Any]) -> int:
    score = 0
    for key in CANONICAL_FIELD_CANDIDATES:
        if _clean_text(job.get(key)):
            score += 1
    return score


def derive_intake_dedupe_key(job: Dict[str, Any]) -> str:
    title = _normalize_text(job.get("normalized_title") or job.get("title"))
    employer = _normalize_text(job.get("employer_name"))
    due = _clean_text(job.get("applicationDue"))
    city = _normalize_text(job.get("work_city"))
    county = _normalize_text(job.get("work_county"))

    if title and employer:
        location = city or county
        return "::".join([title, employer, location or due or "-"])
    return stable_job_id(job)


def prepare_connector_record(
    job: Dict[str, Any],
    *,
    connector_name: str,
    connector_source: str,
    intake_channel: str,
    pretriage_policy: str,
) -> Dict[str, Any]:
    clean = dict(job)
    clean["intake_connector_version"] = INTAKE_CONNECTOR_VERSION
    clean["intake_connector_name"] = _clean_text(connector_name)
    clean["intake_connector_source"] = _clean_text(connector_source)
    clean["intake_channel"] = _clean_text(intake_channel)
    clean["intake_pretriage_policy"] = _clean_text(pretriage_policy) or POLICY_FULL_FEED
    clean["suggested_by_platform"] = bool(
        clean.get("suggested_by_platform") or _suggested_from_policy(clean["intake_pretriage_policy"])
    )
    clean["intake_dedupe_key"] = _clean_text(clean.get("intake_dedupe_key")) or derive_intake_dedupe_key(clean)
    return clean


def append_connector_records(
    out_path: Path,
    jobs: Iterable[Dict[str, Any]],
    *,
    connector_name: str,
    connector_source: str,
    intake_channel: str,
    pretriage_policy: str,
) -> List[Dict[str, Any]]:
    prepared = [
        prepare_connector_record(
            job,
            connector_name=connector_name,
            connector_source=connector_source,
            intake_channel=intake_channel,
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


def _read_connector_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _choose_canonical(group: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    def _rank(job: Dict[str, Any]) -> tuple[int, int]:
        connector_name = _clean_text(job.get("intake_connector_name"))
        is_nav = 1 if connector_name == CONNECTOR_NAV else 0
        return (is_nav, _completeness_score(job))

    return max(group, key=_rank)


def _merge_group(group: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    canonical = dict(_choose_canonical(group))
    alternates = [job for job in group if job is not canonical]

    for alt in alternates:
        for key in CANONICAL_FIELD_CANDIDATES:
            if not _clean_text(canonical.get(key)) and _clean_text(alt.get(key)):
                canonical[key] = alt.get(key)

    policies = {_clean_text(job.get("intake_pretriage_policy")) or POLICY_FULL_FEED for job in group}
    connector_names = sorted({_clean_text(job.get("intake_connector_name")) for job in group if _clean_text(job.get("intake_connector_name"))})

    canonical["intake_merge_version"] = INTAKE_MERGE_VERSION
    canonical["intake_connector_names"] = connector_names
    canonical["intake_pretriage_policy"] = (
        POLICY_SUGGESTED_LEAD if POLICY_SUGGESTED_LEAD in policies else POLICY_FULL_FEED
    )
    canonical["suggested_by_platform"] = any(bool(job.get("suggested_by_platform")) for job in group)
    canonical["intake_source_variants"] = [
        {
            "job_id": _clean_text(job.get("job_id")),
            "source": _clean_text(job.get("source")),
            "connector_name": _clean_text(job.get("intake_connector_name")),
            "connector_source": _clean_text(job.get("intake_connector_source")),
            "intake_channel": _clean_text(job.get("intake_channel")),
            "pretriage_policy": _clean_text(job.get("intake_pretriage_policy")) or POLICY_FULL_FEED,
        }
        for job in group
    ]
    return canonical


def merge_connector_records(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        prepared = prepare_connector_record(
            record,
            connector_name=_clean_text(record.get("intake_connector_name")) or CONNECTOR_LEADS,
            connector_source=_clean_text(record.get("intake_connector_source")) or _clean_text(record.get("source")) or "unknown",
            intake_channel=_clean_text(record.get("intake_channel")) or "unknown",
            pretriage_policy=_clean_text(record.get("intake_pretriage_policy")) or POLICY_FULL_FEED,
        )
        grouped.setdefault(prepared["intake_dedupe_key"], []).append(prepared)

    merged = [_merge_group(group) for group in grouped.values()]
    merged.sort(key=lambda row: (_clean_text(row.get("applicationDue")) or "9999-99-99", _clean_text(row.get("title"))))
    return merged


def rebuild_intake_queue(*, nav_path: Path, leads_path: Path, out_path: Path) -> Dict[str, int]:
    nav_records = _read_connector_records(nav_path)
    lead_records = _read_connector_records(leads_path)
    merged = merge_connector_records([*nav_records, *lead_records])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        for row in merged:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "nav_records": len(nav_records),
        "lead_records": len(lead_records),
        "merged_records": len(merged),
    }


def prune_connector_records(path: Path, processed_keys: Sequence[str]) -> int:
    if not path.exists() or not processed_keys:
        return 0
    processed = set(processed_keys)
    kept: List[str] = []
    removed = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            kept.append(raw)
            continue
        key = _clean_text(obj.get("intake_dedupe_key")) or derive_intake_dedupe_key(obj)
        if key in processed:
            removed += 1
            continue
        kept.append(json.dumps(obj, ensure_ascii=False))
    path.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
    return removed
