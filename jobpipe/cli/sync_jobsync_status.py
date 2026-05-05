from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from jobpipe.cli.mark_status import load_state, normalize_shared_status
from jobpipe.core.jobsync import (
    build_connector_envelope,
    load_jobsync_settings,
    post_jobsync_json,
    resolve_jobsync_user_email,
    write_jobsync_outbox,
)
from jobpipe.core.paths import bootstrap_private_data, get_jobpipe_paths


def _checkpoint_path(reports_dir: Path) -> Path:
    return reports_dir / "jobsync_status_sync.json"


def _load_checkpoint(path: Path) -> Dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def _save_checkpoint(path: Path, checkpoint: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_status_event(job_id: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "externalSource": "jobpipe",
        "externalId": job_id,
        "status": normalize_shared_status(entry),
        "occurredAt": str(entry.get("updated_at") or ""),
        "source": str(entry.get("source") or ""),
        "notes": str(entry.get("notes") or ""),
        "emailSubject": str(entry.get("email_subject") or ""),
        "emailDate": str(entry.get("email_date") or ""),
    }


def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Sync JobPipe application status events into JobSync.")
    ap.add_argument("--data-root", default="", help="JobPipe user data root")
    ap.add_argument("--state", default="", help="Path to application_state.json")
    ap.add_argument("--user-email", default="", help="Override JobSync target user email")
    ap.add_argument("--force", action="store_true", help="Send all known statuses, ignoring checkpoint")
    ap.add_argument("--emit-outbox", action="store_true", help="Write the connector envelope to the local outbox")
    ap.add_argument("--outbox-only", action="store_true", help="Write the connector envelope only, without POSTing")
    ap.add_argument("--dry-run", action="store_true", help="Preview payload only")
    args = ap.parse_args(argv)

    paths = get_jobpipe_paths(args.data_root or None)
    bootstrap_private_data(paths, include_artifacts=False)
    user_email = resolve_jobsync_user_email(paths, args.user_email)

    state_path = Path(args.state) if args.state else paths.application_state_path
    checkpoint_path = _checkpoint_path(paths.reports_dir)

    state = load_state(state_path)
    apps = state.get("applications", {})
    checkpoint = {} if args.force else _load_checkpoint(checkpoint_path)

    events: List[Dict[str, Any]] = []
    updated_checkpoint = dict(checkpoint)

    for job_id, entry in sorted(apps.items(), key=lambda item: str(item[1].get("updated_at") or "")):
        updated_at = str(entry.get("updated_at") or "").strip()
        status = normalize_shared_status(entry)
        if not updated_at or not status:
            continue
        if not args.force and checkpoint.get(job_id) == updated_at:
            continue
        events.append(_build_status_event(job_id, entry))
        updated_checkpoint[job_id] = updated_at

    envelope = build_connector_envelope("application_status_sync", user_email, {"events": events})

    if args.dry_run:
        print(json.dumps(envelope, ensure_ascii=False, indent=2))
        print(f"\n[DRY RUN] Prepared {len(events)} JobPipe status events for JobSync.")
        return

    if not events:
        print("No changed JobPipe status events to sync.")
        return

    if args.emit_outbox or args.outbox_only:
        outbox_path = write_jobsync_outbox(paths, "application_status_sync", envelope)
        print(f"[OK] Wrote connector envelope to {outbox_path}")
        if args.outbox_only:
            return

    settings = load_jobsync_settings(paths)
    response = post_jobsync_json(
        settings,
        settings.status_sync_path,
        envelope,
    )
    _save_checkpoint(checkpoint_path, updated_checkpoint)
    print(
        f"[OK] Synced {int(response.get('updated', 0))} JobSync status updates "
        f"({int(response.get('preserved', 0))} preserved by manual override)."
    )


if __name__ == "__main__":
    main()
