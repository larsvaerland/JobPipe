# Dashboard

## Purpose

The dashboard is the candidate-facing decision surface.

It should behave like a focused decision workbench export, not a generic analytics console.

It should answer:

1. Which jobs am I actually competitive for right now?
2. Why were these jobs prioritized over other plausible-looking roles?
3. What already happened for each job, and what do I need to do next?
4. What changed since the last review that deserves attention now?

## Data sources

The dashboard export reads from canonical state in the primary DB, including:

- `job_evaluations`
- `job_run_events`
- `application_summary`
- `application_events`
- `generated_documents`

Over time it should also surface richer decision support from:

- job claims
- hiring-side selection assessments
- candidate narrative assessments
- watchlists and change events

## Export shape

Canonical export naming should move toward:

- `exports/dashboard.html`
- `exports/dashboard_data.json`

Legacy `reports/dashboard.*` naming may still exist during transition.

## Core views

### Action list

The default view should surface jobs with:

- `APPLY_STRONGLY`
- `APPLY`
- `REVIEW_HIGH`
- plus any job already moved into an explicit user process state such as shortlisted, applied, interview, rejected, or dismissed

The most important fields are:

- title
- employer
- final decision
- location
- deadline
- current application status

The current public `Now` page should behave as a two-pane action queue:

- the left side is the queue
- the right side is the selected-job detail pane
- row selection should not force the list to jump vertically
- one compact search field should control the page
- six compact quick filters should sit directly under the main tab bar:
  - `All`
  - `Apply`
  - `Review`
  - `Expiring`
  - `Applied`
  - `Fresh`

### Decision detail

For a selected job, the dashboard should eventually show:

- triage explanation and signals
- score and decision breakdown
- claims or decision factors that mattered most
- evidence for why the role is winnable, adjacent, or fragile
- generated documents
- application timeline

### Monitoring view

The dashboard should make it easy to inspect:

- expiring-soon jobs
- recent run volume
- skip-reason patterns
- source-quality issues
- watchlist changes and material deltas

## Design rules

1. Actionability first.
2. Show why the role is competitive, not just that it scored well.
3. Prefer compact explanations over raw metric volume.
4. Keep history available without making the default view noisy.
5. Reflect the primary DB as the system of record.

## Current implementation notes

- export is static HTML, not a live web app
- canonical dashboard projection logic now lives in `jobpipe.projections.dashboard`
- `jobpipe.cli.export_dashboard` is the thin CLI wrapper over that projection surface
- application state is merged from the primary DB
- generated document metadata is included in the export payload
- dashboard payload rows now include deterministic `watchlists` and `change_events`
- dashboard payload now also includes a deterministic candidate-local `calibration_summary` and per-job `job_calibration_assessment`
- evaluated jobs without fit/pivot scores now carry explicit `no_score_reason` labels so skip/review rows stay inspectable
- the global top header should stay minimal; the JobPipe logo is enough
- the current `Now` view uses a selected-row detail pane on the right instead of inline unfolding
- the current static export offers browser-local note drafts for quick review notes
- manual status actions currently copy the local CLI command and optimistically update the queue view; the primary DB remains the canonical state after the command is run
- for the current manual validation path, use [public-loop-test-howto.md](public-loop-test-howto.md)

## Future direction

The next useful dashboard improvements are:

- better source-quality visibility
- clearer advantageous-match signals
- better handling of expiring jobs
- tighter presentation of application-state milestones
- stronger presentation of non-obvious but high-probability role matches
- better surfacing of hiring-side selection risk and mitigation moves
- living monitoring views based on watchlists and change events
