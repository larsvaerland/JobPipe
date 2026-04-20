# JobSync Integration Seam

**Date:** 2026-04-19

This spec defines the intended thin integration seam between:

- `JobPipe`
- `jobsync`

The goal is to support a useful companion workflow without turning `JobPipe` into a UI orchestration repo or turning `jobsync` into the source of canonical decision state.

---

## Purpose

`jobsync` should act as a companion workflow surface for the candidate.

It should be able to consume:

- selected job projections
- explicit decision context
- document references
- application-state changes

without becoming the canonical source of:

- job evaluation state
- claims
- selection logic
- evidence or narrative semantics

The architectural rule remains:

- `JobPipe` owns canonical decision state
- `jobsync` consumes bounded projections and emits bounded workflow events back

---

## Non-goals

This seam is not:

- a repo merge
- a shared database
- a shared schema by accident
- a backend fusion
- an excuse to move canonical ranking, claims, or narrative logic into `jobsync`

It should remain deliberately narrow.

---

## Design principles

1. `JobPipe` remains the canonical decision engine.
2. `jobsync` remains a companion workflow/UI system.
3. Data crossing the seam must be explicit, bounded, and versioned.
4. The seam should be additive and tolerant of drift.
5. Write-back from `jobsync` must be event-like, not arbitrary state mutation.
6. The seam must not require shared internal package structure.

---

## What `JobPipe` should send

The seam should project only the minimum companion payload needed for workflow and document handling.

### Canonical outbound families

Recommended outbound projection families:

1. `job_summary`
2. `decision_brief`
3. `document_refs`
4. `application_case_projection`

### 1. `job_summary`

Compact human-facing job context.

Recommended fields:

- `job_id`
- `title`
- `employer`
- `location`
- `application_due`
- `source_url`
- `application_url`
- `updated_at`

### 2. `decision_brief`

Thin explanation of why the job is worth attention.

Recommended fields:

- `final_decision`
- `recommendation_reason`
- `decision_table_summary`
- `selection_risk_level`
- `top_claims`
- `top_selection_signals`
- `top_mitigation_moves`
- `top_evidence_units`
- `narrative_motivation_brief`

Important rule:

- this is a projection of canonical state
- not the full canonical object graph

### 3. `document_refs`

References to generated or reviewed materials.

Recommended fields:

- `document_id`
- `kind`
- `status`
- `storage_path`
- `updated_at`

### 4. `application_case_projection`

The compact case bundle `jobsync` needs to display and act on the job as a workflow item.

Recommended fields:

- `job_summary`
- `decision_brief`
- `document_refs`
- `current_application_status`
- `last_application_event_at`
- `next_action_hint`

---

## What `jobsync` should send back

The write-back seam should be narrow and event-like.

### Canonical inbound families

Recommended inbound families:

1. `application_status_event`
2. `note_event`
3. `document_ref_event`

### 1. `application_status_event`

Maps to canonical `application_events`.

Recommended fields:

- `job_id`
- `candidate_id`
- `event_type`
- `event_at`
- `source`
- `notes`
- `metadata_json`

### 2. `note_event`

Optional freeform working note.

Recommended fields:

- `job_id`
- `candidate_id`
- `note_text`
- `created_at`
- `source`

### 3. `document_ref_event`

Used when `jobsync` helps the user attach or select the document actually used.

Recommended fields:

- `job_id`
- `candidate_id`
- `document_kind`
- `storage_path`
- `status`
- `created_at`
- `source`

---

## Boundary rule

`jobsync` should never be required to understand:

- `job_claims`
- `job_selection_signals`
- `job_selection_assessments`
- `candidate_evidence_units`
- `candidate_narrative_profiles`
- `job_narrative_assessments`

It may display thin projections of those concepts, but canonical ownership stays in `JobPipe`.

---

## Transport options

The seam should remain implementation-agnostic.

Acceptable transport patterns:

- JSON export/import files
- local outbox/inbox folders
- thin HTTP sync endpoint
- later explicit API surface

The transport is secondary to the contract.

---

## First implementation slice

The first useful canonical slice should stay narrow:

1. one versioned outbound payload family from `JobPipe`
2. one versioned inbound status-event family back into `JobPipe`
3. no shared DB
4. no coupled internal imports across repos
5. no requirement for `jobsync` to re-derive ranking or decision semantics

Current status:

- canonical model shapes now exist under `jobpipe/model/`
- canonical projection builders now exist under `jobpipe/projections/`
- canonical inbound status-event runtime helper now exists under `jobpipe/runtime/`
- the first thin transport-facing CLIs are:
  - `jobpipe export-jobsync`
  - `jobpipe record-jobsync-event`

These CLIs are intentionally narrow. They establish the seam without introducing a broad repo-to-repo sync layer.

---

## Recommended code placement in `JobPipe`

When implemented, this seam should land as:

- model shapes in `jobpipe/model/`
- transport/runtime helpers in `jobpipe/runtime/` or `jobpipe/compat/`
- projection builders in `jobpipe/projections/`

It should not start by expanding `jobpipe/core/` or by adding broad orchestration to `jobpipe/cli/`.

---

## Relationship to current salvage work

The separate `agentic_jobpilot` repo contains useful examples of:

- `DecisionBrief`
- `ArtifactPlan`
- `ApplicationCaseProjection`
- status sync
- authoring sync

Those are useful **shape references**, but should only be imported here after they are expressed through the canonical JobPipe boundary model in this spec.

---

## Success criteria

This seam is successful if:

- `jobsync` can show the right jobs with the right compact decision context
- status changes can flow back into canonical `JobPipe` state
- document usage can be traced without making `jobsync` the canonical document store
- neither repo needs to know the other's internal architecture in detail

It fails if:

- canonical decision logic drifts into `jobsync`
- `JobPipe` starts depending on `jobsync` UI/process assumptions
- the seam becomes broad enough that repo separation stops meaning anything
