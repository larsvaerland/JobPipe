# Architecture Plan

Last updated: 2026-04-17

This is the canonical architecture note for the active system. Fold architecture updates into this file instead of creating dated architecture snapshots.

## Red Line

The product only works if the same job can be traced cleanly from source input to final dashboard action:

1. source data arrives intact
2. cheap filters remove noise first
3. every stage leaves evidence
4. the ledger becomes the durable system of record
5. the dashboard projects that record without guessing

If a field is useful for filtering, debugging, scoring, or acting, it should either be carried explicitly or be intentionally excluded with a documented reason.

## Actual Running Architecture

```text
NAV pam-stilling-feed
    ↓ Apps Script
Google Sheet (JobFeed)
    ↓ pull_sheets_csv.py
<data-root>/jobs_delta.jsonl
    ↓ run_feed.py
    00_input.json
    01_triage.json
    02_parsed.json
    03_profile_match.json
    04_pivot.json
    05_moderator.json
    06_application_pack.json   (APPLY/APPLY_STRONGLY only)
    07_cv_highlights.docx      (APPLY/APPLY_STRONGLY only)
    ↓ sync_ledger.py
<data-root>/reports/ledger.sqlite
    ↓ export_dashboard.py
<data-root>/exports/dashboard.html
```

Related local runtime:

```text
dashboard_server.py
    ↓ build_payload()
SQLite + <data-root>/out_runs + <data-root>/reports/application_state.json + <data-root>/reports/resume.json
    ↓
dashboard template + apply template served on localhost
```

## Data Contract By Layer

### 1. Input contract

`pull_sheets_csv.py` already preserves more data than the dashboard currently uses:

- identity: `job_id`, `uuid`
- job metadata: `title`, `employer_name`, `status`, `ad_updated`, `sistEndret`
- action data: `applicationUrl`, `applicationDue`, `sourceurl`, `link`
- location: `work_city`, `work_county`, `work_postalCode`, `workLocations_json`
- zero-cost taxonomy: `occ_level1`, `occ_level2`, `cat_type`, `cat_code`, `cat_name`, `cat_score`
- optional normalization: `normalized_title`

This is good. The main issue is not ingestion; it is carry-through.

### 2. Artifact contract

Each stage writes JSON per job. This gives strong traceability, but the dashboard is not consuming the full artifact graph:

- triage additive fields like `noise_level` and `forced_safety` are not carried into the ledger
- parsed output is not represented in the ledger
- application pack output is only partially represented in the ledger

### 3. Ledger contract

`sync_ledger.py` is the critical narrowing point. It now keeps:

- identity, URLs, location, due date
- triage summary
- reverse triage summary
- fit and pivot scores
- final decision
- selected raw blobs for match, pivot, moderator
- `skip_reason`
- source taxonomy and normalized titles
- application-pack summary fields
- closed state and source identity needed by the dashboard

### 4. Dashboard payload contract

`export_dashboard.py` builds a single payload for both static export and local server mode. It now exports:

- thresholds and config snapshot
- profile/resume summary for the Profile & CV page
- source/taxonomy fields for filtering and debugging
- pack readiness summary
- closed state
- payload budget metadata

### 5. UI contract

The dashboard currently mixes two interaction models:

1. Static report mode
2. Local app mode via `dashboard_server.py`

This is the main architectural reason the dashboard feels clunky. The product surface is split between:

- `dashboard.html`
- `dashboard_server.py`
- `apply_template.html`
- `resume.json`
- per-job files under `out_runs/`

## Verified Breakpoints

These remain the main pressure points after Topics 1-7:

1. Some actionable rows still have no fixed deadline because the source data itself does not provide one.
2. Queue dedupe/grouping still lives in dashboard JS rather than the payload contract.
3. The deep drafting route is still a separate surface from the main workspace page.
4. Documentation and local habits still need to stay aligned with the new external data-root contract.

## Target Architecture

The next stable shape should be:

```text
source jobs
    ↓
normalized artifacts
    ↓
ledger.sqlite   <- single durable record for dashboard-worthy fields
    ↓
build_payload() <- one canonical payload builder
    ↓
static export OR local server
    ↓
same UI contract
```

Principles for that target:

- `build_payload()` is the only source for dashboard data
- static export and server mode share the same payload
- no dashboard logic guesses skip reason, thresholds, or pack state
- profile/CV data is first-class, not hidden behind a per-job workspace
- filesystem reads remain a fallback, not a primary UI dependency

## JobSync Integration Target

The current dashboard stack is stable enough that the next integration step should not be a broad JobPipe refactor. The intended split is:

```text
source jobs + Gmail signals
    ↓
JobPipe
    - ingestion
    - filtering
    - scoring
    - evidence artifacts
    - application-state inference
    ↓
curated job export + normalized status events
    ↓
JobSync
    - operator workspace
    - manual application tracking
    - notes / tags / tasks / activities
    - resume and cover-letter inventory
```

This is a product split, not a UI swap. JobPipe remains the system that decides why a job is worth acting on. JobSync becomes the system used to work the shortlist.

