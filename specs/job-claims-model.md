# Job Ad Claims Model

## Purpose

This spec defines how JobPipe should break down a job ad into a reliable, inspectable set of claims instead of treating the ad as one opaque blob.

The problem is not that job ads contain no information. The problem is that the information is mixed with:

- copied boilerplate
- HR wording
- inflated wishlists
- inconsistent titles
- soft preferences presented as hard requirements
- sector-specific shorthand that hides the actual selection logic

JobPipe should therefore treat a job ad as a **noisy bundle of claims**, not as one clean structured document.

---

## Core product question

For each ad, JobPipe should answer five separate questions:

1. What claims does the ad make?
2. How strong is each claim?
3. How reliable is each extracted claim?
4. Which claims are likely to matter in hiring?
5. How does each claim affect this candidate specifically?

The current parsing model is too shallow for this. `JobParse` can stay as a compact summary view, but the underlying interpretation model should be claim-based.

---

## Non-goals

This feature is not trying to:

- infer hidden truth with fake certainty
- fully replace human judgment
- turn every ad into one final score only
- treat all extracted text as equally important

The model should explicitly represent ambiguity, noise, and confidence.

---

## Design principles

1. Raw source text stays preserved.
2. Claims are extracted before candidate-specific scoring.
3. Normalization is separate from candidate impact.
4. Confidence is explicit.
5. Boilerplate and weak claims should be modeled, not silently discarded.
6. Candidate-specific impact should live in evaluation state, not in the canonical job itself.

---

## Proposed interpretation layers

### Layer 1: raw ad and source structure

Keep:

- raw title
- raw body text
- raw HTML when available
- source metadata
- section boundaries when detectable

This is the audit trail.

### Layer 2: extracted claims

Break the ad into atomic claims such as:

- role responsibility
- required experience
- preferred experience
- education requirement
- certification / clearance
- tooling / method
- domain requirement
- language requirement
- work-mode / location constraint
- reporting line / organizational context
- compensation / benefits
- culture / branding / fluff

This is the main new layer.

### Layer 3: normalized concepts

Map claims onto internal normalized concepts such as:

- role family
- seniority
- capability
- domain
- credential
- language
- location constraint
- regulatory context

This makes repeated reasoning across ads possible.

### Layer 4: candidate-specific impact

For each claim, later determine:

- strong overlap
- meaningful overlap
- neutral
- meaningful gap
- material blocker
- likely noise for this candidate

This belongs in evaluation state, not in canonical job state.

---

## Claim model

### `job_claims`

One row per extracted claim.

Recommended fields:

| Field | Purpose |
|---|---|
| `claim_id` | Stable ID |
| `job_id` | Canonical job |
| `source_record_id` | Optional source-specific origin |
| `claim_text` | Human-readable extracted claim |
| `claim_type` | Requirement, preference, responsibility, context, compensation, culture, etc. |
| `claim_strength` | `explicit_must`, `explicit_preferred`, `inferred_likely`, `weak_signal`, `boilerplate` |
| `claim_subject_type` | `capability`, `domain`, `seniority`, `credential`, `language`, `location`, `org_context`, `compensation`, `culture` |
| `normalized_key` | Stable internal concept key |
| `normalized_label` | Canonical human label |
| `source_section` | Where it came from: title, intro, requirements, responsibilities, benefits, footer |
| `evidence_span` | Text snippet or anchor showing where it came from |
| `confidence_score` | Extraction confidence |
| `importance_score` | Claim importance before candidate-specific scoring |
| `claim_json` | Structured extras |
| `created_at` | Audit timestamp |
| `updated_at` | Audit timestamp |

### `job_claim_assessments`

Candidate-specific view of a claim.

Recommended fields:

| Field | Purpose |
|---|---|
| `candidate_id` | Candidate |
| `job_id` | Canonical job |
| `claim_id` | Claim |
| `evaluation_id` | Specific evaluation context |
| `candidate_impact` | `strong_overlap`, `overlap`, `neutral`, `meaningful_gap`, `material_blocker`, `ignore_noise` |
| `impact_confidence` | Confidence in that impact |
| `assessment_reason` | Short explanation |
| `assessment_json` | Structured evidence |
| `updated_at` | Audit timestamp |

