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

## Status

No active scoped contract is open right now.

The latest completed scoped sprint on `codex/job-catalog-foundation` was the bounded public-transition hardening slice for:

- Sprint 4 Topic 9: candidate-aware target-title safety
- Sprint 4 Topic 10: focused persona-audit evidence refresh

Completed on 2026-04-20 with this evidence:

- `python -m pytest tests/test_triage_target_safety.py tests/test_geo_filter.py -q` -> `32 passed in 2.55s`
- `python -m pytest tests/ -q` -> `191 passed in 5.96s`
- `python compile_check.py` -> `OK — 70 files parsed cleanly`
- `python -m jobpipe.cli.main run --dry-run --no-open` -> OK (`Events scanned: 749; Unique jobs (latest): 748; 871 jobs / 24 actionable / 1 tracked`)
- `python -m jobpipe.cli.persona_audit` -> latest audit root `C:\Users\larsv\JobpipeData\audit\public_oss_persona_audit_20260420_174339`

Tracked code/docs aligned with that closure:

- `jobpipe/stages/triage.py`
- `tests/test_triage_target_safety.py`
- `specs/persona-audit-findings-2026-04-17.md`

## Next handoff

Until a new scoped contract is written, use the canonical planning docs directly:

- `MASTER_PLAN.md`
- `PRODUCT_VISION.md`
- `ROADMAP.md`
- active specs under `specs/`

Write a new scoped contract here only when the next change needs a narrow temporary execution contract.
