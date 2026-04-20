# Persona Audit Findings — 2026-04-17

**Audit root:** `C:\Users\larsv\JobpipeData\audit\public_oss_persona_audit_20260417_no_score_reason_v1`

**Related plan/specs:**

- `MASTER_PLAN.md`
- `ROADMAP.md`
- `specs/persona-audit-plan.md`

## Scope

This document captures the concrete hardening findings from the first runnable public persona matrix.

It is not a generic audit note.

It is the active public hardening bug list derived from:

- the frozen baseline summary
- the matrix summary
- the exported persona dashboards
- direct verification of the isolated persona DBs and current audit runner behavior

## Baseline result

The first runnable matrix is now operating on a valid preserved public state surface:

- `catalog_jobs`: `9815`
- `replay_only_jobs`: `89`
- `full_corpus_jobs`: `9904`
- `rerunnable_evaluations`: `871`
- `audit_slice_jobs`: `6`

This means the previous reproducibility blocker is closed.

The current findings below are the next public hardening issues.

## Resolution update

The first hardening item from the initial matrix is now closed.

Resolved on rerun:

- persona dashboard app-state leakage
- explicit no-score reasons for evaluated jobs without fit/pivot scores

Resolution evidence:

- fixed by explicitly passing the frozen empty audit app-state file through the persona-audit dashboard export path
- rerun audit root: `C:\Users\larsv\JobpipeData\audit\public_oss_persona_audit_20260417_app_state_fix_v1`
- all persona summaries now report:
  - `tracked_applications: 0`
  - `application_status_counts: {}`

That item remains in this file as an audit-history finding, but it is no longer an active next bug.

## Confirmed findings

### 1. Persona dashboard app-state leakage

**Severity:** high

**Status:** resolved

**What is happening**

The persona dashboards are being exported without an explicit `--state` path.

That means `jobpipe.cli.export_dashboard` falls back to the default global sidecar app state instead of staying isolated to the persona DB.

In the current matrix run, every persona dashboard reported the same:

- `tracked_applications: 4`
- `application_status_counts: applied=2, interview=1, rejected=1`

But the isolated persona DBs actually contain:

- `application_events: 0`
- `application_summary: 0`

for all four personas.

**Why this matters**

- audit dashboards are not fully isolated
- dashboard trust signals are contaminated
- app-status-related comparisons across personas are not reliable

**Public hardening action**

- make persona-audit dashboard export explicitly use the empty audit app-state file
- prevent default global sidecar fallback in isolated audit runs
- rerun the matrix after the fix and treat current application-status findings as invalidated

### 2. Score completeness is still weak on some evaluated jobs

**Severity:** high

**Status:** resolved

**What was happening**

Some evaluated jobs still land in the matrix summaries with `fit_score` and `pivot_score` both `null`.

Confirmed examples from the current matrix:

- `c2194490-36e0-4193-89df-67a7b7b5b64d` — `Staff Software Engineer (Tech Lead)`  
  null scores across all four personas
- `f11f16a4-14d2-4fd2-8956-2052125d4237` — `Head of Enterprise Architecture`  
  null scores in multiple persona summaries

**Why this mattered**

- skip/review outcomes are harder to inspect and compare
- dashboard explanations become less trustworthy
- audit output is weaker exactly where borderline or difficult roles should be most legible

**Resolution evidence**

- fixed by deriving and exporting an explicit structured `no_score_reason` / `no_score_reason_label`
- rerun audit root: `C:\Users\larsv\JobpipeData\audit\public_oss_persona_audit_20260417_no_score_reason_v1`
- top-skip rows in the matrix summary now preserve:
  - `no_score_reason`
  - `no_score_reason_label`
- exported persona dashboards now embed and render the same explanation through the risk surface

This item remains in the file as audit history, but it is no longer an active next bug.

### 3. Persona differentiation is still too weak between some non-reference shapes

**Severity:** medium-high

**What is happening**

The `persona_b_specialist` and `persona_c_public_transition` runs converged too strongly on the same decision shape:

- both produced `3 review / 3 skip / 0 apply`
- they shared `2` of `3` top review jobs
- they shared `2` of `3` top skip jobs

The `persona_d_early_adjacent` run also overlapped heavily with those skip sets.

**Why this matters**

