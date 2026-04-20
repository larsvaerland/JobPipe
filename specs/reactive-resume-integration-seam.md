# Reactive Resume Integration Seam

**Date:** 2026-04-19

This spec defines the intended thin integration seam between:

- `JobPipe`
- `Reactive Resume`

The purpose is to let JobPipe use a structured resume system without turning Reactive Resume into the canonical owner of JobPipe's candidate decision semantics.

---

## Purpose

Reactive Resume should act as:

- a resume editing surface
- a structured resume import/export surface
- an optional rendering/export surface

It should not become the canonical source of:

- job claims
- hiring-side selection logic
- evidence selection policy
- candidate narrative assessment
- JobPipe calibration state

The architectural rule remains:

- `JobPipe` owns candidate-specific decision and tailoring semantics
- `Reactive Resume` owns resume editing/rendering concerns where useful

---

## Non-goals

This seam is not:

- a codebase merge
- a requirement to fork Reactive Resume deeply
- a replacement of JobPipe's candidate evidence model
- permission to let an editor UI become canonical decision state

---

## Design principles

1. One canonical tailoring logic layer in `JobPipe`.
2. Resume editing/rendering can stay external.
3. Import/export should be structured and versioned.
4. JobPipe should prefer evidence selection and bounded rewriting over freeform CV rewriting.
5. Multiple render targets should remain possible.
6. Reactive Resume integration should stay optional.

---

## What `JobPipe` should own

Canonical ownership in `JobPipe` should remain:

- candidate evidence units
- evidence rewrite policy
- narrative profile and fragments
- job claims
- selection signals and assessments
- decision tables
- tailored CV projection plans

This means JobPipe should be able to answer:

- what evidence to select
- what to suppress
- what ordering to use
- what must be emphasized
- what must not be rewritten aggressively

before any resume editor/export surface is involved.

---

## What `Reactive Resume` may own

Reactive Resume may reasonably own:

- resume section editing
- ordering and display editing at the editor level
- template/rendering concerns
- PDF/JSON export
- optional import/export of structured resume documents

This is compatible with JobPipe if Reactive Resume is treated as:

- an editor
- a renderer
- a structured interchange surface

not as the canonical decision engine.

---

## Seam object families

### 1. `resume_import_projection`

Used when JobPipe imports or refreshes structured resume content from Reactive Resume.

Recommended fields:

- `candidate_id`
- `resume_source_id`
- `schema_version`
- `basics`
- `work`
- `projects`
- `education`
- `skills`
- `languages`
- `metadata`

This should map into JobPipe's canonical candidate/evidence/narrative model rather than remain the only truth.

### 2. `tailored_cv_plan`

The key outbound seam from JobPipe.

Recommended fields:

- `candidate_id`
- `job_id`
- `evaluation_id`
- `variant_strategy`
- `selected_evidence_unit_ids`
- `selected_section_order`
- `suppressed_items`
- `summary_brief`
- `rewrite_constraints`
- `claim_targets`
- `selection_mitigation_targets`

Important rule:

- this is a plan
- not a freeform rewritten CV

### 3. `tailored_cv_projection`

Optional richer handoff to an editor or renderer.

Recommended fields:

- `headline`
- `summary_text`
- `section_plan`
- `selected_bullets`
- `provenance`
- `render_target`

This may be consumed by a Resume UI, but canonical selection logic stays in JobPipe.

### 4. `rendered_document_ref`

Metadata about the final rendered artifact.

Recommended fields:

- `document_id`
- `job_id`
- `kind`
- `storage_path`
- `status`
- `producer`
- `updated_at`

---

## Boundary rule

Reactive Resume should not need to understand:

- `job_claims`
- `job_selection_signals`
- `job_selection_assessments`
- `job_decision_tables`
- `job_narrative_assessments`

It may receive thin derived targeting hints, but not canonical decision ownership.

---

## First implementation slice

The first useful seam should stay narrow:

1. structured resume import into JobPipe-compatible candidate state
2. one bounded tailored-CV plan exported from JobPipe
3. one render/export handshake back as document refs
4. no attempt to move all tailoring logic into Reactive Resume
5. no deep upstream coupling requirement

Current status:

- canonical seam shapes now exist under `jobpipe/model/`
- thin import into canonical `candidate_profiles` now exists under `jobpipe/cli/`
- thin plan/projection builders now exist under `jobpipe/projections/`
- thin rendered-document write-back now exists under `jobpipe/runtime/`
- the first transport-facing CLIs are:
  - `jobpipe import-reactive-resume`
  - `jobpipe export-reactive-resume-plan`
  - `jobpipe record-reactive-resume-document`

These stay deliberately narrow: one evidence-backed tailoring-plan export and one rendered-document handshake back into canonical document metadata.

---

## Recommended code placement in `JobPipe`

When implemented, this seam should land as:

- model shapes in `jobpipe/model/`
- candidate-state import helpers in `jobpipe/runtime/`
- tailoring logic in `jobpipe/decision/`
- export/render projection helpers in `jobpipe/projections/`

It should not start by creating a second candidate truth bundle in `jobpipe/core/`.

---

## Relationship to current local prototype

The local prototype folder:

- `C:\Users\larsv\Jobpipe\prototype\Prototype - Tailoring and consolidated React Resume  CV +cover letter`

is relevant to this seam as research input.

What should be salvaged from that work is:

- tailoring flow ideas
- CV/cover-letter coordination ideas
- practical export expectations

What should not be imported blindly:

- any freeform rewrite path that bypasses candidate evidence units
- any editor-first truth model

---

## Resume Analysis finding

Reactive Resume now includes a built-in `Resume Analysis` feature in the builder sidebar.

What it currently does:

- sends the current `resume.data` JSON to the configured AI provider/model
- requests a structured general-purpose resume review
- persists the latest analysis per resume
- returns:
  - `overallScore`
  - `scorecard`
  - `strengths`
  - `suggestions`

What it does **not** do in this feature:

- it does not take a job description
- it does not perform candidate-specific hiring-side selection logic
- it does not own canonical tailoring semantics
- it is not the same feature as job-specific resume tailoring

Practical implication for JobPipe:

- this feature is potentially useful as a **post-tailoring QA/review layer**
- it is **not** a good canonical source for tailoring decisions
- it may be useful to validate:
  - clarity
  - ATS hygiene
  - impact wording
  - structure/completeness
- it should not replace:
  - evidence selection
  - claim targeting
  - section ordering strategy
  - narrative constraints

Working recommendation:

- treat Reactive Resume `Resume Analysis` as an optional downstream critique surface
- only use it after JobPipe has already produced:
  - `tailored_cv_plan`
  - `tailored_cv_projection`
- if reused, treat its outputs as:
  - review hints
  - quality warnings
  - polish suggestions

not as canonical generation truth

---

## Relationship to current specs

This seam depends directly on:

- `specs/canonical-data-model.md`
- `specs/controlled-cv-tailoring.md`
- `specs/candidate-narrative-model.md`
- `specs/job-claims-model.md`
- `specs/hiring-side-selection-model.md`

This is an integration seam over those models, not a replacement for them.

---

## Success criteria

This seam is successful if:

- JobPipe can produce a structured, evidence-backed tailoring plan
- Reactive Resume can be used as an optional editing/rendering surface
- final rendered CV artifacts can be traced back to JobPipe's selected evidence and targeting logic
- the seam remains thin enough that Reactive Resume can still be treated as an external dependency

It fails if:

- candidate truth becomes split across editor state and JobPipe state without a clear canonical owner
- JobPipe starts depending on deep Reactive Resume internals
- freeform resume rewriting replaces evidence-backed tailoring
