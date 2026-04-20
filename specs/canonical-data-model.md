# JobPipe Canonical Data Model

## Purpose

This document defines the clean data foundation JobPipe should grow toward.

The goal is to:

- keep the repository lean
- keep the workflow local-first and practical
- support one user well today
- make future multi-user/server work possible without rewriting the product model
- avoid premature architecture drift toward tools the app does not actually need yet

This is a repo-grounded spec. It reflects how JobPipe works today while aligning to the current planning thesis:

- JobPipe is a local-first data-and-reasoning layer for job search
- data is the product
- connectors are adapters
- dashboards and external tools are projections
- the next foundation is evidence-backed decision support with living monitoring
- planning remains candidate-first, but hiring-aware

It still reflects important runtime facts from the current codebase:

- staged pipeline in `jobpipe/stages/`
- per-job run artifacts in `out_runs/`
- latest-state evaluation data in `jobpipe.sqlite`
- follow-up state in `application_state.json`
- candidate truth currently split across `profile_pack.md`, `resume.json`, `.env`, and sidecar files

---

## Current State

Today JobPipe stores meaningfully different kinds of data in different formats:

| Concern | Current shape | Current location |
|---|---|---|
| Candidate targeting | Markdown truth source | `profile_pack.md` |
| Candidate CV data | JSON Resume file | `resume.json` |
| Application lifecycle | Sidecar JSON | `application_state.json` |
| Suggested jobs | JSONL queue | `suggested_jobs.jsonl` |
| Semantic cache | NPY file | `profile_embedding.npy` |
| Raw pipeline artifacts | JSON per stage per job | `out_runs/<run_id>/<job_id>/` |
| Latest evaluation state | SQLite + CSV | `jobpipe.sqlite` (`job_evaluations`, `job_run_events`), `reports/evaluations_latest.csv` |
| Dashboard export | Static HTML/JSON | `reports/dashboard.*` |
| Secrets and credentials | `.env` + Gmail JSON | local files |

This works for a solo local tool, but it creates four real problems:

1. Candidate truth is fragmented across Markdown, JSON, env vars, and generated files.
2. Mutable runtime data still tends to leak into the repo layout.
3. The same business concept is often represented multiple ways.
4. There is no clean boundary between source-of-truth data and derived exports.

---

## Design Principles

The next architecture should follow these rules:

1. One canonical model for business data.
2. Relational data first, artifacts second, embeddings third.
3. Code stays in the repo. Personal data and runtime data live under `JOBPIPE_DATA_DIR`.
4. Structured records are the source of truth. Markdown, JSON exports, HTML, and DOCX are derived views.
5. Append-only history where it matters: runs, evaluations, application events, generated documents.
6. Keep artifact traceability. JobPipe should stay debuggable.
7. Do not introduce a dedicated vector database until the relational model is stable and the actual retrieval workload justifies it.

---

## Recommended Storage Strategy

### Short-term target

Use one local data root plus one primary relational database.

Recommended layout:

```text
JOBPIPE_DATA_DIR/
  db/
    jobpipe.sqlite
  artifacts/
    runs/<run_id>/<job_id>/*.json
  documents/
    profile_pack.md
    resume.json
    <candidate_id>/<job_id>/*
  exports/
    dashboard.html
    dashboard_data.json
    evaluations_latest.csv
  cache/
    profile_embedding.npy
  secrets/
    gmail_credentials.json
    gmail_token.json
```

### Source of truth by type

- Database: candidates, jobs, evaluations, application events, notes, document metadata, settings
- Filesystem: raw stage artifacts, generated DOCX/PDF/HTML, large exports
- `.env` or secret store: API keys and credentials only

### Long-term target

Keep the same logical model and move it to Postgres later if JobPipe becomes server-backed.

That means:

- SQLite now is the most natural consolidation layer
- Postgres or Supabase later is the most natural server layer
- pgvector later is the most natural embedding extension

This is intentionally not a “vector DB first” design. Most of JobPipe is workflow, state, traceability, filtering, deadlines, notes, and document history. That is relational work.

