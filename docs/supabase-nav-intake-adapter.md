# Supabase NAV Intake Adapter

Date: 2026-05-08
Task: S5-SB-01

## Decision

Supabase is an intake source for NAV jobs. It is not the JobDesk case read
model, not the ApplicationWorkspaceHub storage adapter, and not a direct
JobDesk dependency.

The smallest safe adapter is:

```text
JobData hosted Supabase public.jobs / jobs_active
-> JobPipe Supabase NAV puller
-> reports/nav_connector.jsonl
-> jobpipe.core.intake_pipe.rebuild_intake_queue(...)
-> jobs_delta.jsonl
-> existing JobPipe run/drain path
-> current JobPipe SQLite/artifacts
```

JobDesk must continue to read through JobDeskIntegrationGateway and future
ApplicationWorkspaceHub/API wrappers. It must not connect directly to Supabase.

## Sources Inspected

- JobPipe:
  - `jobpipe/cli/pull_supabase_jobs.py`
  - `jobpipe/cli/drain_queue.py`
  - `jobpipe/core/intake_pipe.py`
  - `jobpipe/runtime/catalog.py`
  - `jobpipe/core/primary_db.py`
- JobData GitHub repository:
  - `larsvaerland/JobData`
  - Supabase migrations on `main`
  - NAV import edge-function source on `main`

The stale local Supabase folder is not a source for this audit.

## Existing Intake Seam

JobPipe already has a connector staging seam:

- NAV broad-feed records stage into `<data-root>/reports/nav_connector.jsonl`.
- Suggested leads stage into `<data-root>/reports/leads_connector.jsonl`.
- `jobpipe.core.intake_pipe.prepare_connector_record(...)` stamps connector
  metadata, policy, and `intake_dedupe_key`.
- `jobpipe.core.intake_pipe.rebuild_intake_queue(...)` merges NAV and lead
  connector staging into `<data-root>/jobs_delta.jsonl`.
- NAV records are preferred as canonical during merge, while suggested leads
  can backfill missing fields.
- `jobpipe.cli.drain_queue` then batches `jobs_delta.jsonl` into
  `jobpipe.cli.run_feed`.

This is the correct seam for Supabase NAV intake. The adapter should feed
`nav_connector.jsonl`; it should not bypass the connector merge or write a new
JobDesk-facing model.

## Existing Supabase Connector

`jobpipe/cli/pull_supabase_jobs.py` already provides the first Supabase NAV
connector:

- reads `JOBPIPE_SUPABASE_URL` and `JOBPIPE_SUPABASE_KEY`;
- queries Supabase REST at `/rest/v1/jobs`;
- filters active, non-expired jobs;
- increments by `updated_at` using the existing jobs state file;
- maps rows into canonical JobPipe intake field names;
- emits `nav_feed` connector records with `intake_channel="supabase"`.

`jobpipe/cli/drain_queue.py` automatically selects this connector when both
Supabase environment variables are present. If not, it falls back to the
Google Sheet/CSV intake path.

## JobData Table And Column Summary

Expected hosted Supabase source: `public.jobs`.

Useful view: `public.jobs_active`, which selects active rows only. The current
JobPipe connector queries `public.jobs` directly with `status=eq.ACTIVE` and
`expires_at > now`.

Columns expected by the current JobPipe connector:

| Column | Purpose |
| --- | --- |
| `id` | NAV/source job id |
| `title` | Display title/headline |
| `role` | Canonical role title where available |
| `employer` | Employer/company |
| `municipality` | Primary municipality |
| `county` | Primary county |
| `counties` | All observed counties |
| `location` | Fallback display location |
| `postal_code` | Postal code |
| `description` | Job body/description |
| `application_url` | Apply URL |
| `published_at` | Published timestamp |
| `expires_at` | Expiry timestamp |
| `application_due` | Raw application deadline text |
| `sector` | NAV sector |
| `occupation_level1` | NAV taxonomy level 1 |
| `occupation_level2` | NAV taxonomy level 2 |
| `extent` | Full-time/part-time |
| `engagement_type` | Permanent/temp/project/etc. |
| `position_count` | Number of positions |
| `updated_at` | Incremental sync cursor |
| `status` | `ACTIVE` after NAV status guard |

The JobData migrations also keep `raw_json` in `public.jobs`. That is useful
for provenance and future field extraction, but the JobPipe connector should
not emit raw private payloads to JobDesk.

## Canonical Mapping

Supabase NAV rows should map into JobPipe intake fields as follows:

| Supabase NAV field | JobPipe intake field | Rule |
| --- | --- | --- |
| `id` | `uuid`, `job_id` | Required stable source id |
| `title` | `title` | Display headline |
| `role` | `normalized_title` | Canonical role if present |
| `employer` | `employer_name` | Required employer/company |
| `description` | `description_html` | Preserve as source body; downstream can text-normalize |
| `application_url` | `applicationUrl` | Apply URL |
| `application_due` | `applicationDue` | Prefer raw application deadline text |
| `expires_at` | fallback deadline/expiry metadata | Use only when `application_due` absent |
| `municipality` or `location` | `work_city` | Municipality first, location fallback |
| `county` | `work_county` | Primary county |
| `postal_code` | `work_postalCode` | Postal code |
| `counties` | `workLocations_json` | JSON-encoded array |
| `sector` | `sector` | Preserve structured sector |
| `occupation_level1` | `occ_level1` | Preserve taxonomy |
| `occupation_level2` | `occ_level2` | Preserve taxonomy |
| `extent` | `extent` | Preserve as metadata/additive field |
| `engagement_type` | `engagement_type` | Preserve as metadata/additive field |
| `position_count` | `position_count` | Preserve as metadata/additive field |
| `updated_at` or `published_at` | `ad_updated` | Cursor and freshness signal |
| `id` | `sourceurl` | Build NAV Arbeidsplassen URL from id |
| `status` | `status` | Current active/inactive source signal |