- candidate-specific constraints are under-expressed
- materially different persona shapes can collapse into the same review pile
- the public single-user onboarding path is at risk of feeling “close enough to the reference user” rather than truly candidate-specific

**Public hardening action**

- strengthen persona-sensitive negative constraints
- sharpen role-family and continuity penalties where the profile does not support broad leadership/product placement
- make constrained-fit cases easier to distinguish from adjacent-but-plausible cases

### 4. Product-leadership inertia is still too strong

**Severity:** medium-high

**What is happening**

The same product-leadership roles remain highly ranked across multiple non-reference personas:

- `Produktleder` (`Avinor AS`)
- `Produktleder til team Beredskap og krisehåndtering` (`Politiets IT-enhet`)
- `Produktleder for sentrale backend‑tjenester` (`Entur`)

For the reference persona this is expected.

For the specialist, public-transition, and early-adjacent personas, these roles still dominate review surfaces even when the candidate shape is materially different.

**Why this matters**

- management-title inflation remains a live risk
- role-family continuity is not yet pulling hard enough against attractive leadership labels
- public users may be nudged toward plausible-sounding but weaker process-fit roles

**Public hardening action**

- tighten leadership evidence requirements
- distinguish management/product/platform leadership more explicitly
- require stronger matching signals before leadership-titled roles stay near the top for non-reference personas

**Implementation note — 2026-04-20**

The first bounded hardening slice for findings `3` and `4` is now in the canonical decision layer:

- candidate-profile-aware selection signals now account for:
  - primary and secondary target-role alignment
  - explicit candidate hard-no overlap
  - negative-keyword overlap
  - leadership/scope mismatch for narrower specialist or earlier-career profiles
- the canonical decision context now consumes those signals in:
  - `sync_evaluations`
  - dashboard projection fallback reads
  - controlled Reactive Resume CV plan/projection generation

This is intentionally not marked resolved yet. The matrix needs a fresh rerun before the findings can be closed.

**Rerun evidence — 2026-04-20**

Rerun audit root:

- `C:\Users\larsv\JobpipeData\audit\public_oss_persona_audit_20260420_candidate_alignment_v1`

Observed movement:

- `persona_b_specialist`
  - now `0 apply / 2 review / 4 skip`
  - `Produktleder til team Beredskap og krisehåndtering` -> `SKIP`
  - `Produktleder for sentrale backend‑tjenester` -> `SKIP`
  - `Produktleder` -> `REVIEW_LOW`
- `persona_d_early_adjacent`
  - now `0 apply / 1 review / 5 skip`
  - only `Produktleder` remains in review
  - the other two product-leadership roles now fall to `SKIP`

Interpretation:

- candidate-shape differentiation is materially better for the specialist and early-adjacent personas
- product-leadership inertia is materially reduced for those two non-reference shapes
- the finding is therefore **improving but not fully closed**

Remaining issue:

- `persona_c_public_transition` still keeps all three product-leadership jobs in the review surface
- public-sector transition logic is still not expressing enough distinction between:
  - plausible governance/service-management/public-transition roles
  - generic attractive product-leadership titles that remain too sticky

Next hardening move:

- tighten public-sector / governance directionality in the candidate-sensitive selection layer
- add stronger penalties when leadership/product titles are outside declared target-role anchors even if the raw fit language still looks attractive

**Latest rerun evidence — 2026-04-20**

Latest audit root:

- `C:\Users\larsv\JobpipeData\audit\public_oss_persona_audit_20260420_165145`

Observed movement on the final validated Sprint 3 code state:

- `persona_b_specialist`
  - `0 apply / 3 review / 3 skip`
  - `Produktleder til team Beredskap og krisehåndtering` now falls to `SKIP`
  - `Produktleder` and `Produktleder for sentrale backend‑tjenester` remain `REVIEW_LOW`
- `persona_c_public_transition`
  - `0 apply / 4 review / 2 skip`
  - all three product-leadership roles still remain `REVIEW_LOW`
  - `Head of Enterprise Architecture` also remains in `REVIEW_LOW`
- `persona_d_early_adjacent`
  - `0 apply / 2 review / 4 skip`
  - `Produktleder` remains `REVIEW_LOW`
  - `Produktleder for sentrale backend‑tjenester` and `Produktleder til team Beredskap og krisehåndtering` both stay `SKIP`

