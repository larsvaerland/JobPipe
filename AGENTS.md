# AGENTS.md

## Repository expectations

- Start from docs, not assumptions.
- Make the smallest safe change that solves the stated problem while preserving the current JobPipe direction.
- Keep diffs focused and reversible.
- Do not refactor unrelated code or widen scope casually.
- Do not add dependencies unless necessary and justified against `DEPENDENCY_POLICY.md`.
- Do not start a new sprint/topic on top of unclear git state.
- Do not claim work is done without validation actually having run.
- Do not silently work around doc/code mismatches; resolve them explicitly in docs or stop and report the blocker.
- If behavior, terminology, structure, or planning direction changes, update the relevant docs in the same change.
- Keep private or sensitive data out of git.
- Keep `prototype/` out of git unless the task explicitly promotes something into the product tree.

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

If `specs/current-change.md` is populated for the current task, use it. If it is blank or stale, fall back to the planning docs above.

For transitional cleanup or repo-audit work, also consult these when relevant:

- `docs/mvp-task-plan.md`
- `docs/architecture-plan.md`
- `AUDIT.md`
- `AGENT_STATUS.md`
- `CLAUDE.md`

## Product direction to preserve

Keep these repo truths intact:

- JobPipe is candidate-first.
- JobPipe is hiring-aware where that improves candidate outcomes.
- JobPipe is local-first, structured, and traceable.
- Data is the product.
- Connectors are adapters.
- Dashboards and external tools are projections.
- AI is a bounded interpretation layer, not the product itself.
- The public repo is being aligned as a genuine OSS-first framework/toolkit.

Do not drift into:

- recruiter-product scope
- ATS parity
- broad workflow automation
- generic AI copilot behavior
- speculative feature sprawl
- open-core ambiguity inside the public repo

## Setup and runtime

Use the canonical operator interface:

```text
jobpipe run
jobpipe run --dry-run
```

Fallback:

```text
python -m jobpipe.cli.main run
python -m jobpipe.cli.main run --dry-run
```

Windows wrapper:

```powershell
.\go.ps1
.\go.ps1 -DryRun
```

Baseline local setup:

1. Create `.env` from `.env.example`.
2. Create `profile_pack.md` from `profile_pack.example.md` when needed.
3. Create and activate a virtual environment.
4. Install the package with `python -m pip install -e .`.

Preferred runtime boundary:

- Keep persistent user data outside the repo with `JOBPIPE_DATA_DIR`.
- Treat repo files as code, docs, specs, templates, and fixtures.
- Treat DBs, artifacts, exports, generated documents, credentials, and caches as runtime data.

## Repo-state gate

Before substantial topic or sprint work:

1. Run `git status --short`.
2. Run `git branch --show-current`.
3. If relevant, inspect recent commits or the diff summary.

If repo state is unclear, classify it before coding:

- active sprint work
- unfinished prior sprint work
- unrelated user work
- unexpected or mismatched state

Do not pile new implementation on top of unresolved repo/doc drift. If the tree is not trustworthy for the next topic, do a cleanup or alignment pass first.

For substantial sprint or topic work, report:

- which docs were read
- the current branch
- a concise `git status --short` summary
- the active topic or sprint
- the success criteria

## Change rules

- Prefer narrow, targeted edits.
- Do not change architecture casually; move planning and runtime truth together.
- Preserve traceability in pipeline behavior, state writes, and exported outputs.
- Work on one coherent topic at a time.
- Confirm documented intent first, then check implementability in the current codebase.
- If the plan is incomplete, inconsistent, or not implementable, make the minimal doc correction first or stop and explain the blocker.
- For larger alignment passes, keep the change logically cohesive and avoid mixing speculative architecture work into implementation updates.

## Protected areas

Be extra careful around:

- pipeline stages
- decision logic
- config keys and thresholds
- runtime paths and output locations
- report/dashboard generation
- Gmail integration
- DB schema and state writes

## Boundary rules

- Treat sibling repos under `lars.vaerland` as separate products, not as extensions of JobPipe.
- If work requires touching a sibling repo, read its own docs and architecture first.
- Prefer thin connectors and explicit contracts over invasive rewrites.
- Bias toward less coupling when a repo boundary is unclear.
- JobPipe owns intake, filtering, scoring, analysis, packet generation, structured tailoring, case-scoped authoring state, and the local-first runtime.
- JobSync owns the active application-case workflow.
- Reactive Resume owns manual CV editing, analysis, and export.
- Word or Docs-style tools own manual cover-letter editing and export.
- Prefer structured selection, layout, patching, and provenance over opaque whole-document rewrites.

## Validation

For meaningful code changes:

1. Run the most relevant targeted test.
2. Run `python compile_check.py`.
3. Run a smoke path on a small fixture or dry-run path.
4. Confirm output format is unchanged unless intentionally updated.
5. Confirm the dashboard or other key derived exports still generate as expected.

Preferred smoke path:

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

For docs and planning changes:

- verify root docs do not contradict each other
- verify `OSS_SCOPE.md` and `DEPENDENCY_POLICY.md` match the current planning layer
- verify `specs/architecture-boundaries.md` matches the current planning layer and roadmap sequencing
- verify `docs/` terminology matches the current planning layer
- verify active specs and roadmap sequencing do not drift

Every behavior change should include one of:

- an updated test
- a new focused test
- a short manual validation note explaining why automated coverage was not added

Evidence rules:

- Do not say "validated" unless you list the exact commands actually run.
- Do not say "repo is clean" unless you checked `git status --short`.
- Do not say "aligned with docs" unless you updated the relevant docs or explicitly confirmed no doc changes were needed.
- Do not say "ready for the next topic" unless the current handoff is documented clearly enough for continuation.

For substantial sprint closure or repo-alignment work:

- update `AUDIT.md` with what changed, what was validated, what remains open, and any deviations from plan
- update `AGENT_STATUS.md` with the big picture, current topic state, and the next clean handoff point
- re-run `git status --short`
- state whether the repo is sync-ready or not sync-ready, and why

## Escalate instead of guessing when

- business rules are unclear
- pipeline semantics would materially change
- model cost would materially change
- the request implies recruiter-product or ATS scope
- repo state is too unclear to proceed safely
- required validation cannot be run
- docs and code disagree in a way that needs user or product clarification
- the change would blur the OSS/public boundary and a later private/commercial layer