---

## Canonical Domain Objects

JobPipe should center around these canonical business objects:

1. candidate
2. candidate profile
3. canonical job
4. job evaluation
5. application activity
6. generated document

These next support layers now matter enough to model explicitly rather than hide in loose JSON or prompt state:

7. candidate calibration and feedback
8. capability gaps and gap evidence
9. job-ad claims and claim assessments
10. hiring-side selection signals and selection assessments
11. job decision tables
12. candidate evidence units
13. tailored CV projections built from canonical evidence
14. candidate narrative profiles and narrative assessments
15. watchlists and change events

Everything else is supporting metadata, cache, compatibility scaffolding, or export.

Current first implementation slice:

- the storage substrate for candidate calibration and feedback already exists in the primary DB
- deterministic local calibration summaries and per-job calibration assessments now live under `jobpipe/decision/`
- these are currently projection-time interpretations over local state, not persisted learned model outputs
- job claims, selection signals, selection assessments, decision tables, watchlists, and change events are now promoted into first-class DB rows through `sync_evaluations`
- candidate evidence units, narrative profiles, narrative fragments, narrative evidence links, and job narrative assessments are now promoted into first-class DB rows through `application_pack`

---

## 1. Candidate

Represents one job hunter.

This should exist even in a single-user install, because it is the cleanest path to future multi-user support.

### Required fields

| Field | Notes |
|---|---|
| `candidate_id` | Stable internal ID |
| `display_name` | Human-readable name |
| `email` | Optional for future notifications/login |
| `locale` | Example: `nb-NO` |
| `timezone` | Example: `Europe/Oslo` |
| `base_location` | Free-text current base |
| `seniority_label` | Example: `mid-senior` |
| `positioning_summary` | Compact professional positioning |
| `strategic_direction` | Current search direction |
| `is_active` | Active candidate flag |
| `created_at`, `updated_at` | Audit timestamps |

### Why this matters

Today “the user” is implicit. Making it explicit is the smallest change that keeps future growth sane.

---

## 2. Candidate Profile

This is the structured truth currently spread across `profile_pack.md`, `resume.json`, and some manual assumptions.

The profile should be versioned.

### Recommended shape

Use one active profile version per candidate, backed by structured JSON in the database and renderable back to `profile_pack.md`.

### Core fields

| Field | Notes |
|---|---|
| `profile_version_id` | Stable ID for one profile snapshot |
| `candidate_id` | Owner |
| `source_kind` | `manual_form`, `profile_pack_import`, `resume_import`, `agent_generated` |
| `profile_json` | Canonical structured content |
| `rendered_profile_pack_md` | Derived Markdown view for current pipeline compatibility |
| `resume_json_snapshot` | Optional embedded snapshot reference |
| `is_active` | Which version drives new scoring |
| `created_at`, `updated_at` | Audit timestamps |

### `profile_json` sections

The JSON document should contain:

- snapshot
- strategic_direction
- target_roles
- constraints
- geo_rules
- compensation_preferences
- positive_signals
- negative_signals
- evidence_bullets
- experience
- projects
- education
- language_profile
- application_style
- prompt_preferences

### Important rule

`profile_pack.md` should eventually become an export and import format, not the only truth source.

That preserves the current workflow while removing Markdown as the only system of record.

---

## 3. Canonical Job

Represents one deduplicated job opportunity regardless of where it was seen.

This should be separate from source-specific sightings.

### Recommended split

Use two layers:

1. `job_source_records`
2. `jobs`

### `job_source_records`

Append-only inbound sightings from NAV, FINN, LinkedIn, Gmail, and future sources.

| Field | Notes |
|---|---|
| `source_record_id` | Stable ID for the sighting |
| `source_name` | `nav`, `finn`, `linkedin_alert`, `gmail_suggestion`, etc. |
| `source_job_key` | Native source ID if present |
| `job_id` | Canonical job reference if deduplicated |
| `raw_payload_json` | Normalized raw intake payload |
| `seen_at` | When JobPipe ingested it |
| `is_active` | Source-level active flag |

