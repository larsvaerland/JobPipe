from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from jobpipe.core.companion_revisions import build_companion_revision_report
from jobpipe.core.paths import JOBPIPE_DATA_ROOT_ENV, bootstrap_private_data, get_jobpipe_paths
from jobpipe.core.scheduled_run_state import (
    finish_scheduled_run,
    record_companion_check,
    start_scheduled_run,
    update_scheduled_run,
)


def _tail_log_text(text: str, *, limit: int = 1600) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[-limit:]


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _step(
    key: str,
    label: str,
    *,
    required: bool = True,
    status: str = "pending",
    summary: str = "",
) -> Dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "started_at": "",
        "finished_at": "",
        "summary": summary,
        "log_excerpt": "",
        "required": required,
    }


def _run_subprocess(args: List[str], *, cwd: Path, env: Dict[str, str], timeout: int = 1800) -> Dict[str, Any]:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    stdout_clean = completed.stdout.strip()
    stderr_clean = completed.stderr.strip()
    combined = "\n".join(part for part in [stdout_clean, stderr_clean] if part)
    if stdout_clean:
        summary = stdout_clean.splitlines()[-1]
    elif stderr_clean:
        summary = stderr_clean.splitlines()[-1]
    else:
        summary = f"Exit code {completed.returncode}"
    return {
        "status": "succeeded" if completed.returncode == 0 else "failed",
        "exit_code": int(completed.returncode),
        "summary": summary,
        "log_excerpt": _tail_log_text(combined),
    }


def _set_step(run: Dict[str, Any], step_key: str, **updates: Any) -> None:
    for step in run.get("steps", []):
        if str(step.get("key") or "") != step_key:
            continue
        step.update(updates)
        return


def _persist_run(path: Path, run: Dict[str, Any]) -> None:
    update_scheduled_run(path, str(run.get("run_id") or ""), run)


