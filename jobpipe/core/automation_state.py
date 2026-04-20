from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from jobpipe.core.paths import JobPipePaths

AUTOMATION_SCHEMA_VERSION = "jobpipe.automation.v1"
AUTOMATION_STATE_VERSION = "jobpipe.automation-runs.v1"
_MAX_RUNS = 30


@dataclass(frozen=True)
class AutomationAction:
    key: str
    label: str
    category: str
    description: str
    impact: str


AUTOMATION_ACTIONS: List[AutomationAction] = [
    AutomationAction(
        key="nav_refresh",
        label="Refresh NAV connector",
        category="connector",
        description="Pull only changed rows from the NAV Sheet/API bridge into NAV connector staging.",
        impact="Updates broad-feed staging without running the main pipeline.",
    ),
    AutomationAction(
        key="mailbox_leads_dry_run",
        label="Mailbox lead intake (dry run)",
        category="connector",
        description="Preview recommended-lead intake from mailbox signals without writing new lead rows.",
        impact="Safe connector preview for FINN or later LinkedIn suggestion intake.",
    ),
    AutomationAction(
        key="merge_connectors",
        label="Rebuild merged queue",
        category="pipeline",
        description="Merge NAV and lead-style staging into the shared pre-triage queue with dedupe.",
        impact="Refreshes jobs_delta.jsonl from connector staging without draining the pipeline.",
    ),
    AutomationAction(
        key="export_dashboard",
        label="Rebuild dashboard export",
        category="control_plane",
        description="Re-export the static dashboard from the current ledger and local control-plane state.",
        impact="Refreshes the static export without changing pipeline data.",
    ),
]


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            count += 1
    return count


def _empty_state() -> Dict[str, Any]:
    return {
        "schema_version": AUTOMATION_STATE_VERSION,
        "updated_at": "",
        "runs": [],
    }


def load_automation_state(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_state()
    if not isinstance(raw, dict):
        return _empty_state()
    runs = raw.get("runs", [])
    if not isinstance(runs, list):
        runs = []
    return {
        "schema_version": str(raw.get("schema_version") or AUTOMATION_STATE_VERSION),
        "updated_at": str(raw.get("updated_at") or ""),
        "runs": [run for run in runs if isinstance(run, dict)][:_MAX_RUNS],
    }


def persist_automation_state(path: Path, state: Dict[str, Any]) -> Dict[str, Any]:
    clean = {
        "schema_version": AUTOMATION_STATE_VERSION,
        "updated_at": _utc_now_z(),
        "runs": [run for run in list(state.get("runs", []))[:_MAX_RUNS] if isinstance(run, dict)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return clean


def append_automation_run(path: Path, run: Dict[str, Any]) -> Dict[str, Any]:
    state = load_automation_state(path)
    runs = [candidate for candidate in state.get("runs", []) if candidate.get("run_id") != run.get("run_id")]
    runs.insert(0, run)
    state["runs"] = runs[:_MAX_RUNS]
    return persist_automation_state(path, state)


def update_automation_run(path: Path, run_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    state = load_automation_state(path)
    runs = []
    target: Dict[str, Any] | None = None
    for run in state.get("runs", []):
        if str(run.get("run_id") or "") != run_id:
            runs.append(run)
            continue
        target = {**run, **updates}
        runs.append(target)
    state["runs"] = runs[:_MAX_RUNS]
    persist_automation_state(path, state)
    return target or {}


def build_automation_payload(paths: JobPipePaths, *, state_path: Path | None = None) -> Dict[str, Any]:
    state_file = state_path or paths.automation_state_path
    state = load_automation_state(state_file)
    runs = [dict(run) for run in state.get("runs", []) if isinstance(run, dict)]
    running = sum(1 for run in runs if str(run.get("status") or "") == "running")
    failed = sum(1 for run in runs if str(run.get("status") or "") == "failed")
    succeeded = sum(1 for run in runs if str(run.get("status") or "") == "succeeded")
    last_run_at = ""
    for run in runs:
        finished_at = str(run.get("finished_at") or run.get("started_at") or "")
        if finished_at:
            last_run_at = finished_at
            break

    return {
        "schema_version": AUTOMATION_SCHEMA_VERSION,
        "state_path": str(state_file),
        "updated_at": str(state.get("updated_at") or ""),
        "connector_counts": {
            "nav_connector_rows": _count_jsonl_rows(paths.nav_connector_path),
            "lead_connector_rows": _count_jsonl_rows(paths.leads_connector_path),
            "merged_queue_rows": _count_jsonl_rows(paths.jobs_delta_path),
        },
        "summary": {
            "running": running,
            "failed": failed,
            "succeeded": succeeded,
            "recent_runs": len(runs),
            "last_run_at": last_run_at,
        },
        "actions": [
            {
                "key": action.key,
                "label": action.label,
                "category": action.category,
                "description": action.description,
                "impact": action.impact,
            }
            for action in AUTOMATION_ACTIONS
        ],
        "recent_runs": runs,
    }