### `jobs`

Latest normalized canonical job record.

| Field | Notes |
|---|---|
| `job_id` | Stable canonical ID |
| `dedupe_key` | Derived normalization key |
| `title` | Canonical title |
| `employer` | Canonical employer |
| `work_city`, `work_county`, `work_postal_code` | Normalized location |
| `source_url` | Best public listing URL |
| `application_url` | Best apply URL |
| `application_due` | Normalized date |
| `description_text` | Cleaned text form |
| `description_html` | Optional original HTML |
| `job_metadata_json` | Sector, employment type, extent, etc. |
| `first_seen_at`, `last_seen_at` | Lifecycle tracking |
| `closed_at` | Expired or removed |
| `content_hash` | Detect meaningful text changes |

### Important rule

All candidate-specific scoring must live outside `jobs`.

The same job may be evaluated differently for different candidates later.

---

## 4. Job Evaluation

Represents how one candidate was evaluated against one job in one pipeline run.

This is the heart of JobPipe.

### Recommended split

Use:

1. `pipeline_runs`
2. `job_evaluations`
3. `job_replay_inputs`
4. optional `stage_artifacts`

### `pipeline_runs`

| Field | Notes |
|---|---|
| `run_id` | Stable run ID |
| `candidate_id` | Candidate evaluated in this run |
| `profile_version_id` | Which candidate profile was used |
| `config_version` | Pipeline config identity |
| `started_at`, `finished_at` | Runtime tracking |
| `source_batch_json` | Inputs, filters, or scheduler metadata |
| `status` | `running`, `completed`, `failed` |

### `job_evaluations`

One row per candidate x job x run.

| Field | Notes |
|---|---|
| `evaluation_id` | Stable ID |
| `run_id` | Run reference |
| `candidate_id` | Candidate evaluated |
| `job_id` | Canonical job |
| `triage_decision`, `triage_confidence`, `triage_explanation` | Triage output |
| `triage_signals_json` | Structured signals, not comma text |
| `reverse_decision`, `reverse_confidence`, `reverse_rationale` | Reverse triage output |
| `fit_score` | Profile match |
| `fit_dimensions_json` | Role/domain/seniority/skills breakdown |
| `pivot_score`, `pivot_type`, `pivot_risk` | Pivot output |
| `final_decision`, `final_confidence` | Moderator result |
| `recommendation_reason` | Human-facing explanation |
| `cv_focus_json` | Structured list |
| `feedback_flags_json` | Structured list |
| `skip_reason` | `geo`, `hard_no`, `semantic`, `triage_llm`, `fit_floor`, `moderate`, `passed` |
| `is_latest_for_candidate_job` | Convenient latest marker |
| `created_at` | Evaluation time |

### `stage_artifacts`

Metadata table pointing to raw files under `artifacts/runs/...`.

| Field | Notes |
|---|---|
| `artifact_id` | Stable ID |
| `run_id`, `job_id`, `candidate_id` | Ownership |
| `stage_name` | `input`, `triage`, `profile_match`, `pivot`, `moderator`, `application_pack` |
| `path` | Filesystem path |
| `content_hash` | Integrity/debugging |
| `created_at` | Timestamp |

### Why this matters

This keeps the current artifact-trace philosophy while giving the app a real queryable history model instead of relying on ad hoc file reads alone.

### `job_replay_inputs`

One rerunnable input snapshot per evaluated job.

This keeps the public OSS loop reproducible even after the live canonical catalog has changed or a source row is no longer available.

Recommended fields:

| Field | Notes |
|---|---|
| `job_id` | Canonical job ID |
| `source_name` | Source family captured from the original input |
| `source_job_key` | Source-native key if known |
| `input_payload_json` | Full rerunnable job input payload |
| `input_hash` | Integrity and change tracking |
| `captured_from_run_id` | Pipeline run that produced the snapshot |
| `captured_at` | Original run timestamp |
| `updated_at` | Last stored snapshot time |

Current implementation status:

