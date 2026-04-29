# Deprecation Map

This file is the first-pass cleanup inventory for transitional and likely-stale paths.

It is not a delete list.

Use it to track:

- why a file still exists
- whether it still has live callers
- what the intended replacement is
- what evidence is needed before removal

Status meanings:

- `keep`: canonical or still clearly needed
- `review-first`: likely transitional; verify callers and validation before changing
- `compat`: keep thin; do not enlarge
- `candidate-delete`: likely removable once callers/usage are proven absent

## Initial inventory

| Path | Current role | Status | Likely replacement / owner | Evidence needed before delete |
|---|---|---|---|---|
| `jobpipe/core/schema.py` | Compatibility import surface retained while `jobpipe/model/schema.py` becomes canonical | compat | `jobpipe/model/schema.py` | Keep until import-compat contract is explicitly retired; compat test exists |
| `jobpipe/core/job_catalog.py` | Compatibility import surface for runtime catalog ownership migration | compat | `jobpipe/runtime/catalog.py` | Keep until import-compat contract is explicitly retired; compat test exists |
| `jobpipe/core/paths.py` | Compatibility import surface for runtime path ownership migration | compat | `jobpipe/runtime/paths.py` | Keep until import-compat contract is explicitly retired; path compat tests exist |
| `jobpipe/core/io.py` | Mixed shared helper surface; file is live, but at least one helper is now unreachable | review-first | split surviving shared helpers by owning runtime/decision surface; remove dead helper(s) separately | Function-level caller audit before editing; do not delete the file wholesale |
| `jobpipe/core/runner.py` | Live orchestration dependency still imported by `jobpipe/cli/run_feed.py` | review-first | thin CLI orchestration + owned runtime helpers | Caller audit confirms live use; any extraction must preserve `run_feed` behavior |
| `jobpipe/cli/run_feed.py` | Main feed entrypoint and live pipeline assembly/orchestration concentration point | review-first | thinner CLI wrapper over a clearer pipeline/runtime boundary | Stage wiring, DB run bookkeeping, and repair logic are still concentrated here; extraction should be a dedicated slice |
| `jobpipe/cli/sync_evaluations.py` | Live bridge from stage artifacts into canonical DB and decision persistence | review-first | thinner CLI wrapper over canonical decision/runtime persistence helpers | Mirror path is still live and couples staged artifacts to DB writes; do not change casually |
| `jobpipe/runtime/catalog.py` | Canonical runtime owner for source normalization and catalog dedupe rules | keep | none; this is the replacement owner already | none before delete; this is active ownership |
| `jobpipe/runtime/paths.py` | Canonical runtime owner for local-first roots, exports, DB, and secrets paths | keep | none; this is the replacement owner already | none before delete; this is active ownership |
| `jobpipe/runtime/jobsync.py` | Canonical runtime write-back seam for JobSync application status events | keep | none; keep thin over canonical DB helpers | none before delete; this is active ownership |
| `jobpipe/runtime/reactive_resume.py` | Canonical runtime write-back seam for Reactive Resume document refs | keep | none; keep thin over canonical DB helpers | none before delete; this is active ownership |
| `jobpipe/stages/reverse_triage.py` | Still-live optional stage referenced by `jobpipe/cli/run_feed.py`, `sync_evaluations.py`, and model schema | review-first | none yet; requires explicit stage-removal decision | Config check + caller audit + schema impact review before any removal |
| `jobpipe/stages/application_pack.py` | Live stage that still mixes orchestration, document generation, and DB/document sync | review-first | thinner stage wrapper over `jobpipe/authoring/`, runtime write-backs, and canonical persistence helpers | `_sync_generated_documents` and rendering path are still live; extraction must preserve package semantics |
| `jobpipe/cli/export_dashboard.py` | Thin wrapper over projection/export path | keep | `jobpipe.projections.dashboard` as owner | none; wrapper is intentional while CLI stays canonical |
| `jobpipe/cli/export_jobsync.py` | Thin wrapper over projection/export path | keep | `jobpipe.projections.jobsync` | none; wrapper is intentional |
| `jobpipe/cli/export_reactive_resume_plan.py` | Thin wrapper over projection/export path | keep | `jobpipe.projections.reactive_resume` | none; wrapper is intentional |
| `jobpipe/compat/__init__.py` | Reserved compat namespace, currently minimal | compat | explicit compatibility shims only | confirm future compat use before adding code |

## Highest-value review targets

Start cleanup review in this order:

1. `jobpipe/cli/run_feed.py`
2. `jobpipe/core/runner.py`
3. `jobpipe/stages/reverse_triage.py`
4. `jobpipe/core/schema.py`
5. `jobpipe/core/job_catalog.py`
6. `jobpipe/core/paths.py`
7. `jobpipe/cli/sync_evaluations.py`
8. `jobpipe/stages/application_pack.py`

