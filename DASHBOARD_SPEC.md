# Dashboard Spec

Last updated: 2026-04-18

## Product Job

The dashboard must answer two questions quickly:

1. What should Lars do right now?
2. Why did this job survive or fail the pipeline?

Everything else is secondary.

## Current Runtime Modes

### 1. Static export

Built by:

```powershell
.venv\Scripts\python.exe -m jobpipe.cli.export_dashboard
```

Output:
- `<data-root>/exports/dashboard.html` by default
- any alternate `--out` target, including repo-local exports when explicitly requested

Behavior:
- read-only
- payload is embedded inline at export time
- no local mutation endpoints

### 2. Local interactive mode

Started by:

```powershell
.venv\Scripts\python.exe -m jobpipe.cli.dashboard_server
```

Serves:
- the same tracked dashboard template rendered directly from live `build_payload()` output
- application status updates
- notes
- application workspace
- `resume.json`

Behavior:
- no dependency on a previously exported `reports/dashboard.html`
- detail-pane status buttons write through `/api/status`
- detail-pane notes write through `/api/notes`
- generated documents download through the server route instead of raw filesystem links
- `/api/data` returns the same payload contract as static export

## Current Verified State

As of the 2026-04-18 Topic 6 hardening pass:

- jobs in ledger: 7,684
- events: 8,980
- actionable jobs: 87
- payload size: about 14.1 MB
- payload schema version: `jobpipe.dashboard.v2`
- source taxonomy rows in ledger: 7,499
- taxonomy rows without source identity after carry-through rebuild: 0
- pack-ready rows in ledger: 26
- grouped actionable queue rows in Jobs/Workspace views: 85
- payload soft budget: 16 MiB
- payload meta now reports actual size and event pruning state on every build

The exporter is still fast enough for local use. The remaining pressure is payload growth over time, JS-only queue grouping, and the still-separate deep drafting surface.

## Payload Budget And Pruning

The dashboard payload now has explicit guardrails:

- soft budget: `16 MiB`
- event hard cap: `10,000` rows
- event floor after pruning: `2,000` rows
- pruning target: oldest event history first

Rules:

1. Keep the full `jobs` list because the dashboard/debug surfaces still depend on it.
2. Cap `events` at the newest `10,000` rows.
3. If the payload still exceeds the soft budget, prune additional oldest events in chunks until the payload drops under budget or reaches the `2,000`-event floor.
4. Report the result in `payload_meta` so static export and local server mode can both expose truthful size/pruning state.

## Current Gaps

1. some actionable rows still have no fixed deadline because the source data itself does not expose one.
2. queue dedupe/grouping is currently a UI concern; the raw payload and pipeline metrics still keep source-level duplicates for traceability.
3. the local CV builder now persists to `<data-root>/reports/profile_builder_state.json`; that solves the repo-boundary issue, but the draft still intentionally does not write back into tracked source files.
4. the application workspace now has a first-class dashboard entry page, but deep drafting still opens the dedicated `/apply/<job_id>` surface.

## Required Payload Shape

The dashboard should receive one canonical payload from `build_payload()`, and both static/exported outputs should be built from the same tracked template:

```json
{
  "generated_at": "2026-04-17T12:34:56Z",
  "schema_version": "jobpipe.dashboard.v2",
  "payload_meta": {},
  "thresholds": {},
  "config_snapshot": {},
  "profile": {},
  "jobs": [],
  "events": []
}
```

## Job Record Requirements

Every job record should carry these groups of fields.

### Identity

- `job_id`
- `run_id`
- `job_source`
- `job_status`
- `suggested_by_platform`
- `title`
- `normalized_title`
- `employer`

### Timing

- `run_seen_at`
- `updated_at`
- `applicationDue`
- `closed_at`

### Action links

- `source_url`
- `application_url`

### Location

- `work_city`
- `work_county`
- `work_postalCode`

### Source taxonomy

- `occ_level1`
- `occ_level2`
- `cat_type`
- `cat_code`
- `cat_name`
- `cat_score`
- `sector`

### Decision pipeline

- `triage_decision`
- `triage_confidence`
- `triage_signals`
- `triage_explanation`
- `skip_reason`
- `fit_score`
- `pivot_score`
- `final_decision`
- `final_confidence`
- `recommendation_reason`

### Detail/debug

- overlaps
- gaps
- hard blockers
- profile-match dimensions
- pivot rationale
- moderator guidance

### Application tracking

- `app_status`
- `app_stages`
- `app_outcome`
- `app_notes`
- `app_updated_at`
- `app_source`

#### Shared Workflow Status

For JobPipe-only debugging, keep the richer application fields above. For any operator-facing integration contract, `app_status` must normalize to the shared workflow vocabulary:

- `draft`
- `applied`
- `interview`
- `offer`
- `rejected`
- `dismissed`

Normalization rules:

1. if `app_outcome == accepted`, expose `app_status = offer`
2. if `app_outcome == rejected`, expose `app_status = rejected`
3. if `app_outcome == dismissed`, expose `app_status = dismissed`
4. else if `app_stages` contains `second_interview`, expose `app_status = interview`
5. else if `app_stages` contains `interview`, expose `app_status = interview`
6. else if `app_stages` contains `applied`, expose `app_status = applied`
7. else if `app_stages` contains `called`, expose `app_status = draft`
8. else if `app_stages` contains `shortlisted`, expose `app_status = draft`
9. else expose `app_status = null` internally; imported external-workspace jobs may coerce this to `draft`

Do not throw away:

- `app_stages`
- `app_outcome`
- `app_notes`
- `events`

