# Topic-By-Topic Task Plan

Last updated: 2026-04-18

This is the only active execution-order plan. Do not create separate "next steps" or parallel plan files; update this one.

Rule: finish one topic completely before starting the next. Each topic ends with validation and documentation updates.

## Topic 1. Documentation And Contracts

Status: done on 2026-04-17

Scope:
- reconcile repo docs with the actual `jobpipe/` pipeline
- audit dashboard/data-flow documentation
- write the current architecture and full audit down in one place

Exit criteria:
- README reflects the real system
- stale Supabase-first planning is removed from active docs
- dashboard/data contract is documented
- shared audit/status docs updated

## Topic 2. Data Carry-Through Contract

Status: done on 2026-04-17

Scope:
- define the exact field matrix from source input to artifacts to ledger to dashboard payload
- stop dropping useful fields without intent
- make `skip_reason` authoritative in the UI

Implementation targets:
- extend `sync_ledger.py` with explicit carry-through for source/taxonomy/application-pack summary fields
- export thresholds and config snapshot from `export_dashboard.py`
- add payload-level schema versioning
- remove guesswork from dashboard classification

Validation:
- automated assertions for field completeness on representative fixtures
- at least one test file covering `sync_ledger.py` and one covering `export_dashboard.py`

## Topic 3. Dashboard Runtime Unification

Status: done on 2026-04-17

Scope:
- stop treating the dashboard as half static report, half local app
- unify `dashboard.html`, `dashboard_server.py`, and payload building

Implementation targets:
- one canonical `build_payload()` contract for both modes
- fix stale artifact filename assumptions in server mode
- serve the dashboard through the local server without changing the UI contract
- keep static export as a supported read-only mode

Validation:
- manual smoke test in both modes
- server mode can read latest artifacts and application pack correctly

## Topic 4. Information Architecture And Pages

Status: done on 2026-04-17

Scope:
- make the dashboard answer "what do I do now?"
- add the missing profile/CV surface

Target pages:
1. Jobs
2. Pipeline
3. Profile & CV
4. Application Workspace
5. Debug / Data

Validation:
- top navigation matches page model
- profile/CV page renders from tracked source data, not hardcoded text
- no page depends on undocumented side files

## Topic 5. Interaction And Dynamic Data

Status: done on 2026-04-18

Scope:
- remove clunky workflows
- tighten queue behavior and make local editing/state less fragile

Implementation targets:
- dedupe or group duplicate-style postings in the queue
- persist local CV-builder/workspace state more intentionally than browser-local draft only
- keep pack/status/note changes reflected immediately in local app mode
- make deadlines, badges, and counters stay truthful after live updates

Validation:
- duplicate-style rows are meaningfully reduced or grouped
- local builder/workspace state survives refresh in a controlled way
- counters and charts match the active payload after updates

## Topic 6. Performance, Testing, And Hardening

Status: done on 2026-04-18

Scope:
- lock the contract down after the data/runtime redesign

Implementation targets:
- payload-size budget and pruning rules
- dashboard contract tests
- dashboard-server state tests for local notes/profile draft persistence
- end-to-end fixture run from input JSONL to payload
- documented smoke-test commands

Validation:
- `compile_check.py`
- `pytest`
- one fixture-based dashboard payload test
- one server-side local-state persistence test
- one manual rebuild + open pass

## Topic 7. Local-First Data Boundary And Portability

Status: done on 2026-04-18

Scope:
- separate versioned code from private user data cleanly
- make the OSS version portable, local-first, and platform agnostic
- define the boundary between single-user OSS mode and future hosted multi-user mode

Implementation targets:
- define one canonical user data root outside the git worktree
- move credentials, tokens, profile/CV files, ledgers, app state, caches, artifacts, and exports behind that path contract
- add path resolution rules for Windows, macOS, and Linux
- make repo checkouts and branch switches reuse the same private data without re-auth or re-entry
- document what belongs in OSS local storage vs. hosted private infrastructure

Validation:
- a fresh clone can attach to an existing local data root without Gmail re-setup
- repo deletion or branch switching does not destroy private state
- bootstrap and backup/restore steps are documented in one canonical place

Outcomes:
- canonical data-root path rules now exist for Windows, macOS, Linux, and `JOBPIPE_DATA_ROOT`
- active CLI/runtime commands bootstrap legacy repo-local private data into the external data root
- dashboard export now defaults to `<data-root>/exports/dashboard.html`
- direct validation passed for `sync_ledger`, `export_dashboard`, and `dashboard_server`

## Topic 8. Tree Cleanup, Version-Safe Repo Surface, And Commit Prep

Status: done on 2026-04-18