Why this order:

- `run_feed.py`, `core/runner.py`, and `reverse_triage.py` form a live orchestration seam that looks more removable than it is
- `core/schema.py`, `core/job_catalog.py`, and `core/paths.py` have explicit compatibility value and test coverage
- `sync_evaluations.py` and `application_pack.py` are the next live bridge surfaces where stage-local behavior still reaches deep into canonical persistence
- several replacements are already named in [docs/architecture.md](C:/Users/larsv/Jobpipe-codex-v2/docs/architecture.md), but removal still requires caller and contract review

## Evidence from first review pass

Confirmed current evidence:

- `jobpipe/core/schema.py` is covered by [tests/test_model_schema_compat.py](C:/Users/larsv/Jobpipe-codex-v2/tests/test_model_schema_compat.py)
- `jobpipe/core/job_catalog.py` is covered by [tests/test_runtime_catalog_compat.py](C:/Users/larsv/Jobpipe-codex-v2/tests/test_runtime_catalog_compat.py)
- `jobpipe/core/paths.py` is still imported directly by [tests/test_paths.py](C:/Users/larsv/Jobpipe-codex-v2/tests/test_paths.py)
- `jobpipe/cli/run_feed.py` still owns stage assembly, DB run bookkeeping, per-job execution, and post-run index repair
- `jobpipe/core/runner.py` is still imported by [jobpipe/cli/run_feed.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/cli/run_feed.py)
- `jobpipe/stages/reverse_triage.py` is still referenced by:
  - [jobpipe/cli/run_feed.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/cli/run_feed.py)
  - [jobpipe/cli/sync_evaluations.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/cli/sync_evaluations.py)
  - [jobpipe/model/schema.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/model/schema.py)

## Evidence from second review pass

Confirmed current evidence:

- `jobpipe/core/schema.py`, `jobpipe/core/job_catalog.py`, and `jobpipe/core/paths.py` are literal re-export shims over canonical owners:
  - [jobpipe/model/schema.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/model/schema.py)
  - [jobpipe/runtime/catalog.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/runtime/catalog.py)
  - [jobpipe/runtime/paths.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/runtime/paths.py)
- `jobpipe/core/io.py` is not dead as a file, but Axon reports `load_profile_pack` as unreachable while other helpers such as `clean` and `now_iso` remain live via broad caller sets.
- `jobpipe/runtime/catalog.py` is the real active owner for catalog dedupe and source normalization and is imported from multiple CLI paths and tests.
- `jobpipe/runtime/paths.py` is the real active owner for runtime roots and is imported broadly across CLI, projections, core helpers, stages, and tests.
- `jobpipe/runtime/jobsync.py` is a thin but live canonical write-back seam called by:
  - [jobpipe/cli/record_jobsync_event.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/cli/record_jobsync_event.py)
  - [tests/test_jobsync_runtime.py](C:/Users/larsv/Jobpipe-codex-v2/tests/test_jobsync_runtime.py)
- `jobpipe/runtime/reactive_resume.py` is a thin but live canonical write-back seam called by:
  - [jobpipe/cli/record_reactive_resume_document.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/cli/record_reactive_resume_document.py)
  - [tests/test_reactive_resume_runtime.py](C:/Users/larsv/Jobpipe-codex-v2/tests/test_reactive_resume_runtime.py)
- `jobpipe/cli/sync_evaluations.py::mirror_to_primary_db` still bridges stage artifacts into:
  - canonical DB upserts in [jobpipe/core/primary_db.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/core/primary_db.py)
  - canonical decision persistence in [jobpipe/decision/persistence.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/decision/persistence.py)
  - monitoring/decision context builders in [jobpipe/decision](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/decision)
- `jobpipe/stages/application_pack.py::_sync_generated_documents` still writes generated-document state through:
  - [jobpipe/core/primary_db.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/core/primary_db.py)
  - [jobpipe/decision/persistence.py](C:/Users/larsv/Jobpipe-codex-v2/jobpipe/decision/persistence.py)
  - stage-local rendering and preview helpers in the same module

Implication:

- the next safe cleanup work is not more broad deletion in `core/`
- it is a bounded extraction review around `sync_evaluations.py` and `application_pack.py`

## Review procedure for each file

Before reclassifying or deleting a file:

1. Check imports and CLI reachability.
2. Check whether tests still reference it directly.
3. Check whether docs/specs still name it as an active path.
4. Run targeted validation after any narrow removal or extraction.
5. Only then move from `review-first` to `candidate-delete` or remove it.

## Explicit non-goal

Do not use this file to justify broad cleanup by intuition.

The purpose is to make cleanup:

- explicit
- reviewable
- reversible
- evidence-backed
