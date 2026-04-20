# Candidate Narrative Model

## Purpose

This spec defines how JobPipe should represent the candidate's professional story as structured, durable data instead of regenerating it from scratch for every job.

The hard problem is not only:

- what the candidate has done
- what the job requires

It is also:

- why this kind of role makes sense now
- what future the candidate is moving toward
- why a pivot is credible
- how to explain motivation without sounding generic or false

JobPipe should therefore maintain a **candidate narrative layer** that is:

- structured
- evidence-backed
- calibrated over time
- usable in triage, tailoring, and active discovery

---

## Core product question

For a given candidate and job, JobPipe should be able to answer:

1. Why is this role plausible for this candidate?
2. Why would this candidate want this role category now?
3. What makes the pivot or transition credible?
4. Which parts of the candidate's story should be emphasized?
5. Which parts of the story should not be used because they sound false, weak, or generic?

The output should not be "a nice story." It should be a **credible, evidence-backed explanation** that improves decisions and downstream communication.

---

## Why this matters

Generic AI tends to fail in one of two ways:

1. it writes recruiter-flavored admiration fluff
2. it invents a too-clean identity story that the candidate would not naturally stand behind

Both reduce credibility.

The narrative model exists to stop that failure mode by separating:

- private motives
- professional framing
- supporting evidence
- recruiter-facing language

This is a product layer, not just a prompt trick.

---

## Non-goals

This feature is not:

- therapy in structured form
- a generic personal-branding engine
- freeform autobiographical writing
- a replacement for actual evidence
- an invitation to exaggerate motivation for every role

The system should not force a candidate to sound more certain, more passionate, or more title-committed than is credible.

---

## Design principles

1. Narrative must be evidence-backed.
2. Narrative should be versioned and candidate-specific.
3. Private motives and public-facing language must be separated.
4. Pivot logic must be explicit, not improvised ad hoc.
5. The system should store anti-patterns as well as preferred story lines.
6. Narrative should influence triage and ranking, not only letter generation.
7. Learning should refine narrative emphasis over time.

---

## Narrative layers

JobPipe should represent narrative in at least seven parts.

### 1. Core identity

What the candidate reliably does well across roles, independent of title.

This is the stable professional center.

Example shape:

- brings structure into messy digital/service environments
- translates between business, systems, delivery, and people
- creates momentum through prioritization and coordination

This is not a slogan. It is a reusable interpretation anchor.

### 2. Future direction

Where the candidate is trying to move.

This should capture:

- desired direction of growth
- acceptable adjacent role families
- acceptable domain shifts
- role/environment preferences that matter for long-term fit

This is how JobPipe distinguishes a technically plausible role from a strategically useful role.

### 3. Motivation themes

What genuinely makes the work worth doing.

These are the durable "why" themes, but they should be stored as themes, not dumped directly into recruiter-facing text.

Examples:

- wants clearer ownership and visible value creation
- wants work with meaningful responsibility and better long-term fit
- is open to relocation or domain shift if the work is more aligned

### 4. Pivot thesis

Why the candidate's next move is credible even when it is not a straight title continuation.

This should answer:

- what is changing
- what is not changing
- what in the background makes the move believable

This is central for career pivots and adjacent roles.

### 5. Proof themes

Recurring patterns of evidence that support the narrative.

Examples:

- change leadership in digital settings
- cross-functional delivery under complexity
- product/service/platform improvement
- coordination across business, IT, suppliers, and operations

This connects narrative to actual evidence units.

### 6. Story boundaries

What should not be claimed or emphasized.

Examples:

- do not pretend a loose adjacent experience equals deep specialist identity
- do not oversell every role as a long-term passion
- do not force a pure product-leadership story where the evidence is broader and more mixed

This is a critical anti-generic safeguard.

### 7. Public-facing tone rules

How the candidate should sound in recruiter-facing material.

Examples:

- grounded, concrete, not overexcited
- future-oriented, but not vague
- credible pivot language, not reinvention fantasy
- specific about value, not adjective-heavy

---

## Private motives vs professional framing

This distinction matters.

The candidate may privately want things like:

- be happier more often
- get out of a draining work pattern
- move if necessary
- find a domain that fits better over time

Those are valid drivers, but they are not recruiter copy.

JobPipe should therefore store both:

### Private driver

What actually matters to the candidate.

### Professional framing

How that driver should be expressed in a credible work context.

Examples:

| Private driver | Professional framing |
|---|---|
| wants a happier life | looking for work with better long-term fit and more sustainable motivation |
| wants less chaos | looking for environments where structure, ownership, and visible delivery matter |
| open to moving | open to relocation for the right long-term role fit |
| wants a meaningful pivot | looking for adjacent roles where existing strengths transfer into a stronger future direction |

This translation step should be explicit in the data model.

---

## Proposed data model

### `candidate_narrative_profiles`

One active narrative profile per candidate version, with historical versions retained.

Recommended fields:

| Field | Purpose |
|---|---|
| `narrative_version_id` | Stable ID |
| `candidate_id` | Owner |
| `source_kind` | `manual`, `guided_form`, `agent_draft`, `calibrated_update` |
| `core_identity_json` | Core identity statements |
| `future_direction_json` | Desired role/direction state |
| `motivation_themes_json` | Private and public motive themes |
| `pivot_thesis_json` | Why the transition is credible |
| `proof_themes_json` | Recurring evidence-backed strengths |
| `story_boundaries_json` | Anti-story / what not to claim |
| `tone_rules_json` | Recruiter-facing tone rules |
| `narrative_summary` | Compact human-readable summary |
| `is_active` | Active version flag |
| `created_at`, `updated_at` | Audit timestamps |

### `narrative_fragments`

Reusable approved text fragments tied to the narrative profile.

