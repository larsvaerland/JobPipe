# Decision Model

## Objective

The decision model exists to:

- eliminate obvious noise cheaply
- reserve deeper evaluation for plausible jobs
- produce final decisions that can be inspected and tuned
- move toward evidence-backed, hiring-aware decision support

## Current stage order

The current configured stage order is:

1. `triage`
2. `parse`
3. `profile_match`
4. `pivot`
5. `moderate`
6. `application_pack`

`reverse_triage` remains available in the codebase but is currently disabled in `configs/pipeline.v1.yaml`.

## Current cheap filters

Before the deeper model steps matter, JobPipe applies several low-cost filters:

- geo filter
- hard-no title regex
- semantic filter
- safety overrides around target titles and positive signals

These are intentionally earlier than the heavier scoring stages.

## Current decision tiers

Current thresholds from `configs/pipeline.v1.yaml`:

| Decision | Threshold |
|---|---|
| `APPLY_STRONGLY` | `fit_score >= 78` |
| `APPLY` | `fit_score >= 67` |
| `REVIEW_HIGH` | `fit_score >= 58` |
| `REVIEW_LOW` | `fit_score >= 30` |
| `SKIP` | `fit_score < 30` or earlier filter stop |

Other important thresholds:

- semantic filter threshold: `0.30`
- hard review floor: `review_min_fit = 30`
- review-high split: `review_high_min_fit = 58`

## Interpretation

The important point is not that the current numbers are universally correct.

The point is that:

- the thresholds are explicit
- they are inspectable
- they can be tuned against observed outcomes

## Near-term direction

The next planning direction is to evolve from a mostly score-centric pipeline into a more explicit decision model built around:

- job claims
- hiring-side selection signals
- candidate evidence units
- narrative assessments
- watchlist-driven change review

Conceptually, the system should become stronger across four questions:

- `can_do`
- `can_get`
- `should_want`
- `can_explain`

The current pipeline already covers parts of this, but the next layers should make those dimensions more explicit.

## First public decision slice

The first stable public decision slice now lives under:

- `jobpipe/decision/`

Current public objects:

- `job_claims`
- `selection_signals`
- `selection_assessment`
- `decision_table`
- `candidate_evidence_units`
- `selected_evidence_units`
- `candidate_narrative_profile`
- `narrative_fragments`
- `job_narrative_assessment`
- `watchlists`
- `change_events`
- `candidate_calibration_summary`
- `job_calibration_assessment`

Current implementation scope:

- deterministic claim derivation from canonical job/evaluation fields
- deterministic hiring-aware selection assessment from current fit, pivot, blocker, and triage state
- candidate-sensitive selection adjustments from the canonical candidate profile, including:
  - primary/secondary target-role alignment
  - explicit hard-no overlap
  - negative-keyword overlap
  - leadership/scope mismatch for narrower or earlier-career profiles
- deterministic decision-table derivation across:
  - `can_do`
  - `can_get`
  - `should_want`
  - `can_explain`
  - `act_now`
- deterministic candidate evidence-unit derivation from current resume/profile context
- deterministic evidence selection for one target job
- deterministic candidate narrative-profile derivation from current profile pack and evidence context
- deterministic per-job narrative assessment and motivation brief generation
- deterministic watchlist derivation from the current job and decision state
- deterministic change-event derivation from prior run history and current application state where available
- deterministic candidate-local calibration summary derivation from feedback events, application outcomes, and explicit settings
- deterministic per-job calibration assessment from local feedback and outcome patterns
- projection of that decision context into the dashboard payload
- persistence of job claims, selection signals, selection assessments, and decision tables as first-class DB rows via `sync_evaluations`
- persistence of watchlists and change events as first-class DB rows via `sync_evaluations`
- consumption of selected evidence units in `application_pack`
- consumption of narrative profile, fragments, and motivation brief in `application_pack`
- persistence of candidate evidence units, narrative profiles, narrative fragments, narrative evidence links, and per-job narrative assessments as first-class DB rows via `application_pack`

This is intentionally a narrow first slice.

It does **not** yet mean:

- the current stages have been replaced
- LLM-backed claim extraction is complete
- the current deterministic table is the final policy model
- controlled tailoring is fully moved off raw resume context
- narrative calibration exists beyond deterministic heuristics
- learned calibration settings are updated automatically

Calibration remains intentionally different:

- the calibration storage substrate already exists in the primary DB
- calibration summaries and per-job calibration assessments are still derived local interpretations, not separately persisted learned-state rows

It does mean the repo now has stable public decision objects and a first-class persisted decision substrate instead of hiding the whole decision layer inside `stages/`, projections, and prompt output.

## Reviewability

Every job should leave behind enough state to understand:

- which filter or stage stopped it
- what the fit and pivot outputs were
- why the final decision tier was assigned
- which claims or selection signals mattered most

This is why JobPipe favors deterministic moderation after model-assisted interpretation.

## Where to change it

Edit:

- `configs/pipeline.v1.yaml`

Then validate with:

- targeted tests where available
- `python compile_check.py`
- `jobpipe run --dry-run`
