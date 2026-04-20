# JobPipe Master Plan

**Last updated:** 2026-04-17

This is the single planning source of truth for JobPipe.

## Canonical product thesis

JobPipe is a candidate-first, hiring-aware, local-first career intelligence workbench.

Its job is to help a candidate identify and act on the opportunities they are genuinely competitive for, including non-obvious roles, by turning messy candidate data, market data, and outcome history into better decisions.

The core mechanism is:

**structured evidence -> explicit decision support -> living monitoring -> better action**

The product is not the connectors, dashboard, or UI shell. The product is the application of structured data and bounded reasoning to produce better job-search decisions.

Current public market label:

- **career intelligence workbench**

Plain-language fallback:

- **job-search decision system**

## Scope decision

JobPipe is:

- candidate-first
- hiring-aware where that improves candidate outcomes
- local-first
- evidence-backed
- decision-oriented
- traceable and inspectable

JobPipe is not:

- a recruiter platform
- an ATS replacement
- a mass auto-apply tool
- a generic AI copilot
- a broad workflow automation suite
- a connector marketplace
- a resume-builder product
- a multi-tenant SaaS platform today

This is the correct wedge for the current phase. The vision becomes too broad only when it drifts into trying to own every adjacent workflow surface.

## Invariants

These should not drift:

1. User state lives outside the repo.
2. The primary DB is the canonical runtime state layer.
3. Artifacts, exports, and generated documents are derived outputs.
4. Connectors are adapters, not the product.
5. Dashboards and external tools are projections, not sources of truth.
6. AI is for bounded interpretation; deterministic code is for operations.
7. Learning is local-first by default.
8. Privacy is a hard requirement.
9. The canonical operator interface is the Python CLI; OS-specific wrappers are secondary.
10. Planning stays candidate-first even when the system becomes hiring-aware.

## Planning hierarchy

The repo should be interpreted in this order:

1. `MASTER_PLAN.md`
2. `PRODUCT_VISION.md`
3. `ROADMAP.md`
4. `OSS_SCOPE.md`
5. `DEPENDENCY_POLICY.md`
6. `docs/`
7. `specs/`

Document roles:

- `MASTER_PLAN.md`: canonical planning source of truth
- `PRODUCT_VISION.md`: durable product thesis and wedge framing
- `ROADMAP.md`: short execution view only
- `OSS_SCOPE.md`: public repo scope, OSS/private boundary, and contribution surface definition
- `DEPENDENCY_POLICY.md`: maintained-OSS building-block direction and license policy for the public repo
- `docs/`: current runtime, workflow, and operator guidance
- `specs/`: active and future build targets, migration notes, and design scaffolding

## Naming architecture

Naming should stay stable across planning, repo presentation, and later business evolution.

Lock these decisions for this phase:

- `JobPipe` remains the umbrella project name
- `JobPipe` remains the OSS/framework name
- the public repo should be described as the public JobPipe framework/toolkit
- a later private/commercial implementation may use the product name **JobPipe Workbench**

This avoids both premature rebranding and future confusion between the public foundation and a paid implementation.

## Canonical product shape

The system should stay organized around these objects:

- candidate
- candidate profile
- canonical job
- job source record
- pipeline run
- job evaluation
- application event / summary
- generated document
- candidate calibration setting
- candidate feedback event
- capability gap
- gap evidence / gap assessment
- job-ad claim / claim assessment
- job decision table
- candidate evidence unit
- candidate narrative profile / narrative assessment
- hiring-side selection signal / selection assessment
- watchlist / change event

Everything else is subordinate to this model.

## Candidate-first but hiring-aware

JobPipe should explicitly account for the other side of the table where that changes outcomes.

That includes:

- recruiter screening pressure
- ATS-style structural gates
- title and domain continuity bias
- ambiguity tolerance in the hiring process
- evidence burden required to make a pivot or adjacent move legible early

This does **not** mean JobPipe becomes recruiter software.

It means the product should answer not only:

- can the candidate do this work?
- should the candidate want this work?
- can the candidate explain this role credibly?

But also:

- how is this role likely to be filtered and judged?
- what evidence must be visible early to survive review?
- where is this job plausible in substance but weak in process terms?

## Current phase

JobPipe is now in a public hardening and audit-preparation phase.

The planning reset, runtime boundary cleanup, first public decision substrate, and dashboard projection are in place.

The main objective is now to make the public OSS loop:

- stable for clean local installs
- credible through the dashboard
- auditable against more than one candidate shape
- still consistent with the candidate-first, hiring-aware thesis

The latest public hardening closures now include:

- reproducible replay inputs for evaluated jobs
- isolated persona-audit dashboard state
- explicit no-score reasons for evaluated jobs that were skipped before fit/pivot scoring

That means the next phase should emphasize:

- public onboarding defaults
- end-to-end loop reliability
- explanation quality
- dashboard trustworthiness
- persona-based generalization audits
- no drift into recruiter-platform, multi-tenant SaaS, or generic-copilot scope

## Public repo scope

The current public repo should be aligned toward a genuine OSS-first scope now.

That means:

- the public repo should be useful on its own
- the public repo should expose stable canonical models, runtime behavior, examples, and extension points
- the public repo should not be positioned as crippleware or a teaser for private code
- the public repo should also not attempt to expose every future commercial workflow

The current repo should therefore represent:

- the public JobPipe framework/toolkit
- the canonical public data model and workflow substrate
- public examples and proof-of-work surfaces
- public contribution surfaces for generic infrastructure, local workflows, and reusable runtime functionality

## Later private/commercial layer

The later private/commercial layer is real in planning terms, but it should remain out of current public repo scope.

That later layer may include:

- tuned decision logic
- premium workflow bundles
- calibration and learned defaults
- sensitive or high-maintenance connectors
- premium packaging and product UX

It should build on the public foundation rather than redefining the public model.

## Strategic build sequence

### Phase 1. Planning and cleanup baseline

Deliver:

- coherent root docs and planning hierarchy
- explicit active specs vs later specs
- cleanup plan for runtime outputs, connector boundaries, and stale terminology
- candidate-first but hiring-aware framing reflected across docs

### Phase 2. Runtime boundary and intake cleanup

Deliver:

- stronger external data-root-first behavior
- runtime output naming cleanup around `artifacts/` and `exports/`
- stronger canonical intake and cross-source deduplication
- thinner connector boundaries, especially for mail and source-specific ingestion

### Phase 3. Decision substrate

Deliver:

- `job_claims`
- hiring-side selection signals
- explicit decision-table direction in the product model
- inspection surfaces that show why a role is winnable, risky, or weak

### Phase 4. Candidate evidence and controlled tailoring

Deliver:

- candidate evidence units
- controlled CV projections
- evidence-first tailoring rather than freeform AI rewriting

### Phase 5. Candidate narrative and explainability

Deliver:

- candidate narrative profiles
- narrative evidence links
- better `should_want` and `can_explain` support in triage and prioritization

### Phase 6. Living monitoring and change detection

Deliver:

- watchlists
- change events
- repeated-use monitoring surfaces
- delta-based review instead of repeated full rescans

### Phase 7. Calibration and outcome learning

Deliver:

- feedback-aware prioritization
- better capability-gap refinement
- outcome-linked improvement of ranking and explanation quality

## Active specs

These are the active next-build specs and planning documents:

- `specs/architecture-boundaries.md`
- `specs/canonical-data-model.md`
- `specs/platform-alignment-audit.md`
- `specs/persona-audit-plan.md`
- `specs/job-claims-model.md`
- `specs/hiring-side-selection-model.md`
- `specs/controlled-cv-tailoring.md`
- `specs/candidate-narrative-model.md`

These are active but slightly later in the sequence:

- `specs/local-calibration-learning.md`
- `specs/capability-gap-analysis.md`

These are transitional or lower-priority:

- `specs/legacy-merge-plan.md`
- `specs/current-change.md`

## Planned cleanup priorities before architecture

The following work should now be treated as planned cleanup, not optional tidying:

1. runtime output externalization under `JOBPIPE_DATA_DIR`
2. architecture-boundary definition for public package slices and the OSS/private seam
3. `reports/` and `out_runs/` terminology cleanup toward `exports/` and `artifacts/`
4. code/template separation from generated-output folders
5. connector boundary cleanup
6. Gmail refactor direction toward provider-neutral ingestion
7. doc consistency across root docs and `docs/`
8. promotion of active specs and retirement/merging of stale scaffolding
9. cleanup of workflow scaffolding that assumes `specs/current-change.md` is authoritative when it is still a placeholder
10. explicit OSS/private boundary framing in the public planning layer
11. dependency and license policy alignment for an OSS-first public repo

## Current hardening priorities

The next public-OSS priorities are now:

1. close remaining install/runtime blockers in the single-user local loop
2. keep the dashboard complete and trustworthy as the public proof-of-work surface
3. freeze an audit corpus and config baseline
4. run a persona-based generalization audit
5. convert audit findings into:
   - onboarding fixes
   - threshold and heuristic fixes
   - evidence/narrative fixes
   - dashboard usability fixes

The first runnable matrix findings are now tracked in:

- `specs/persona-audit-findings-2026-04-17.md`

That bug list currently says the next public hardening order is:

1. guarantee score completeness or explicit no-score reasons
2. tighten candidate-shape differentiation and reduce product-leadership inertia
3. reduce monitoring/watchlist noise
4. rerun the matrix and turn the next findings pass into code fixes and dashboard polish

This is the right next phase because the main risk is no longer missing core product direction.

The main risk is overfitting, weak defaults, and silent quality drift.

## Policy directions

### AI policy

Use AI where ambiguity matters:

- claim extraction
- market/title translation
- fit and gap interpretation
- candidate-specific explanation
- evidence-backed narrative support
- bounded monitoring summaries

Do not use AI as the primary mechanism for:

- connector plumbing
- identity mapping
- sync checkpoints
- runtime control flow
- canonical state management

Rule:

**AI-first for interpretation, deterministic-first for operations.**

### Connector policy

Priority order:

1. open/file-based inputs
2. standard protocols
3. provider APIs
4. scraping only as targeted enrichment

Implications:

- connectors stay thin
- provider-specific logic stops at normalization
- scraping should not become the product foundation
- mail logic should move toward provider-neutral ingestion

### Projection policy

JobPipe remains the control plane.

That means candidate state, calibration, dedupe ambiguity, selection logic, and review state stay anchored in JobPipe.

Dashboards, exported reports, Notion, or future web UIs can consume and update selected state, but they should not own the model.

### OSS and dependency policy

The public repo should prefer maintained permissive OSS building blocks for generic concerns.

Preferred license families for the public repo and anything it should compose cleanly with later:

- MIT
- BSD-2 / BSD-3
- Apache-2.0
- ISC
- PSF

Use maintained OSS directly where the capability is generic:

- schema validation
- storage and migrations
- CLI/runtime ergonomics
- HTTP and parsing utilities
- templating
- testing and observability

Wrap or compose maintained OSS where the abstraction should stay owned by JobPipe:

- scheduling
- LLM/agent runtime integrations
- document rendering backends

Build custom where differentiation lives:

- claims
- decision tables
- evidence units
- narrative profiles
- change-event semantics
- calibration and premium workflow logic

Avoid making the public foundation depend on restrictive copyleft or source-available licenses if that would complicate a later private/commercial layer.

## Non-goals

Not for this phase:

- recruiter-side product scope
- ATS feature parity
- mass auto-apply
- full recruiter CRM or sourcing workflows
- broad workflow automation beyond the current loop
- full resume-builder GUI parity
- vector-database-first architecture
- own-model training as a product priority
- settings UI for every internal knob
- provider- or OS-locked architecture
- premature repo split before the public planning layer is stable
- open-core ambiguity inside the same repo

## Success test

This phase is succeeding if:

- the root docs tell one coherent product story
- active specs and the roadmap agree on the next build sequence
- runtime/output terminology is clearly transitioning to one canonical model
- candidate-first but hiring-aware logic is reflected explicitly in the plan
- the repo is prepared for the next architecture pass without needing another planning reset
