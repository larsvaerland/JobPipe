# Legacy Dashboard Spec Redirect

Last updated: 2026-04-20

This filename exists as a compatibility redirect for historical references recovered from:
- `C:\Users\larsv\agentic_jobpilot`
- older local `AGENT_STATUS.md` / `AUDIT.md` entries

It is not the primary dashboard contract file for the current `Jobpipe` repo.

## Use these current files instead

- [docs/dashboard.md](docs/dashboard.md)
  - current dashboard purpose, export model, and UX rules
- [docs/public-loop-test-howto.md](docs/public-loop-test-howto.md)
  - current step-by-step manual validation path
- [TESTING.md](TESTING.md)
  - current validation rules
- [docs/cli.md](docs/cli.md)
  - current CLI/export commands
- [docs/architecture.md](docs/architecture.md)
  - current runtime and boundary model

## Why this redirect exists

The separate `agentic_jobpilot` worktree had a broader dashboard/apply-session/server contract that included:
- `jobpipe.cli.dashboard_server`
- apply-session manifests
- local interactive server flows

Those are not the canonical runtime surface of the current `Jobpipe` repo.

In current `Jobpipe`:
- the primary DB is the system of record
- the canonical operator interface is `jobpipe` / `python -m jobpipe.cli.main`
- dashboard validation is based on static export, not a required local dashboard server

If an older note tells you to read `DASHBOARD_SPEC.md`, read [docs/dashboard.md](docs/dashboard.md) first and treat any `dashboard_server` or apply-session references as historical unless current code and docs explicitly restore them.
