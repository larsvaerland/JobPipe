from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import requests

from jobpipe.core.io import load_env_file
from jobpipe.core.paths import JobPipePaths


@dataclass(frozen=True)
class JobSyncSettings:
    base_url: str
    token: str
    user_email: str
    jobs_import_path: str = "/api/integrations/jobpipe/jobs"
    status_sync_path: str = "/api/integrations/jobpipe/status"
    authoring_sync_path: str = "/api/integrations/jobpipe/authoring"
    timeout_seconds: float = 30.0


CONNECTOR_CONTRACT_VERSION = "jobpipe.jobsync.v1"
APPLICATION_PACKET_VERSION = "jobpipe.application-packet.v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def jobsync_outbox_dir(paths: JobPipePaths) -> Path:
    return paths.reports_dir / "connectors" / "jobsync"


def resolve_jobsync_user_email(paths: JobPipePaths, explicit_email: str = "") -> str:
    load_env_file(paths.env_file)
    user_email = explicit_email.strip() or os.environ.get("JOBSYNC_USER_EMAIL", "").strip()
    if not user_email:
        raise RuntimeError("Missing JobSync integration setting: JOBSYNC_USER_EMAIL")
    return user_email


def build_connector_envelope(kind: str, user_email: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "contractVersion": CONNECTOR_CONTRACT_VERSION,
        "producer": "jobpipe",
        "kind": kind,
        "sentAt": _now_iso(),
        "userEmail": user_email,
        **payload,
    }


def write_jobsync_outbox(paths: JobPipePaths, kind: str, envelope: Dict[str, Any]) -> Path:
    outbox_dir = jobsync_outbox_dir(paths)
    outbox_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = outbox_dir / f"{stamp}_{kind}.json"
    path.write_text(__import__("json").dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_jobsync_settings(paths: JobPipePaths) -> JobSyncSettings:
    load_env_file(paths.env_file)

    base_url = os.environ.get("JOBSYNC_BASE_URL", "http://127.0.0.1:3737").strip().rstrip("/")
    token = os.environ.get("JOBSYNC_SYNC_TOKEN", "").strip()
    user_email = os.environ.get("JOBSYNC_USER_EMAIL", "").strip()
    jobs_import_path = os.environ.get("JOBSYNC_JOBS_IMPORT_PATH", "/api/integrations/jobpipe/jobs").strip() or "/api/integrations/jobpipe/jobs"
    status_sync_path = os.environ.get("JOBSYNC_STATUS_SYNC_PATH", "/api/integrations/jobpipe/status").strip() or "/api/integrations/jobpipe/status"
    authoring_sync_path = os.environ.get("JOBSYNC_AUTHORING_SYNC_PATH", "/api/integrations/jobpipe/authoring").strip() or "/api/integrations/jobpipe/authoring"

    missing = []
    if not token:
        missing.append("JOBSYNC_SYNC_TOKEN")
    if not user_email:
        missing.append("JOBSYNC_USER_EMAIL")
    if missing:
        raise RuntimeError("Missing JobSync integration settings: " + ", ".join(missing))

    return JobSyncSettings(
        base_url=base_url,
        token=token,
        user_email=user_email,
        jobs_import_path=jobs_import_path,
        status_sync_path=status_sync_path,
        authoring_sync_path=authoring_sync_path,
        timeout_seconds=float(os.environ.get("JOBSYNC_TIMEOUT_SECONDS", "30").strip() or "30"),
    )


def post_jobsync_json(settings: JobSyncSettings, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(
        settings.base_url + path,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "X-JobPipe-Token": settings.token,
        },
        timeout=settings.timeout_seconds,
    )

    try:
        data = response.json()
    except Exception:
        data = {"raw_text": response.text}

    if not response.ok:
        message = ""
        if isinstance(data, dict):
            message = str(data.get("message") or data.get("error") or data)
        raise RuntimeError(f"JobSync request failed ({response.status_code}): {message}")

    return data if isinstance(data, dict) else {"data": data}
