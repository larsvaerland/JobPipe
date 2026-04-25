# CLI cheatsheet

Fast-reference companion to `docs/cli.md`. Organized by use case rather than by command. All commands run from `C:\Users\larsv\Jobpipe`. Paths default to `JobpipeData/` via `JOBPIPE_DATA_DIR` in `.env`.

If the `jobpipe` console script is not on PATH, prefix every command with:
```powershell
.venv\Scripts\python.exe -m jobpipe.cli.main
```

## End-to-end pipe

**Daily incremental run** (pull → process → sync → dashboard, single command):
```powershell
jobpipe run --candidate-id default
```

| Flag | Default | Effect |
|---|---|---|
| `--max-jobs N` | 100 (2 in dry-run) | Cap jobs |
| `--dry-run` | off | Bounded smoke test, no live sheet pull, no browser |
| `--no-open` | off | Skip browser open |
| `--with-suggestions` | off | Add Gmail intake + FINN search before main flow |

## Drain (the workhorse)

`drain-queue` is what `run` calls under the hood. Use it directly when you want loop control, batching, or to skip the dashboard step.

**Typical drain (only NEW or CHANGED rows):**
```powershell
jobpipe drain-queue --candidate-id default --max-jobs 400
```

**Full uncapped drain:**
```powershell
jobpipe drain-queue --candidate-id default --max-loops 500
```

**Re-evaluate everything (no DB wipe — keeps history, reprocesses every job):**
```powershell
jobpipe drain-queue --candidate-id default --reset-state --no-skip-processed --max-loops 500
```

Drain flags worth knowing:

| Flag | Default | Purpose |
|---|---|---|
| `--max-jobs N` | 0 (unlimited) | Hard stop after N jobs processed |
| `--max-loops N` | 200 | Safety cap; one loop ≈ one batch |
| `--batch-size N` | 50 | Jobs per loop |
| `--reset-state` | off | Delete `jobs_state.json` first → forces full re-pull |
| `--no-skip-processed` | off | Reprocess jobs already in DB |
| `--no-only-changed` | off | Pull all rows every loop (expensive, almost never wanted) |
| `--status-filter STATUS` | ACTIVE | Pass `ALL` to disable |
| `--no-skip-expired-deadline` | off | Include past-deadline jobs |
| `--sleep N` | 0 | Seconds between loops (rate-limit) |
| `--overwrite` | off | Re-write per-job stage JSONs even if present |
| `--no-sync-evaluations-after` | off | Skip post-drain sync (faster, but DB lags artifacts) |

## Source intake (pull only)

```powershell
jobpipe pull-sheets
```
Reads `JOBPIPE_CSV_URL`, writes `jobs_delta.jsonl` + `jobs_state.json`, mirrors catalog into DB. Filters `ACTIVE` + future `applicationDue` by default.

| Flag | Purpose |
|---|---|
| `--csv-url URL` | Override `JOBPIPE_CSV_URL` |
| `--only-changed` | Write only changed rows |
| `--no-dedupe` | Disable dedupe by uuid/job_id |
| `--status-filter STATUS` | Default ACTIVE; pass `ALL` to disable |
| `--no-skip-expired-deadline` | Include past-deadline rows |
| `--no-mirror-db` | Skip writing canonical jobs/source into DB |
| `--source-name NAME` | Default `nav_sheet` |
| `--expired-out PATH` | JSONL for ACTIVE→INACTIVE transitions |

## Sync evaluations only

```powershell
jobpipe sync-evaluations --detailed-report
```
Rebuilds `evaluations_latest.csv` from on-disk artifacts. Useful after a crashed drain.

| Flag | Purpose |
|---|---|
| `--detailed-report` | Also write JSON+CSV with full per-stage breakdown |
| `--decisions APPLY,REVIEW_HIGH` | Filter detailed report by tier |
| `--only-non-expired` | Drop past-deadline rows from detailed report |
| `--limit N` | Cap detailed report rows |
| `--include-description` | Add description snippet column |
| `--expired-file PATH` | Apply closed_at from expiry events |

## Inspect DB

```powershell
jobpipe inspect-db --show summary
```

