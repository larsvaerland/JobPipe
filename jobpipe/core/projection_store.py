from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


PROJECTION_STORE_VERSION = "jobpipe.projection-store.v1"


def _default_store() -> Dict[str, Any]:
    return {
        "schemaVersion": PROJECTION_STORE_VERSION,
        "inputEnrichment": {},
        "detailProjections": {},
    }


def load_projection_store(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return _default_store()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_store()
    if not isinstance(raw, dict):
        return _default_store()
    store = _default_store()
    if isinstance(raw.get("inputEnrichment"), dict):
        store["inputEnrichment"] = raw["inputEnrichment"]
    if isinstance(raw.get("detailProjections"), dict):
        store["detailProjections"] = raw["detailProjections"]
    return store


def persist_projection_store(path: Path, store: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _default_store()
    if isinstance(store.get("inputEnrichment"), dict):
        normalized["inputEnrichment"] = store["inputEnrichment"]
    if isinstance(store.get("detailProjections"), dict):
        normalized["detailProjections"] = store["detailProjections"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def projection_key(*, run_id: str, job_id: str) -> str:
    return f"{str(run_id).strip()}::{str(job_id).strip()}"


def get_projection(store: Dict[str, Any], section: str, key: str) -> Dict[str, Any]:
    bucket = store.get(section, {})
    if not isinstance(bucket, dict):
        return {}
    value = bucket.get(key, {})
    return value if isinstance(value, dict) else {}


def set_projection(store: Dict[str, Any], section: str, key: str, value: Dict[str, Any]) -> None:
    if section not in store or not isinstance(store.get(section), dict):
        store[section] = {}
    store[section][key] = value


def load_job_projection_context(path: Path, *, run_id: str, job_id: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    store = load_projection_store(path)
    key = projection_key(run_id=run_id, job_id=job_id)
    input_projection = get_projection(store, "inputEnrichment", key)
    detail_projection = get_projection(store, "detailProjections", key)
    return (
        input_projection if isinstance(input_projection, dict) else {},
        detail_projection if isinstance(detail_projection, dict) else {},
    )


def build_job_projection_bundle(
    *,
    input_enrichment: Dict[str, Any] | None = None,
    detail_projection: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "input_enrichment": input_enrichment if isinstance(input_enrichment, dict) else {},
        "detail_projection": detail_projection if isinstance(detail_projection, dict) else {},
    }


def projection_bundle_input_enrichment(bundle: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(bundle, dict):
        return {}
    value = bundle.get("input_enrichment", {})
    return value if isinstance(value, dict) else {}


def projection_bundle_detail_projection(bundle: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(bundle, dict):
        return {}
    value = bundle.get("detail_projection", {})
    return value if isinstance(value, dict) else {}


def get_job_projection_bundle(store: Dict[str, Any], *, run_id: str, job_id: str) -> Dict[str, Any]:
    key = projection_key(run_id=run_id, job_id=job_id)
    return build_job_projection_bundle(
        input_enrichment=get_projection(store, "inputEnrichment", key),
        detail_projection=get_projection(store, "detailProjections", key),
    )


def load_job_projection_bundle(path: Path, *, run_id: str, job_id: str) -> Dict[str, Any]:
    store = load_projection_store(path)
    return get_job_projection_bundle(store, run_id=run_id, job_id=job_id)


def set_job_projection_bundle(
    store: Dict[str, Any],
    *,
    run_id: str,
    job_id: str,
    bundle: Dict[str, Any],
) -> None:
    key = projection_key(run_id=run_id, job_id=job_id)
    input_enrichment = projection_bundle_input_enrichment(bundle)
    detail_projection = projection_bundle_detail_projection(bundle)
    if input_enrichment:
        set_projection(store, "inputEnrichment", key, input_enrichment)
    if detail_projection:
        set_projection(store, "detailProjections", key, detail_projection)


def projection_job_summary(detail_projection: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(detail_projection, dict):
        return {}
    projection = detail_projection.get("application_case_projection", {})
    if not isinstance(projection, dict):
        return {}
    summary = projection.get("job_summary", {}) or {}
    return summary if isinstance(summary, dict) else {}


def projection_decision_brief(detail_projection: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(detail_projection, dict):
        return {}
    brief = detail_projection.get("decision_brief", {}) or {}
    return brief if isinstance(brief, dict) else {}


def build_input_enrichment_projection(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "employer": str(row.get("employer") or ""),
        "normalized_title": str(row.get("normalized_title") or ""),
        "application_url": str(row.get("application_url") or ""),
        "source_url": str(row.get("source_url") or ""),
        "applicationDue": str(row.get("applicationDue") or ""),
        "work_city": str(row.get("work_city") or ""),
        "work_county": str(row.get("work_county") or ""),
        "work_postalCode": str(row.get("work_postalCode") or ""),
        "job_source": str(row.get("job_source") or ""),
    }


def apply_input_enrichment_projection(row: Dict[str, Any], projection: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    if not isinstance(projection, dict) or not projection:
        return row
    for field_name in (
        "employer",
        "normalized_title",
        "application_url",
        "source_url",
        "applicationDue",
        "work_city",
        "work_county",
        "work_postalCode",
        "job_source",
    ):
        if not str(row.get(field_name) or "").strip():
            row[field_name] = projection.get(field_name) or row.get(field_name) or ""
    return row


def build_projected_job_input(
    *,
    job_id: str,
    input_projection: Dict[str, Any],
    detail_projection: Dict[str, Any],
) -> Dict[str, Any]:
    summary = projection_job_summary(detail_projection)
    return {
        "job_id": job_id,
        "title": summary.get("title", ""),
        "normalized_title": input_projection.get("normalized_title", ""),
        "employer_name": input_projection.get("employer") or summary.get("company", ""),
        "work_city": input_projection.get("work_city", ""),
        "work_county": input_projection.get("work_county", ""),
        "work_postalCode": input_projection.get("work_postalCode", ""),
        "applicationDue": input_projection.get("applicationDue") or summary.get("application_due", ""),
        "sourceurl": input_projection.get("source_url") or summary.get("source_url", ""),
        "applicationUrl": input_projection.get("application_url") or summary.get("application_url", ""),
        "source": input_projection.get("job_source") or summary.get("job_source", ""),
        "description": summary.get("description_snippet", ""),
    }


def apply_detail_projection(detail: Dict[str, Any], projection: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(detail, dict) or not isinstance(projection, dict) or not projection:
        return detail if isinstance(detail, dict) else {}
    decision_brief = projection_decision_brief(projection)
    if decision_brief.get("schema_version"):
        detail["decision_brief"] = decision_brief
    application_case_projection = projection.get("application_case_projection", {})
    if (
        isinstance(application_case_projection, dict)
        and application_case_projection.get("schema_version")
    ):
        detail["application_case_projection"] = application_case_projection
    return detail


def build_detail_projection(
    *,
    decision_brief: Dict[str, Any] | None,
    application_case_projection: Dict[str, Any] | None,
    updated_at: str = "",
) -> Dict[str, Any]:
    projection: Dict[str, Any] = {}
    if isinstance(decision_brief, dict) and decision_brief.get("schema_version"):
        projection["decision_brief"] = decision_brief
    if isinstance(application_case_projection, dict) and application_case_projection.get("schema_version"):
        projection["application_case_projection"] = application_case_projection
    if updated_at:
        projection["updated_at"] = str(updated_at)
    return projection
