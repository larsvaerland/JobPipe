# Hiring-Side Selection Model

## Purpose

This spec defines how JobPipe should account for the other side of the table without turning into recruiter software.

The candidate does not compete only against the job description. The candidate also competes against:

- recruiter bandwidth
- ATS-style structural filters
- title continuity bias
- domain familiarity bias
- risk aversion in ambiguous shortlists
- shallow first-pass screening

JobPipe should therefore maintain a **hiring-side selection layer** that estimates how a role is likely to be filtered and judged in practice.

This is a candidate advantage model, not a recruiter product.

---

## Core product question

For a given candidate and job, JobPipe should be able to answer:

1. Which parts of this job are likely to operate as real screening gates?
2. Where is the hiring side likely to be rigid versus flexible?
3. How much ambiguity is the candidate likely allowed before being screened out?
4. What evidence has to be visible early to survive first-pass review?
5. Is this role substantively plausible but procedurally hard to win?

This is the missing bridge between:

- "the candidate could probably do this"

and:

- "the candidate will actually survive the hiring process for this"

---

## Why this matters

Candidate-side tools often fail because they answer only:

- does this look like a fit?

They do not answer:

- what is the hiring system likely to reward or penalize?

That creates predictable errors:

- recommending roles that are genuinely adjacent but operationally hard to explain
- underestimating rigid filters around location, credentials, or title continuity
- generating good prose for applications that still hide the evidence recruiters need first
- confusing substantive fit with process survivability

JobPipe should reduce those failures.

---

## Non-goals

This feature is not trying to:

- read recruiters' minds with fake certainty
- build an ATS or recruiter CRM
- optimize for mass application volume
- reduce hiring to one hidden probability score
- replace outcome feedback from real applications

The model should represent uncertainty and allow revision from observed outcomes.

---

## Design principles

1. Stay candidate-first.
2. Separate job claims from selection logic.
3. Separate substantive fit from process risk.
4. Model uncertainty explicitly.
5. Prefer practical screening signals over theoretical psychologizing.
6. Use the selection layer to improve prioritization, explanation, and tailoring.

---

## Selection layers

JobPipe should model hiring-side reality in at least five layers.

### 1. Structural gates

These are the easiest ways to get screened out.

Examples:

- location / on-site requirement
- work authorization or language requirement
- hard credential or clearance requirement
- salary mismatch where visible
- explicit years-of-experience floor

These should be modeled separately from softer signals.

### 2. Screening signals

These are the things likely used in first-pass review.

Examples:

- title continuity
- domain continuity
- specific tool or stack familiarity
- regulated-sector experience
- leadership scope
- education prestige or required degree

These are often not absolute blockers, but they shape shortlist probability.

### 3. Ambiguity tolerance

Some roles tolerate adjacent candidates. Others do not.

Examples of lower tolerance:

- high-volume inbound roles
- narrow specialist roles
- regulated roles with explicit compliance burden
- roles where the ad emphasizes exact prior experience repeatedly

Examples of higher tolerance:

- transformation roles
- hybrid business/technology roles
- scale-up roles with broader ownership language
- jobs that emphasize outcomes over pedigree

This should be estimated, not asserted.

### 4. Process shape

The candidate is judged through a process, not one unified brain.

JobPipe should distinguish likely stages such as:

- ATS / application intake
- recruiter screen
- hiring-manager screen
- panel / case / technical review

Some weaknesses matter early. Some only matter later.

### 5. Evidence burden

For each job, JobPipe should estimate what evidence must be made explicit early.

Examples:

- quantified delivery evidence
- direct domain examples
- title translation
- stakeholder scope
- relocation clarity
- motivation/pivot explanation

This should directly influence CV tailoring and motivation briefs.

---

## Proposed data model

### `job_selection_signals`

One row per inferred hiring-side selection signal.

Recommended fields:

| Field | Purpose |
|---|---|
| `selection_signal_id` | Stable ID |
| `job_id` | Canonical job |
| `source_record_id` | Optional source-specific origin |
| `signal_type` | `structural_gate`, `screening_signal`, `ambiguity_tolerance`, `process_shape`, `evidence_burden` |
| `signal_label` | Human-readable label |
| `selection_stage` | `ats`, `recruiter_screen`, `hiring_manager`, `panel`, `overall` |
| `signal_strength` | `hard`, `strong`, `moderate`, `weak`, `speculative` |
| `normalized_key` | Stable internal concept key |
| `evidence_required` | What the candidate must show |
| `confidence_score` | Confidence in the inferred signal |
| `importance_score` | How much this likely affects selection |
| `source_basis` | `explicit_claim`, `repeated_claim`, `derived_pattern`, `market_heuristic` |
| `signal_json` | Structured extras |
| `created_at`, `updated_at` | Audit timestamps |

### `job_selection_assessments`

Candidate-specific assessment of hiring-side survivability.

Recommended fields:

| Field | Purpose |
|---|---|
| `candidate_id` | Candidate |
| `job_id` | Canonical job |
| `evaluation_id` | Evaluation context |
| `structural_pass` | Whether obvious gates are passed |
| `screenability_score` | Likely first-pass survivability |
| `title_continuity_score` | How legible the candidate looks from title history |
| `domain_continuity_score` | How legible the candidate looks from domain history |
| `ambiguity_risk_score` | Risk of being screened out due to ambiguity |
| `evidence_burden_score` | How much explicit evidence is needed |
| `selection_risk_level` | `low`, `medium`, `high`, `very_high` |
| `likely_rejection_vectors_json` | Structured reasons the candidate may be filtered out |
| `mitigation_moves_json` | Candidate-side mitigation moves |
| `assessment_reason` | Compact explanation |
| `updated_at` | Audit timestamp |

---

## Relationship to job claims

The selection model should be derived partly from `job_claims`, but it is not the same thing.

`job_claims` answers:

- what the ad says

The selection model answers:

- how those claims are likely to be used in screening and decision-making

That distinction matters because:

- some explicit claims are not heavily enforced
- some repeated soft claims signal real hiring rigidity
- some adjacent candidates are viable only if the right evidence is visible early

---

## Relationship to narrative

The selection layer should directly improve narrative use.

It should help answer:

- what must be explained explicitly
- what can be left implicit
- where a pivot story is necessary
- where a pivot story is too costly because the hiring side is too rigid

This strengthens `can_get` and `can_explain` together.

---

## How this should affect JobPipe outputs

### Triage

JobPipe should stop at "good fit" less often and ask:

- good fit for the work
- but what is the likely selection risk?

### Ranking

A role should be demoted when:

- the substantive fit is real
- but the evidence burden is too high for the likely process

A role should be promoted when:

- the fit is slightly adjacent
- but the process appears more tolerant and explainable

### Tailoring

Selection signals should influence:

- which evidence bullets are surfaced first
- whether title translation is needed
- whether domain transfer must be made explicit
- whether relocation / work-mode clarity should be front-loaded

### Watchlists and monitoring

Changes in selection logic should be treated as meaningful deltas.

Examples:

- degree requirement removed
- remote changed to hybrid
- scope broadened
- title softened
- repeated domain wording added

---

## First implementation slice

The first useful slice should stay narrow.

Deliver:

1. inference of a small set of high-value selection signals:
   - structural gates
   - title continuity pressure
   - domain rigidity
   - credential rigidity
   - ambiguity tolerance
   - evidence burden
2. one candidate-specific selection assessment per evaluated job
3. one inspection surface showing:
   - why the role looks winnable or fragile from the hiring side
4. CV/narrative guidance driven by the top 2-4 mitigation moves

Do not start by simulating full recruiter workflows.

---

## Success criteria

This layer is working if:

- JobPipe recommends fewer substantively-good but procedurally-unwinnable roles
- candidate-facing explanations become more realistic about screening risk
- tailored outputs expose the evidence most needed to survive first-pass review
- adjacent-role recommendations improve because the product distinguishes flexibility from rigidity
- outcome feedback can refine the selection heuristics over time

It fails if it becomes:

- fake recruiter mind-reading
- a hidden black-box score
- recruiter-product creep
- disconnected from actual application outcomes