`--show` accepts: `summary | profile | applications | events | candidates | documents | calibration | feedback | suggestions | gaps | gap_assessments | jobs | source_records | runs | evaluations | job_events | job_claims | job_selection_signals | job_selection_assessments`

Add `--json` for parseable output, `--limit N`, `--job-id ID` to filter to one job.

## Dashboard

```powershell
jobpipe export-dashboard
```
Writes `JobpipeData\exports\dashboard.html` (self-contained). `run` calls this automatically.

## Mark applications

Stages accumulate over time; outcomes are mutually exclusive terminals.

```powershell
# add stages (additive, idempotent)
jobpipe mark-status JOB_ID shortlisted
jobpipe mark-status JOB_ID called --notes "Snakket med X" --pre-call-notes "..."
jobpipe mark-status JOB_ID applied --notes "Sendt via Webcruiter"
jobpipe mark-status JOB_ID interview
jobpipe mark-status JOB_ID second_interview

# terminal outcomes (mutually exclusive)
jobpipe mark-status JOB_ID accepted
jobpipe mark-status JOB_ID rejected --notes "..."
jobpipe mark-status JOB_ID dismissed
jobpipe mark-status JOB_ID clear

# query
jobpipe mark-status --list
jobpipe mark-status --list --filter-status applied
```

## Feedback (calibration signal)

```powershell
jobpipe record-feedback JOB_ID good_fit --notes "..."
```

Signals: `bad_fit | bad_recommendation | demote | good_fit | good_recommendation | promote`. Writes to `candidate_feedback_events`, feeds calibration.

## Gap analysis

```powershell
jobpipe gap-analysis --min-fit 30
```
Aggregates capability gaps from evaluated jobs above `--min-fit`, writes both Markdown and JSON reports, persists to DB.

| Flag | Purpose |
|---|---|
| `--min-fit N` | Min fit_score to include (default 0) |
| `--out PATH` | Markdown output path |
| `--out-json PATH` | JSON output path |

## Reset / archive runtime

```powershell
jobpipe reset-runtime --tag <descriptive_tag>
```
Moves `db/`, `.jobpipe_tmp/`, `jobs_state.json`, `jobs_delta.jsonl`, `jobs_expired.jsonl`, `artifacts/`, `exports/`, `out_runs/`, `reports/`, `cache/`, `profile_embedding.npy`, `suggested_jobs.jsonl` to `<data-root>/_archives/<tag>/`. Restores `application_state.json` into the fresh baseline by default.

| Flag | Purpose |
|---|---|
| `--tag TAG` | Archive folder name (default: timestamped `post_refactor_baseline_*`) |
| `--data-root PATH` | Override `JOBPIPE_DATA_DIR` |
| `--archive-root PATH` | Override `<data-root>/_archives` |
| `--no-restore-app-state` | Don't copy `application_state.json` back |

For the full wipe-and-rerun workflow see `docs/full-reevaluation-runbook.md`.

## Other surfaces

Less-common commands available via `jobpipe <name>`:

| Command | Purpose |
|---|---|
| `author-package` | Application package authoring (CV/cover letter generation) |
| `bootstrap-state-db` | Initialize / migrate the primary DB schema |
| `build-authoring-context` | Smoke test for authoring pipeline |
| `pull-finn-ext` | Direct Finn.no extension scrape |
| `pull-finn-search` | Finn search scrape |
| `pull-suggested` | Process suggested-jobs intake |
| `import-reactive-resume` | Import reactive-resume profile |
| `export-jobsync` | Export jobsync handoff |
| `export-reactive-resume-plan` | Export reactive-resume plan |
| `record-jobsync-event` | Log a jobsync event |
| `record-reactive-resume-document` | Log a reactive-resume document |
| `scan-gmail` | Gmail intake (status + suggestions) |

Run `jobpipe <command> --help` for any of them.

## Safe-while-drain-running commands

While a `drain-queue` is active, only these are guaranteed safe (read-only or non-conflicting):
```powershell
Get-Content drain_*.log -Tail 30
jobpipe inspect-db --show summary
jobpipe inspect-db --show evaluations --limit 20
jobpipe mark-status --list
```

Avoid `pull-sheets`, `mark-status JOB_ID ...`, `record-feedback`, `reset-runtime`, `sync-evaluations` while a drain is active — they can race on the DB or state files.
