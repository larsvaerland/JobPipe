# Local Calibration and Learning

## Purpose

This spec defines how JobPipe should improve over time without creating a privacy trap.

The core rule is:

**learning is local by default, structured first, and opt-in before anything is shared.**

This follows directly from the product model:

- the product is the application of available data
- candidate state is a core asset
- connectors and dashboards are adapters
- privacy is a hard requirement, not a nice-to-have

---

## Product objective

JobPipe should become better at answering:

- which jobs are actually winnable for this candidate
- which recommendations were good or bad in practice
- which non-obvious role families repeatedly convert well
- which gaps are real blockers versus noisy requirements

The first useful learning layer is not a shared global model. It is a **candidate-specific calibration loop**.

---

## Design principles

1. Local-first by default.
2. Structured signals before raw text sharing.
3. Candidate feedback and outcome history are the primary learning inputs.
4. Deterministic state should remain queryable and inspectable.
5. Shared learning, if added later, must be explicit opt-in.
6. Raw resumes, emails, and freeform notes should not be pooled by default.

---

## Learning stack

JobPipe should treat learning as three separate layers.

### 1. Personal calibration

Local, candidate-specific adaptation based on:

- manual promotions/demotions
- applications
- interviews
- rejections
- accepted offers
- "good recommendation" / "bad recommendation" feedback
- repeated gap evidence

This should be the first and most important learning layer.

### 2. Shared structured learning

Only later, only opt-in, and only from minimized structured examples such as:

- normalized role families
- normalized gap tags
- coarse outcomes
- decision overrides
- confidence/error signals

This is not part of the first implementation slice.

### 3. General LLM interpretation

LLMs remain useful for:

- semantic parsing
- market translation
- gap extraction
- candidate-specific explanation

But they are not the long-term memory of the system.

---

## First implementation scope

The first slice should add storage and reporting primitives, not model training.

Specifically:

1. candidate feedback events
2. candidate calibration settings
3. persisted capability gaps
4. persisted gap evidence
5. persisted gap assessments

That creates the durable substrate needed for:

- local heuristics
- later report generation
- future small local models

---

## Candidate feedback

JobPipe needs an append-only record of how the candidate judged recommendations and what happened after acting on them.

### `candidate_feedback_events`

One row per feedback event.

Examples:

- manually promoted a job
- manually demoted a job
- marked recommendation as useful
- marked recommendation as misleading
- explicitly stated "good fit" / "bad fit"
- entered outcome that changes how earlier recommendations should be judged

Recommended fields:

- `feedback_event_id`
- `candidate_id`
- `job_id`
- `evaluation_id`
- `feedback_type`
- `feedback_value`
- `source`
- `notes`
- `evidence_json`
- `created_at`

Important rule:

This is append-only. JobPipe should learn from history, not just the latest overwrite.

### First operator surface

The first manual input path should stay explicit and small:

- `good_recommendation`
- `bad_recommendation`
- `promote`
- `demote`
- `good_fit`
- `bad_fit`

These signals are enough to start local calibration without inventing a larger feedback UI too early.

---

## Calibration settings

JobPipe also needs durable, candidate-specific tuning data that is more explicit than inferred feedback.

### `candidate_calibration_settings`

This stores stable local tuning values such as:

- confidence thresholds
- review/apply sensitivity
- source weighting
- role-family weighting
- tolerance for pivot roles
- gap severity heuristics
- hidden dashboard/UI preferences that matter to ranking logic

Recommended fields:

- `candidate_id`
- `scope`
- `setting_key`
- `value_json`
- `updated_at`

Examples:

- `scope=ranking`, `setting_key=apply_floor`
- `scope=sources`, `setting_key=linkedin_weight`
- `scope=gaps`, `setting_key=leadership_gap_penalty`

This is still local-first state, not a model.

---

## Capability gaps and evidence

This extends the capability-gap analysis work into persisted state.

### `capability_gaps`

One normalized gap concept per candidate.

Examples:

- `formal_people_leadership`
- `product_analytics_depth`
- `public_procurement_domain`

Recommended fields:

- `gap_id`
- `candidate_id`
- `gap_key`
- `label`
- `gap_type`
- `description`
- `created_at`
- `updated_at`

### `gap_evidence`

Append-only evidence tying a gap to a specific evaluation or job.

Recommended fields:

- `gap_evidence_id`
- `candidate_id`
- `gap_id`
- `job_id`
- `evaluation_id`
- `run_id`
- `severity`
- `evidence_source`
- `evidence_text`
- `evidence_json`
- `fit_score`
- `pivot_score`
- `final_decision`
- `created_at`

### `gap_assessments`

Rolled-up candidate-specific view of whether a gap is worth addressing.

Recommended fields:

- `candidate_id`
- `gap_id`
- `frequency_score`
- `severity_score`
- `unlock_score`
- `opportunity_quality_score`
- `time_to_close`
- `confidence_score`
- `priority`
- `assessment_json`
- `updated_at`

This table is mutable and represents the latest assessment.

---

## Privacy model

The default privacy posture is:

- all raw feedback stays local
- all calibration settings stay local
- all gap evidence stays local
- no sharing by default

If shared learning is added later, it should use a separate export path and a separate explicit consent model.

That later model should prefer:

- normalized features
- de-identified records
- derived labels

over raw freeform candidate data.

---

## Future model training

When JobPipe eventually adds actual learned models, the first useful model should be small and structured.

Recommended order:

1. heuristics on local structured feedback
2. lightweight supervised local model
3. optional shared structured reranker

Do not start with:

- LLM fine-tuning
- pooled raw candidate text
- broad "train on all users" behavior

The purpose of this spec is to create the data layer that makes future learning disciplined.

---

## Later bounded extension: shadow review loop

After the current public hardening phase, a reasonable next local-first extension is:

1. shadow-only comparison of candidate-local ranking variants
2. human review of promoted or downgraded cases
3. explicit outcome-backed promotion discipline

Important rule:

- this should be built on top of the existing primary DB and projection surfaces
- it should not introduce a second file-based canonical store
- it should not auto-apply ranking/config changes

This is the main salvageable learning idea from the separate `agentic_jobpilot` worktree, but it should be reimplemented here only when the public hardening roadmap makes room for it.

---

## First schema slice acceptance criteria

The first implementation slice is successful when:

- the primary DB can store candidate feedback events
- the primary DB can store candidate calibration settings
- the primary DB can store capability gaps, gap evidence, and gap assessments
- helpers exist for writing these records safely
- tests cover round-trip persistence of the new tables

Current first public implementation slice:

- deterministic local calibration summary now lives under `jobpipe/decision/`
- it derives candidate-local calibration patterns from:
  - feedback events
  - application outcomes
  - explicit calibration settings
- it derives a per-job calibration assessment for dashboard/projection use
- it does **not** yet mutate calibration settings automatically
- it does **not** yet train a local model

At that point, JobPipe has the necessary substrate for:

- local calibration
- capability-gap reporting
- future candidate-specific learning

without committing to a heavy ML architecture.
