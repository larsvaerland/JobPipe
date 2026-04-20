from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict
from urllib.parse import quote

from jobpipe.core.io import load_env_file
from jobpipe.core.jobsync import (
    build_connector_envelope,
    load_jobsync_settings,
    post_jobsync_json,
    resolve_jobsync_user_email,
    write_jobsync_outbox,
)
from jobpipe.core.paths import JobPipePaths
from jobpipe.core.settings_state import load_settings_state


AUTHORING_SYNC_VERSION = "jobpipe.authoring-sync.v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clean_artifact_refs(value: Any) -> list[Dict[str, str]]:
    refs: list[Dict[str, str]] = []
    if not isinstance(value, list):
        return refs
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        ref = {
            "kind": _clean_text(item.get("kind")),
            "label": _clean_text(item.get("label")),
            "path": _clean_text(item.get("path")),
            "url": _clean_text(item.get("url")),
        }
        if not any(ref.values()):
            continue
        refs.append(ref)
    return refs


def _clean_authoring_state(authoring_state: Dict[str, Any]) -> Dict[str, Any]:
    sections = {
        "resume": (
            "variantRef",
            "variantLabel",
            "sourceUrl",
            "exportRef",
            "exportLabel",
            "exportUrl",
            "exportFormat",
            "exportedAt",
            "exportPdfPath",
            "exportJsonPath",
        ),
        "coverLetter": (
            "documentRef",
            "documentLabel",
            "sourceUrl",
            "exportRef",
            "exportLabel",
            "exportUrl",
            "exportFormat",
            "exportedAt",
            "exportDocxPath",
        ),
        "screeningAnswers": (
            "documentRef",
            "documentLabel",
            "sourceUrl",
            "exportRef",
            "exportLabel",
            "exportUrl",
            "exportFormat",
            "exportedAt",
            "exportDocxPath",
        ),
    }
    clean = {
        "schemaVersion": _clean_text(authoring_state.get("schemaVersion")) or AUTHORING_SYNC_VERSION,
        "jobId": _clean_text(authoring_state.get("jobId")),
        "updatedAt": _clean_text(authoring_state.get("updatedAt")) or _now_iso(),
    }
    for section_name, field_names in sections.items():
        raw = authoring_state.get(section_name)
        section: Dict[str, Any] = {"artifactRefs": []}
        if isinstance(raw, dict):
            for field_name in field_names:
                section[field_name] = _clean_text(raw.get(field_name))
            section["artifactRefs"] = _clean_artifact_refs(raw.get("artifactRefs"))
        else:
            for field_name in field_names:
                section[field_name] = ""
        clean[section_name] = section
    return clean


def _jobpipe_base_url(paths: JobPipePaths) -> str:
    load_env_file(paths.env_file)
    base_url = (
        os.environ.get("JOBPIPE_BASE_URL", "").strip()
        or os.environ.get("NEXT_PUBLIC_JOBPIPE_BASE_URL", "").strip()
    )
    return base_url.rstrip("/")


def build_authoring_sync_record(
    job_id: str,
    authoring_state: Dict[str, Any],
    *,
    jobpipe_base_url: str = "",
) -> Dict[str, Any]:
    clean = _clean_authoring_state(authoring_state)
    base_url = jobpipe_base_url.rstrip("/")
    encoded_job_id = quote(str(job_id), safe="")
    return {
        "externalSource": "jobpipe",
        "externalId": str(job_id).strip(),
        "updatedAt": clean["updatedAt"],
        "workspaceUrl": f"{base_url}/apply/{encoded_job_id}" if base_url else "",
        "applySessionUrl": f"{base_url}/api/apply_session/{encoded_job_id}" if base_url else "",
        "authoringState": clean,
    }


def sync_authoring_state(paths: JobPipePaths, job_id: str, authoring_state: Dict[str, Any]) -> Dict[str, Any]:
    settings_state = load_settings_state(paths.settings_state_path)
    jobsync_integration = (settings_state.get("integrations", {}) or {}).get("jobsync", {}) or {}
    if not jobsync_integration.get("enabled"):
        return {"status": "skipped", "reason": "JobSync integration disabled in local settings."}

    try:
        settings = load_jobsync_settings(paths)
        user_email = resolve_jobsync_user_email(paths)
    except Exception as exc:
        return {"status": "skipped", "reason": str(exc)}

    record = build_authoring_sync_record(
        job_id,
        authoring_state,
        jobpipe_base_url=_jobpipe_base_url(paths),
    )
    envelope = build_connector_envelope(
        "authoring_sync",
        user_email,
        {"authoring": [record]},
    )

    try:
        response = post_jobsync_json(
            settings,
            settings.authoring_sync_path,
            envelope,
        )
        return {
            "status": "synced",
            "updated": int(response.get("updated", 0)),
            "missing": int(response.get("missing", 0)),
        }
    except Exception as exc:
        outbox_path = write_jobsync_outbox(paths, "authoring_sync", envelope)
        return {
            "status": "failed",
            "error": str(exc),
            "outboxPath": str(outbox_path),
        }
