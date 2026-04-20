# Artifacts and Exports

## Purpose

JobPipe keeps a structured artifact trail so evaluation decisions stay inspectable.

Artifacts and exports are not accidental byproducts. They are part of the product's trust model.

## Canonical terminology

The canonical naming direction is:

- `artifacts/` for per-run trace outputs
- `exports/` for derived dashboard/reporting outputs
- `documents/` for generated candidate-facing material

The repo still contains legacy `out_runs/` and `reports/` naming in places. Treat those as transitional runtime names during cleanup, not as the long-term model.

## Main artifact families

### Run artifacts

Per-job stage outputs belong conceptually under:

```text
artifacts/runs/<run_id>/<job_id>/
```

Typical files in the current stage order:

```text
00_input.json
01_triage.json
02_parsed.json
03_profile_match.json
04_pivot.json
05_moderator.json
06_application_pack.json
```

If `reverse_triage` is enabled, numbering shifts for that run.

### Canonical DB

`jobpipe.sqlite` is the canonical state layer for:

- candidate state
- application events and summaries
- latest evaluations
- run history
- suggestion leads
- generated document metadata

### Derived exports

Derived exports belong conceptually under:

- `exports/dashboard.html`
- `exports/dashboard_data.json`
- `exports/evaluations_latest.csv`

### Generated documents

Generated application material should live under the documents root, while metadata is indexed into the primary DB.

## Why this matters

The artifact model should make it easy to answer:

- why did this job get skipped?
- what changed between runs?
- what document was generated for this job?
- what exactly did the model output at each stage?

That is materially better than a pipeline that emits only a final label.

## Planning implication

The cleanup path is:

1. preserve artifact traceability
2. separate generated outputs from code/templates
3. externalize runtime outputs under `JOBPIPE_DATA_DIR`
4. normalize naming around `artifacts/`, `exports/`, and `documents/`