Recommended fields:

| Field | Purpose |
|---|---|
| `fragment_id` | Stable ID |
| `candidate_id` | Owner |
| `narrative_version_id` | Narrative profile version |
| `fragment_type` | `identity`, `motivation`, `pivot`, `summary`, `intro`, `anti_pattern` |
| `audience` | `internal`, `recruiter`, `cover_letter`, `cv_summary`, `interview` |
| `canonical_text` | Approved text |
| `rewrite_policy` | `verbatim_preferred`, `light_rewrite_only`, `can_summarize` |
| `fragment_json` | Structured metadata |
| `created_at`, `updated_at` | Audit timestamps |

### `narrative_evidence_links`

Links between the narrative and evidence units.

Recommended fields:

| Field | Purpose |
|---|---|
| `narrative_link_id` | Stable ID |
| `candidate_id` | Owner |
| `narrative_version_id` | Narrative version |
| `evidence_unit_id` | Linked evidence unit |
| `link_type` | `supports_identity`, `supports_pivot`, `supports_motivation`, `supports_role_family` |
| `strength_score` | How strongly the evidence supports the narrative element |
| `notes` | Short explanation |
| `created_at`, `updated_at` | Audit timestamps |

### `job_narrative_assessments`

Per-job assessment of narrative alignment.

Recommended fields:

| Field | Purpose |
|---|---|
| `candidate_id` | Candidate |
| `job_id` | Canonical job |
| `evaluation_id` | Evaluation context |
| `direction_fit_score` | Does this job fit the candidate's forward direction? |
| `motivation_fit_score` | Is this kind of work aligned with what the candidate actually wants? |
| `pivot_credibility_score` | Can the candidate tell a believable story into this role? |
| `story_strength_score` | How strong is the candidate's explainable narrative here? |
| `misalignment_flags_json` | Why it may still be a poor narrative fit |
| `assessment_reason` | Short explanation |
| `updated_at` | Audit timestamp |

This is the bridge into triage and ranking.

---

## How it fits triage

The narrative layer should add a missing dimension to triage.

Today the product is strongest on:

- can_do
- parts of can_get

The narrative layer should strengthen:

- should_want
- can_explain

### Proposed triage questions

In addition to fit and pivot scoring, JobPipe should ask:

1. Does this role fit the candidate's intended direction?
2. Is the pivot into this role credible?
3. Can the candidate explain why this role makes sense now?
4. Does the role fit the kind of work/environment the candidate is trying to move toward?

That will reduce cases where:

- the job is technically plausible but strategically wrong
- the role is attractive on paper but hard to explain credibly
- the role is slightly adjacent but actually a better future move

---

## How it fits learning and calibration

Narrative should not stay static.

Over time, JobPipe should learn from:

- manual promotions/demotions
- applications sent
- interviews reached
- rejections
- accepted offers
- "good recommendation" / "bad recommendation" feedback
- "good fit" / "bad fit" judgments

This allows calibration of:

- which role families are more credible than first assumed
- which narrative angles lead to interviews
- which pivot stories fail repeatedly
- which motivation themes align with real action, not just stated preference

### Important rule

Calibration should change emphasis first, not rewrite identity wholesale.

The system should become more precise over time, not more synthetic.

---

## How it fits active opportunity discovery

The narrative model is also useful for proactive lead discovery.

An active discovery agent should not search only by title keywords. It should search by:

- role family
- claim patterns
- domain adjacency
- candidate proof themes
- future direction alignment
- pivot credibility

That means the narrative model becomes part of retrieval and ranking for:

- unfamiliar titles
- adjacent domains
- employer patterns
- opportunities the candidate would not have searched for manually

### Bounded active-discovery use

The narrative layer should support:

- search term expansion
- adjacent-role discovery
- employer/category targeting
- lead prioritization

It should not be used as freeform motivational text for autonomous agents.

---

## How it fits CV and letter tailoring

The narrative layer should feed:

- CV summary selection
- cover-letter angle
- job-specific motivation briefs
- recruiter-facing intro paragraphs

But it should do so through controlled fragments and evidence links, not by improvising a new personality for each job.

### Recommended generation sequence

1. job claims
2. candidate evidence selection
3. narrative assessment
4. motivation brief
5. controlled CV / cover-letter projection

That is safer and more useful than direct full-text generation from the raw job ad.

---

## First implementation slice

The first useful slice should stay narrow.

Deliver:

1. `candidate_narrative_profiles`
2. `narrative_fragments`
3. `narrative_evidence_links`
4. one compact narrative-assessment output per job
5. one internal "motivation brief" for top jobs

Do not start by building a full narrative editor or freeform letter generator.

The repo now has a first deterministic narrative slice under `jobpipe/decision/`:

- candidate narrative profile derived from `profile_pack` and evidence context
- narrative fragments for controlled downstream use
- narrative evidence links
- one per-job narrative assessment with a compact motivation brief

These narrative objects are now also promoted into first-class canonical rows through `jobpipe/stages/application_pack.py`:

- `candidate_narrative_profiles`
- `narrative_fragments`
- `narrative_evidence_links`
- `job_narrative_assessments`

What is still deferred:

- narrative calibration beyond deterministic heuristics
- a dedicated narrative editing workflow
- a cleaner candidate-level narrative refresh seam outside `application_pack`

---

## Success criteria

This layer is working if:

- the candidate can describe a pivot without sounding generic
- triage improves on future-fit and explainability, not just skill fit
- application materials become more believable and less generic
- manual feedback can refine narrative emphasis over time
- active lead discovery surfaces more credible adjacent opportunities

The layer fails if it becomes:

- vague self-branding prose
- disconnected from evidence
- too unstable across runs
- more polished than truthful