def main(argv: List[str] | None = None) -> None:
    default_paths = get_jobpipe_paths()
    ap = argparse.ArgumentParser(description="Run the canonical JobPipe scheduled operator flow.")
    ap.add_argument(
        "--data-root",
        default="",
        help=f"JobPipe user data root (default: {default_paths.data_root})",
    )
    ap.add_argument("--config-overlay", action="append", default=[], help="Optional config overlay YAML. Can be passed multiple times.")
    ap.add_argument("--max-jobs", type=int, default=100, help="Maximum jobs to process in the run.")
    ap.add_argument("--with-suggestions", action="store_true", help="Include mailbox lead intake and FINN search refresh before the main run.")
    ap.add_argument(
        "--allow-companion-drift",
        action="store_true",
        help="Allow the run to continue even if companion revisions are not aligned.",
    )
    args = ap.parse_args(argv)

    paths = get_jobpipe_paths(args.data_root or None)
    os.environ[JOBPIPE_DATA_ROOT_ENV] = str(paths.data_root)
    bootstrap_private_data(paths, include_artifacts=True)

    env = os.environ.copy()
    env[JOBPIPE_DATA_ROOT_ENV] = str(paths.data_root)
    py = Path(sys.executable)

    run_id = f"scheduled_{uuid4().hex[:12]}"
    run = {
        "run_id": run_id,
        "flow_key": "scheduled_full_run",
        "label": "Scheduled operator flow",
        "status": "running",
        "started_at": _utc_now_z(),
        "finished_at": "",
        "summary": "Scheduled flow started.",
        "log_excerpt": "",
        "max_jobs": int(args.max_jobs),
        "with_suggestions": bool(args.with_suggestions),
        "allow_companion_drift": bool(args.allow_companion_drift),
        "companion_status": "",
        "steps": [
            _step("companion_preflight", "Companion drift preflight"),
            _step("mailbox_leads", "Mailbox lead intake", required=False, summary="Skipped unless --with-suggestions is enabled."),
            _step("pull_finn_search", "FINN search refresh", required=False, summary="Skipped unless --with-suggestions is enabled."),
            _step("drain_queue", "Drain pipeline queue"),
            _step("export_dashboard", "Rebuild dashboard export"),
        ],
    }
    start_scheduled_run(paths.scheduled_run_state_path, run)

    def persist_status(summary: str, *, log_excerpt: str = "", status: str | None = None) -> None:
        if status:
            run["status"] = status
        run["summary"] = summary
        run["log_excerpt"] = log_excerpt
        _persist_run(paths.scheduled_run_state_path, run)

    try:
        companion_report = build_companion_revision_report(paths.repo_root)
        companion_state = record_companion_check(paths.scheduled_run_state_path, companion_report)
        run["companion_status"] = str(companion_state.get("status") or "")
        preflight_summary = str(companion_state.get("summary") or "")
        if companion_report.get("status") != "aligned":
            drift_items = [
                f"{item.get('id')}: {item.get('status')}"
                for item in companion_report.get("companions", [])
                if str(item.get("status") or "") != "aligned"
            ]
            if drift_items:
                preflight_summary = preflight_summary + " " + "; ".join(drift_items)
        _set_step(
            run,
            "companion_preflight",
            status="succeeded" if companion_report.get("status") == "aligned" else "failed",
            started_at=run["started_at"],
            finished_at=_utc_now_z(),
            summary=preflight_summary.strip(),
            log_excerpt=preflight_summary.strip(),
        )
        persist_status("Companion preflight completed.")

        if companion_report.get("status") != "aligned" and not args.allow_companion_drift:
            summary = "Scheduled flow blocked by companion revision drift."
            finish_scheduled_run(
                paths.scheduled_run_state_path,
                run_id,
                {
                    **run,
                    "status": "preflight_failed",
                    "finished_at": _utc_now_z(),
                    "summary": summary,
                    "log_excerpt": preflight_summary.strip(),
                },
            )
            print(summary)
            sys.exit(1)

        overlay_args: List[str] = []
        for overlay in args.config_overlay:
            overlay_args.extend(["--config-overlay", overlay])

        if args.with_suggestions:
            mailbox_cmd = [
                str(py),
                "-m",
                "jobpipe.cli.sync_mailbox_leads",
                "--data-root",
                str(paths.data_root),
                "--days",
                "30",
                "--max",
                "20",
            ]
            _set_step(run, "mailbox_leads", status="running", started_at=_utc_now_z())
            persist_status("Running mailbox suggestion intake.")
            mailbox_result = _run_subprocess(mailbox_cmd, cwd=paths.repo_root, env=env, timeout=600)
            _set_step(
                run,
                "mailbox_leads",
                status=mailbox_result["status"],
                finished_at=_utc_now_z(),
                summary=mailbox_result["summary"],
                log_excerpt=mailbox_result["log_excerpt"],
            )
            persist_status("Optional suggestion intake completed.")

            finn_cmd = [
                str(py),
                "-m",
                "jobpipe.cli.pull_finn_search",
                "--data-root",
                str(paths.data_root),
                "--max",
                "40",
                *overlay_args,
            ]
            _set_step(run, "pull_finn_search", status="running", started_at=_utc_now_z())
            persist_status("Running FINN search refresh.")
            finn_result = _run_subprocess(finn_cmd, cwd=paths.repo_root, env=env, timeout=900)
            _set_step(
                run,
                "pull_finn_search",
                status=finn_result["status"],
                finished_at=_utc_now_z(),
                summary=finn_result["summary"],
                log_excerpt=finn_result["log_excerpt"],
            )
            persist_status("Optional FINN refresh completed.")
        else:
            now = _utc_now_z()
            _set_step(run, "mailbox_leads", status="skipped", started_at=now, finished_at=now, summary="Skipped because --with-suggestions was not set.")
            _set_step(run, "pull_finn_search", status="skipped", started_at=now, finished_at=now, summary="Skipped because --with-suggestions was not set.")
            persist_status("Optional suggestion steps skipped.")

        drain_cmd = [
            str(py),
            "-m",
            "jobpipe.cli.drain_queue",
            "--data-root",
            str(paths.data_root),
            "--batch-size",
            str(args.max_jobs),
            "--max-total-jobs",
            str(args.max_jobs),
            "--overwrite",
            *overlay_args,
        ]
        _set_step(run, "drain_queue", status="running", started_at=_utc_now_z())
        persist_status("Running main queue flow.")
        drain_result = _run_subprocess(drain_cmd, cwd=paths.repo_root, env=env, timeout=7200)
        _set_step(
            run,
            "drain_queue",
            status=drain_result["status"],
            finished_at=_utc_now_z(),
            summary=drain_result["summary"],
            log_excerpt=drain_result["log_excerpt"],
        )
        if drain_result["status"] != "succeeded":
            summary = "Scheduled flow failed during queue processing."
            finish_scheduled_run(
                paths.scheduled_run_state_path,
                run_id,
                {
                    **run,
                    "status": "failed",
                    "finished_at": _utc_now_z(),
                    "summary": summary,
                    "log_excerpt": drain_result["log_excerpt"],
                },
            )
            print(summary)
            sys.exit(int(drain_result["exit_code"] or 1))

        export_cmd = [
            str(py),
            "-m",
            "jobpipe.cli.export_dashboard",
            "--data-root",
            str(paths.data_root),
            *overlay_args,
        ]
        _set_step(run, "export_dashboard", status="running", started_at=_utc_now_z())
        persist_status("Rebuilding dashboard export.")
        export_result = _run_subprocess(export_cmd, cwd=paths.repo_root, env=env, timeout=1800)
        _set_step(
            run,
            "export_dashboard",
            status=export_result["status"],
            finished_at=_utc_now_z(),
            summary=export_result["summary"],
            log_excerpt=export_result["log_excerpt"],
        )
        if export_result["status"] != "succeeded":
            summary = "Scheduled flow failed during dashboard export."
            finish_scheduled_run(
                paths.scheduled_run_state_path,
                run_id,
                {
                    **run,
                    "status": "failed",
                    "finished_at": _utc_now_z(),
                    "summary": summary,
                    "log_excerpt": export_result["log_excerpt"],
                },
            )
            print(summary)
            sys.exit(int(export_result["exit_code"] or 1))

        summary = "Scheduled flow completed successfully."
        finish_scheduled_run(
            paths.scheduled_run_state_path,
            run_id,
            {
                **run,
                "status": "succeeded",
                "finished_at": _utc_now_z(),
                "summary": summary,
                "log_excerpt": export_result["log_excerpt"] or drain_result["log_excerpt"],
            },
        )
        print(summary)
    except subprocess.TimeoutExpired as exc:
        summary = f"Scheduled flow timed out while running {' '.join(exc.cmd) if exc.cmd else 'a subprocess'}."
        finish_scheduled_run(
            paths.scheduled_run_state_path,
            run_id,
            {
                **run,
                "status": "failed",
                "finished_at": _utc_now_z(),
                "summary": summary,
                "log_excerpt": summary,
            },
        )
        print(summary)
        sys.exit(1)
    except Exception as exc:
        summary = f"Scheduled flow failed: {exc}"
        finish_scheduled_run(
            paths.scheduled_run_state_path,
            run_id,
            {
                **run,
                "status": "failed",
                "finished_at": _utc_now_z(),
                "summary": summary,
                "log_excerpt": summary,
            },
        )
        print(summary)
        sys.exit(1)


if __name__ == "__main__":
    main()
