# Current Change

This file is an optional scoped-change scaffold.

It is **not** the canonical planning source of truth for the repository.

Use the planning hierarchy in this order:

1. `MASTER_PLAN.md`
2. `PRODUCT_VISION.md`
3. `ROADMAP.md`
4. `docs/`
5. relevant active `specs/`

Only use this file when a specific change needs a temporary working contract for:

- one concrete goal
- a narrow allowed file set
- explicit acceptance criteria
- explicit validation steps

If this file is blank or stale, ignore it and follow the canonical planning documents instead.

---

## Goal

Close the immediate trustworthiness gap on the active `codex/job-catalog-foundation` branch by making the canonical smoke path (`python -m jobpipe.cli.main run --dry-run --no-open`) complete reliably, or by narrowing and documenting an honest bounded smoke contract if the current dry-run path is too broad for reproducible validation.

## Why

The current worktree still contains coherent active sprint work across `jobpipe/runtime`, `jobpipe/model`, `jobpipe/decision`, `jobpipe/projections`, `jobpipe/connectors/mail`, the canonical CLI entrypoint, and related docs/tests. That broad branch scope is already documented and should not be reclassified as drift.

The immediate blocker is validation honesty:

- compile check passes
- focused boundary-slice tests pass
- `export-dashboard` and `inspect-db` pass
- the canonical one-shot smoke path currently times out in the local setup

Until that gap is closed, the branch is not in a trustworthy continuation state and should not be treated as sprint-complete.

## Current sprint

### Sprint 1. Branch trustworthiness closure

#### Topic 1. Canonical dry-run closure

- trace where `jobpipe run --dry-run --no-open` stalls
- classify the cause:
  - real hang/regression
  - oversized or unstable local input path
  - missing bounded fixture/smoke contract
- make the smallest in-scope fix in:
  - `jobpipe/cli/`
  - `jobpipe/runtime/`
  - `jobpipe/model/`
  - `jobpipe/decision/`
  - `jobpipe/projections/`
  - `jobpipe/connectors/mail/`
  - related tests/docs

#### Topic 2. Runtime fallback hygiene

- keep repo-local fallback runtime data from appearing as ambiguous worktree drift
- preserve `JOBPIPE_DATA_DIR` as the preferred truth
- keep repo-local fallback behavior compatibility-only

#### Topic 3. Branch closure notes

- update `AUDIT.md`
- update `AGENT_STATUS.md`
- re-run `git status --short`
- state sync-ready or not sync-ready explicitly

## Allowed files

- `.gitignore`
- `AUDIT.md`
- `AGENT_STATUS.md`
- `specs/current-change.md`
- files under:
  - `jobpipe/runtime/`
  - `jobpipe/model/`
  - `jobpipe/decision/`
  - `jobpipe/projections/`
  - `jobpipe/connectors/mail/`
  - `jobpipe/cli/` when the change is required to keep the canonical `jobpipe` entrypoint or thin orchestration aligned with those slices
  - `tests/` covering the touched boundary slices
  - current canonical docs/specs when needed to keep the branch contract, runtime guidance, and architecture notes aligned with the implementation

## Not allowed

- No unrelated refactor
- No dependency changes
- No scope expansion beyond the active architecture-boundary pass
- No discard or rewrite of active branch implementation
- No deletion or move of local folders
- No deletion or archive of GitHub repos
- No prototype intake work beyond keeping `prototype/` out of git
- No sibling-repo changes unless a later scoped contract explicitly requires them
- No broad product-surface expansion outside runtime/model/decision/projections/mail/CLI boundary cleanup

## Acceptance criteria

- the active scoped contract describes the immediate trustworthiness sprint rather than a generic alignment pass
- `python -m jobpipe.cli.main run --dry-run --no-open` either:
  - completes successfully, or
  - is replaced by a narrower documented smoke contract that is honest, bounded, and reproducible
- any fix stays inside the active architecture-boundary slices and does not widen scope
- `prototype/` remains out of git
- local handoff notes classify the dirty tree as active sprint work and call out the remaining validation state honestly
- repo-hygiene work stays minimal and does not disturb the in-flight runtime-foundation implementation

## Validation

- verify `git status --short` reflects the same active-sprint story after the trustworthiness pass
- verify `prototype/` no longer appears as untracked work
- verify the updated scoped contract and local handoff notes agree on branch scope
- verify the canonical planning/docs layer still points to the same architecture-boundary sequence:
  - `MASTER_PLAN.md`
  - `ROADMAP.md`
  - `docs/architecture.md`
  - `specs/architecture-boundaries.md`
- when code changes are made inside this branch scope, also run:
  - the most relevant targeted tests for the touched slices
  - `python compile_check.py`
  - `python -m jobpipe.cli.main run --dry-run --no-open` or the explicitly documented bounded replacement smoke path if that contract changes
