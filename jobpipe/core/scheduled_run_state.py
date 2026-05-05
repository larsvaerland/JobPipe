from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from jobpipe.core.paths import JobPipePaths

SCHEDULED_RUN_STATE_VERSION = "jobpipe.scheduled-run-state.v1"
SCHEDULED_RUN_CONTROL_VERSION = "jobpipe.scheduled-run-control.v1"
_FRESH_HOURS = 36.0
_AGING_HOURS = 72.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_z() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def _parse_iso_utc(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _empty_state() -> Dict[str, Any]:
    return {
        "schema_version": SCHEDULED_RUN_STATE_VERSION,
        "updated_at": "",
        "current_run": {},
        "last_attempt": {},
        "last_success": {},
        "last_companion_check": {},
    }


def _clean_run(run: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(run, dict):
        return {}
    steps = run.get("steps") if isinstance(run.get("steps"), list) else []
    clean_steps: List[Dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        clean_steps.append(
            {
                "key": str(step.get("key") or ""),
                "label": str(step.get("label") or ""),
                "status": str(step.get("status") or ""),
                "started_at": str(step.get("started_at") or ""),
                "finished_at": str(step.get("finished_at") or ""),
                "summary": str(step.get("summary") or ""),
                "log_excerpt": str(step.get("log_excerpt") or ""),
                "required": bool(step.get("required", True)),
            }
        )
    return {
        "run_id": str(run.get("run_id") or ""),
        "flow_key": str(run.get("flow_key") or ""),
        "label": str(run.get("label") or ""),
        "status": str(run.get("status") or ""),
        "started_at": str(run.get("started_at") or ""),
        "finished_at": str(run.get("finished_at") or ""),
        "summary": str(run.get("summary") or ""),
        "log_excerpt": str(run.get("log_excerpt") or ""),
        "max_jobs": int(run.get("max_jobs") or 0),
        "with_suggestions": bool(run.get("with_suggestions")),
        "allow_companion_drift": bool(run.get("allow_companion_drift")),
        "companion_status": str(run.get("companion_status") or ""),
        "steps": clean_steps,
    }


def _compact_companion(check: Dict[str, Any]) -> Dict[str, Any]:
    companions = check.get("companions") if isinstance(check.get("companions"), list) else []
    return {
        "checked_at": str(check.get("checked_at") or ""),
        "status": str(check.get("status") or ""),
        "summary": str(check.get("summary") or ""),
        "companions": [
            {
                "id": str(item.get("id") or ""),
                "status": str(item.get("status") or ""),
                "actual_branch": str(item.get("actual_branch") or ""),
                "actual_commit": str(item.get("actual_commit") or ""),
                "pinned_branch": str(item.get("pinned_branch") or ""),
                "pinned_commit": str(item.get("pinned_commit") or ""),
                "dirty": bool(item.get("dirty")),
                "notes": [str(note) for note in item.get("notes", []) if str(note).strip()],
            }
            for item in companions
            if isinstance(item, dict)
        ],
    }


def load_scheduled_run_state(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_state()
    if not isinstance(raw, dict):
        return _empty_state()
    return {
        "schema_version": str(raw.get("schema_version") or SCHEDULED_RUN_STATE_VERSION),
        "updated_at": str(raw.get("updated_at") or ""),
        "current_run": _clean_run(raw.get("current_run")),
        "last_attempt": _clean_run(raw.get("last_attempt")),
        "last_success": _clean_run(raw.get("last_success")),
        "last_companion_check": _compact_companion(raw.get("last_companion_check") or {}),
    }


def persist_scheduled_run_state(path: Path, state: Dict[str, Any]) -> Dict[str, Any]:
    clean = {
        "schema_version": SCHEDULED_RUN_STATE_VERSION,
        "updated_at": _utc_now_z(),
        "current_run": _clean_run(state.get("current_run")),
        "last_attempt": _clean_run(state.get("last_attempt")),
        "last_success": _clean_run(state.get("last_success")),
        "last_companion_check": _compact_companion(state.get("last_companion_check") or {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return clean


def start_scheduled_run(path: Path, run: Dict[str, Any]) -> Dict[str, Any]:
    state = load_scheduled_run_state(path)
    clean_run = _clean_run(run)
    state["current_run"] = clean_run
    state["last_attempt"] = clean_run
    persist_scheduled_run_state(path, state)
    return clean_run


def update_scheduled_run(path: Path, run_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    state = load_scheduled_run_state(path)
    current = dict(state.get("current_run") or {})
    attempt = dict(state.get("last_attempt") or {})
    target = current if str(current.get("run_id") or "") == run_id else attempt
    if str(target.get("run_id") or "") != run_id:
        return {}
    target = _clean_run({**target, **updates})
    if str((state.get("current_run") or {}).get("run_id") or "") == run_id:
        state["current_run"] = target
    state["last_attempt"] = target
    persist_scheduled_run_state(path, state)
    return target


def finish_scheduled_run(path: Path, run_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    state = load_scheduled_run_state(path)
    target = dict(state.get("last_attempt") or {})
    if str(target.get("run_id") or "") != run_id:
        current = dict(state.get("current_run") or {})
        if str(current.get("run_id") or "") == run_id:
            target = current
    if str(target.get("run_id") or "") != run_id:
        return {}
    target = _clean_run({**target, **updates})
    state["current_run"] = {}
    state["last_attempt"] = target
    if str(target.get("status") or "") == "succeeded":
        state["last_success"] = target
    persist_scheduled_run_state(path, state)
    return target


def record_companion_check(path: Path, report: Dict[str, Any]) -> Dict[str, Any]:
    state = load_scheduled_run_state(path)
    companions = report.get("companions") if isinstance(report.get("companions"), list) else []
    summary = (
        "Companion revisions aligned."
        if str(report.get("status") or "") == "aligned"
        else "Companion revision drift detected."
    )
    state["last_companion_check"] = _compact_companion(
        {
            "checked_at": _utc_now_z(),
            "status": str(report.get("status") or ""),
            "summary": summary,
            "companions": companions,
        }
    )
    persist_scheduled_run_state(path, state)
    return dict(state["last_companion_check"])


def _freshness_summary(last_success_at: str) -> Dict[str, Any]:
    parsed = _parse_iso_utc(last_success_at)
    if not parsed:
        return {
            "status": "never",
            "label": "Never run",
            "hours_since_success": None,
        }
    hours = round((_utc_now() - parsed).total_seconds() / 3600.0, 2)
    if hours <= _FRESH_HOURS:
        status = "fresh"
        label = "Fresh"
    elif hours <= _AGING_HOURS:
        status = "aging"
        label = "Aging"
    else:
        status = "stale"
        label = "Stale"
    return {
        "status": status,
        "label": label,
        "hours_since_success": hours,
    }


def build_scheduled_run_payload(paths: JobPipePaths, *, state_path: Path | None = None) -> Dict[str, Any]:
    state_file = state_path or paths.scheduled_run_state_path
    state = load_scheduled_run_state(state_file)
    current_run = dict(state.get("current_run") or {})
    last_attempt = dict(state.get("last_attempt") or {})
    last_success = dict(state.get("last_success") or {})
    companion = dict(state.get("last_companion_check") or {})
    last_success_at = str(last_success.get("finished_at") or last_success.get("started_at") or "")
    last_attempt_at = str(last_attempt.get("finished_at") or last_attempt.get("started_at") or "")
    freshness = _freshness_summary(last_success_at)

    if str(current_run.get("status") or "") == "running":
        overall_status = "running"
    elif not last_attempt:
        overall_status = "never_run"
    elif str(last_attempt.get("status") or "") == "succeeded":
        overall_status = "ready" if freshness["status"] != "stale" else "stale"
    else:
        overall_status = str(last_attempt.get("status") or "failed")

    return {
        "schema_version": SCHEDULED_RUN_CONTROL_VERSION,
        "state_path": str(state_file),
        "entrypoint_command": ".\\go.ps1",
        "underlying_cli": "python -m jobpipe.cli.run_scheduled_flow",
        "updated_at": str(state.get("updated_at") or ""),
        "summary": {
            "status": overall_status,
            "last_attempt_at": last_attempt_at,
            "last_success_at": last_success_at,
            "freshness_status": freshness["status"],
            "freshness_label": freshness["label"],
            "hours_since_success": freshness["hours_since_success"],
            "companion_status": str(companion.get("status") or "unknown"),
        },
        "current_run": current_run,
        "last_attempt": last_attempt,
        "last_success": last_success,
        "last_companion_check": companion,
    }
