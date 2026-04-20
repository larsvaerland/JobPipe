from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.parse import urlparse

import yaml

from jobpipe.core.io import load_env_file, now_iso
from jobpipe.core.primary_db import connect_primary_db, upsert_job, upsert_job_source_record
from jobpipe.projections.dashboard import build_payload
from jobpipe.runtime.paths import primary_db_path, repo_root

load_env_file(".env")


_ACTIONABLE = {"APPLY_STRONGLY", "APPLY"}
_REVIEW = {"REVIEW_HIGH", "REVIEW_LOW"}
_SKIP = {"SKIP"}
_DEFAULT_CANDIDATE_ID = (os.environ.get("JOBPIPE_CANDIDATE_ID") or "default").strip() or "default"


def _safe_json_text(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _safe_locations(value: Any) -> list[dict[str, Any]]:
    parsed = _safe_json_text(json.dumps({"locations": value})).get("locations")
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(value, str):
        try:
            raw = json.loads(value)
            if isinstance(raw, list):
                return [item for item in raw if isinstance(item, dict)]
        except Exception:
            return []
    return []


def _canonical_source_name(metadata: dict[str, Any]) -> str:
    raw = str(
        metadata.get("_canonical_source_name")
        or metadata.get("source_name")
        or metadata.get("_canonical_source_platform")
        or ""
    ).strip()
    if raw:
        return raw
    return "audit_baseline"


def _source_host(url: str) -> str:
    try:
        return (urlparse(str(url or "")).hostname or "").lower()
    except Exception:
        return ""


def _decision_bucket(decision: str) -> str:
    normalized = str(decision or "").strip().upper()
    if normalized in _ACTIONABLE:
        return "actionable"
    if normalized in _REVIEW:
        return "review"
    return "skip"


def reconstruct_audit_job_input(row: dict[str, Any]) -> dict[str, Any]:
    metadata = _safe_json_text(row.get("job_metadata_json"))
    raw_locations = metadata.get("workLocations_json")
    locations = _safe_locations(raw_locations)
    primary_location = locations[0] if locations else {}

    source_url = str(row.get("source_url") or "").strip()
    application_url = str(row.get("application_url") or "").strip()
    description_html = str(row.get("description_html") or "").strip()
    description_text = str(row.get("description_text") or "").strip()

    return {
        "job_id": str(row.get("job_id") or "").strip(),
        "title": str(row.get("title") or "").strip(),
        "employer_name": str(row.get("employer") or "").strip(),
        "description_html": description_html,
        "description_text": description_text,
        "applicationDue": str(row.get("applicationDue") or "").strip(),
        "work_city": str(row.get("work_city") or primary_location.get("city") or primary_location.get("municipal") or "").strip(),
        "work_county": str(row.get("work_county") or primary_location.get("county") or "").strip(),
        "work_postalCode": str(row.get("work_postalCode") or primary_location.get("postalCode") or "").strip(),
        "sourceurl": source_url,
        "applicationUrl": application_url,
        "source": _canonical_source_name(metadata),
        "sector": str(row.get("sector") or "").strip(),
        "parse_method": "audit_baseline",
        "reconstructed_from_audit_baseline": True,
        "audit_source_host": _source_host(source_url or application_url),
    }


def _pick_diverse(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    selected: list[dict[str, Any]] = []
    seen_employers: set[str] = set()
    seen_hosts: set[str] = set()

    for row in candidates:
        if len(selected) >= limit:
            break
        employer = str(row.get("employer") or "").strip().lower()
        host = _source_host(str(row.get("source_url") or row.get("application_url") or ""))
        if employer and employer in seen_employers:
            continue
        if host and host in seen_hosts:
            continue
        selected.append(row)
        if employer:
            seen_employers.add(employer)
        if host:
            seen_hosts.add(host)

    if len(selected) >= limit:
        return selected

    selected_ids = {str(row.get("job_id") or "").strip() for row in selected}
    for row in candidates:
        if len(selected) >= limit:
            break
        job_id = str(row.get("job_id") or "").strip()
        if not job_id or job_id in selected_ids:
            continue
        selected.append(row)
        selected_ids.add(job_id)
    return selected


def choose_audit_slice(
    evaluation_rows: list[dict[str, Any]],
    jobs_by_id: dict[str, dict[str, Any]],
    *,
    jobs_per_bucket: int,
) -> list[dict[str, Any]]:
    bucketed: dict[str, list[dict[str, Any]]] = {
        "actionable": [],
        "review": [],
        "skip": [],
    }

    sorted_rows = sorted(
        evaluation_rows,
        key=lambda row: (
            -(float(row.get("final_confidence") or 0.0)),
            -(int(row.get("fit_score") or 0)),
            -(int(row.get("pivot_score") or 0)),
            str(row.get("updated_at") or ""),
        ),
    )
    for row in sorted_rows:
        job_id = str(row.get("job_id") or "").strip()
        if not job_id or job_id not in jobs_by_id:
            continue
        bucketed[_decision_bucket(str(row.get("final_decision") or ""))].append(row)

    selected_ids: list[str] = []
    for bucket_name in ("actionable", "review", "skip"):
        picked = _pick_diverse(bucketed[bucket_name], jobs_per_bucket)
        for row in picked:
            job_id = str(row.get("job_id") or "").strip()
            if job_id and job_id not in selected_ids:
                selected_ids.append(job_id)

    selected_jobs = [jobs_by_id[job_id] for job_id in selected_ids if job_id in jobs_by_id]
    return selected_jobs


def _query_rows(db_path: Path, sql: str, params: Iterable[Any] | None = None) -> list[dict[str, Any]]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in conn.execute(sql, list(params or []))]
    finally:
        conn.close()
    return rows


def load_live_catalog_rows(db_path: Path) -> list[dict[str, Any]]:
    return _query_rows(
        db_path,
        """
        SELECT job_id, title, employer, work_city, work_county, work_postalCode,
               applicationDue, source_url, application_url,
               description_text, description_html, sector, job_metadata_json, closed_at
        FROM jobs
        ORDER BY updated_at DESC, last_seen_at DESC, job_id ASC
        """,
    )


def load_replay_input_jobs(db_path: Path) -> dict[str, dict[str, Any]]:
    rows = _query_rows(
        db_path,
        """
        SELECT job_id, input_payload_json
        FROM job_replay_inputs
        ORDER BY updated_at DESC, captured_at DESC, job_id ASC
        """,
    )
    jobs: dict[str, dict[str, Any]] = {}
    for row in rows:
        job_id = str(row.get("job_id") or "").strip()
        if not job_id or job_id in jobs:
            continue
        payload = _safe_json_text(row.get("input_payload_json"))
        if not payload:
            continue
        payload.setdefault("job_id", job_id)
        jobs[job_id] = payload
    return jobs


def load_rerunnable_jobs_by_id(db_path: Path) -> tuple[dict[str, dict[str, Any]], int, int]:
    catalog_jobs = [
        reconstruct_audit_job_input(row)
        for row in load_live_catalog_rows(db_path)
    ]
    jobs_by_id = {
        str(job.get("job_id") or "").strip(): job
        for job in catalog_jobs
        if str(job.get("job_id") or "").strip()
    }
    replay_only = 0
    for job_id, payload in load_replay_input_jobs(db_path).items():
        if job_id not in jobs_by_id:
            jobs_by_id[job_id] = payload
            replay_only += 1
    return jobs_by_id, len(catalog_jobs), replay_only


def load_live_evaluation_rows(db_path: Path, candidate_id: str) -> list[dict[str, Any]]:
    return _query_rows(
        db_path,
        """
        SELECT job_id, final_decision, final_confidence, fit_score, pivot_score,
               title, employer, source_url, application_url, updated_at
        FROM job_evaluations
        WHERE candidate_id = ?
        ORDER BY updated_at DESC, final_confidence DESC, fit_score DESC
        """,
        [candidate_id],
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _copy_catalog_tables(source_db: Path, target_db: Path) -> None:
    jobs = _query_rows(source_db, "SELECT * FROM jobs")
    source_records = _query_rows(source_db, "SELECT * FROM job_source_records")

    conn = connect_primary_db(target_db)
    try:
        for row in jobs:
            payload = dict(row)
            payload["job_metadata_json"] = _safe_json_text(payload.get("job_metadata_json"))
            upsert_job(conn, payload)
        for row in source_records:
            payload = dict(row)
            payload["raw_payload_json"] = _safe_json_text(payload.get("raw_payload_json"))
            upsert_job_source_record(conn, payload)
        conn.commit()
    finally:
        conn.close()


def freeze_live_audit_baseline(
    *,
    live_db: Path,
    audit_root: Path,
    config_path: Path,
    personas_manifest: Path,
    candidate_id: str,
    jobs_per_bucket: int,
) -> dict[str, Any]:
    baseline_dir = audit_root / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)

    jobs_by_id, catalog_job_count, replay_only_jobs = load_rerunnable_jobs_by_id(live_db)
    full_jobs = list(jobs_by_id.values())
    live_evaluations = load_live_evaluation_rows(live_db, candidate_id)
    rerunnable_evaluations = [
        row
        for row in live_evaluations
        if str(row.get("job_id") or "").strip() in jobs_by_id
    ]
    audit_slice = choose_audit_slice(rerunnable_evaluations, jobs_by_id, jobs_per_bucket=jobs_per_bucket)

    full_corpus_path = baseline_dir / "jobs_corpus.full.jsonl"
    slice_path = baseline_dir / "jobs_corpus.audit_slice.jsonl"
    config_copy_path = baseline_dir / "pipeline.v1.yaml"
    manifest_copy_path = baseline_dir / "personas.manifest.json"
    empty_app_state_path = baseline_dir / "empty_application_state.json"
    baseline_yaml_path = baseline_dir / "persona-audit-baseline.yaml"
    summary_json_path = baseline_dir / "baseline_summary.json"

    _write_jsonl(full_corpus_path, full_jobs)
    _write_jsonl(slice_path, audit_slice)
    shutil.copy2(config_path, config_copy_path)
    shutil.copy2(personas_manifest, manifest_copy_path)
    _write_json(
        empty_app_state_path,
        {
            "applications": {},
            "updated_at": now_iso(),
        },
    )

    live_decision_counts = Counter(_decision_bucket(str(row.get("final_decision") or "")) for row in live_evaluations)
    rerunnable_decision_counts = Counter(
        _decision_bucket(str(row.get("final_decision") or ""))
        for row in rerunnable_evaluations
    )
    slice_hosts = Counter(_source_host(str(job.get("sourceurl") or job.get("applicationUrl") or "")) or "unknown" for job in audit_slice)

    baseline_payload = {
        "version": 1,
        "audit_name": audit_root.name,
        "notes": [
            "Local live audit baseline frozen from the current public OSS setup.",
            "This file is local operational state and must not be committed with personal data.",
        ],
        "public_repo": {
            "repo_root": str(repo_root()),
            "config_path": str(config_copy_path),
            "candidate_id": candidate_id,
        },
        "runtime_baseline": {
            "live_primary_db_path": str(live_db),
            "audit_root": str(audit_root),
            "full_corpus_path": str(full_corpus_path),
            "audit_slice_path": str(slice_path),
            "empty_app_state_path": str(empty_app_state_path),
        },
        "audit_scope": {
            "use_live_job_corpus": True,
            "freeze_config_before_run": True,
            "freeze_dashboard_output": True,
            "personas_manifest": str(manifest_copy_path),
            "jobs_per_bucket": jobs_per_bucket,
            "matrix_mode": "stratified_audit_slice",
        },
        "review_questions": [
            "Are top actionable roles plausible for this persona?",
            "Are strongest skips actually good skips?",
            "Are adjacent roles surfaced where they should be?",
            "Is evidence selection credible and reusable?",
            "Is the dashboard trustworthy and readable?",
        ],
    }
    baseline_yaml_path.write_text(
        yaml.safe_dump(baseline_payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    summary_payload = {
        "frozen_at": now_iso(),
        "live_primary_db_path": str(live_db),
        "catalog_jobs": catalog_job_count,
        "replay_only_jobs": replay_only_jobs,
        "full_corpus_jobs": len(full_jobs),
        "audit_slice_jobs": len(audit_slice),
        "jobs_per_bucket": jobs_per_bucket,
        "live_decision_bucket_counts": dict(live_decision_counts),
        "rerunnable_decision_bucket_counts": dict(rerunnable_decision_counts),
        "rerunnable_evaluations": len(rerunnable_evaluations),
        "audit_slice_source_hosts": dict(slice_hosts),
        "audit_slice_job_ids": [job["job_id"] for job in audit_slice],
        "audit_slice_titles": [
            {
                "job_id": job["job_id"],
                "title": job.get("title", ""),
                "employer_name": job.get("employer_name", ""),
                "source": job.get("source", ""),
            }
            for job in audit_slice
        ],
    }
    _write_json(summary_json_path, summary_payload)
    return summary_payload


def _run_command(command: list[str], *, cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    log_path.write_text(output, encoding="utf-8")
    if output:
        print(output, end="")
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, command)


def _persona_summary(payload: dict[str, Any], *, persona_id: str, persona_label: str) -> dict[str, Any]:
    jobs = payload.get("jobs", [])
    decision_counts = Counter(str(job.get("final_decision") or "").strip() for job in jobs)

    def _top(decisions: set[str], limit: int = 5) -> list[dict[str, Any]]:
        filtered = [job for job in jobs if str(job.get("final_decision") or "").strip() in decisions]
        return [
            {
                "job_id": str(job.get("job_id") or "").strip(),
                "title": str(job.get("title") or "").strip(),
                "employer": str(job.get("employer") or "").strip(),
                "final_decision": str(job.get("final_decision") or "").strip(),
                "fit_score": job.get("fit_score"),
                "pivot_score": job.get("pivot_score"),
                "no_score_reason": str(job.get("no_score_reason") or "").strip(),
                "no_score_reason_label": str(job.get("no_score_reason_label") or "").strip(),
            }
            for job in filtered[:limit]
        ]

    return {
        "persona_id": persona_id,
        "label": persona_label,
        "generated_at": payload.get("generated_at"),
        "summary": payload.get("summary", {}),
        "decision_counts": dict(decision_counts),
        "top_actionable": _top(_ACTIONABLE),
        "top_review": _top(_REVIEW),
        "top_skip": _top(_SKIP),
    }


def run_persona_matrix(
    *,
    audit_root: Path,
    live_db: Path,
    python_exe: Path,
    repo_root_path: Path,
) -> dict[str, Any]:
    baseline_dir = audit_root / "baseline"
    config_path = baseline_dir / "pipeline.v1.yaml"
    slice_path = baseline_dir / "jobs_corpus.audit_slice.jsonl"
    manifest_path = baseline_dir / "personas.manifest.json"
    empty_app_state_path = baseline_dir / "empty_application_state.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    personas = manifest.get("personas", [])
    matrix_summaries: list[dict[str, Any]] = []

    for persona in personas:
        persona_id = str(persona.get("persona_id") or "").strip()
        if not persona_id:
            continue
        persona_label = str(persona.get("label") or persona_id).strip()
        persona_source_dir = manifest_path.parent.parent / persona_id
        if not persona_source_dir.exists():
            persona_source_dir = repo_root_path / "tests" / "fixtures" / "personas" / persona_id

        persona_dir = audit_root / "personas" / persona_id
        inputs_dir = persona_dir / "inputs"
        artifacts_dir = persona_dir / "artifacts"
        exports_dir = persona_dir / "exports"
        logs_dir = persona_dir / "logs"
        db_path = persona_dir / "jobpipe.sqlite"
        dashboard_path = exports_dir / "dashboard.html"
        summary_path = persona_dir / "summary.json"

        inputs_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(persona_source_dir / "profile_pack.md", inputs_dir / "profile_pack.md")
        shutil.copy2(persona_source_dir / "resume.json", inputs_dir / "resume.json")

        if db_path.exists():
            db_path.unlink()
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir)
        if exports_dir.exists():
            shutil.rmtree(exports_dir)

        _run_command(
            [
                str(python_exe),
                "-m",
                "jobpipe.cli.bootstrap_state_db",
                "--db",
                str(db_path),
                "--profile",
                str(inputs_dir / "profile_pack.md"),
                "--resume",
                str(inputs_dir / "resume.json"),
                "--app-state",
                str(empty_app_state_path),
                "--candidate-id",
                persona_id,
            ],
            cwd=repo_root_path,
            log_path=logs_dir / "01_bootstrap.log",
        )

        _copy_catalog_tables(live_db, db_path)

        _run_command(
            [
                str(python_exe),
                "-m",
                "jobpipe.cli.run_feed",
                "--jobs",
                str(slice_path),
                "--profile",
                str(inputs_dir / "profile_pack.md"),
                "--db",
                str(db_path),
                "--candidate-id",
                persona_id,
                "--out",
                str(artifacts_dir),
                "--config",
                str(config_path),
                "--overwrite",
            ],
            cwd=repo_root_path,
            log_path=logs_dir / "02_run_feed.log",
        )

        _run_command(
            [
                str(python_exe),
                "-m",
                "jobpipe.cli.sync_evaluations",
                "--out",
                str(artifacts_dir),
                "--reports",
                str(exports_dir),
                "--db",
                str(db_path),
                "--candidate-id",
                persona_id,
            ],
            cwd=repo_root_path,
            log_path=logs_dir / "03_sync_evaluations.log",
        )

        _run_command(
            [
                str(python_exe),
                "-m",
                "jobpipe.cli.export_dashboard",
                "--artifacts",
                str(artifacts_dir),
                "--app-state",
                str(empty_app_state_path),
                "--db",
                str(db_path),
                "--candidate-id",
                persona_id,
                "--out",
                str(dashboard_path),
            ],
            cwd=repo_root_path,
            log_path=logs_dir / "04_export_dashboard.log",
        )

        payload = build_payload(
            artifacts_dir,
            state_path=empty_app_state_path,
            primary_db_path_=db_path,
            candidate_id=persona_id,
            config_path=config_path,
        )
        summary = _persona_summary(payload, persona_id=persona_id, persona_label=persona_label)
        summary["paths"] = {
            "db_path": str(db_path),
            "artifacts_dir": str(artifacts_dir),
            "exports_dir": str(exports_dir),
            "dashboard_path": str(dashboard_path),
        }
        _write_json(summary_path, summary)
        matrix_summaries.append(summary)

    result = {
        "completed_at": now_iso(),
        "audit_root": str(audit_root),
        "persona_count": len(matrix_summaries),
        "personas": matrix_summaries,
    }
    _write_json(audit_root / "matrix_summary.json", result)
    return result


def _default_audit_root() -> Path:
    live_db = primary_db_path()
    parent = live_db.parent.parent if len(live_db.parents) >= 2 else repo_root()
    ts = now_iso().replace(":", "").replace("-", "").replace("T", "_").replace("Z", "")
    return parent / "audit" / f"public_oss_persona_audit_{ts}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Freeze a local persona-audit baseline and run an isolated public-OSS persona matrix."
    )
    parser.add_argument("--live-db", default=str(primary_db_path()), help="Path to the live primary JobPipe DB.")
    parser.add_argument("--candidate-id", default=_DEFAULT_CANDIDATE_ID, help="Reference candidate ID for live evaluation reads.")
    parser.add_argument(
        "--audit-root",
        default=str(_default_audit_root()),
        help="Local audit workspace root. Defaults to a timestamped folder under the current JobPipeData root.",
    )
    parser.add_argument(
        "--config",
        default=str(repo_root() / "configs" / "pipeline.v1.yaml"),
        help="Public pipeline config to freeze into the audit baseline.",
    )
    parser.add_argument(
        "--personas-manifest",
        default=str(repo_root() / "tests" / "fixtures" / "personas" / "manifest.json"),
        help="Synthetic personas manifest.",
    )
    parser.add_argument(
        "--jobs-per-bucket",
        type=int,
        default=2,
        help="How many jobs to keep per decision bucket in the first audit slice (default: 2).",
    )
    parser.add_argument(
        "--python-exe",
        default=sys.executable,
        help="Python executable used to run the underlying JobPipe CLIs.",
    )
    parser.add_argument("--freeze-only", action="store_true", help="Freeze the baseline only. Do not run the persona matrix.")
    args = parser.parse_args(argv)

    live_db = Path(args.live_db)
    audit_root = Path(args.audit_root)
    config_path = Path(args.config)
    personas_manifest = Path(args.personas_manifest)
    python_exe = Path(args.python_exe)
    repo_root_path = repo_root()

    baseline_summary = freeze_live_audit_baseline(
        live_db=live_db,
        audit_root=audit_root,
        config_path=config_path,
        personas_manifest=personas_manifest,
        candidate_id=args.candidate_id,
        jobs_per_bucket=args.jobs_per_bucket,
    )

    print("=== Persona Audit Baseline Frozen ===")
    print(f"Audit root:      {audit_root}")
    print(f"Live DB:         {live_db}")
    print(f"Full corpus:     {baseline_summary['full_corpus_jobs']} jobs")
    print(f"Audit slice:     {baseline_summary['audit_slice_jobs']} jobs")
    print(f"Jobs per bucket: {baseline_summary['jobs_per_bucket']}")
    print(f"Rerunnable evals: {baseline_summary['rerunnable_evaluations']}")

    if args.freeze_only:
        return

    matrix_summary = run_persona_matrix(
        audit_root=audit_root,
        live_db=live_db,
        python_exe=python_exe,
        repo_root_path=repo_root_path,
    )

    print("=== Persona Audit Matrix Complete ===")
    print(f"Audit root:    {audit_root}")
    print(f"Personas run:  {matrix_summary['persona_count']}")
    for persona in matrix_summary["personas"]:
        counts = persona.get("decision_counts", {})
        queue_size = int(persona.get("summary", {}).get("actionable_jobs") or 0)
        print(
            f"  - {persona['persona_id']}: "
            f"attention_queue={queue_size}, "
            f"apply={counts.get('APPLY_STRONGLY', 0) + counts.get('APPLY', 0)}, "
            f"review={counts.get('REVIEW_HIGH', 0) + counts.get('REVIEW_LOW', 0)}, "
            f"skip={counts.get('SKIP', 0)}"
        )


if __name__ == "__main__":
    main()