Interpretation:

- the bounded Sprint 3 slice is real and visible in the matrix:
  - the reference persona still keeps the three product-leadership roles in the actionable surface, which is the intended contrast
  - the specialist and early-adjacent personas now show clearer suppression of some off-anchor product-leadership roles
- product-leadership inertia is therefore **reduced but not resolved**
- the public-transition persona remains the main unresolved case because all three product-leadership roles still stay in review

Status update:

- finding `4` remains open
- the next clean hardening move is narrower:
  - keep pushing public-sector/governance directionality and target-role-anchor penalties
  - do not reopen the already-landed bounded Sprint 3 slice

### 5. Monitoring is still too noisy relative to audit slice size

**Severity:** medium

**What is happening**

The matrix slice contains only `6` jobs, but watchlist and change-event volume remains comparatively high:

- reference persona: `watchlist_count=14`, `change_event_count=6`
- specialist persona: `watchlist_count=9`, `change_event_count=6`
- public-transition persona: `watchlist_count=13`, `change_event_count=6`
- early-adjacent persona: `watchlist_count=6`, `change_event_count=6`

Some of this is legitimate multi-watchlist behavior, but the current ratio still suggests monitoring surfaces are denser than they need to be for candidate-facing review.

**Why this matters**

- dashboard monitoring can feel busier than the underlying work really is
- high-materiality events are harder to distinguish from background monitoring state
- public trust suffers when the monitoring layer looks louder than the decision layer

**Public hardening action**

- deduplicate or aggregate watchlists per job where possible
- make high-materiality change signals more visually distinct from background monitoring
- reduce candidate-facing monitoring noise before adding more dashboard complexity

**Latest rerun evidence — 2026-04-20**

Latest audit root:

- `C:\Users\larsv\JobpipeData\audit\public_oss_persona_audit_20260420_165145`

Observed monitoring summary on the final validated Sprint 3 code state:

- reference persona:
  - `watchlist_count=16`
  - `watchlist_count_by_materiality: high=2, medium=6, low=8`
  - `change_event_count=6`
- specialist persona:
  - `watchlist_count=10`
  - `watchlist_count_by_materiality: high=0, medium=6, low=4`
  - `change_event_count=6`
- public-transition persona:
  - `watchlist_count=15`
  - `watchlist_count_by_materiality: high=0, medium=6, low=9`
  - `change_event_count=6`
- early-adjacent persona:
  - `watchlist_count=8`
  - `watchlist_count_by_materiality: high=0, medium=4, low=4`
  - `change_event_count=6`

Interpretation:

- the new materiality split is still useful because background watches are now inspectable instead of one flat count
- but the final validated rerun shows that total watchlist density is still too high:
  - reference rises to `16`
  - public-transition rises to `15`
  - early-adjacent rises to `8`
- the compatibility-path fix kept dashboard summaries honest, but it did not close the underlying monitoring-noise issue
- finding `5` is therefore **still open and not yet materially improved overall**

Implementation note:

- a broader validation sweep after the Sprint 3 code landed exposed one dashboard fallback compatibility regression:
  - when persisted monitoring state was absent, the fallback payload could collapse actionable/review rows to `watchlist_count=0` if the sparse derived decision table returned `act_now=skip`
  - fixed on 2026-04-20 by making monitoring fallback prefer the stored `final_decision` bucket for watchlist derivation when the full persisted decision surface is unavailable
- that fix keeps repo-wide validation honest and preserves the intended monitoring summary in compatibility paths without widening the Sprint 3 scope

Status update:

- finding `5` remains open
- next hardening should focus on further per-job aggregation or demotion of medium-noise watches, not on reopening the current materiality model

## Active hardening order

The next public hardening order should be:

1. tighten candidate-shape differentiation and reduce product-leadership inertia
2. reduce monitoring/watchlist noise
3. rerun the persona matrix and convert the next findings pass into code fixes and dashboard polish

## Public/private boundary note

These findings are all public-OSS issues.

They do **not** require:

- multi-user login
- private workspace routing
- private-only evaluation infrastructure

The current correct scope remains:

- public OSS: single-user hardening, auditability, dashboard trust, onboarding defaults
- later private layer: deeper workflows, multi-user support if pursued, and broader operational controls
