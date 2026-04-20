# Repo Guidance for AI Agents

Mission: make the smallest safe change that solves the stated problem while preserving the current JobPipe direction.

## Canonical reading order

Before making non-trivial changes, read in this order:

1. `MASTER_PLAN.md`
2. `PRODUCT_VISION.md`
3. `ROADMAP.md`
4. `OSS_SCOPE.md`
5. `DEPENDENCY_POLICY.md`
6. relevant files in `docs/`
7. `specs/architecture-boundaries.md` when the change affects package layout, runtime boundaries, connector placement, or the OSS/private seam
8. relevant active specs in `specs/`

If `specs/current-change.md` is populated for the task, use it. If it is blank or stale, fall back to the canonical planning docs above.

## Directional rules

Preserve these truths:

- JobPipe is candidate-first.
- JobPipe is hiring-aware where that improves candidate outcomes.
- Data is the product.
- Connectors are adapters.
- Dashboards and external tools are projections.
- AI is a bounded interpretation layer, not the product itself.
- The public repo is being aligned as a genuine OSS-first framework/toolkit.
- A later private/commercial layer may build on top of this repo, but should not be prematurely assumed to exist here.

Do not casually drift into:

- recruiter-product scope
- ATS parity
- broad automation suites
- generic AI copilot behavior
- surface-area expansion without strengthening the core model
- open-core ambiguity inside the current public repo

## Change rules

- Prefer the smallest safe change.
- Keep diffs focused and reversible.
- Do not refactor unrelated code.
- Do not add dependencies unless necessary and justified.
- Do not change architecture casually; planning and runtime truth should move first.
- Do not move premium-only or sensitive business logic into the public repo without an explicit boundary decision.
- When planning docs drift, update overlapping docs together rather than leaving conflicting explanations.

## Scope guidance

Default to narrow changes, but do not artificially keep a planning-alignment pass tiny if the task explicitly asks for repo-wide planning coherence.

For larger passes:

- keep the change logically cohesive
- preserve one clear direction
- avoid mixing speculative architecture work into planning updates

## Protected areas

Be extra careful around:

- pipeline stages
- decision logic
- config keys
- runtime paths and output locations
- report/dashboard generation
- Gmail integration
- DB schema and state writes

## Validation rules

- Add or update a focused test when behavior changes.
- Run `python compile_check.py` for code changes.
- Prefer narrow validation over broad churn.
- For docs/planning changes, verify cross-doc consistency instead of pretending runtime tests are relevant.

## Escalate instead of guessing when

- business rules are unclear
- pipeline semantics would materially change
- model cost would materially change
- the change starts to imply recruiter-product or ATS scope
- the request would require choosing between multiple conflicting repo copies or worktrees
- the change would blur the OSS/public boundary and a later private/commercial layer
