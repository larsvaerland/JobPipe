# Capability Gap Analysis

## Purpose

This spec defines how JobPipe should help a candidate decide which missing capabilities are actually worth addressing.

The problem is not just "what skills are mentioned in job ads?" The useful question is:

**Which missing capabilities repeatedly block the candidate from jobs they could otherwise realistically win?**

That makes this a product extension of JobPipe's core thesis:

- find winnable opportunities
- explain why they are winnable or not
- identify the smallest, highest-leverage improvements that would expand the candidate's opportunity set

This is directly relevant to decisions such as:

- whether to take a course or certification
- whether to build portfolio evidence in a certain area
- whether to shift target roles
- whether a long-term investment like an executive program is market-aligned

---

## Product question

JobPipe should eventually answer:

1. Which gaps are repeatedly blocking me from otherwise strong roles?
2. Which gaps are only noisy wishlist items and not worth optimizing for?
3. If I invest in one capability next, which one unlocks the most realistic opportunities?
4. Did a past investment in education or experience appear to improve my competitiveness?

The system should not pretend to know whether any education decision was "correct" in the abstract. It should answer the narrower, more defensible question:

**Did this capability investment improve competitiveness for the roles the candidate is actually closest to winning?**

---

## Non-goals

This feature is not:

- a generic course recommender
- a resume keyword optimizer
- a labor-market forecasting engine
- an LLM-only opinion generator

It should not recommend learning based on raw keyword frequency alone.

---

## Core decision model

Capability-gap analysis should focus on jobs in three buckets:

1. **winnable now**
   Strong enough fit that no major intervention is needed.
2. **adjacent but blocked**
   Roles that are close enough that one or two meaningful gaps are stopping the recommendation.
3. **not worth optimizing for**
   Roles that are too far from the candidate's profile, wrong domain, wrong seniority, or otherwise poor investments.

The highest-value analysis sits in bucket 2.

### Good recommendation rule

JobPipe should only recommend addressing a gap when all of the following are true:

- the candidate is otherwise a plausible match
- the gap appears repeatedly across desirable roles
- the gap is material, not incidental
- closing the gap would likely unlock a meaningful set of opportunities

This is the difference between:

- "many ads mention this keyword"
- and "this is the highest-ROI capability gap in your current market"

---

## Inputs from existing JobPipe data

The current product already has enough data to build a first useful version.

Relevant existing inputs:

- `job_evaluations`
  - `fit_score`
  - `pivot_score`
  - `final_decision`
  - `recommendation_reason`
  - `raw_match_json`
  - `raw_pivot_json`
  - `raw_moderator_json`
- `job_run_events`
  - repeated observations across runs
- `jobs`
  - canonical title, employer, description, metadata
- `candidate_profiles`
  - candidate evidence, stated direction, target roles, negative signals
- `application_events` / `application_summary`
  - downstream outcome feedback over time

The first version should rely heavily on:

- gaps extracted in `raw_match_json`
- blockers or risk signals from `raw_pivot_json`
- recommendation context from `recommendation_reason`

That keeps the first release grounded in what the pipeline already computes.

---

## New conceptual model

JobPipe needs a normalized concept of a "capability gap."

### Capability gap

A capability gap is a missing or weak capability that matters for a set of otherwise relevant jobs.

Examples:

- B2B SaaS commercialization
- procurement and public-sector tendering
- financial modeling
- product analytics
- formal people leadership
- enterprise architecture
- a specific certification
- stronger portfolio proof in a domain

This should not be limited to hard skills. It can include:

- domain knowledge
- tooling
- operating experience
- credential/certification
- evidence/proof gaps
- seniority/scope gaps

### Gap evidence

Each inferred gap should keep supporting evidence:

- jobs where it appeared
- how often it appeared
- whether it was a soft gap or hard blocker
- which source text or stage output supports it
- how close the candidate otherwise was to a recommendation

---

## Recommended scoring dimensions

Each gap should be scored along these dimensions:

### 1. Frequency

How often does this gap appear across adjacent-but-blocked roles?

### 2. Severity

How much does the gap appear to matter?

Suggested levels:

- `nice_to_have`
- `meaningful_gap`
- `material_blocker`

### 3. Unlock potential

If this gap were reduced, how many additional strong or near-strong opportunities would likely open up?

### 4. Opportunity quality

Are the blocked roles actually worth targeting?

A recurring gap in low-quality or weak-fit roles should be deprioritized.

### 5. Time-to-close

Estimated effort to close:

- low
- medium
- high