Minimum required row fields before a record enters the normal JobPipe run:

- stable external/source id;
- title or role;
- employer;
- description/body;
- source URL or application URL;
- published/updated timestamp if available;
- deadline or expiry if available;
- location/workplace fields if available.

Rows missing title/role, employer, and description should be counted and
reported by the connector rather than silently becoming high-cost AI inputs.

## NAV-Only Metadata Preservation

Extra NAV fields should remain additive. Do not force every NAV field into the
core JobPipe `jobs` columns.

Preserve as connector payload/source metadata where present:

- `extent`
- `engagement_type`
- `position_count`
- `occupation_level1`
- `occupation_level2`
- `sector`
- `counties`
- `published_at`
- `expires_at`
- `application_due`
- raw source status
- raw extraction/source timestamps
- safe source id and source URL

The current `jobpipe.runtime.catalog._metadata_json(...)` already preserves
non-core intake fields into `jobs.job_metadata_json`, and
`job_source_records.raw_payload_json` preserves the connector payload. This is
the right preservation path for NAV-only fields.

## Dedupe And Upsert

Source identity:

- Source name should be `nav` or `nav_supabase`; prefer `nav` while the data is
  still semantically the NAV broad feed.
- Source job key is Supabase `jobs.id`.
- Connector name remains `nav_feed`.
- Connector source remains `nav`.
- Intake channel is `supabase`.

Dedupe behavior:

- Connector-level dedupe uses `derive_intake_dedupe_key(...)`:
  normalized title/role + employer + location/deadline.
- Catalog-level dedupe uses `jobpipe.runtime.catalog.canonical_job_dedupe_key`.
- Runtime catalog source precedence already gives NAV high priority.
- `job_source_records` keeps source-specific identity and raw connector
  payloads.

Upsert behavior:

- Supabase rows are read-only inputs to JobPipe.
- The connector writes only local connector staging/state files.
- Existing JobPipe run/sync writes current SQLite/artifacts.
- No Supabase write-back is part of this intake adapter.

## One-Run Command Shape

Recommended direct smoke:

```powershell
python -m jobpipe.cli.pull_supabase_jobs --data-root <JOBPIPE_DATA_ROOT> --out <JOBPIPE_DATA_ROOT>\reports\nav_connector.jsonl --state <JOBPIPE_DATA_ROOT>\jobs_state.json --only-changed
python -m jobpipe.cli.drain_queue --data-root <JOBPIPE_DATA_ROOT> --batch-size 10 --max-total-jobs 10
```

Recommended operator path:

```powershell
$env:JOBPIPE_SUPABASE_URL = "<hosted Supabase URL>"
$env:JOBPIPE_SUPABASE_KEY = "<service/backend key>"
python -m jobpipe.cli.drain_queue --data-root <JOBPIPE_DATA_ROOT> --batch-size 50
```

`drain_queue` should remain the normal seam because it handles connector
refresh, merge, dedupe, batching, ledger filtering, run-feed execution, and
sync-back into local JobPipe state.

## Output Storage Decision

For this slice, outputs remain in current JobPipe storage:

- primary SQLite DB under the JobPipe data root;
- run artifacts under the JobPipe data root;
- reports/exports as currently produced.

Supabase write-back is deferred. If later needed, it should be introduced as a
separate output/status adapter behind ApplicationWorkspaceHub or an approved
JobPipe storage seam. It must not be coupled to NAV intake.

## Blockers Before Implementation

- Confirm the live hosted Supabase schema matches JobData `main`; this audit
  did not query the live database.
- Decide whether the connector should read `public.jobs` with explicit filters
  or `public.jobs_active`. The current code uses `public.jobs` with filters.
- Add tests for `pull_supabase_jobs._map_row(...)` and query/select-column
  expectations.
- Decide whether source name should stay `nav` everywhere or become
  `nav_supabase` only at source-record level.
- Decide how to count/report rows with insufficient required fields.

## Exact Next Implementation Task

S5-SB-02 — Harden Supabase NAV Intake Puller

Goal: make the existing `pull_supabase_jobs.py` adapter production-safe without
changing downstream JobPipe or JobDesk behavior.

Scope:

- keep Supabase as intake source only;
- add focused tests for `_map_row(...)`;
- preserve NAV-only fields in connector payload/source metadata;
- optionally switch read source to `jobs_active` if validated against hosted
  Supabase;
- add a dry-run/limit/report mode if absent;
- do not write to Supabase;
- do not implement JobDesk read model;
- do not add ApplicationWorkspaceHub storage adapter;
- do not depend on old dashboard code.
