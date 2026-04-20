# JobPipe

*A local-first career intelligence workbench built around structured evidence, explicit decisions, and living monitoring.*

JobPipe helps a candidate identify and act on the jobs they are genuinely competitive for, including non-obvious roles. It is not trying to automate the whole job search. It is trying to own the useful data-and-reasoning layer beneath that workflow.

The product thesis is:

- data is the product
- connectors are adapters
- dashboards and external tools are projections
- AI is a bounded interpretation layer
- evidence-backed decision support and living monitoring are the core mechanisms

Market label:

- **career intelligence workbench**

Plain-language fallback:

- **job-search decision system**

## What JobPipe is

JobPipe is:

- a candidate-first, hiring-aware decision workbench
- a local-first workflow system for job-search state and follow-up
- a canonical data layer for candidate, job, evaluation, narrative, and outcome history
- a traceable pipeline that preserves inspectable artifacts and explicit decisions

JobPipe is not:

- an ATS replacement
- a recruiter platform
- a mass auto-apply tool
- a generic AI copilot
- a resume-builder product
- a connector catalog for its own sake

## Public repo scope

This public repository is being aligned toward an OSS-first scope.

That means this repo should become a genuinely useful public framework/toolkit for:

- local-first job-search intelligence workflows
- canonical candidate/job/evaluation state
- inspectable decision support
- watchlist and change-detection workflows
- projections, examples, and extension points

This repo should **not** become crippleware.

The current direction is:

- `JobPipe` stays the umbrella and OSS/framework name
- the public repo should stand on its own for developers, hobbyists, tinkerers, and single users
- a later private/commercial implementation may build on top of this public foundation

Provisional later commercial product name:

- **JobPipe Workbench**

## Current product direction

JobPipe is converging on a local-first data-and-reasoning layer for job search.

The current product foundation is now organized around:

- job claims
- hiring-aware decision tables
- candidate evidence units
- candidate narrative profiles
- watchlists and change events

That means the product should get better at answering:

- what this job is actually asking for
- whether this candidate should want it
- whether the candidate can explain it credibly
- how the role is likely to be filtered and judged on the hiring side
- what changed since the last review

## Planning hierarchy

The repo should be read in this order:

1. [MASTER_PLAN.md](MASTER_PLAN.md)  
   Single planning source of truth: scope, invariants, active priorities, build sequence, cleanup direction.
2. [PRODUCT_VISION.md](PRODUCT_VISION.md)  
   Durable product thesis: what JobPipe is for, who it serves now, why it matters, and what differentiates it.
3. [ROADMAP.md](ROADMAP.md)  
   Short execution view: current phase and ordered near-term work.
4. [OSS_SCOPE.md](OSS_SCOPE.md)  
   Public repo scope, OSS/private boundary, and what this repository is for now.
5. [DEPENDENCY_POLICY.md](DEPENDENCY_POLICY.md)  
   Dependency, license, and maintained-OSS building-block direction for the public repo.
6. `docs/`  
   Operational and repo-facing explanations of the current runtime and interfaces.
7. `specs/`  
   Forward-looking design targets. Some are active next-build specs, some are later strategic specs, and some are transitional notes.

## Current priorities

The planning layer now treats these as the next public priorities:

1. harden the single-user local-first loop
2. keep the dashboard complete and trustworthy as the public proof-of-work surface
3. freeze an audit corpus and config baseline
4. run a persona-based generalization audit
5. turn audit findings into onboarding, threshold, explanation, and dashboard fixes

## Naming direction

Canonical naming decisions for this phase:

- `JobPipe` = umbrella project name
- `JobPipe` = OSS/framework name
- `JobPipe Workbench` = reserved name for a later private/commercial implementation if that split happens

This keeps the public and future private layers legible without creating an unnecessary new brand now.

## Runtime shape

JobPipe currently runs as a local Python package with:

- a primary SQLite database as canonical state
- staged evaluation artifacts for traceability
- exported dashboard/report surfaces as derived outputs
- source intake from sheet exports, FINN, Gmail, and related inputs

The repo is still in transition away from legacy runtime/output naming. Canonical naming is moving toward:

- `db/`
- `artifacts/`
- `exports/`
- `documents/`

rather than repo-local `out_runs/` and `reports/` as long-term defaults.

## Canonical operator interface

Use:

```text
jobpipe run --dry-run
```

Fallback:

```text
python -m jobpipe.cli.main run --dry-run
```

Windows wrapper:

```powershell
.\go.ps1 -DryRun
```

## Recommended data boundary

For normal use, keep user data outside the repo with `JOBPIPE_DATA_DIR`.

The intended separation is:

- repo: code, docs, specs, templates
- external data root: DB, candidate files, artifacts, exports, generated documents, credentials, caches

## Key docs

- [MASTER_PLAN.md](MASTER_PLAN.md)
- [PRODUCT_VISION.md](PRODUCT_VISION.md)
- [ROADMAP.md](ROADMAP.md)
- [OSS_SCOPE.md](OSS_SCOPE.md)
- [DEPENDENCY_POLICY.md](DEPENDENCY_POLICY.md)
- [docs/architecture.md](docs/architecture.md)
- [specs/architecture-boundaries.md](specs/architecture-boundaries.md)
- [docs/decision-model.md](docs/decision-model.md)
- [docs/configuration.md](docs/configuration.md)
- [docs/cli.md](docs/cli.md)
- [docs/artifacts.md](docs/artifacts.md)
- [docs/dashboard.md](docs/dashboard.md)
- [specs/canonical-data-model.md](specs/canonical-data-model.md)
- [specs/job-claims-model.md](specs/job-claims-model.md)
- [specs/hiring-side-selection-model.md](specs/hiring-side-selection-model.md)
- [specs/candidate-narrative-model.md](specs/candidate-narrative-model.md)
- [specs/controlled-cv-tailoring.md](specs/controlled-cv-tailoring.md)
- [specs/platform-alignment-audit.md](specs/platform-alignment-audit.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [TESTING.md](TESTING.md)

## Status

The repository is in active cleanup and restructuring.

The immediate goal is not more feature breadth. It is to make the codebase, runtime model, docs, active specs, and public OSS scope point in one coherent direction before the next architecture pass.

## License

MIT for the current public repo.

See [DEPENDENCY_POLICY.md](DEPENDENCY_POLICY.md) for dependency and license direction.