### Ownership Boundaries

JobPipe owns:

- source intake
- dedupe and filtering
- scoring, recommendation, and explainability
- ledger truth and artifact provenance
- Gmail-derived application-state inference
- generated pack / drafting artifacts

JobSync owns:

- operator-facing dashboard and daily workspace
- tracked-job CRUD
- notes and tags
- tasks and activities
- question bank
- resume / cover-letter inventory and editing

Do not duplicate ownership for discovery, pipeline reasoning, or mailbox classification inside JobSync in v1.

### Shared Workflow Status Model

The shared top-level workflow vocabulary between JobPipe and JobSync should be:

- `draft`
- `applied`
- `interview`
- `offer`
- `rejected`
- `dismissed`

JobPipe should keep richer internal state:

- `app_stages`
- `app_outcome`
- `app_notes`
- `events`

But expose one normalized `app_status` for integration and UI consumption.

### JobPipe Status Normalization

Map current JobPipe stage/outcome detail to the shared status set:

- `shortlisted` -> `draft`
- `called` -> `draft`
- `applied` -> `applied`
- `interview` -> `interview`
- `second_interview` -> `interview`
- `accepted` -> `offer`
- `rejected` -> `rejected`
- `dismissed` -> `dismissed`

Normalization precedence:

1. terminal outcome wins
2. otherwise use the most advanced stage reached
3. collapse detailed stages into the shared workflow buckets above

This keeps JobPipe detail intact while avoiding duplicate meanings across systems.

### Integration Contract

The integration should use explicit external identity fields instead of fuzzy matching:

- `externalSource`
- `externalId`
- `externalStatusSource`
- `externalStatusAt`
- `externalStatusMeta`
- `syncMode`

JobSync should treat JobPipe-imported jobs as externally identified records and upsert them by `[externalSource, externalId]`.

### Sync Directions

Phase 1:

- JobPipe -> JobSync curated job import
- JobPipe -> JobSync normalized status sync

Phase 2:

- JobSync -> JobPipe manual status / notes writeback, only if needed after the one-way model is stable

Do not start with full bidirectional field sync. Keep the seam narrow until the imported-workspace model is proven.

## Page Model For The Dashboard

The dashboard should evolve into a small local product with these pages:

1. Jobs
   Action list, filters, deadlines, statuses, pack state.
2. Pipeline
   Funnel, skip reasons, score distributions, calibration and source metrics.
3. Profile & CV
   `<data-root>/reports/resume.json`, `<data-root>/profile_pack.md`, strengths, target roles, reusable CV material.
4. Application Workspace
   Current `apply_template.html`, but integrated intentionally.
5. Debug / Data
   Field completeness, schema version, run health, payload validation.

## Companion UI Split

The working target is not one monolithic dashboard. It is a split system with separate responsibilities.

### JobPipe UI

JobPipe should remain the control plane and setup surface. Grounded in the current codebase, it already has:

- `Jobs`
- `Pipeline`
- `Profile & CV`
- `Application Workspace`
- `Debug / Data`

From:

- `DASHBOARD_SPEC.md`
- `reports/dashboard_template.html`
- `reports/apply_template.html`
- `jobpipe/cli/dashboard_server.py`

The intended JobPipe page model should become:

1. Setup & Integrations
   API keys, Google/Gmail auth, NAV/Sheet setup, external tool links.
2. Sources & Ingestion
   Feed health, Sheet visibility, raw import diagnostics.
3. Triage Review
   Why a job passed or failed, score distributions, pipeline truth.
4. Profile & Resume Source
   Canonical resume/profile import, Reactive Resume import/export touchpoints.
5. Sync Health
   JobSync export state, status-sync health, mailbox sync truth.

JobPipe should not try to become the day-to-day application workspace.

### JobSync UI

Grounded in the current upstream JobSync route tree, the existing pages are:

- `/dashboard`
- `/dashboard/myjobs`
- `/dashboard/tasks`
- `/dashboard/activities`
- `/dashboard/questions`
- `/dashboard/profile`
- `/dashboard/settings`
- `/dashboard/admin`
- `/dashboard/automations`

Grounded in the current upstream app structure, JobSync already exposes pages for dashboard, tracked jobs, tasks, activities, questions, profile, settings, admin, and automations.

If adopted as the operator workspace, JobSync should own:

1. active application queue
2. notes and manual status work
3. tasks and follow-up
4. artifact links per job
5. day-to-day review of jobs already chosen for action

### Reactive Resume Touchpoints

Reactive Resume should remain an external CV tool.

Grounded in the official docs, it provides:

- self-hosting with Docker
- JSON schema for structured resume data
- JSON and PDF export
- public share links and multiple resume variants

References:

- `https://github.com/AmruthPillai/Reactive-Resume`
- `https://docs.rxresume.org/self-hosting/docker`
- `https://docs.rxresume.org/guides/json-resume-schema`

The intended touchpoints are:

