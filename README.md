# JobPipe / Agentic JobPilot

An AI-powered job hunting pipeline. Pulls jobs from NAV's pam-stilling-feed via Google Sheets, runs a staged triage + scoring pipeline, and produces a self-contained HTML dashboard showing only the jobs worth acting on.

## Quick start

```powershell
# Run the full pipeline (pull, process, sync, open dashboard)
.\go.ps1

# Test mode - process 2 jobs only
.\go.ps1 -DryRun

# Full run, skip auto-opening browser
.\go.ps1 -NoOpen
```

## How it works

```
NAV pam-stilling-feed API
    -> Apps Script (hourly trigger, ~50 jobs/run)
Google Sheet (JobFeed tab, ~35,000+ rows)
    -> pull_sheets_csv.py (delta pull, ACTIVE jobs only)
jobs_delta.jsonl
    -> run_feed.py / drain_queue.py
       [FREE]  Geo postal filter      (Oslo/Akershus/Vestfold-Telemark/Agder)
       [FREE]  Hard-no title regex    (retail, trades, healthcare, etc.)
       [FREE]  Semantic pre-filter    (multilingual cosine similarity vs profile)
       [NANO]  Triage                 (gpt-4.1-nano, SKIP/REVIEW/APPLY + noise_level)
       [MINI]  Parse                  (gpt-4.1-mini, structured requirements)
       [MINI]  Profile match          (gpt-4.1-mini, fit_score 0-100, 4 dimensions)
       [MINI]  Pivot                  (gpt-4.1-mini, pivot_score 0-100)
       [FREE]  Moderate               (deterministic thresholds -> final_decision)
       [DEEP]  Application pack       (deepagents + FilesystemBackend, APPLY+ only)
out_runs/<run_id>/<job_id>/   per-job JSON artifacts
    -> sync_ledger.py         -> reports/ledger.sqlite
    -> export_dashboard.py    -> reports/dashboard.html
```

## Setup

```powershell
python -m venv .venv
.venv\Scripts\pip install -e .
```

Copy `.env.example` to `.env` and fill in:
- `OPENAI_API_KEY`
- `JOBPIPE_CSV_URL` (Google Sheets published CSV URL)

## Decision thresholds

| Decision | fit_score required |
|---|---|
| APPLY_STRONGLY | >= 78 |
| APPLY | >= 67 |
| REVIEW_HIGH | >= 58 (with high pivot) |
| REVIEW_LOW | >= 30 |
| SKIP | < 30 |

Thresholds live in `configs/pipeline.v1.yaml` and are re-applied at dashboard export time - no pipeline re-run needed after threshold changes.

## Key files

| File | Purpose |
|---|---|
| `go.ps1` | One-shot runner (pull + process + sync + dashboard) |
| `configs/pipeline.v1.yaml` | All config: models, thresholds, regex patterns |
| `profile_pack.md` | Candidate profile - truth source for triage/matching |
| `reports/ledger.sqlite` | Deduplicated job ledger |
| `reports/dashboard.html` | Self-contained HTML dashboard |
| `reports/application_state.json` | Application tracking sidecar |

## Agent coordination

Three Cowork agents work this project in parallel. See `CLAUDE.md` for the full operating guide and `AGENT_STATUS.md` for current workstream state.
