# JobSync Purge — Research + Prep

**Date:** 2026-04-23
**Owner:** Coordinator (research) → Lars (confirm) → TBD (execute)
**Status:** Research-only. **No destructive action permitted until Lars signs off on §4 checklist.**
**Escalation gates tripped:** destructive data op + pipeline semantics + cross-repo state (JobSync upstream).

---

## 1. Why this exists

Before the staged NAV ingest (100 → 500 → full feed), old jobs must be purged from both
sides of the seam so triage calibration and dedup stats are not contaminated by legacy
data.

JobPipe-side purge is documented (`docs/cli.md` → `jobpipe reset-runtime`, archive-based,
reversible). **JobSync-side purge is not documented anywhere.** This execplan closes
that gap.

---

## 2. What we know

From `specs/jobsync-integration-seam.md`:

- JobSync is a self-hosted Next.js v1.1.10 app, runs locally at `http://localhost:3737`
  via Docker.
- Surfaces: application tracker, decision board, tasks/activities, cover letter + resume
  attached per job.
- State direction: JobPipe writes `application_case_projections` via
  `export-jobsync` → `jobsync_cases.json`. JobSync emits status events back via
  `record-jobsync-event`.
- Repo is an upstream fork — JobSync owns its own DB. JobPipe does not manage JobSync
  schema.

Seam CLIs in JobPipe:

| CLI | Direction | Effect |
|---|---|---|
| `export-jobsync` | JobPipe → JobSync | Writes `jobsync_cases.json` projection |
| `record-jobsync-event` | JobSync → JobPipe | Records one status event back into canonical DB |

---

## 3. Open questions (must answer before writing the procedure)

These require access to the JobSync repo. Coordinator cannot answer from this worktree.

1. **Storage layer.** What DB does JobSync use (Postgres? SQLite? Docker volume?)
   and where does it live on disk?
2. **Table inventory.** What tables hold job data? Typical candidates:
   - `applications` / `jobs` / `job_records`
   - `status_events` / `application_status_history`
   - `tasks` / `activities`
   - `documents` / `attachments` (cover letters, resumes)
   - `decisions` / `notes`
3. **What to wipe vs. preserve.**
   - **Wipe:** application records, status history, tasks/activities tied to jobs,
     per-job documents.
   - **Preserve:** user/auth config, UI preferences, any cross-run candidate settings,
     Docker volume config.
4. **Cross-reference integrity.** JobPipe stores `jobsync_event_id` or similar FK
   back-references in its canonical DB. If JobSync is wiped, do any JobPipe rows become
   orphaned pointers? (`jobpipe reset-runtime` in the same window makes this moot, but
   confirm.)
5. **Backup mechanism.**
   - Docker volume snapshot?
   - SQL dump (`pg_dump` / `sqlite3 .dump`)?
   - File-level copy of the volume mount?
6. **Execution primitive.**
   - Is there a JobSync CLI / admin endpoint for a bulk purge?
   - Or is it DB-level SQL (`DELETE FROM ...` / `TRUNCATE`)?
   - Or "delete the Docker volume and let the container rebuild schema on restart"?
7. **Rebuild verification.** After purge + restart, what's the smallest sanity check
   that JobSync is healthy and empty (row counts, UI load at localhost:3737)?

---

## 4. Safety checklist (MUST be green before any destructive action)

- [ ] All open questions in §3 answered and recorded in this doc.
- [ ] Backup taken: method + path documented here.
- [ ] Restore procedure written and smoke-tested (restore to a sandbox, confirm UI
      loads, confirm at least one application record is visible).
- [ ] JobPipe-side purge (`jobpipe reset-runtime --tag pre_new_cv_<YYYYMMDD>`)
      coordinated to happen in the same window so no orphaned FKs remain.
- [ ] Lars explicitly signs off in writing (chat or commit message) that the wipe
      can proceed.
- [ ] If purge is SQL-based: a dry-run `SELECT COUNT(*)` confirming row counts match
      expectations before running `DELETE`.

---

## 5. Procedure (FILL IN AFTER §3 + §4)

To be written after research answers §3 and safety checklist §4 is green.
Structure placeholder:

```
1. Stop JobSync container
2. Snapshot backup: <exact command>
3. Execute purge: <exact command(s)>
4. Restart container
5. Verify empty state: <exact command>
6. Verify UI loads at http://localhost:3737
7. Record tag + timestamp in docs/current-state.json
```

---

## 6. Rollback

Rollback path depends on backup mechanism chosen in §3 (Q5). Must be written
before execution. At minimum:

- Command to stop JobSync
- Command to restore the backup
- Command to restart JobSync
- Verification that pre-wipe row counts are restored

---

## 7. Success criteria

- JobSync UI loads at `http://localhost:3737` after purge.
- All job/application/status tables are empty (or contain only seed rows if seeded
  on schema init).
- JobPipe canonical DB no longer references jobsync event IDs that point at
  deleted JobSync rows (or those rows are tolerated as historical).
- Fresh `export-jobsync` run produces an empty `jobsync_cases.json` (or one
  reflecting only post-purge state).

---

## 8. Not in scope here

- Automatic purge scheduling.
- Admin UI for selective purge.
- Any change to the JobSync repo itself beyond recording the procedure used.

Those belong in a follow-up backlog item if the purge is expected to repeat.