Scope:
- remove leftover repo noise from the dashboard/portability work
- make the canonical docs and plan files match the active runtime
- classify which local files are first-class project assets versus private/local-only material

Implementation targets:
- correct repo-local path drift in the canonical docs
- document the cleanup topic in the execution plan before commit
- keep personal calibration material out of accidental git churn
- confirm which untracked files are real product assets that should be promoted during commit prep

Validation:
- `compile_check.py`
- `pytest`
- manual review of `git status --short`
- manual review of the canonical doc set

Outcomes:
- the canonical docs now describe the external JobPipe data root consistently
- the cleanup/commit-prep topic is now part of the tracked execution plan
- private local calibration material is explicitly kept out of git noise
- the remaining untracked files are classified as first-class assets, not random leftovers

## Topic 9. Pipeline Behavior Audit And Tuning

Status: done on 2026-04-18

Scope:
- verify that the pipe behavior and dashboard truth match the current live data
- tune geo, semantic, triage, and queue behavior only after the data contract and cleanup work are stable

Implementation targets:
- verify geo-block counts and funnel truth against the live ledger/events
- inspect duplicate-looking rows and source-variant grouping for misleading action items
- review semantic-filter and triage distributions for over-uniform categories or drift
- tighten dashboard formatting issues that still interfere with acting on the queue

Validation:
- live-snapshot checks against the current ledger/export
- targeted tests where code contracts change
- rebuild/export/server smoke after any tuning change

Outcomes:
- live dashboard truth was rechecked against the current ledger: `7,686` jobs, `8,982` events, `87` actionable, `4,315` geo skips, `1,567` semantic skips, and `1,072` triage-LLM skips
- the earlier `2.8%` snapshot was confirmed to be stale; the current actionable rate is about `1.13%`
- geo blocks were confirmed to happen at the cheap pre-LLM stage, not after intake; the current geo-block rate is about `56.1%`
- queue duplication was narrowed to two real grouped source-variant cases in the actionable set, while the more serious uniformity issue came from sparse `favorites` source rows
- `merge_job_details()` and exporter enrichment now backfill employer, normalized title, location, and source more aggressively from `00_input.json`
- the Jobs view now has a source filter, grouped-source labels, data-gap disclosure, rolling-deadline normalization, and cleaner decision/status formatting
- broken inline action handlers in the exported dashboard were fixed and revalidated from a headless DOM dump

## Topic 10. Stable Baseline Commit And Dashboard Redesign Start

Status: done on 2026-04-18

Scope:
- commit the cleaned, validated baseline before the larger dashboard redesign
- then rebuild the dashboard shell and interaction model more intentionally around the new data contract

Implementation targets:
- review the remaining first-class untracked assets and promote the right ones into the repo
- make one clean baseline commit with docs, tests, and runtime paths aligned
- define the redesign entry point from the stable CareerTrack-style information architecture already chosen
- keep the next redesign topic separate from pipeline-truth fixes so regressions stay attributable

Validation:
- `compile_check.py`
- `pytest`
- `git status --short` reviewed for intentional contents only
- canonical docs and plan updated before commit

Outcomes:
- the canonical docs now describe the companion-project split consistently across `README.md`, `docs/architecture-plan.md`, and `DASHBOARD_SPEC.md`
- the JobSync integration seam is now documented as a narrow contract instead of an implicit repo-sprawl plan
- canonical docs no longer depend on `.jobpipe_tmp` research paths
- baseline validation passed before commit prep: `compile_check.py`, `pytest`, and manual tree review

## Topic 11. JobSync Integration And Shared Workflow Status

Status: next

Scope:
- keep JobPipe stable while defining a narrow, durable integration seam with JobSync
- align application workflow vocabulary across systems without forcing full status parity
- make JobPipe the curation/status-inference engine and JobSync the operator workspace

Implementation targets:
- normalize JobPipe `app_status` to the shared workflow status set while preserving `app_stages`, `app_outcome`, and events internally
- add a JobPipe status-sync client that posts normalized status events to JobSync
- add JobSync external identity fields and upsert-by-external-id support for imported jobs
- add JobSync status ingestion endpoint with manual-override protection
- replace JobSync seeded statuses with the shared workflow set and remove row-order assumptions in UI logic
- keep JobSync automation discovery state separate from main application workflow status

Shared workflow statuses:
- `draft`
- `applied`
- `interview`
- `offer`
- `rejected`
- `dismissed`

JobPipe normalization:
- `shortlisted` -> `draft`
- `called` -> `draft`
- `applied` -> `applied`
- `interview` -> `interview`
- `second_interview` -> `interview`
- `accepted` -> `offer`
- `rejected` -> `rejected`
- `dismissed` -> `dismissed`

Execution tickets:

1. JobPipe ticket
- add shared-status normalization helper to `mark_status.py`
- ensure `export_dashboard.py` exposes normalized `app_status`
- keep Gmail scan behavior unchanged except for normalized outward-facing status
- add `sync_jobsync_status.py` for one-way normalized status sync

2. JobSync backend ticket
- extend `Job` with external identity and sync metadata fields
- add migration and TypeScript model updates
- add curated-job import endpoint
- add normalized status-sync endpoint with `manual_override` handling

3. JobSync UI cleanup ticket
- replace seeded statuses with the shared set
- remove form assumptions based on status row ordering
- centralize status helpers/grouping
- replace hardcoded status checks in jobs table/detail/filter surfaces
- surface external provenance lightly in job detail

Validation:
- JobPipe exported `app_status` uses only the shared workflow statuses
- one imported JobPipe job upserts into JobSync by stable external identity
- one Gmail-derived JobPipe status update reaches the correct JobSync job
- repeated sync is idempotent
- manual override in JobSync prevents silent overwrite
- JobSync automation discovery state remains separate from application workflow status

### Detailed Execution Checklist

#### Task 1. Normalize JobPipe status

Files:
- `jobpipe/cli/mark_status.py`

Do:
- add `normalize_shared_status(entry)`
- map internal stage/outcome detail to the shared workflow statuses:
  - `shortlisted` -> `draft`
  - `called` -> `draft`
  - `applied` -> `applied`
  - `interview` -> `interview`
  - `second_interview` -> `interview`
  - `accepted` -> `offer`
  - `rejected` -> `rejected`
  - `dismissed` -> `dismissed`

Done when:
- any application-state entry can produce one normalized shared status
- internal `stages`, `outcome`, notes, and email metadata remain unchanged

Risk / notes:
- keep this additive only; do not weaken the current richer state model

#### Task 2. Export normalized status in JobPipe payload

Files:
- `jobpipe/cli/export_dashboard.py`

Do:
- make exported `app_status` use the normalization helper
- keep:
  - `app_stages`
  - `app_outcome`
  - `app_notes`
  - `app_updated_at`

Done when:
- dashboard payload exposes only shared workflow statuses at top level
- rich application detail still survives in the payload

Risk / notes:
- avoid breaking any existing dashboard assumptions that still rely on status labels

#### Task 3. Align Gmail scanner output with normalized status

Files:
- `jobpipe/cli/scan_gmail.py`

Do:
- keep current email classification and monotonic upgrade behavior
- ensure any outward-facing status for sync/export is normalized to the shared vocabulary

Done when:
- Gmail scan still detects `applied`, `interview`, and `rejected`
- exported/shared status is always one of:
  - `draft`
  - `applied`
  - `interview`
  - `offer`
  - `rejected`
  - `dismissed`

Risk / notes:
- do not weaken current progression safeguards

#### Task 4. Add JobPipe -> JobSync status sync client

Files:
- `jobpipe/cli/sync_jobsync_status.py`

Do:
- create a one-way sync script
- read changed JobPipe application-state entries
- POST normalized status events to JobSync
- persist a sync checkpoint under the JobPipe private data root

Done when:
- one changed JobPipe status can be sent once and skipped on rerun
- sync is idempotent

Risk / notes:
- use explicit external IDs only; do not introduce fuzzy matching

#### Task 5. Add external identity fields to JobSync jobs

Files:
- `prisma/schema.prisma`

Do:
- add to `Job`:
  - `externalSource`
  - `externalId`
  - `externalStatusSource`
  - `externalStatusAt`
  - `externalStatusMeta`
  - `syncMode`
- add a unique index on `[externalSource, externalId]`

Done when:
- imported JobPipe jobs can be addressed deterministically

Risk / notes:
- keep new fields nullable for a low-risk migration

#### Task 6. Create JobSync migration

Files:
- `prisma/migrations/...`

Do:
- generate a migration for the new `Job` fields

Done when:
- existing JobSync databases upgrade cleanly

Risk / notes:
- validate the uniqueness constraint against any existing imported test rows

#### Task 7. Update JobSync TypeScript job model

Files:
- `src/models/job.model.ts`

Do:
- add new external/sync fields to the TS model

Done when:
- backend routes and UI can compile with imported job metadata

Risk / notes:
- keep fields optional initially

#### Task 8. Add curated JobPipe job import endpoint to JobSync

Files:
- `src/app/api/integrations/jobpipe/jobs/route.ts`

Do:
- upsert imported curated jobs by `[externalSource, externalId]`
- map a narrow curated field set from JobPipe into JobSync job records

Done when:
- the same external job imports idempotently

Risk / notes:
- do not overmodel JobPipe internals in v1

#### Task 9. Add normalized status sync endpoint to JobSync

