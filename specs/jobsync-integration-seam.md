# JobSync Integration Seam

**Date:** 2026-04-19  
**Updated:** 2026-04-22 — reflects actual implemented state  
**Status:** Seam is live. Both sides have working code. Manual write-back loop.

---

## What JobSync is

JobSync is a self-hosted Next.js (v1.1.10) job-search companion app, running locally at `http://localhost:3737` via Docker. It provides:

- **Application tracker** — job list with status, applied date, due date, source, cover letter + resume attached per job
- **Decision board / dashboard** — activity metrics, pipeline statistics, search progress visualisation
- **Task and activity management** — tasks and activities linked to jobs with time tracking
- **AI capabilities** — resume review, job-match scoring (supports Ollama locally, OpenAI, Gemini, DeepSeek, OpenRouter via settings UI)
- **Automation engine** — scheduled job discovery via jsearch board with keyword matching, match threshold, deduplication, and accept/dismiss workflow
- **Resume and cover letter storage** — variants stored and linked per job
- **Notes and questions** per job

JobSync is candidate-facing. JobPipe is the decision engine. The seam is narrow and deliberate.

---

## Architectural rule (unchanged)

- `JobPipe` owns canonical decision state, claims, evaluation logic, evidence, and narrative semantics.
- `JobSync` consumes bounded projections and emits bounded workflow events back.
- Neither repo knows the other's internal architecture.

---

## What is actually built

### JobPipe side

| Component | Location | What it does |
|---|---|---|
| `export-jobsync` CLI | `jobpipe/cli/export_jobsync.py` | Reads canonical DB + artifact runs, builds `application_case_projections`, writes `jobsync_cases.json` |
| `record-jobsync-event` CLI | `jobpipe/cli/record_jobsync_event.py` | Records one `JobSyncApplicationStatusEvent` back into canonical DB |
| Projection builders | `jobpipe/projections/jobsync.py` | `build_jobsync_job_summary`, `build_jobsync_decision_brief`, `build_jobsync_document_refs`, `build_jobsync_application_case_projection/s` |
| Model | `jobpipe/model/` | `JobSyncApplicationStatusEvent` |
| Runtime helper | `jobpipe/runtime/` | `record_jobsync_application_status_event()` |

Default export filter: `APPLY_STRONGLY`, `APPLY`, `REVIEW_HIGH`, `REVIEW_LOW`. Can be overridden per job or decision type via CLI flags.

### JobSync side

| Endpoint | Method | Accepts | What it does |
|---|---|---|---|
| `/api/integrations/jobpipe/jobs` | POST | `ExternalJobsImportEnvelope` (kind: `curated_jobs_import`) | Imports curated APPLY-decision jobs into JobSync tracker |
| `/api/integrations/jobpipe/authoring` | POST | `ExternalAuthoringSyncEnvelope` (kind: `authoring_sync`) | Syncs generated document refs (CV, cover letter, screening answers) per job |
| `/api/jobs/export` | POST | — | Streams tracked jobs as CSV |

Authentication: `X-JobPipe-Token` header must match `JOBSYNC_SYNC_TOKEN` env var in JobSync.

---

## Contract types (source of truth: `jobsync/src/lib/external-jobs.ts`)

### Outbound from JobPipe → JobSync: `ExternalJobsImportEnvelope`

```typescript
ExternalJobsImportEnvelope {
  contractVersion?: string
  producer?: string          // "jobpipe"
  kind?: string              // "curated_jobs_import"
  sentAt?: string
  userEmail?: string
  jobs?: ExternalJobImportRecord[]
}

ExternalJobImportRecord {
  externalSource: string     // "jobpipe"
  externalId: string         // canonical job_id
  title: string
  company: string
  location?: string
  jobUrl?: string
  applicationUrl?: string
  description?: string
  jobSource?: string
  status?: string
  decision?: string          // "APPLY", "APPLY_STRONGLY", etc.
  fitScore?: number | null
  pivotScore?: number | null
  triageExplanation?: string
  decisionBrief?: Record<string, unknown>
  artifactPlan?: Record<string, unknown>
  applicationCaseProjection?: Record<string, unknown>
  applicationPacket?: Record<string, unknown>
  updatedAt?: string
}
```

JobSync stores full `externalData` blob per job (decision brief, scores, artifact plan, application packet) and surfaces decision context in the tracker.

### Authoring sync: `ExternalAuthoringSyncEnvelope`

```typescript
ExternalAuthoringSyncEnvelope {
  kind: "authoring_sync"
  authoring?: ExternalAuthoringSyncRecord[]
}

ExternalAuthoringSyncRecord {
  externalSource: string
  externalId: string         // canonical job_id
  workspaceUrl?: string
  applySessionUrl?: string
  authoringState?: {
    resume?: ExternalAuthoringSection
    coverLetter?: ExternalAuthoringSection
    screeningAnswers?: ExternalAuthoringSection
  }
}

ExternalAuthoringSection {
  variantRef?: string
  documentRef?: string
  exportPdfPath?: string
  exportJsonPath?: string
  exportDocxPath?: string
  artifactRefs?: Array<Record<string, unknown>>
}
```

### Write-back from JobSync → JobPipe: `JobSyncApplicationStatusEvent`

Recorded via `record-jobsync-event` CLI:

```
jobpipe record-jobsync-event <job_id> <event_type> [--notes "..."] [--event-at ISO8601] [--metadata-json {...}]
```

Event types: `applied`, `interviewed`, `rejected`, `offer`, `withdrawn`, etc. (bounded by canonical `application_events` model).

---

## How the loop works today

```
JobPipe DB (APPLY decisions)
  ↓
jobpipe export-jobsync         → jobsync_cases.json
  ↓
POST /api/integrations/jobpipe/jobs  (with X-JobPipe-Token)
  ↓
JobSync tracker shows curated jobs with decision context
  ↓
User works the jobs in JobSync (track, note, attach docs, apply)
  ↓
POST /api/integrations/jobpipe/authoring  (after author-package run)
  ↓
JobSync shows linked CV/cover letter per job
  ↓
User clicks Apply in JobSync
  ↓
[manual today] jobpipe record-jobsync-event <job_id> applied
  ↓
Canonical application_events in JobPipe DB
```

---

## What is NOT automatic yet

The write-back from JobSync → JobPipe on "Apply" is manual today. JobSync does not currently push a webhook or call back to JobPipe when a user marks a job as applied. The `record-jobsync-event` CLI closes the loop but must be invoked manually.

Options for making this automatic:
1. JobSync automation plugin that POSTs to a JobPipe local HTTP endpoint on status change
2. JobPipe polling the JobSync `/api/jobs/export` CSV and diffing status changes
3. A thin jobpipe-mcp-server that JobSync can call as a tool (Sprint 4 candidate)

The current manual pattern is acceptable for a single-user local setup. Automation is a Sprint 4+ item.

---

## Boundary rules (unchanged)

`jobsync` should never be required to understand:
- `job_claims`, `job_selection_signals`, `job_selection_assessments`
- `candidate_evidence_units`, `candidate_narrative_profiles`
- `job_narrative_assessments`

Thin projections of those concepts may be displayed. Canonical ownership stays in JobPipe.

---

## Non-goals

- Shared DB or schema
- Repo merge or coupled imports
- JobSync as canonical decision store
- JobPipe depending on JobSync UI/process assumptions

---

## Success criteria

- JobSync shows the right jobs with the right compact decision context ✓
- Status changes can flow back into canonical JobPipe state (manually today, automatic later)
- Document usage can be traced without making JobSync the canonical document store (authoring sync endpoint exists)
- Neither repo knows the other's internal architecture ✓