The normalized status exists to align JobPipe with the main operator workflow, not to replace the richer internal trace.

### Pack summary

- `generated_documents`
- `no_score_reason_label`
- `pack_ready`
- `pack_generated_at`
- `pack_has_cover_letter`
- `pack_highlight_count`
- `pack_docx_ready`

## Profile Payload Requirements

The dashboard needs a first-class profile object built from:
- `<data-root>/profile_pack.md`
- `<data-root>/reports/resume.json`

It should expose:
- basics: name, label, summary, location
- builder state: persisted local CV edits when present
- target roles
- target geography
- strengths and evidence highlights
- reusable CV highlights
- skills
- current education / modules

This is the data source for the live Profile & CV builder/preview page.

## Event Payload Requirements

Events should support:
- run volume
- pass rate
- APPLY volume
- source mix
- calibration over time

Minimum event fields:
- `run_id`
- `job_id`
- `run_mtime`
- `seen_at`
- `job_source`
- `job_status`
- `skip_reason`
- `triage_decision`
- `final_decision`
- `fit_score`
- `pivot_score`

## Smoke Test

Run this after dashboard/export/server changes:

```powershell
.venv\Scripts\python.exe compile_check.py
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m jobpipe.cli.export_dashboard
.venv\Scripts\python.exe -m jobpipe.cli.dashboard_server --no-open
```

Manual pass:
- open `<data-root>/exports/dashboard.html`
- open `http://127.0.0.1:5100/`
- confirm `/api/data` returns the payload
- confirm a saved note or CV draft survives refresh in local mode

## Pages

### 1. Jobs

Purpose:
- daily action list
- status updates

## JobSync Integration Contract

If JobSync becomes the main operator app, JobPipe should integrate with it through explicit import and status-sync contracts instead of trying to mirror the full dashboard payload.

### Curated Job Import Payload

Import only curated jobs that have already survived JobPipe decisioning, for example `APPLY`, `APPLY_STRONGLY`, and optionally `REVIEW_HIGH`.

Minimum record:

```json
{
  "externalSource": "jobpipe",
  "externalId": "24dc9013-65ac-4c75-be39-63867b0ed111",
  "runId": "2026-04-18T09-44-12Z",
  "title": "Produktleder",
  "company": "Politiets IT-enhet",
  "location": "Oslo, Oslo",
  "jobUrl": "https://example.com/job",
  "applicationUrl": "https://example.com/apply",
  "description": "...",
  "jobSource": "nav",
  "status": "draft",
  "decision": "APPLY_STRONGLY",
  "fitScore": 86,
  "pivotScore": 85,
  "triageExplanation": "...",
  "artifactsPath": "C:\\\\Users\\\\larsv\\\\JobPipeData\\\\out_runs\\\\...",
  "packReady": false,
  "packDocxReady": false,
  "updatedAt": "2026-04-18T09:44:12Z"
}
```

### Status Sync Payload

Normalized JobPipe status events should be emitted separately from curated-job import:

```json
{
  "externalSource": "jobpipe",
  "externalId": "24dc9013-65ac-4c75-be39-63867b0ed111",
  "status": "interview",
  "occurredAt": "2026-04-18T10:42:00Z",
  "source": "gmail",
  "notes": "Interview invitation detected",
  "emailSubject": "Invitation to interview",
  "emailDate": "2026-04-18"
}
```

### Conflict Rule

When a downstream workspace supports manual override, external JobPipe status sync must obey this rule:

1. if the external job record is in normal sync mode, overwrite the shared workflow status
2. if the external job record is in manual override mode, preserve the local status and only store external metadata

The goal is to keep mailbox-driven automation valuable without trampling explicit user actions.
- deadline triage
- pack-ready visibility

Must show:
- decision
- status
- title/employer/location
- fit/pivot
- deadline
- source/apply link
- pack-ready state
- source filter for queue-facing review
- visible data-gap disclosure when a row is missing employer, deadline, location, apply link, or taxonomy

### 2. Pipeline

Purpose:
- understand what the pipe is doing

Must show:
- funnel based on explicit `skip_reason`
- skip breakdown
- score distributions
- threshold overlays from payload thresholds
- token-waste view

### 3. Profile & CV

Purpose:
- keep the source-of-truth candidate material inside the product
- allow fast local tailoring without leaving the dashboard

Must show:
- editable local CV fields seeded from tracked source data
- persisted local builder draft when available
- live CV preview
- resume summary
- experience
- reusable highlights
- current study modules
- target roles and signals from `<data-root>/profile_pack.md`

### 4. Application Workspace

Purpose:
- write, refine, and export job-specific application material

Current implementation:
- `reports/apply_template.html`

Future requirement:
- keep the dedicated drafting route, but persist its local state more intentionally and tie it more closely to queue grouping/dedupe.

### 5. Debug / Data

Purpose:
- inspect completeness and failures quickly

Should show:
- payload version
- field completeness
- latest run id
- pack generation status
- server/static mode
- per-source quality summary so sparse sources such as favorites are visible instead of being mistaken for scoring drift

## Validation Rules

The dashboard is correct only if:

- funnel counts equal ledger `skip_reason` counts
- geo-block KPI equals explicit `skip_reason='geo'` count
- threshold lines use exported thresholds
- config-sensitive views read `config_snapshot` rather than hardcoded assumptions
- jobs do not disappear because the UI guessed wrong
- the same tracked template can rebuild both repo output and any user-facing `--out` target
- profile/CV data is visible without leaving the main product surface
- queue-facing views may group duplicate source variants without changing raw pipeline totals
- static mode and local server mode read the same payload contract
