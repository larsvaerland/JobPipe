# Agentic Jobpilot Salvage Audit

**Date:** 2026-04-19

This audit reconciles salvageable work from the separate local repo:

- `C:\Users\larsv\agentic_jobpilot`

against the canonical public repo:

- `C:\Users\larsv\Jobpipe`

The purpose is not to justify cross-repo copying. The purpose is to decide what can be reused **without violating JobPipe's actual architecture**.

---

## Validation baseline

The canonical repo was validated before this audit:

- `.\.venv\Scripts\python.exe compile_check.py` -> `OK — 60 files parsed cleanly`
- `.\.venv\Scripts\python.exe -m pytest tests -q` -> `142 passed`

This matters because salvage work must fit a green baseline, not replace one.

---

## Canonical JobPipe boundary

After reading the canonical planning stack, the decisive rule is:

- `JobPipe` is DB-first and local-first
- connectors are adapters
- dashboards are projections
- canonical state must outlive tool changes
- stable code should grow into:
  - `jobpipe/runtime`
  - `jobpipe/model`
  - `jobpipe/decision`
  - `jobpipe/projections`
  - `jobpipe/connectors`
  - `jobpipe/compat`

That means work shaped around:

- `core/` as the long-term home
- JSON projection stores as parallel truth
- broad apply-session/dashboard-server orchestration
- sibling-repo seams as product boundaries

does **not** transfer directly.

---

## High-level conclusion

The separate `agentic_jobpilot` repo contains useful ideas, but much of it is shaped around the wrong architecture for this repo.

The best salvage categories are:

1. bounded spec inputs
2. future local calibration/shadow-eval ideas
3. future controlled tailoring research inputs
4. selected UI/readout ideas for the dashboard projection

The weakest salvage categories are:

1. direct code copies into `jobpipe/core`
2. primary runtime logic based on JSON side stores instead of the primary DB
3. broad stage chains that bypass the current claims/selection/decision-table model
4. any coupling to sibling repos or external dashboard-server/apply-session seams

---

## Salvage matrix

### 1. `jobpipe/core/profile_layer.py`

Status:

- do **not** migrate as code

Why:

- it creates a parallel candidate model outside the primary DB
- it overlaps with the canonical direction already defined in:
  - `specs/canonical-data-model.md`
  - `specs/controlled-cv-tailoring.md`
  - `specs/candidate-narrative-model.md`
- it is structured around a projection bundle, not canonical persisted candidate state

What to salvage:

- the insistence on structured evidence and narrative inputs
- the distinction between targeting/triage/authoring views

Where that belongs in JobPipe:

- future DB-backed candidate profile versions
- future evidence-unit and narrative-profile persistence

### 2. `jobpipe/core/triage_v3.py`
### 3. `jobpipe/stages/triage_features.py`
### 4. `jobpipe/stages/triage_decision_v3.py`
### 5. `jobpipe/stages/triage_ambiguity_v3.py`
### 6. `jobpipe/stages/advantage_assessment_v3.py`
### 7. `jobpipe/stages/narrative_strategy_v3.py`

Status:

- do **not** migrate as code

Why:

- the weighting/gating model is a different decision architecture from the current JobPipe thesis
- canonical JobPipe now treats the job as:
  - claims
  - selection signals
  - decision tables
  - evidence units
  - narrative assessments
- direct migration would create a second competing decision substrate

What to salvage:

- some audit questions
- some ambiguity-review ideas
- some operator-facing explanation patterns

Where that belongs in JobPipe:

- persona-audit fixtures
- future heuristics inside `jobpipe/decision/` only if they are re-expressed through the existing claims/selection model

### 8. `jobpipe/core/projection_store.py`

Status:

- do **not** migrate as code

Why:

- JobPipe's canonical state layer is the primary DB
- the projection-store work was created to compensate for a different repo architecture
- importing it here would reintroduce file-bucket truth beside the DB

What to salvage:

- the idea that projections should degrade gracefully when trace files go missing

Where that belongs in JobPipe:

- future projection helpers in `jobpipe/projections/`
- never as a second canonical store

### 9. `jobpipe/core/experiments.py`
### 10. `jobpipe/core/experiment_review_state.py`
### 11. `jobpipe/core/outcome_feedback.py`

Status:

- salvage as **future design input**, not direct code copy

Why:

- these modules contain the strongest portable idea set from the other repo:
  - local shadow eval
  - human adjudication loop
  - promotion queue
  - outcome-backed review
- but they are implemented against the wrong surrounding surfaces

What to salvage:

- shadow-only threshold/weight comparison
- human review of experiment candidates
- outcome-backed promotion discipline
- local review state before any live ranking change

Where that belongs in JobPipe:

- future local calibration extensions under:
  - `jobpipe/decision`
  - `jobpipe/projections`
- informed by `specs/local-calibration-learning.md`

### 12. Dashboard/apply-session/server work in `agentic_jobpilot`

Status:

- do **not** migrate

Why:

- this repo's canonical dashboard model is:
  - static export
  - DB-backed projection
  - thin CLI wrapper
- the other repo's work assumes a broader interactive orchestration surface and sibling integration model

What to salvage:

- some compact review/readout ideas only

Where that belongs in JobPipe:

- `jobpipe/projections/dashboard.py`
- `reports/dashboard_template.html`

### 13. Local prototype folder

Path:

- `C:\Users\larsv\Jobpipe\prototype\Prototype - Tailoring and consolidated React Resume  CV +cover letter`

Status:

- preserve as later research/prototype input

Why:

- this is in the correct repo tree already
- it is relevant to controlled tailoring
- but it should not become canonical runtime logic without first being mapped onto the evidence/narrative/tailoring model

Where that belongs in JobPipe:

- later bounded work under `specs/controlled-cv-tailoring.md`

---

## What is already present in JobPipe and should not be duplicated

JobPipe already has first-class canonical groundwork for:

- job claims
- hiring-side selection signals and assessments
- decision tables
- candidate evidence units
- candidate narrative profiles and fragments
- narrative evidence links
- job narrative assessments
- watchlists and change events
- candidate-local calibration summaries
- DB-backed dashboard projection

That means the salvage task is **not**:

- "port all the new architecture here"

It is:

- "protect the canonical architecture here and import only the parts that strengthen it"

---

## Immediate migration decision

The first bounded salvage move should be:

1. record the audit in this repo
2. feed the useful parts into the correct specs
3. defer code migration until a slice clearly fits:
   - `jobpipe/decision`
   - `jobpipe/projections`
   - or a future DB-backed candidate-state implementation

This is safer than importing transitional code that was built against a different system boundary.

---

## Recommended next migration order

### 1. Controlled tailoring research input

Use the local prototype folder as bounded input to the existing tailoring spec.

### 2. Local calibration extension

If public hardening later justifies it, import the **concept** of:

- shadow review queue
- human adjudication
- outcome-backed promotion discipline

but reimplement it on top of the current primary-DB and projection model.

### 3. Candidate-state evolution

Only after the DB-backed candidate profile model is ready should any part of the old `profile_layer` ideas be reconsidered.

---

## Explicit no-copy list

Do not directly copy from `agentic_jobpilot` into this repo:

- `jobpipe/core/profile_layer.py`
- `jobpipe/core/triage_v3.py`
- `jobpipe/core/projection_store.py`
- `jobpipe/stages/triage_features.py`
- `jobpipe/stages/triage_decision_v3.py`
- `jobpipe/stages/triage_ambiguity_v3.py`
- `jobpipe/stages/advantage_assessment_v3.py`
- `jobpipe/stages/narrative_strategy_v3.py`
- any `dashboard_server`-style orchestration seam
- any `jobsync`-oriented seam

Those can only return later if re-expressed inside JobPipe's real boundaries.

---

## Bottom line

The wrong repo work is **not wasted**, but most of it is valuable as:

- product clarification
- bounded spec input
- future migration hints

not as direct code to import.

That is the correct salvage result for this repository.
