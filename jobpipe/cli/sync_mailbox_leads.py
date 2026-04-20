from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from jobpipe.core.paths import bootstrap_private_data, get_jobpipe_paths
from jobpipe.core.settings_state import load_settings_state

_DEFAULT_PATHS = get_jobpipe_paths()


def _scan_suggestions(**kwargs: Any) -> int:
    from jobpipe.cli.scan_gmail import scan_suggestions

    return scan_suggestions(**kwargs)


def _process_suggested_queue(**kwargs: Any) -> Dict[str, Any]:
    from jobpipe.cli.pull_suggested import process_suggested_queue

    return process_suggested_queue(**kwargs)


def run_mailbox_lead_intake(
    *,
    data_root: str | None = None,
    settings_path: Path | None = None,
    days: int = 30,
    max_jobs: int = 20,
    min_delay: float = 3.0,
    max_delay: float = 9.0,
    force_daytime: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    paths = get_jobpipe_paths(data_root or None)
    bootstrap_private_data(paths, include_artifacts=False)
    state_path = settings_path or paths.settings_state_path
    settings = load_settings_state(state_path)
    gmail = settings.get("integrations", {}).get("gmail", {})

    if not gmail.get("lead_intake_enabled"):
        return {
            "status": "disabled",
            "queued": 0,
            "fetched": 0,
            "remaining": 0,
        }

    queued = _scan_suggestions(
        days=days,
        suggested_path=paths.suggested_jobs_path,
        ledger_path=paths.ledger_sqlite_path,
        token_path=paths.gmail_token_path,
        creds_path=paths.gmail_credentials_path,
        dry_run=dry_run,
        verbose=verbose,
    )
    fetch_result = _process_suggested_queue(
        suggested_path=paths.suggested_jobs_path,
        out_path=paths.leads_connector_path,
        ledger_path=paths.ledger_sqlite_path,
        max_jobs=max_jobs,
        min_delay=min_delay,
        max_delay=max_delay,
        force_daytime=force_daytime,
        dry_run=dry_run,
        verbose=verbose,
    )
    return {
        "status": fetch_result.get("status", "ok"),
        "queued": queued,
        "fetched": fetch_result.get("fetched", 0),
        "failed": fetch_result.get("failed", 0),
        "remaining": fetch_result.get("remaining", 0),
        "linkedin_pending": fetch_result.get("linkedin_pending", 0),
    }


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Run mailbox recommendation intake into the normal JobPipe lead connector. "
            "This reads the JobPipe settings state and only processes Gmail lead intake when enabled."
        )
    )
    ap.add_argument(
        "--data-root",
        default="",
        help=f"JobPipe user data root (default: {_DEFAULT_PATHS.data_root})",
    )
    ap.add_argument(
        "--settings",
        default="",
        help=f"Settings state path (default: {_DEFAULT_PATHS.settings_state_path})",
    )
    ap.add_argument("--days", type=int, default=30, help="Days back to scan mailbox recommendations.")
    ap.add_argument("--max", type=int, default=20, help="Max FINN leads to fetch from the mailbox queue.")
    ap.add_argument("--min-delay", type=float, default=3.0, help="Min seconds between FINN fetches.")
    ap.add_argument("--max-delay", type=float, default=9.0, help="Max seconds between FINN fetches.")
    ap.add_argument("--force-daytime", action="store_true", help="Bypass the daytime guard during testing.")
    ap.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args(argv)

    result = run_mailbox_lead_intake(
        data_root=args.data_root or None,
        settings_path=Path(args.settings) if args.settings else None,
        days=args.days,
        max_jobs=args.max,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        force_daytime=args.force_daytime,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    if result["status"] == "disabled":
        print("Mailbox lead intake is disabled in Settings / Integrations. No leads were scanned.")
        return

    print(
        f"Mailbox lead intake summary:\n"
        f"  queued from Gmail: {result['queued']}\n"
        f"  fetched into lead connector staging: {result['fetched']}\n"
        f"  failed fetches: {result.get('failed', 0)}\n"
        f"  remaining mailbox queue: {result['remaining']}\n"
        f"  LinkedIn manual follow-up: {result.get('linkedin_pending', 0)}\n"
        f"  status: {result['status']}"
    )


if __name__ == "__main__":
    main()