1. import a canonical resume/profile into JobPipe
2. create or edit CV variants in Reactive Resume
3. link the relevant Reactive Resume variant or exported artifact back to the job record in JobSync

Reactive Resume should not become the workflow hub or replace JobSync.

Grounded operation notes from the official docs:

- Reactive Resume self-hosting is documented as a Docker Compose stack with:
  - app
  - PostgreSQL
  - printer service
- the official docs treat `APP_URL`, `DATABASE_URL`, `PRINTER_ENDPOINT`, and `AUTH_SECRET` as required
- the current documented local URL example is `http://localhost:3000`
- the official JSON schema endpoint is `https://rxresu.me/schema.json`

This means JobPipe should integrate with Reactive Resume at the JSON/file/link layer, not by assuming it is a lightweight single-container sidecar.

### NAV / Sheets Bridge

The NAV -> Google Sheets -> JobPipe bridge should be treated as its own companion codebase.

Grounded in the current running architecture, JobPipe already assumes:

- NAV feed data lands in Google Sheets first
- JobPipe then pulls deltas into `<data-root>/jobs_delta.jsonl`

From:

- `pull_sheets_csv.py`
- `docs/gmail_filter_spec.md`
- the current runtime diagram in this file

That bridge is operationally important, but it is not part of the JobPipe runtime itself. The right boundary is:

1. separate Apps Script repo for:
   - NAV API fetch logic
   - Sheet write/update logic
   - script deployment/setup notes
2. JobPipe repo for:
   - consuming the exported Sheet/CSV contract
   - validating/importing the resulting feed

Do not mix Apps Script source into the JobPipe repo just because JobPipe depends on its output.

## Local Multi-Repo Operating Model

For easiest maintenance, keep each external project separate.

Recommended rule:

- separate git repos for active codebases
- separate deployment folders for Docker/env files when no source modifications are needed
- separate private data from repo checkouts

Why:

1. upstream updates stay simple
2. local changes are attributable to the correct project
3. you avoid turning JobPipe into an umbrella vendor repo

Recommended local layout:

```text
<workspace-root>/
  agentic_jobpilot/         # this repo
  jobsync/                  # sibling repo if you customize JobSync
  reactive-resume/          # optional sibling repo if you customize it
  nav-jobpipe-sheet-sync/   # sibling repo for Apps Script + Sheet/NAV bridge
  stacks/
    jobsync-local/          # compose/env/data if only deploying JobSync
    reactive-resume-local/  # compose/env/data if only deploying Reactive Resume
```

This is a standard polyrepo workflow. Developers usually work with sibling repos plus one parent workspace folder, not by nesting unrelated upstream repositories inside the main application repo.

### Install And Run Order

For a clean local operator setup, bring the systems up in this order:

1. JobPipe
   - validate current pipeline/export/server behavior first
   - this repo already has the local-first path contract in `jobpipe/core/paths.py`
   - the local UI is served by `jobpipe/cli/dashboard_server.py`
2. JobSync
   - install and validate as a separate app
   - the upstream README quickstart is `git clone`, `cd jobsync`, `docker compose up`
   - the current upstream compose uses port `3737`, SQLite at `file:/data/dev.db`, and persistent volume `./jobsyncdb/data:/data`
3. Reactive Resume
   - install and validate separately
   - the official self-hosting guide uses Docker Compose with app + Postgres + printer
   - the documented local example URL is `http://localhost:3000`

Do not start by wiring the stack together. Validate each project independently, then add the integration seam.

### Repo Versus Deployment Folder

Use this rule set:

1. If you will change source code, keep a sibling repo.
2. If you only need to run the app, keep a deployment folder with compose/env/volume data.
3. Do not copy upstream code into `agentic_jobpilot` unless you intend to fork and own long-term divergence.

For the current plan, that means:

- `agentic_jobpilot/` stays its own repo
- `jobsync/` should be a sibling repo if you add JobPipe integration endpoints or UI changes
- `reactive-resume/` does not need to be cloned unless you decide to customize it beyond stock self-hosting and JSON import/export
- `nav-jobpipe-sheet-sync/` should be a separate repo for Apps Script development and deployment

### Boundary Enforcement Rules

To keep the repos clean during development:

1. exchange data only through explicit seams
   - Google Sheet / CSV / JSONL
   - HTTP integration endpoints
   - artifact links / IDs
2. do not copy source modules across repos
3. keep deployment/runtime files with the app that owns them
4. keep private state out of every repo and inside mounted/local data directories

Practical examples:

- JobPipe may document the Sheet contract, but it should not contain the Apps Script implementation
- JobSync may expose import/status endpoints, but it should not embed JobPipe stage logic
- Reactive Resume may be linked/imported via JSON, but it should not become the source of pipeline truth
- future JobPipe containerization should mount `JOBPIPE_DATA_ROOT` instead of relocating private state into the image

## Validation Standard

A change is not done until these hold:

- field origin is documented
- field owner is clear
- field survives to ledger or is intentionally excluded
- dashboard reads explicit values instead of inferring from gaps
- tests cover the contract where code exists