This allows the same claim to matter differently for different candidates later.

---

## Controlled vocabulary

### Claim type

Start with:

- `role_summary`
- `responsibility`
- `must_requirement`
- `preferred_requirement`
- `education_requirement`
- `credential_requirement`
- `domain_requirement`
- `tool_requirement`
- `language_requirement`
- `location_requirement`
- `org_context`
- `compensation`
- `benefit`
- `culture_signal`
- `boilerplate`

### Claim strength

- `explicit_must`
- `explicit_preferred`
- `inferred_likely`
- `weak_signal`
- `boilerplate`

### Candidate impact

- `strong_overlap`
- `overlap`
- `neutral`
- `meaningful_gap`
- `material_blocker`
- `ignore_noise`

---

## Extraction method

Use a hybrid approach.

### Deterministic first

Use rules and pattern extraction for:

- explicit must/preferred wording
- dates
- location
- salary
- education phrases
- certifications and clearances
- language requirements
- source URLs and source-native IDs

### AI interpretation second

Use bounded model calls for:

- role-family translation
- seniority interpretation
- separating meaningful requirements from generic wording
- mapping messy text to normalized concepts
- assigning preliminary importance when the text is ambiguous

### Candidate impact third

Only after claims are extracted should JobPipe ask:

- which claims matter for this candidate
- which are blockers
- which are weak signals
- which are likely not worth penalizing

This separation is necessary for explainability and future calibration.

---

## Confidence model

Every extracted claim should carry confidence.

Suggested dimensions:

- extraction confidence
- normalization confidence
- candidate-impact confidence

These should not be collapsed into one hidden number too early.

---

## How this fits the existing pipeline

### Current state

Today JobPipe has:

- `JobParse`
- `ProfileMatchOut`
- `PivotOut`
- `ModeratorOut`

This is useful but too compressed for robust interpretation.

### Proposed role of `job_claims`

The claims layer should sit between raw job text and the current summary outputs.

Flow:

1. raw job intake
2. claim extraction
3. claim normalization
4. candidate-impact assessment
5. current compact summary outputs for triage/match/moderation

The existing `JobParse` model can become a compact derivative of the richer claims model rather than the only parsed representation.

---

## Why this matters to the product

If JobPipe is going to get better at finding genuinely winnable roles, it has to stop treating job ads as:

- one title
- one score
- one explanation

The system needs to know which parts of the ad actually carry hiring meaning and which parts are noise.

This is the foundation for:

- stronger advantageous-match detection
- better gap analysis
- better candidate-specific explanations
- better calibration over time
- fewer generic and misleading recommendations

Claims alone are still not enough.

The project should also derive a separate hiring-side selection layer from those claims:

- which claims likely operate as real gates
- which are likely used in first-pass screening
- where the process is rigid versus tolerant of adjacency
- what evidence must be visible early for this candidate to survive review

That logic should be modeled separately rather than hidden inside raw claim extraction.

See also:

- `specs/hiring-side-selection-model.md`

---

## Relationship to selection modeling

`job_claims` should answer:

- what the ad says

The selection layer should answer:

- how those claims are likely to be used in screening and decision-making

That distinction matters because:

- some explicit claims are weakly enforced
- some repeated soft claims signal real hiring rigidity
- some adjacent candidates are viable only if the right evidence is surfaced early

---

## First implementation slice

The first useful slice should not try to solve everything.

Delivered now:

1. a deterministic `job_claims` model in `jobpipe/decision/`
2. a first-class `job_claims` table in the primary DB
3. extraction of a small high-value claim set:
   - role responsibilities
   - must requirements
   - preferred requirements
   - education / credential requirements
   - domain requirements
   - language / location requirements
   - obvious boilerplate
4. explicit confidence and claim strength
5. deterministic hiring-aware `job_selection_signals`
6. candidate-specific `job_selection_assessments`
7. inspection output so the extracted claims can be audited

Still deferred:

- candidate-specific `job_claim_assessments`
- LLM-backed richer claim extraction beyond the deterministic first slice

This should happen before trying to make the scoring layer more complex.
