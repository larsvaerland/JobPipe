# JobPipe

AI-assisted job hunting pipeline for Lars Værland. It ingests listings from NAV and FINN-related sources, runs a staged filter and scoring pipeline, writes per-job JSON artifacts, syncs the latest state into SQLite, and exports a dashboard for daily decision-making.

```powershell
.\go.ps1
```

## What Is Running Today

```text
NAV pam-stilling-feed + FINN leads
    ↓ Apps Script / pull scripts
Google Sheet / JSONL delta
    ↓ pull_sheets_csv.py
<data-root>/jobs_delta.jsonl
    ↓ run_feed.py
    [FREE] Geo filter
    [FREE] Hard-no title regex
    [FREE] Semantic pre-filter
    [NANO] Triage
    [MINI] Parse
    [MINI] Profile match
    [MINI] Pivot
    [FREE] Moderate
    [MINI] Application pack
    ↓
<data-root>/out_runs/<run_id>/<job_id>/
    ↓ sync_ledger.py
<data-root>/reports/ledger.sqlite
    ↓ export_dashboard.py
<data-root>/exports/dashboard.html
```

The core rule is unchanged throughout the repo: cheap filters run before any LLM call.

## Local Data Root

Private user data now lives outside the git worktree by default.

- Windows: `~/JobpipeData`
- macOS: `~/Library/Application Support/JobPipe`
- Linux: `$XDG_DATA_HOME/jobpipe` or `~/.local/share/jobpipe`
- Override anywhere with `JOBPIPE_DATA_ROOT`

This data root holds local state such as `.env`, `profile_pack.md`, `resume.json`, Gmail credentials/tokens, `jobs_state.json`, `jobs_delta.jsonl`, `out_runs/`, `reports/ledger.sqlite`, and the exported dashboard. The repo keeps code, templates, configs, and docs.

## Quick Start

Requirements:
- Python 3.11+
- `.venv` with project dependencies installed
- `OPENAI_API_KEY` in the data-root `.env`
- Google Sheet CSV access for the NAV feed

Run the standard flows:

```powershell
.\go.ps1
.\go.ps1 -DryRun
.\go.ps1 -NoOpen
```

Useful direct commands:

```powershell
.venv\Scripts\python.exe compile_check.py
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m jobpipe.cli.sync_ledger
.venv\Scripts\python.exe -m jobpipe.cli.export_dashboard
start $HOME\JobpipeData\exports\dashboard.html
```

## Dashboard Modes

Two supported dashboard modes exist, but they now share one payload contract and the same tracked template:

1. `<data-root>/exports/dashboard.html`
   Static self-contained export from SQLite. Read-only.
2. `python -m jobpipe.cli.dashboard_server`
   Local interactive mode for direct status updates, notes, CV-builder draft persistence, and application-workspace flows.

Both modes now render from the canonical `build_payload()` output in `jobpipe/cli/export_dashboard.py`.

## Companion Projects

The current target stack is:

- `JobPipe` as control plane for setup, profile source data, ingestion, triage review, and sync health
- `JobSync` as the operator workspace for active applications, notes, tasks, and day-to-day status work
- `Reactive Resume` as an external CV authoring/layout tool, linked back to jobs rather than merged into the JobPipe UI
- a separate `NAV Google Apps Script` project as the feed bridge between NAV/Google Sheets and JobPipe

This split is documented in:

- `docs/architecture-plan.md`
- `docs/mvp-task-plan.md`
- `DASHBOARD_SPEC.md`

### Maintenance Strategy

Do **not** vendor `JobSync`, `Reactive Resume`, or the NAV Google Apps Script into this repo.

For easiest maintenance:

1. keep `agentic_jobpilot` as its own git repo
2. keep `jobsync` as its own git repo or deployment directory
3. keep `reactive-resume` as its own deployment directory, and only clone the source repo if you intend to modify it
4. keep the NAV Apps Script in its own git repo so Sheet/API code does not leak into the JobPipe repo

This is the normal developer setup for multi-project local stacks: separate repos or stack directories under one parent folder, not one repo containing all upstream codebases.

Recommended local layout:

```text
C:\Users\larsv\work\
  agentic_jobpilot\
  jobsync\
  reactive-resume\
  nav-jobpipe-sheet-sync\
  stacks\
    jobsync-local\
    reactive-resume-local\
```

This is the standard polyrepo pattern:

- one parent workspace folder
- one repo per codebase you may modify
- optional stack folders for Compose files, env files, and persistent volumes

That keeps upstream updates and local fixes attributable to the correct project.

### Boundary Rules During Development

Use these rules so the projects do not pollute each other:

1. `agentic_jobpilot`
   - Python pipeline, dashboard/control-plane UI, local data-root contract, integration docs
   - no checked-in Next.js app code from JobSync
   - no checked-in Docker stack from Reactive Resume
   - no checked-in Apps Script source except interface docs or sample payload specs
2. `jobsync`
   - operator workspace UI and its own backend/runtime
   - no copies of JobPipe pipeline code
   - no copies of NAV Apps Script logic
3. `reactive-resume`
   - CV builder/runtime only
   - no job-ingestion or pipeline code
4. `nav-jobpipe-sheet-sync`
   - Apps Script, NAV fetch logic, Sheet write logic, install/setup notes for that bridge
   - no JobPipe private data, no JobSync code

The integration seam between repos should be files, payload contracts, and HTTP endpoints, not copied modules.

### Recommended Local Install Order

Install and validate the stack one project at a time:

1. `JobPipe`
   - keep this repo at `C:\Users\larsv\agentic_jobpilot` or move it under a common workspace root later
   - validate the current local runtime first:
     - `.\go.ps1`
     - `python -m jobpipe.cli.dashboard_server`
   - confirm:
     - `http://127.0.0.1:5100/`
     - `<data-root>/exports/dashboard.html`
2. `JobSync`
   - install separately
   - validate its own login and local DB before thinking about integration
   - confirm:
     - `http://localhost:3737`
3. `Reactive Resume`
   - install separately
   - validate resume create/import/export before linking it to jobs
   - confirm:
     - `http://localhost:3000`
4. `NAV Apps Script`
   - keep as a separate repo after the local apps are stable
   - validate the script against its target Sheet and NAV endpoint independently of JobPipe

Do not start by wiring all four together. Get each one running on its own first.

### JobSync Installation

The official JobSync repo README and bundled compose file support a simple Docker deployment:

- clone the repo
- run `docker compose up`
- open `http://localhost:3737`

Relevant upstream references:

- `https://github.com/Gsync/jobsync`

Grounded details from the upstream README and bundled compose:

- port: `3737`
- runtime: Docker image `ghcr.io/gsync/jobsync:latest`
- local DB path in the container: `file:/data/dev.db`
- persistent volume in the sample compose: `./jobsyncdb/data:/data`
- important env knobs:
  - `NEXTAUTH_URL`
  - `AUTH_SECRET`
  - `ENCRYPTION_KEY`
  - `TZ`
  - optional AI keys such as `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `RAPIDAPI_KEY`

For this project, treat JobSync as a **separate codebase**:

- if you plan to customize JobSync UI or add JobPipe integration endpoints, clone it as a sibling repo
- if you only want to run stock JobSync, keep its compose/env/data in a separate deployment folder under `stacks/`

The official upstream quickstart is clone + compose. The maintainable local pattern is still separate from this repo.

### Reactive Resume Installation

Reactive Resume officially supports:

- cloud use
- self-hosting with Docker
- JSON import/export

Relevant upstream references:

- `https://github.com/AmruthPillai/Reactive-Resume`
- `https://docs.rxresume.org/self-hosting/docker`
- `https://docs.rxresume.org/guides/json-resume-schema`

Grounded details from the official self-hosting docs:

- default app URL example: `http://localhost:3000`
- required services in the documented Compose setup:
  - Reactive Resume app
  - PostgreSQL
  - printer service for PDF/screenshots
- required env vars:
  - `APP_URL`
  - `DATABASE_URL`
  - `PRINTER_ENDPOINT`
  - `AUTH_SECRET`
- optional but documented:
  - Google/GitHub OAuth
  - SMTP
  - S3-compatible storage

For easiest maintenance, prefer a **standalone deployment folder** for Reactive Resume unless you need to patch the code:

1. create a folder with `compose.yml`, `.env`, and a persistent data directory
2. run Docker Compose there
3. keep JobPipe linked to Reactive Resume by resume IDs/URLs or imported JSON, not by copying its source into this repo

Reactive Resume is currently best treated as a CV tool, not as part of the main JobPipe runtime.

### Repository Choice Rules

Use these rules to decide whether the companion projects belong as repos or just runtime folders on your machine:

1. `JobSync`
   - clone the repo if you will add custom endpoints, status sync, or UI changes
   - otherwise a deployment folder is enough
2. `Reactive Resume`
   - use a deployment folder by default
   - clone the repo only if you intend to patch its source or build deeper automation against its internals
3. `NAV Google Apps Script`
   - keep it as a separate repo by default
   - it is integration code, not JobPipe runtime code

For your current direction, the cleanest setup is:

- `agentic_jobpilot` as a repo
- `jobsync` as a sibling repo
- `reactive-resume-local` as a deployment folder, not necessarily a source repo
- `nav-jobpipe-sheet-sync` as a sibling repo for Apps Script and Sheet setup

That is how developers usually keep maintenance simple in a small multi-app local stack.

### Future Container Note

Later, once the JobPipe integration contracts are stable, it likely makes sense to containerize JobPipe too.

Not yet:

- JobPipe still has evolving module boundaries
- Gmail auth and local-first file handling are still operator-centric

Later target:

- one `jobpipe` container
- mounted external `JOBPIPE_DATA_ROOT`
- explicit env contract
- explicit port for the local server/API

Containerizing JobPipe should preserve the existing data-root boundary in `jobpipe/core/paths.py`, not move private state into the container filesystem.

## Smoke Test

Use this after dashboard/export/server changes:

```powershell
.venv\Scripts\python.exe compile_check.py
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m jobpipe.cli.export_dashboard
.venv\Scripts\python.exe -m jobpipe.cli.dashboard_server --no-open
```

Manual checks:
- open `http://127.0.0.1:5100/`
- confirm `/api/data` loads
- confirm a note save or CV-draft save survives refresh in local mode
- rebuild `<data-root>/exports/dashboard.html` and confirm the static export still opens cleanly

## Core Docs

- [CLAUDE.md](./CLAUDE.md)
- [PRODUCT_VISION.md](./PRODUCT_VISION.md)
- [AGENT_STATUS.md](./AGENT_STATUS.md)
- [AUDIT.md](./AUDIT.md)
- [docs/architecture-plan.md](./docs/architecture-plan.md)
- [docs/mvp-task-plan.md](./docs/mvp-task-plan.md)
- [DASHBOARD_SPEC.md](./DASHBOARD_SPEC.md)

## Documentation Discipline

This repo should stay on a small canonical doc set. Do not create ad hoc dated audits, loose research dumps, duplicate agent guides, or extra "next steps" files when the information belongs in an existing source of truth.

Use these files instead:

- `README.md`: repo entrypoint and operator quickstart
- `CLAUDE.md`: operating rules and workflow guardrails
- `AGENT_STATUS.md`: current state, handoffs, cross-agent requests
- `AUDIT.md`: bugs, quality issues, and audit history
- `PRODUCT_VISION.md`: product goals and roadmap
- `docs/architecture-plan.md`: architecture and red-line contract
- `docs/mvp-task-plan.md`: one ordered execution plan
- `DASHBOARD_SPEC.md`: dashboard and payload contract

Specialized docs are allowed only when they map to a concrete subsystem with durable operational value, for example `APPS_SCRIPT_CHANGES.md` or `docs/gmail_filter_spec.md`.

## Current Focus

The current project direction is:
- preserve the red line from source data to decision to dashboard
- keep the dashboard contract hardened and truthful under live updates
- keep the local-first data boundary consistent across runtime, docs, and versioning
- keep the OSS track portable and valuable without hosted infrastructure
- clean the repo surface before commit so only intentional first-class assets remain

## Historical Note

Earlier Supabase-first and backend-heavy planning docs are not the active architecture anymore. The current repo is the file-based `jobpipe/` pipeline described above. Historical notes are kept only for reference.
