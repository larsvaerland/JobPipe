# Legacy Architecture Plan Redirect

Last updated: 2026-04-20

This filename exists as a compatibility redirect for historical references recovered from the older `agentic_jobpilot` worktree.

It is not the primary architecture note for current `Jobpipe`.

## Use these current files instead

- [architecture.md](architecture.md)
  - current runtime shape, package-slice direction, and boundary rules
- [../MASTER_PLAN.md](../MASTER_PLAN.md)
  - canonical planning source of truth
- [../OSS_SCOPE.md](../OSS_SCOPE.md)
  - current public/OSS scope boundary
- [../DEPENDENCY_POLICY.md](../DEPENDENCY_POLICY.md)
  - dependency and license direction
- [../specs/architecture-boundaries.md](../specs/architecture-boundaries.md)
  - target public boundary model

## Historical note

Older references to `docs/architecture-plan.md` usually came from a dashboard/apply-flow-heavy planning phase in `agentic_jobpilot`.

Current `Jobpipe` intentionally centers:
- the primary DB as canonical state
- dashboards and external tools as projections
- the public CLI/runtime/model/decision/projections boundary model

If an older note conflicts with [architecture.md](architecture.md), prefer the current `Jobpipe` docs.
