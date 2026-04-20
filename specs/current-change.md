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

The latest completed scoped sprint on `codex/job-catalog-foundation` is the bounded post-refactor baseline-rebuild slice for:

- Sprint 6 Topic 13: explicit runtime archive/reset seam for safe fresh-baseline rebuilds
- Sprint 6 Topic 14: live bounded baseline rebuild on `JOBPIPE_DATA_DIR`

Completed on 2026-04-20 with this evidence:

- `python -m pytest tests/test_reset_runtime_cli.py tests/test_main_cli.py tests/test_bootstrap_state_db.py -q` -> `8 passed in 0.28s`
- `python compile_check.py` -> `OK — 71 files parsed cleanly`
- `python -m jobpipe.cli.main reset-runtime --tag sprint6_post_refactor_baseline` -> archived `12` runtime paths and restored `db/application_state.json`
- `python -m jobpipe.cli.main bootstrap-state-db` -> restored candidate/profile state into a fresh schema v8 DB (`Events stored: 4`, `Jobs tracked: 4`)
- `python -m jobpipe.cli.main inspect-db --show summary` -> confirmed fresh baseline state (`jobs=0`, `source_records=0`, `evaluations=0`, `application statuses: applied=2 / interview=1 / rejected=1`)
- attempted `python -m jobpipe.cli.main drain-queue --reset-state --no-skip-processed --overwrite --batch-size 100` on the fresh baseline, but stopped after the operator clarified that a 9k+ NAV queue rebuild is not the right validation surface now
- `python -m jobpipe.cli.main reset-runtime --tag sprint6_bounded_baseline` -> re-cleared the partial ingest attempt and restored `db/application_state.json`
- `python -m jobpipe.cli.main bootstrap-state-db` -> rebuilt the bounded fresh baseline again
- `python -m jobpipe.cli.main run --dry-run --no-open` -> OK (`Events scanned: 0; Unique jobs (latest): 0; 0 jobs / 0 actionable / 0 tracked`)

Tracked code/docs aligned with that closure:

- `jobpipe/cli/reset_runtime.py`
- `jobpipe/cli/main.py`
- `tests/test_reset_runtime_cli.py`
- `tests/test_main_cli.py`
- `docs/cli.md`
- `docs/configuration.md`

Outcome summary:

- the repo now has an explicit audited runtime-reset seam instead of relying on ad hoc manual DB deletion
- the command archives generated runtime state under `JOBPIPE_DATA_DIR/_archives/<tag>/` and preserves candidate inputs, secrets, and audit outputs
- the live `JobpipeData` baseline can now be rebuilt cleanly from preserved candidate inputs plus `bootstrap-state-db`
- the live baseline is now intentionally bounded and empty of repulled queue/catalog state until a deliberate later full ingest is run
- a large NAV queue rebuild is explicitly deferred; it is not part of normal smoke validation and should happen later when the app/intake path is ready
- monitoring/noise and remaining persona hardening stay open as future product work on top of a cleaner runtime baseline

The previous completed sprint was the bounded moderator/projection hardening slice for:

- Sprint 5 Topic 11: candidate-aware moderator demotion for weak-fit off-anchor product-leadership reviews
- Sprint 5 Topic 12: dashboard payload preservation of persisted `final_decision` for persona-audit correctness

Completed on 2026-04-20 with this evidence:

- `python -m pytest tests/test_moderate.py tests/test_export_dashboard_app_state.py tests/test_persona_audit.py -q` -> `41 passed in 0.62s`
- `python -m pytest tests/ -q` -> `195 passed in 5.28s`
- `python compile_check.py` -> `OK — 70 files parsed cleanly`
- `python -m jobpipe.cli.main run --dry-run --no-open` -> OK (`Events scanned: 749; Unique jobs (latest): 748; 871 jobs / 24 actionable / 1 tracked`)
- `python -m jobpipe.cli.persona_audit` -> latest audit root `C:\Users\larsv\JobpipeData\audit\public_oss_persona_audit_20260420_181802`

Tracked code/docs aligned with that closure:

- `jobpipe/stages/moderate.py`
- `jobpipe/projections/dashboard.py`
- `tests/test_moderate.py`
- `tests/test_export_dashboard_app_state.py`
- `specs/persona-audit-findings-2026-04-17.md`

Outcome summary:

- the early-adjacent persona now pushes all three product-leadership roles to `SKIP`
- the dashboard/persona-audit projection now preserves persisted candidate-aware `final_decision` values instead of silently reclassifying them from thresholds alone
- the public-transition persona still keeps `Produktleder for sentrale backend-tjenester` and `Head of Enterprise Architecture` in `REVIEW_LOW`
- monitoring/watchlist noise remains open and should be handled as its own next slice rather than being inferred from projection quirks

## Next handoff

Until a new scoped contract is written, use the canonical planning docs directly:

- `MASTER_PLAN.md`
- `PRODUCT_VISION.md`
- `ROADMAP.md`
- active specs under `specs/`

Write a new scoped contract here only when the next change needs a narrow temporary execution contract.
