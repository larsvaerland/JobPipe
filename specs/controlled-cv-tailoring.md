# Controlled CV Tailoring

## Purpose

This spec defines how JobPipe should help tailor a CV directly from candidate data without letting an LLM rewrite the candidate into generic recruiter language.

The current problem is not just "generate better CV text." The real problem is:

- tailoring is slow
- tailoring is often done outside the system
- AI tends to rewrite into generic wording
- visual CV builders may look good but produce extraction and formatting friction
- candidate wording and evidence are not governed tightly enough

The product goal is:

**use structured candidate data to generate role-specific CV variants while preserving voice, evidence integrity, and stable document structure.**

---

## What "good" means

A good tailored CV system for JobPipe should do five things:

1. reuse existing candidate evidence directly
2. tailor selection and ordering more than freeform rewriting
3. keep wording close to candidate-approved phrasing
4. produce export formats that survive recruiter systems and machine reading
5. preserve a clean audit trail of what changed for which job

---

## Grounded observations from the current CV

From `C:\Users\larsv\Downloads\Endingsleder CV NO 2026.pdf` and the current Jobseeker flow:

- the CV is visually strong and compact
- the PDF text is machine-extractable, but noisy in places
- visual bullet glyphs and multi-column layout reduce extraction cleanliness
- some text merges or breaks awkwardly in extraction
  - example: `skjæringspunktet mellomkrysningspunktet`
- profile and competency sections are compact but prone to genericness if AI rewrites them
- the current JobPipe `application_pack` stage only produces:
  - JSON application-pack draft
  - selected CV highlights
  - DOCX supplement

That is not yet a full controlled tailored-CV system.

---

## Non-goals

This feature is not:

- freeform CV generation from scratch every time
- an AI-driven visual resume designer
- a recruiter-keyword stuffing engine
- uncontrolled paraphrasing of the candidate's actual experience

It should explicitly resist generic, inflated, or fabricated language.

---

## Design principles

1. Tailor by **selection, ordering, and bounded rewriting** before full text generation.
2. Separate canonical candidate evidence from role-specific projections.
3. Keep candidate-approved wording as reusable source material.
4. Track provenance for every tailored bullet.
5. Support both machine-friendly and visually polished export paths.
6. Treat visual template choice as a projection layer, not the source of truth.

---

## Canonical CV data model

JobPipe needs a stronger distinction between:

1. canonical candidate evidence
2. reusable wording units
3. tailored CV projections

### Canonical evidence

This should come from:

- work history
- selected project cases
- education
- certifications
- domain exposure
- concrete outcomes

Each reusable evidence unit should be structured.

### Proposed concept: `candidate_evidence_units`

One row per candidate-approved reusable CV evidence item.

Recommended fields:

| Field | Purpose |
|---|---|
| `evidence_unit_id` | Stable ID |
| `candidate_id` | Owner |
| `source_type` | `work_highlight`, `project_case`, `education`, `summary_claim`, `skill_claim` |
| `source_ref` | Work entry, project, or profile reference |
| `role_family_tags` | What kinds of roles this supports |
| `domain_tags` | Relevant sectors/domains |
| `capability_tags` | Capability mapping |
| `outcome_tags` | What kind of result it shows |
| `canonical_text` | Candidate-approved baseline wording |
| `evidence_json` | Structured facts |
| `rewrite_policy` | `verbatim_preferred`, `light_rewrite_only`, `can_summarize` |
| `created_at`, `updated_at` | Audit timestamps |

This is the real substrate for controlled tailoring.

---

## Tailoring model

### Tailored CV projection

For one candidate and one job, JobPipe should create a projection, not a replacement of the candidate master CV.

### Proposed concept: `tailored_cv_variants`

Recommended fields:

| Field | Purpose |
|---|---|
| `cv_variant_id` | Stable ID |
| `candidate_id` | Owner |
| `job_id` | Target job |
| `evaluation_id` | Evaluation context |
| `template_id` | Export template |
| `variant_strategy` | `conservative`, `balanced`, `aggressive` |
| `summary_text` | Tailored summary |
| `selected_evidence_json` | Ordered chosen evidence units |
| `section_plan_json` | Which sections were included and in what order |
| `rendered_markdown` | Canonical text projection |
| `rendered_html` | Optional formatted output |
| `rendered_docx_path` | Export path |
| `rendered_pdf_path` | Export path |
| `created_at`, `updated_at` | Audit timestamps |

This should sit alongside, not replace, generated document metadata.

---

## Tailoring rules

### What the system should do

1. Select the most relevant existing evidence.
2. Reorder sections for the target role.
3. Emphasize relevant domain/capability overlap.
4. Condense low-relevance material.
5. Produce a role-specific summary and headline.
6. Keep each tailored bullet tied back to a known evidence unit.

### What the system should not do

1. Invent experience.
2. Rewrite everything into recruiter-speak.
3. Change strong candidate wording without reason.
4. Merge claims so heavily that they lose evidence traceability.
5. Treat visual polish as more important than text integrity.

---

## Rewrite policy

This part matters most.

The system should support three rewrite levels:

### 1. Verbatim preferred

Use candidate-approved wording as-is unless minor cleanup is necessary.