- `job_replay_inputs` is now a first-class table in the primary DB
- the current write path is driven from `jobpipe/cli/sync_evaluations.py`
- the current persona-audit tooling uses these replay inputs when the live canonical catalog no longer contains a rerunnable row

### Near-term extension: decision support layer

The current `job_evaluations` model is still too compressed for the next product phase.

The next planning direction should add an explicit decision-support layer on top of evaluation history:

- `job_claims`
- `job_claim_assessments`
- `job_selection_signals`
- `job_selection_assessments`
- `job_decision_tables`

#### `job_decision_tables`

One candidate-specific decision snapshot per evaluated job.

Recommended fields:

| Field | Notes |
|---|---|
| `decision_table_id` | Stable ID |
| `candidate_id` | Candidate |
| `job_id` | Canonical job |
| `evaluation_id` | Evaluation context |
| `can_do_score` | Substantive ability/readiness |
| `can_get_score` | Process survivability / hiring-side plausibility |
| `should_want_score` | Forward-fit and strategic desirability |
| `can_explain_score` | Narrative and evidence-backed explainability |
| `decision_label` | `apply_strongly`, `apply`, `review_high`, `review_low`, `skip` |
| `risk_flags_json` | Structured risk list |
| `mitigation_moves_json` | Structured candidate-side moves |
| `assessment_reason` | Compact explanation |
| `updated_at` | Audit timestamp |

This should become the product-facing bridge between raw evaluation traces and later candidate actions.

Current implementation status:

- `job_claims`, `job_selection_signals`, `job_selection_assessments`, and `job_decision_tables` are now first-class tables in the primary DB
- the current write path is driven from `jobpipe/cli/sync_evaluations.py`

---

## 5. Application Activity

Represents everything that happens after a job becomes actionable.

The current `application_state.json` is useful, but it collapses timeline data into one mutable record.

The cleaner model is append-only events plus a derived summary.

### Recommended split

Use:

1. `application_events`
2. `application_summary`
3. optional `candidate_job_notes`

### `application_events`

| Field | Notes |
|---|---|
| `application_event_id` | Stable ID |
| `candidate_id` | Candidate |
| `job_id` | Job |
| `event_type` | `shortlisted`, `called`, `applied`, `interview`, `second_interview`, `accepted`, `rejected`, `dismissed`, `note_added` |
| `event_at` | When it happened |
| `source` | `manual`, `gmail_scan`, `dashboard`, `agent` |
| `notes` | Optional event note |
| `metadata_json` | Email subject, message IDs, external refs |
| `created_at` | Insert timestamp |

### `application_summary`

Derived latest status for fast UI use.

| Field | Notes |
|---|---|
| `candidate_id`, `job_id` | Composite key |
| `current_stage` | Latest non-terminal stage |
| `current_outcome` | Terminal outcome if any |
| `effective_status` | Backward-compatible simple status |
| `last_event_at` | Last change |
| `notes_latest` | Optional latest note preview |

### `candidate_job_notes`

Optional freeform notes separate from stage changes.

This is useful when the user wants working notes without mutating the official application timeline.

---

## 6. Generated Document

Represents any generated application material tied to a job and candidate.

This includes both JobPipe-generated materials and externally refined outputs.

### `generated_documents`

| Field | Notes |
|---|---|
| `document_id` | Stable ID |
| `candidate_id` | Owner |
| `job_id` | Job reference |
| `evaluation_id` | Optional evaluation that produced it |
| `kind` | `application_pack_json`, `cv_highlights_docx`, `cover_letter_md`, `cover_letter_docx`, `cv_pdf`, `external_final_upload` |
| `producer` | `jobpipe_pipeline`, `chatgpt`, `claude`, `manual`, `dashboard_server` |
| `status` | `draft`, `reviewed`, `final`, `archived` |
| `storage_path` | Filesystem path under `documents/` |
| `preview_text` | Small searchable excerpt |
| `document_json` | Optional structured payload for JSON artifacts |
| `created_at`, `updated_at` | Audit timestamps |

### Important rule

The database should store metadata and structured payloads.

Large binaries like DOCX and PDF should stay on disk.

---