This is heuristic, but still useful for ranking.

### 6. Confidence

How reliable is the inference?

Confidence should rise when:

- the same gap shows up repeatedly
- it appears in otherwise strong roles
- it aligns across multiple stage outputs
- it matches explicit job requirements rather than fuzzy inferred language

---

## First product output

The first useful version should be a report, not a full UI system.

### Output: Capability Gap Report

For one candidate, the report should produce:

1. **Top high-leverage gaps**
   Gaps worth addressing now.
2. **Monitor-only gaps**
   Repeated signals that are too weak or noisy to justify action yet.
3. **Ignore gaps**
   Signals associated mostly with poor-fit or low-value roles.
4. **Evidence summary**
   The jobs and reasons behind each recommendation.

### Example output shape

```text
Gap: Product analytics depth
Priority: close_now
Confidence: high
Why:
- Appears in 14 otherwise plausible roles
- Often the main difference between REVIEW_HIGH and APPLY
- Mostly present in attractive digital product roles
Suggested action:
- strengthen evidence through one portfolio project and one measurable case
```

### Recommended buckets

- `close_now`
- `monitor`
- `ignore`
- `already_strong_enough`

---

## Data model additions

The first implementation can compute reports on the fly. But the stable model should support persisted gap evidence.

### Proposed tables

#### `capability_gaps`

One row per normalized gap concept.

Fields:

- `gap_id`
- `candidate_id`
- `gap_key`
- `label`
- `gap_type`
- `description`
- `created_at`
- `updated_at`

#### `gap_evidence`

Append-only evidence rows tying a gap to a job evaluation.

Fields:

- `gap_evidence_id`
- `candidate_id`
- `gap_id`
- `job_id`
- `run_id`
- `severity`
- `evidence_source`
- `evidence_text`
- `fit_score`
- `pivot_score`
- `final_decision`
- `created_at`

#### `gap_assessments`

Latest rolled-up assessment per candidate + gap.

Fields:

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

---

## Extraction strategy

The first version should not attempt perfect ontology mapping.

Use a pragmatic pipeline:

1. collect gap candidates from:
   - `raw_match_json.gaps`
   - `raw_match_json.hard_blockers`
   - `raw_pivot_json.potential_risk`
   - explicit requirement phrases in the job description where relevant
2. normalize obvious duplicates
3. cluster into a smaller set of candidate gap concepts
4. score and rank

The normalization should start simple:

- lowercase normalization
- singular/plural cleanup
- obvious synonym merging
- optional manual alias rules in config

Do not introduce embeddings or a vector database just for this first layer.

---

## Candidate investment decisions

This feature should eventually help with investment decisions such as:

- executive education
- certifications
- targeted projects
- writing samples / portfolio work
- domain immersion

The output should not say:

- "take this course"

It should say:

- "this capability appears to be the highest-leverage blocker in your current market"

That leaves the education choice to the candidate while making the market signal much sharper.

---

## BI / executive education example

For a case like executive management studies, the system should not attempt a binary judgment.

Instead it should ask:

- did this investment improve competitiveness for the roles the candidate is nearest to winning?
- does the market repeatedly reward this capability in strong-fit roles?
- does it unlock adjacent role families that would otherwise remain weak?
- or is it mostly strengthening a signal that hiring markets are not pricing highly for this candidate's best opportunities?

That is the level at which JobPipe can be useful without pretending to solve career strategy in the abstract.

---

## UI implications

This should not start as a complex dashboard feature.

Recommended progression:

1. offline report
2. dashboard summary card
3. drill-down evidence view
4. candidate investment tracking over time

The dashboard should only surface high-signal results:

- top gaps worth addressing
- why they matter
- how many plausible roles they block

Detailed evidence can remain in a deeper inspection view or exported report.

---

## First implementation slice

The first useful implementation should:

1. define a normalized gap object in code
2. extract repeated gap candidates from current evaluation outputs
3. score them using simple heuristics
4. emit a candidate-specific report
5. validate whether the report is actually useful in real review sessions

### Acceptance criteria for the first slice

- works from current primary DB data
- produces a ranked gap report for one candidate
- distinguishes `close_now`, `monitor`, and `ignore`
- provides evidence per recommendation
- does not require a new GUI to test usefulness

---

## Relationship to the product vision

This feature is not a side quest. It is a direct extension of the product thesis.

If JobPipe's job is to help the candidate discover the jobs they are genuinely competitive for, then the next natural step is:

**show which missing capabilities most limit that competitiveness, and which are actually worth addressing.**
