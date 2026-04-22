# Intake Pipeline Inventory

**Date:** 2026-04-22  
**Status:** Reflects implemented state as of Sprint 3 close.

This document describes every source that feeds jobs and status events into the JobPipe canonical pipeline, how deduplication works, and how platform-curated leads are distinguished from manual browsing.

---

## Pipeline overview

```
NAV job board scrape           ──┐
Gmail suggestion scan          ──┤  jobs_delta.jsonl / suggestion queue
FINN Chrome Extension capture  ──┤                ↓
(LinkedIn scrape — future)     ──┘         intake + dedup
                                               ↓
                                      JobPipe canonical DB
                                               ↓
                                   triage / scoring / decision
                                               ↓
                               JobSync export (APPLY / APPLY_STRONGLY / REVIEW)
                                               ↓
                                    user works job in JobSync
                                               ↓
                               Gmail status scan → canonical DB → JobSync update
```

---

## Source 1: NAV job board scrape

**CLI:** `jobpipe pull-nav` (or equivalent scrape entry point)  
**Output:** `jobs_delta.jsonl` → pipeline via `go.ps1`  
**`suggested_by_platform`:** `false` — direct structured source, not algorithm recommendation  

What it does:
- Fetches structured job ads from NAV (Norwegian labor market authority)
- Normalizes to canonical JSONL
- Deduplicates within-run and against the primary DB
- Feeds into the main triage pipeline

Notes:
- NAV is the primary volume source for Norwegian job ads
- Ads include structured metadata (employer, title, location, deadline, description)
- The `pull-finn-ext` Finn scraper supplements NAV when a FINN ad is not already in the DB (see Source 3)

---

## Source 2: Gmail suggestion scan (Finn.no + LinkedIn email leads)

**CLI:** `jobpipe scan-gmail --scan-suggestions`  
**Output:** suggestion queue in canonical DB + `suggested_jobs.jsonl` sidecar  
**`suggested_by_platform`:** `true`

What it does:
- Scans Gmail for FINN "Ledige stillinger" digest emails and LinkedIn "New jobs for you" emails
- Extracts job URLs from each email
- Deduplicates extracted URLs against the primary DB
- Queues new suggestions as canonical job records with `suggested_by_platform=true`

Why `suggested_by_platform=true` matters:

The semantic filter in the triage pipeline would normally kill low-signal or ambiguous leads before LLM triage. Jobs flagged `suggested_by_platform=true` bypass this gate — they are treated as pre-qualified by the platform's AI and candidate profile engine (LinkedIn algorithm or FINN match engine). These leads skip cheap pre-filtering and go directly into full triage.

This is the right tradeoff: LinkedIn and FINN have already run candidate-profile matching against these roles. Treating them like cold scraped ads wastes the signal.

Dedup logic:
- URL-level dedup against primary DB
- Cross-source dedup: a FINN lead arriving by email that already exists from a NAV scrape or Chrome Extension capture is not re-queued

---

## Source 3: FINN Chrome Extension capture

**CLI:** `jobpipe pull-finn-ext`  
**Extension:** local Flask server on port 5071, output at `C:\Users\larsv\projects\Tools\job-hunter-pilot-chrome extension Finn\output\jobs.jsonl`  
**Output:** `jobs_delta.jsonl` → pipeline via `go.ps1`  
**`suggested_by_platform`:** `false`

What it does:
- Chrome Extension captures FINN job ads during active browsing
- Local Flask server receives captures, writes to `jobs.jsonl`
- `pull-finn-ext` reads the JSONL, normalizes to canonical format (`job_id=finn_{finnkode}`), parses Norwegian dates, splits location
- Deduplicates against primary DB
- When a FINN ad is captured that has no existing match in the DB, the scraper fetches the missing structured data from Finn.no

Why `suggested_by_platform=false`:
The user browsed to these ads manually. The Chrome Extension captures what the user already found — it is not an algorithm recommendation. These go through normal triage including semantic filtering.

Key normalization:
- `job_id`: `finn_{finnkode}` — stable canonical ID
- Norwegian date parsing for deadlines and posted dates
- Location split: city / region / remote

