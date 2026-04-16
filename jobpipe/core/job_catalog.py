from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from jobpipe.core.io import clean, html_to_text, pick, stable_job_id


def _normalize_key_part(value: Any) -> str:
    text = clean(value).lower()
    text = re.sub(r"\s+", " ", text)
    return text


def canonical_job_dedupe_key(job: Mapping[str, Any]) -> str:
    title = _normalize_key_part(pick(job.get("normalized_title"), job.get("title")))
    employer = _normalize_key_part(pick(job.get("employer_name"), job.get("employer")))
    city = _normalize_key_part(job.get("work_city"))
    due = _normalize_key_part(job.get("applicationDue"))
    source_url = _normalize_key_part(pick(job.get("sourceurl"), job.get("link"), job.get("applicationUrl")))
    return "|".join([title, employer, city, due, source_url])


def canonical_job_content_hash(job: Mapping[str, Any]) -> str:
    payload = {
        "title": clean(job.get("title")),
        "normalized_title": clean(job.get("normalized_title")),
        "employer_name": clean(job.get("employer_name")),
        "description_html": clean(job.get("description_html")),
        "sourceurl": clean(job.get("sourceurl")),
        "link": clean(job.get("link")),
        "applicationUrl": clean(job.get("applicationUrl")),
        "applicationDue": clean(job.get("applicationDue")),
        "work_city": clean(job.get("work_city")),
        "work_county": clean(job.get("work_county")),
        "work_postalCode": clean(job.get("work_postalCode")),
        "sector": clean(job.get("sector")),
        "status": clean(job.get("status")),
    }
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def source_job_key(job: Mapping[str, Any]) -> str:
    return pick(
        job.get("uuid"),
        job.get("id"),
        job.get("stilling_id"),
        job.get("job_id"),
        job.get("sourceurl"),
        job.get("link"),
        job.get("applicationUrl"),
        stable_job_id(dict(job)),
    )


def source_record_id(source_name: str, source_job_key_value: str) -> str:
    raw = f"{clean(source_name)}|{clean(source_job_key_value)}"
    return "src_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _metadata_json(job: Mapping[str, Any]) -> dict[str, Any]:
    core_keys = {
        "job_id",
        "uuid",
        "id",
        "stilling_id",
        "title",
        "normalized_title",
        "employer_name",
        "employer",
        "description_html",
        "sourceurl",
        "link",
        "applicationUrl",
        "applicationDue",
        "work_city",
        "work_county",
        "work_postalCode",
        "sector",
        "status",
        "sistEndret",
        "ad_updated",
    }
    return {str(k): v for k, v in job.items() if k not in core_keys and v not in ("", None)}


def canonical_job_row(job: Mapping[str, Any], seen_at: str) -> dict[str, Any]:
    return {
        "job_id": stable_job_id(dict(job)),
        "dedupe_key": canonical_job_dedupe_key(job),
        "title": pick(job.get("normalized_title"), job.get("title")),
        "employer": pick(job.get("employer_name"), job.get("employer")),
        "work_city": clean(job.get("work_city")),
        "work_county": clean(job.get("work_county")),
        "work_postalCode": clean(job.get("work_postalCode")),
        "applicationDue": clean(job.get("applicationDue")),
        "source_url": pick(job.get("sourceurl"), job.get("link")),
        "application_url": clean(job.get("applicationUrl")),
        "description_text": html_to_text(clean(job.get("description_html")), max_chars=5000),
        "description_html": clean(job.get("description_html")),
        "sector": clean(job.get("sector")),
        "job_metadata_json": _metadata_json(job),
        "content_hash": canonical_job_content_hash(job),
        "first_seen_at": seen_at,
        "last_seen_at": seen_at,
        "closed_at": "",
        "updated_at": seen_at,
    }


def job_source_record_row(job: Mapping[str, Any], source_name: str, seen_at: str) -> dict[str, Any]:
    source_key = source_job_key(job)
    return {
        "source_record_id": source_record_id(source_name, source_key),
        "source_name": clean(source_name),
        "source_job_key": source_key,
        "job_id": stable_job_id(dict(job)),
        "seen_at": seen_at,
        "last_seen_at": seen_at,
        "is_active": 0 if clean(job.get("status")).upper() == "INACTIVE" else 1,
        "source_url": pick(job.get("sourceurl"), job.get("link")),
        "work_city": clean(job.get("work_city")),
        "work_county": clean(job.get("work_county")),
        "work_postalCode": clean(job.get("work_postalCode")),
        "applicationDue": clean(job.get("applicationDue")),
        "content_hash": canonical_job_content_hash(job),
        "raw_payload_json": dict(job),
        "updated_at": seen_at,
    }
