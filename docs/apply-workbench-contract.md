# Apply Workbench Contract

Defines the handoff contract between systems when the candidate clicks Apply in JobSync.

## Trigger

```
Candidate clicks Apply in JobSync → jobpipe trigger-authoring JOB_ID
```

## JobPipe Assembles AuthoringCaseContext From

- Canonical job state (triage decision, fit score, gap analysis, claims)
- Candidate profile (resume.json, profile_pack.md, motivation.md, constraints.md)
- Cover letter voice (cover_letter_voice.md)

## What Opens Automatically After Apply

- Reactive Resume GUI — for CV editing/review
- JobSync application editor — for cover letter editing/review
- Job ad browser tab (source URL)

## What Remains Manual (Candidate-Only)

- Final approval of CV in Reactive Resume
- Final approval of cover letter in JobSync editor
- Submitting the actual application to the recruiter/portal
- Any direct outbound messages (no auto-email, no auto-submit)

## Write-backs to JobPipe

| Action | Command |
|--------|---------|
| CV saved in Reactive Resume | `jobpipe record-reactive-resume-document JOB_ID` |
| Cover letter / screening answers | `jobpipe record-jobsync-event JOB_ID` + document_ref_event |
| Application submitted | `jobpipe mark-status JOB_ID applied` |

## Status Lifecycle

```
shortlisted → apply_ready → applying → applied → (interview | rejected | withdrawn)
```

## Hard Stops

These actions require explicit candidate approval and must never happen automatically:

- Do not submit to recruiter portal without explicit Apply confirmation from candidate
- Do not send outbound email, message, or contact without candidate approval
- Do not alter the final CV or cover letter after the candidate's save write-back

## Source of Truth

All new jobs must be curated in Jobpipe first. JobSync is the candidate-facing view of Jobpipe's curated queue, not a separate source of truth.