## Candidate Evidence Units

JobPipe should stop relying on ad hoc bullet selection and instead maintain a reusable, candidate-approved evidence layer.

### `candidate_evidence_units`

One reusable evidence item tied back to candidate history.

Recommended fields:

| Field | Notes |
|---|---|
| `evidence_unit_id` | Stable ID |
| `candidate_id` | Owner |
| `source_type` | `work_highlight`, `project_case`, `education`, `summary_claim`, `skill_claim` |
| `source_ref` | Link back to work/project/profile source |
| `role_family_tags_json` | Relevant role families |
| `domain_tags_json` | Relevant domains |
| `capability_tags_json` | Relevant capabilities |
| `outcome_tags_json` | Types of evidence shown |
| `canonical_text` | Candidate-approved wording |
| `rewrite_policy` | `verbatim_preferred`, `light_rewrite_only`, `can_summarize` |
| `evidence_json` | Structured facts and references |
| `created_at`, `updated_at` | Audit timestamps |

This layer is the durable substrate for controlled tailoring, narrative support, and decision explainability.

Current implementation status:

- `candidate_evidence_units` is now a first-class table in the primary DB
- the current write path is driven from `jobpipe/stages/application_pack.py`

---

## Watchlists and Change Events

Living monitoring should be treated as a first-class product layer, not just repeated rescanning.

### `watchlists`

Track what the candidate wants to monitor over time.

Recommended fields:

| Field | Notes |
|---|---|
| `watchlist_id` | Stable ID |
| `candidate_id` | Owner |
| `watch_type` | `employer`, `role_family`, `search_pattern`, `source_feed`, `job` |
| `watch_key` | Canonical normalized target |
| `watch_label` | Human-readable label |
| `watch_config_json` | Structured filters or matching config |
| `is_active` | Active flag |
| `created_at`, `updated_at` | Audit timestamps |

### `change_events`

Track meaningful deltas rather than only storing repeated snapshots.

Recommended fields:

| Field | Notes |
|---|---|
| `change_event_id` | Stable ID |
| `candidate_id` | Owner |
| `watchlist_id` | Optional watch source |
| `job_id` | Optional affected job |
| `change_type` | `new_job`, `job_changed`, `deadline_changed`, `selection_logic_changed`, `watch_match`, `status_changed` |
| `change_summary` | Human-readable summary |
| `change_json` | Structured delta details |
| `materiality` | `low`, `medium`, `high` |
| `detected_at` | Detection timestamp |
| `reviewed_at` | Optional review timestamp |

This is the product substrate for repeat usage, not just a notification mechanism.

Current first implementation slice:

- deterministic watchlist derivation now lives under `jobpipe/decision/`
- deterministic change-event derivation uses prior `job_run_events` history and current application state when available
- the current slice is projected into dashboard payloads
- `watchlists` and `change_events` are now first-class tables in the primary DB
- the current write path is driven from `jobpipe/cli/sync_evaluations.py`

---

## Optional Capability: Embeddings

Embeddings should be treated as a support layer, not the core architecture.

### Why

JobPipe’s hard problems are:

- job normalization
- candidate modeling
- evaluation history
- application status tracking
- generated document traceability

Those are not vector-database problems.

### Recommended model

Use one optional `embeddings` table later.

| Field | Notes |
|---|---|
| `embedding_id` | Stable ID |
| `owner_type` | `candidate_profile`, `job`, `document`, `profile_section` |
| `owner_id` | Entity reference |
| `chunk_key` | Optional section identifier |
| `model_name` | Embedding model |
| `text_hash` | Rebuild trigger |
| `vector` | SQLite blob now, pgvector later |
| `created_at` | Timestamp |

### Recommendation

- SQLite + file cache now is fine
- Postgres + pgvector later is the natural upgrade
- a separate vector database should be considered only if search scale or latency proves it necessary

---

## Recommended Physical Model for vNext

If we move from the current scattered files toward one cleaner store, the most practical next step is:

### One primary database

`JOBPIPE_DATA_DIR/db/jobpipe.sqlite`

