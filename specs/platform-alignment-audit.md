# Platform Alignment Audit

**Date:** 2026-04-17

This audit reviews JobPipe against the current thesis:

**JobPipe should be the local-first data-and-reasoning layer for job search.**

That means:

- data is the product
- connectors are adapters
- GUIs and external tools are projections
- canonical state should outlive code changes, tool changes, and provider changes

---

## Overall assessment

The project is directionally strong.

The canonical state model is now materially better than the public-release version:

- primary DB exists
- candidate state is explicit
- evaluations and follow-up live in the DB
- suggestion leads, generated documents, feedback, and gaps now have durable storage

That is the right foundation for a platform-through-data model.

The main remaining problems are now:

1. some planning docs still lag the actual repo state
2. connector quality and source-specific behavior still need more hardening
3. the public onboarding/default path still needs stronger quality control
4. the next real risk is overfitting to the current reference candidate rather than missing core product layers

The project is no longer blocked by missing product direction. It is blocked by consistency.

---

## What already aligns well

### 1. Canonical state is becoming real

Strong alignment:

- `jobpipe.sqlite` is now the canonical runtime state layer
- candidate-scoped data exists
- follow-up and feedback state are no longer just sidecars
- gap analysis and calibration have durable storage

This is the strongest part of the current architecture.

### 2. Product thesis is sharper

Strong alignment:

- focus on winnable opportunities
- non-obvious role discovery
- candidate-specific reasoning
- local-first privacy

The newer planning docs are stronger than the older “pipeline utility” framing.

### 3. Connectors are conceptually subordinate

Partial but real alignment:

- the docs increasingly describe connectors as intake layers
- the platform logic is moving into structured domain state

This is correct and should be preserved.

---

## Main misalignments

### 1. Connector boundaries are still too thick

Affected:

- `jobpipe/cli/scan_gmail.py`
- NAV/App Script mental model

Problem:

- provider access, parsing, classification, matching, and state writes are still mixed together in large CLI files
- this does not fit the intended adapter model

Impact:

- provider migration is harder than it should be
- testing is harder than it should be
- the code still reflects service-specific workflows instead of normalized message/source models

### 2. Planning/docs are still ahead of some runtime boundaries

Affected:

- `README.md`
- `PRODUCT_VISION.md`
- `docs/architecture.md`
- connector/runtime implementation details

Problem:

- the docs now correctly describe JobPipe as a data-and-reasoning layer
- some runtime boundaries still lag that framing

Impact:

- contributors can still fall back into connector-first thinking if the next code refactors do not follow the docs
- the architectural story is now clearer than the implementation in a few key places

### 3. Public quality is still under-audited across candidate shapes

Affected:

- onboarding defaults
- threshold tuning
- evidence and narrative presentation
- dashboard trustworthiness

Impact:

- the public loop may still be too shaped by the current reference candidate
- quality problems can hide behind a working local setup
- the next improvements should come from structured audit findings rather than intuition alone

### 4. Operator surface is still more Windows-shaped than the core architecture

Affected:

- some lower-level CLI help text
- provider-specific module docs
- package metadata before cleanup

Problem:

- the core Python system is portable
- the canonical operator interface should be the Python CLI, with OS-specific wrappers secondary

Impact:

- if the help output and packaging metadata lag the architecture, contributors will keep treating the wrapper as the product interface

---

## Recommended cleanup order

### Phase A: Align docs and operator framing

Done in this pass.

1. make `MASTER_PLAN.md` the planning reference
2. update `README.md` and `docs/architecture.md` to emphasize:
   - data as product
   - adapters/projections
   - DB-first state
3. make `ROADMAP.md` a short execution view only

### Phase B: Make direct CLIs obey the data-root model

Done in this pass for the main runner, intake, sync, and export surfaces.

1. replace repo-local defaults in direct CLIs with path helpers
2. default artifacts/exports/state files to the path policy already defined in `jobpipe/core/paths.py`
3. keep repo-local fallback only as developer convenience

### Phase C: Make the canonical CLI and package metadata match the architecture

Done in this pass.

1. introduce a canonical cross-platform `jobpipe` CLI
2. make `go.ps1` a thin Windows wrapper over the canonical CLI
3. update docs to teach the canonical CLI first

### Phase D: Refactor connector boundaries

Do next.

1. separate provider access from normalization
2. move Gmail toward a provider-neutral mail model
3. move NAV toward a proper connector module instead of operational dependence on Apps Script mental models

### Phase E: Run the public hardening audit

Do after the above.

1. freeze one live audit corpus
2. create synthetic persona packs
3. run the same public loop for each persona
4. compare decision quality, explanation quality, and dashboard quality
5. turn findings into a hardening list

This is the next high-leverage quality layer.

---

## Practical conclusion

JobPipe is already close to the right architecture.

The project does **not** need a conceptual rewrite.

It needs:

- documentation cleanup
- operator-surface cleanup
- connector-boundary cleanup
- public hardening through structured persona audits

That is a manageable path, and it fits the current branch work.