---

## Source 4: LinkedIn scraping (future)

**Status:** Not yet implemented. Planned as a later intake source.

When implemented, LinkedIn job ads found via direct browsing or structured scraping would follow the same pattern as FINN Chrome Extension: `suggested_by_platform=false`, normal triage pipeline.

LinkedIn algorithm-recommended leads already arrive via Gmail suggestion scan (Source 2) with `suggested_by_platform=true`.

MCP + crewAI is a candidate architecture for LinkedIn integration — LinkedIn's API restrictions make scraping sensitive; a browser-based MCP approach may be more maintainable.

---

## Deduplication logic

Dedup runs at multiple levels:

| Level | What it checks | Where |
|---|---|---|
| Within-run | Duplicate entries in the same batch | `pull-*` normalizers |
| Against primary DB | `job_id` or URL match against canonical jobs table | `pull-*` normalizers |
| Cross-source | Same job appearing from multiple sources (NAV + FINN email + Chrome ext) | DB-level, canonical job_id |
| Suggestion queue | URL match before queuing a new suggestion | `scan_gmail --scan-suggestions` |

When a duplicate is detected, the existing DB record wins. The new record is logged and skipped. No silent overwrites.

---

## `suggested_by_platform` flag semantics

| Value | Meaning | Pipeline effect |
|---|---|---|
| `true` | Job was surfaced by a platform algorithm against the candidate's profile (LinkedIn, FINN match engine) | Bypasses cheap semantic pre-filter. Goes directly to full LLM triage. |
| `false` | Job was scraped structurally (NAV, FINN Chrome Extension) or manually sourced | Full pipeline including semantic pre-filter. |
| (absent) | Older records or direct DB inserts | Treated as `false` for pipeline purposes. |

The filter bypass for `suggested_by_platform=true` is intentional and correct. LinkedIn and FINN have candidate-profile match engines. Overriding their output with a cheap semantic filter would discard pre-qualified signal.

---

## Status write-back loop

After the user works a job in JobSync (applies, interviews, gets rejected), status events flow back to the canonical DB via two paths:

### Automatic: Gmail status scanner

**CLI:** `jobpipe scan-gmail` (default mode, no flags)

Scans Gmail for ATS confirmation/rejection/interview emails from platforms including Jobbnorge, EasyCruit, Teamtailor, WebCruiter. Classifies each email, fuzzy-matches to a canonical job via employer name + title scoring, and writes a `JobSyncApplicationStatusEvent` to the DB.

Status priority order (only upgrades, never downgrades):
```
applied=1 < interview=2 < rejected=3
```

After the DB is updated, the next `export-jobsync` run pushes the new status back to the JobSync tracker, completing the loop.

### Manual: record-jobsync-event CLI

```
jobpipe record-jobsync-event <job_id> applied [--notes "..."]
```

For statuses not arriving via email, or for immediate recording without waiting for a Gmail scan.

---

## Open gaps and future work

| Gap | Priority | Notes |
|---|---|---|
| LinkedIn scraping | Next | Possible via MCP + crewAI browser agent |
| Automatic authoring sync to JobSync | Sprint 4 | After `author-package` runs, auto-POST to `/api/integrations/jobpipe/authoring` (GitHub #29) |
| jobpipe-mcp-server | Sprint 4 | Exposes evidence, decision brief, narrative as MCP tools for crewAI and Claude in Word |
| Gmail scan scheduler | Later | Currently on-demand; could be scheduled via OS task or jobpipe scheduler |
| LinkedIn status emails | Later | LinkedIn sends interview/rejection emails — scan_gmail may already catch some via generic email pattern |

---

## Related specs and docs

- `specs/jobsync-integration-seam.md` — JobSync contract types, endpoints, and loop detail
- `specs/reactive-resume-integration-seam.md` — Reactive Resume JSON round-trip seam
- `specs/ai-document-authoring-mvp-workflow-2026-04-21.md` — T002 authoring MVP governing spec
- `specs/crewai-integration-decision.md` — crewAI architecture and isolation rules
- `docs/ai-playbook.md` — shared workflow source of truth