### Files kept on disk

- run artifacts
- exported dashboard files
- generated CV and cover-letter documents
- Gmail credential files
- optional local caches

### Files that become derived compatibility views

- `profile_pack.md`
- `resume.json`
- `application_state.json`

These should remain usable during migration, but they should stop being the only truth source.

---

## Migration Roadmap

### Phase 1: Consolidate state without changing product behavior

Goal: one clean data root and one clearer system boundary.

Work:

- keep the existing pipeline and artifact model
- add database paths under `JOBPIPE_DATA_DIR/db/`
- define the canonical tables above in SQLite
- write import/sync code from:
  - `profile_pack.md`
  - `resume.json`
  - `application_state.json`
  - `jobpipe.sqlite`
- keep current CLI behavior intact

Success criteria:

- no repo-local personal data is required for normal use
- no business-critical state is stranded in one-off JSON files

### Phase 2: Make current sidecar files derived, not primary

Goal: stop duplicating truth by hand.

Work:

- store candidate profile as structured DB data
- render `profile_pack.md` from the active profile version
- store application events in DB
- generate `application_state.json` only for compatibility if needed
- store generated document metadata in DB
- add decision-support tables as structured state rather than prompt-only logic

Success criteria:

- editing the candidate profile no longer requires manual synchronization across multiple files
- dashboard and status tools can rely on one canonical model

### Phase 3: Move runtime outputs fully under the data root

Goal: make the repo code-only.

Work:

- move `out_runs`, `reports`, and related exports under `JOBPIPE_DATA_DIR`
- keep repo-local defaults only as developer convenience
- add path helpers for runtime roots, not just personal data files
- keep watchlists, change events, and exports under the same external data-root policy

Success criteria:

- the repository can be recloned without carrying runtime history with it
- data backup is a matter of backing up one external folder

### Phase 4: Prepare the same model for server use

Goal: future-proof without overbuilding now.

Work:

- lift SQLite schema to Postgres when needed
- add auth-bound `candidate_id`
- add row-level isolation later if server-backed
- add pgvector only for the parts that truly need embeddings

Success criteria:

- the same domain model works for one user locally and multiple users later
- server migration is a storage migration, not a product rewrite

---

## What Not To Do Yet

1. Do not redesign JobPipe around a dedicated vector database.
2. Do not build a big settings UI before the profile model is stable.
3. Do not throw away artifact files; keep traceability.
4. Do not treat generated markdown, HTML, or DOCX as the source of truth.
5. Do not normalize everything to death. Keep the model clear, not academic.

---

## Immediate Next Steps

The most practical next implementation sequence is:

1. Add path helpers for a database root, document root, artifact root, and export root under `JOBPIPE_DATA_DIR`.
2. Define a first SQLite schema for:
   - `candidates`
   - `candidate_profiles`
   - `application_events`
   - `generated_documents`
3. Extend the canonical state plan to include:
   - `job_claims`
   - `job_selection_signals`
   - `job_decision_tables`
   - `candidate_evidence_units`
   - `watchlists`
   - `change_events`
4. Write a bootstrap/import CLI that imports current local files into that schema.
5. Keep `profile_pack.md` and `application_state.json` as compatibility exports during the transition.
6. Keep `reports/evaluations_latest.csv` only as a derived reporting export, not a second source of truth.

---

## Bottom Line

The most natural path for JobPipe is:

- one clean local data root
- one canonical relational model
- artifacts on disk
- generated documents on disk with metadata in the DB
- embeddings as an optional indexed capability, not the foundation

That keeps the app lean today and makes later Postgres or Supabase work straightforward without forcing a premature platform rewrite.

---

## Related specs

- [capability-gap-analysis.md](capability-gap-analysis.md)
- [local-calibration-learning.md](local-calibration-learning.md)
- [job-claims-model.md](job-claims-model.md)
- [hiring-side-selection-model.md](hiring-side-selection-model.md)
- [controlled-cv-tailoring.md](controlled-cv-tailoring.md)
- [candidate-narrative-model.md](candidate-narrative-model.md)