Best for:

- core achievements
- regulated/compliance work
- subtle leadership wording
- phrases the candidate considers identity-bearing

### 2. Light rewrite only

Allow:

- compression
- terminology alignment
- tense cleanup
- bullet cleanup

Do not allow:

- new claims
- stronger implied seniority
- generic embellishment

### 3. Summarize allowed

Allow stronger summarization for:

- lower-priority older work
- repeated support bullets
- compact side sections

This policy should be stored per evidence unit, not decided ad hoc each time.

---

## Candidate experience problem to solve

Today the tailoring workflow often looks like this:

1. inspect job
2. copy CV content into AI or CV tool
3. ask for tailoring
4. clean up generic phrasing
5. fix formatting
6. manually restore lost nuance

That is slow and unreliable.

JobPipe should replace that with:

1. evaluate job
2. select evidence from canonical state
3. generate a bounded tailored projection
4. export to machine-friendly and optional visual formats
5. allow review and final human edits

This is where real hard value appears for the user.

---

## Export strategy

JobPipe should not rely on one visual builder as the canonical format.

It should support at least two projection types:

### 1. ATS / machine-friendly export

Goals:

- single-column
- clean section hierarchy
- stable typography
- minimal glyph dependency
- predictable extraction

Good outputs:

- Markdown
- clean DOCX
- simple PDF generated from a machine-friendly source

### 2. Visually polished export

Goals:

- good feel
- compact and attractive layout
- still reasonably extractable

This can coexist, but should be downstream of canonical text, not the only artifact.

The key rule is:

**one canonical tailored content model, multiple render targets.**

---

## Reactive Resume analysis note

Reactive Resume's built-in `Resume Analysis` feature should be treated as a **review layer**, not a generation core.

Observed behavior:

- it analyzes the current resume JSON
- it produces:
  - overall score
  - scorecard
  - strengths
  - prioritized suggestions
- it is general resume critique, not job-specific targeting

This makes it potentially useful for:

- post-generation QA
- ATS-style hygiene checks
- catching weak bullets, vague wording, or missing quantification

This does **not** make it a good canonical source for:

- evidence selection
- section planning
- claim coverage
- narrative strategy
- final CV generation policy

Recommended usage pattern if adopted:

1. JobPipe generates the tailored CV plan/projection first.
2. Reactive Resume may render/edit it.
3. `Resume Analysis` may then critique the resulting variant.
4. Any accepted changes should still be filtered back through JobPipe's evidence and rewrite-policy rules.

---

## How this fits the current system

### Current state

The current `application_pack` stage already does:

- role-specific context packaging
- selection of 4–6 CV highlights
- light alignment to job terminology
- DOCX supplement output

### Current limitation

It does not yet:

- manage a canonical evidence-unit library
- preserve rewrite policy per evidence unit
- produce full tailored CV projections
- produce ATS-safe and visual variants from the same content model
- keep full provenance for all tailored CV content

The repo now has a first deterministic evidence-unit slice under `jobpipe/decision/`:

- candidate evidence units derived from current resume/profile context
- job-specific evidence selection consumed by `application_pack`

That is useful progress, but it is still not the same as having evidence units persisted and managed as first-class canonical rows.

---

## Proposed pipeline

### Step 1: candidate evidence curation

Create and maintain reusable candidate-approved evidence units.

### Step 2: job-driven section plan

Use job claims + evaluation output to decide:

- which sections matter
- which evidence units to show
- what order to use
- which parts to suppress

### Step 3: bounded summary generation

Generate:

- tailored headline
- tailored profile summary
- optional section intros

with strict rewriting policy.

### Step 4: projection render

Render:

- ATS-safe variant
- optional visual variant

from the same selected content.

### Step 5: review + final export

Allow the candidate to inspect:

- what evidence was used
- what was lightly rewritten
- what was suppressed
- which claims from the job the variant is targeting

---

## Relationship to job claims

This feature depends on the claims model.

The strongest tailoring is not:

- "use keywords from ad"

It is:

- understand which claims actually matter
- choose evidence that answers those claims directly
- preserve wording quality while increasing relevance

That means `job_claims` and tailored CV generation should be designed together.

---

## Local prototype input

There is a local prototype folder inside this repo that should be treated as later bounded research input:

- `C:\Users\larsv\Jobpipe\prototype\Prototype - Tailoring and consolidated React Resume  CV +cover letter`

This prototype may contain useful examples for:

- tailoring flow
- consolidated resume projection
- cover-letter generation

Important rule:

- the prototype is not canonical runtime logic
- it must not bypass the evidence-unit and narrative-model direction in this spec
- anything reused from it should be mapped back into:
  - canonical evidence units
  - rewrite policy
  - tailored CV projections
  - machine-friendly export discipline

---

## First implementation slice

The first useful slice should stay narrow:

1. define a canonical evidence-unit model
2. add rewrite policy per evidence unit
3. build a CV variant plan from:
   - job claims
   - profile match
   - moderator focus
4. generate one ATS-safe tailored CV export
5. keep the current visual PDF builder external for now if needed
6. persist provenance for every selected bullet

This gets to the hard user value faster than trying to replace the entire visual CV-builder workflow at once.
