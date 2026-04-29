CONTEXT
- Task: #127
- Governing spec(s): [docs/execplans/sprint-3-canonical-application-loop-hardening.md](C:/Users/larsv/Jobpipe-codex-v2/docs/execplans/sprint-3-canonical-application-loop-hardening.md), [docs/deprecation-map.md](C:/Users/larsv/Jobpipe-codex-v2/docs/deprecation-map.md), [docs/ai-playbook.md](C:/Users/larsv/Jobpipe-codex-v2/docs/ai-playbook.md)
- GitHub Project item: Linked: #127
- Branch: `codex/127-sync-bridge-hardening`
- Base: `main`

GOAL
- Thin `jobpipe/cli/sync_evaluations.py::mirror_to_primary_db()` so it no longer owns every canonical sync bridge concern inline, while preserving existing DB and decision/monitoring persistence behavior.

IN SCOPE
- [jobpipe/cli/sync_evaluations.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/cli/sync_evaluations.py)
- [tests/test_sync_evaluations_primary_db.py](C:/Users/larsv/Jobpipe-codex-v2/tests/test_sync_evaluations_primary_db.py)
- One additional helper module only if it keeps the diff clearer and still narrow

OUT OF SCOPE (explicit no-go list)
- [jobpipe/stages/application_pack.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/stages/application_pack.py)
- DB schema changes
- connector changes
- dashboard/projection changes
- prompt/content-quality work
- CrewAI runtime work
- broad refactor of unrelated CLI or decision modules

CONSTRAINTS
- Preserve current persistence semantics for:
  - `upsert_job_replay_input`
  - `upsert_job_evaluation`
  - `persist_job_decision_state`
  - `persist_monitoring_state`
  - `upsert_job_run_event`
- Keep the change small and reversible.
- Prefer helper extraction over architectural invention.
- Do not change canonical row shape unless a test proves the old shape was wrong.
- Respect the Windows pytest workaround in `docs/ai-playbook.md`.

ACCEPTANCE CRITERIA
- `mirror_to_primary_db()` no longer assembles and persists every bridge concern inline.
- Helper ownership is explicit and traceable in code.
- [tests/test_sync_evaluations_primary_db.py](C:/Users/larsv/Jobpipe-codex-v2/tests/test_sync_evaluations_primary_db.py) passes.
- `python compile_check.py` succeeds.
- No unrelated files are touched.

VALIDATION COMMANDS (run exactly these)
- `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_sync_evaluations_primary_db.py -q -p no:debugging -p no:cacheprovider --basetemp "$env:TEMP\\jobpipe-pytest-sync-bridge"`
- `python compile_check.py`

ESCALATION GATES
- Stop and ask the coordinator before:
  - introducing a new dependency
  - changing DB schema or persistence contract shape
  - changing pipeline semantics or decision/monitoring meaning
  - moving canonical ownership into external-tool-specific shapes
  - broadening the slice beyond the sync bridge seam
- Stop and ask before any Approval Gate from [docs/ai-playbook.md](C:/Users/larsv/Jobpipe-codex-v2/docs/ai-playbook.md) §Approval Gates.

DELIVERABLE
- One commit on branch `codex/127-sync-bridge-hardening`
- PR into `main`, linked to `#127`
- Report:
  - commands run
  - test output
  - files touched
  - whether the final shape stayed file-local or introduced one new helper module