Files:
- `src/app/api/integrations/jobpipe/status/route.ts`

Do:
- find imported jobs by external identity
- update workflow status plus external metadata
- if `syncMode == manual_override`, store metadata but do not overwrite status

Done when:
- one posted status update changes the correct job
- manual override blocks overwrite safely

Risk / notes:
- keep the endpoint deterministic and side-effect-light
- the endpoint depends on the shared `JobStatus` rows already existing in JobSync, including `dismissed`; do not wire the sync client before Task 10 is complete

#### Task 10. Replace JobSync seeded workflow statuses

Files:
- `src/lib/constants.ts`
- `src/actions/auth.actions.ts`

Do:
- seed the shared workflow statuses:
  - `draft`
  - `applied`
  - `interview`
  - `offer`
  - `rejected`
  - `dismissed`
- optionally keep admin-only:
  - `expired`
  - `archived`

Done when:
- new users receive the shared workflow status set

Risk / notes:
- do not mix automation discovery state into the seeded application statuses
- ensure the seeded/shared status set includes every value JobPipe can emit:
  - `draft`
  - `applied`
  - `interview`
  - `offer`
  - `rejected`
  - `dismissed`

#### Task 11. Remove JobSync status row-order assumptions

Files:
- `src/components/myjobs/AddJob.tsx`

Do:
- stop assuming status row order implies workflow meaning
- look statuses up explicitly by `value`

Done when:
- add/edit job flow works regardless of DB row ordering

Risk / notes:
- this is a subtle but high-value cleanup

#### Task 12. Centralize JobSync status logic

Files:
- `src/lib/job-status.ts`

Do:
- add helpers such as:
  - `getStatusByValue`
  - `isDraftLike`
  - `isInterviewLike`
  - `isTerminal`
  - `isAdminOnly`

Done when:
- UI status behavior no longer depends on scattered literal-string checks

Risk / notes:
- keep this small; do not turn it into an abstraction framework

#### Task 13. Clean up JobSync jobs filter logic

Files:
- `src/components/myjobs/JobsContainer.tsx`

Do:
- replace current hardcoded workflow filter logic with shared-status-aware logic

Done when:
- filters still behave correctly after the status set changes

Risk / notes:
- preserve current usability and scan speed

#### Task 14. Clean up JobSync table/detail status rendering

Files:
- `src/components/myjobs/MyJobsTable.tsx`
- `src/components/myjobs/JobDetails.tsx`

Do:
- replace direct status string checks with helper-driven rendering
- keep `expired` as an administrative overlay, not a main workflow state
- optionally surface sync provenance lightly

Done when:
- badge colors, labels, and expired behavior remain correct

Risk / notes:
- make sure `offer` reads as the final positive workflow state

#### Task 15. Keep automation discovery state separate

Files:
- `src/lib/scraper/mapper.ts`
- related automation UI files as needed

Do:
- leave automation discovery states such as `new` separate from main application workflow status

Done when:
- discovery queue and tracked-job workflow state are still distinct concepts

Risk / notes:
- mixing these models will make the system harder to reason about

#### Task 16. Add manual override behavior in JobSync

Files:
- `src/actions/job.actions.ts`
- status UI files as needed

Do:
- when the user manually changes the status of an imported job, set `syncMode = manual_override`
- optionally add a later way to resume external sync

Done when:
- external sync cannot silently overwrite explicit user choices

Risk / notes:
- this is the main safeguard against mailbox-driven noise

#### Task 17. Add provenance display in JobSync

Files:
- `src/components/myjobs/JobDetails.tsx`

Do:
- show lightweight provenance such as:
  - source = JobPipe
  - last synced at
  - last synced from Gmail or another source

Done when:
- users can distinguish external updates from manual edits

Risk / notes:
- keep this lightweight, not a debug dump

#### Task 18. End-to-end validation

Files:
- JobPipe tests and smoke flow
- JobSync tests where appropriate

Do:
- test normalized export
- test curated job import upsert
- test status sync
- test manual override
- test idempotent rerun

Done when:
- one representative job can move through:
  - imported as `draft`
  - synced to `applied`
  - synced to `interview`
  - synced to `rejected` or `offer`

Risk / notes:
- validate one realistic path before broadening scope

### Suggested Execution Order

1. Task 1
2. Task 2
3. Task 5
4. Task 6
5. Task 7
6. Task 9
7. Task 4
8. Task 10
9. Task 11
10. Task 12
11. Task 13
12. Task 14
13. Task 16
14. Task 17
15. Task 18

### First Milestone

The first real proof point is:

- JobPipe exports normalized shared status
- JobSync can receive a status update for an imported job by external ID
- one JobPipe Gmail-derived update changes the correct JobSync job
