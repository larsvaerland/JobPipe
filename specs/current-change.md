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

The previous scoped contract in this file was the earlier branch-trustworthiness sprint and is now complete.

The latest completed scoped sprint on `codex/job-catalog-foundation` was the bounded public-hardening slice for:

- Sprint 3 Topic 7: persona differentiation hardening
- Sprint 3 Topic 8: monitoring noise reduction

Completed on 2026-04-20 with this evidence:

- `python -m pytest tests/ -q` -> `187 passed`
- `python compile_check.py` -> `OK — 70 files parsed cleanly`
- `python -m jobpipe.cli.main run --dry-run --no-open` -> OK (`Events scanned: 749; Unique jobs (latest): 748; 871 jobs / 24 actionable / 1 tracked`)
- `python -m jobpipe.cli.main inspect-db --show summary` -> live DB reports `Schema version: 8`
- `python -m jobpipe.cli.persona_audit` -> latest audit root `C:\Users\larsv\JobpipeData\audit\public_oss_persona_audit_20260420_165145`

Tracked code/docs aligned with that closure:

- `jobpipe/decision/derive.py`
- `jobpipe/decision/models.py`
- `jobpipe/decision/monitoring.py`
- `jobpipe/decision/persistence.py`
- `jobpipe/projections/dashboard.py`
- `jobpipe/core/primary_db.py`
- `tests/test_decision_context.py`
- `tests/test_monitoring_context.py`
- `specs/persona-audit-findings-2026-04-17.md`

## Next handoff

Until a new scoped contract is written, use the canonical planning docs directly:

- `MASTER_PLAN.md`
- `PRODUCT_VISION.md`
- `ROADMAP.md`
- active specs under `specs/`

Write a new scoped contract here only when the next change needs a narrow temporary execution contract.
