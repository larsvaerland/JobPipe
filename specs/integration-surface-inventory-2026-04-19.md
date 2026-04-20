# Integration Surface Inventory

**Date:** 2026-04-19

This inventory captures the current visible integration surface in the canonical local repo:

- `C:\Users\larsv\Jobpipe`

The purpose is to separate:

1. integration that is already present in canonical JobPipe code
2. integration that exists only in prototypes or separate repos
3. integration work that exists in `agentic_jobpilot` but is not yet present here

This is an inventory only. It is not a migration plan by itself.

---

## Validation baseline

The repo validated cleanly before and after this inventory pass:

- `.\.venv\Scripts\python.exe compile_check.py`
- `.\.venv\Scripts\python.exe -m pytest tests -q`

---

## Current visible seams in `JobPipe`

### 1. `jobsync`

Current result:

- no explicit `jobsync` code seam was found in the canonical `JobPipe` package paths scanned:
  - `jobpipe/cli`
  - `jobpipe/projections`
  - `jobpipe/decision`
  - `jobpipe/runtime`
  - `docs`
  - `specs`
  - `tests`

That means:

- there is currently no visible first-class `jobsync` adapter or sync contract in the canonical local `JobPipe` codebase
- if integration work exists, it is not yet represented in the scanned canonical surfaces

### 2. `reactive-resume`

Current result:

- no explicit code seam was found in the canonical `JobPipe` package paths scanned
- the visible references are prototype/spec-level, not runtime adapter code

That means:

- `Reactive Resume` is currently a planning/prototype concern here, not a visible canonical runtime seam

---

## What does exist in canonical `JobPipe`

The strongest current candidate-facing integration substrate is internal, not sibling-repo based.

Visible first-class canonical layers already present:

- `jobpipe/decision`
  - job claims
  - hiring-side selection signals and assessments
  - decision tables
  - evidence units
  - candidate narrative profiles/fragments/assessments
  - watchlists and change events
  - local calibration summaries
- `jobpipe/projections/dashboard.py`
  - DB-backed dashboard projection over canonical state
- `jobpipe/runtime`
  - data-root and path policy

This means the current public repo is prepared for:

- stronger tailoring
- stronger narrative guidance
- stronger local calibration

without yet having explicit sibling-repo runtime seams checked into the canonical surfaces.

---

## Visible prototype-level integration signals

The main visible local signal for resume/letter integration is:

- `prototype/Prototype - Tailoring and consolidated React Resume  CV +cover letter`

This suggests real local exploration exists for:

- resume tailoring
- consolidated CV flow
- cover-letter generation
- likely interaction with Reactive Resume concepts

But today this is still:

- prototype input
- not canonical runtime integration

---

## What exists in `agentic_jobpilot` but not here

The separate local repo contains explicit integration-oriented code such as:

- `jobpipe/core/jobsync.py`
- `jobpipe/core/jobsync_authoring.py`
- `jobpipe/cli/sync_jobsync_jobs.py`
- `jobpipe/cli/sync_jobsync_status.py`
- `jobpipe/cli/dashboard_server.py`
- boundary objects such as:
  - `DecisionBrief`
  - `ArtifactPlan`
  - `ApplicationCaseProjection`

It also contains orchestration/readout surfaces around:

- apply-session manifests
- authoring briefs
- sync payloads
- review/promotion queues

Those surfaces are **not** currently visible in canonical local `JobPipe`.

---

## Practical interpretation

This repo is currently in a transitional state where:

- the internal decision substrate is strong and explicit
- the sibling integration substrate is either:
  - not yet moved into canonical code
  - or exists only in prototypes / separate repos / separate worktrees

So if we later move integration work from `agentic_jobpilot` into `JobPipe`, the correct question is not:

- "what already exists in JobPipe and just needs a small patch?"

The correct question is:

- "which thin sibling seams should be introduced into canonical JobPipe, and how should they sit on top of the already-canonical decision/projection model?"

---

## Immediate conclusion

As of this audit:

- canonical `JobPipe` does **not** yet expose a strong checked-in `jobsync` seam
- canonical `JobPipe` does **not** yet expose a strong checked-in `reactive-resume` seam
- the nearest visible bridge is the local prototype folder for tailoring and consolidated CV/cover-letter flow

That makes the next safe migration step:

1. define the intended thin seam explicitly
2. only then port bounded code into `JobPipe`

not the other way around.
