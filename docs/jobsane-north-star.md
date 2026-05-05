# JobSane North Star

## Mission

Only surface the most important decisions Lars can make best: apply, skip, research, follow up, prepare, or improve profile strategy.

## Product Loop

```
Discover → curate in Jobpipe → decide → apply workbench → track → follow up → learn
```

## Guardrails

- Jobpipe is canonical for new jobs and lifecycle state.
- No auto-apply or recruiter portal submit without approval.
- No fake CV or cover letter claims.
- Recommendations must cite evidence.
- Status updates must be traceable.

## Operating Principles

1. **JobPipe is the system of record.** Crews receive data from JobPipe and write results back through existing seams. No canonical state lives in crew output directly.
2. **Crews are transient processors.** Minimum data in, structured results out, no state between runs.
3. **Data sovereignty over local compute.** Cloud LLM APIs are acceptable. All candidate data stays in JobPipe's local state.
4. **Contracts are agent-runtime-swappable.** If a better agent framework appears, the contracts survive the swap.
5. **The candidate reviews everything.** Crews produce drafts; the candidate approves finals.
6. **Sub-crews are independently replaceable.** A better CV crew can replace the CV crew without touching the cover letter crew.

## Human Decision Points

| Decision | Action |
|----------|--------|
| Apply to this job | Approve tailored CV + cover letter, click Apply |
| Skip this job | Dismiss from queue |
| Research before deciding | Defer with note |
| Follow up on application | Send or schedule follow-up |
| Prepare for interview | Trigger Interview Prep crew |
| Improve profile or application strategy | Edit resume.json, motivation.md, constraints.md |

## Non-Goals

- Mass auto-apply
- ATS parity or recruiter portal integration without candidate approval
- Freeform document generation that bypasses evidence provenance
- Single monolithic crew doing everything
- Canonical state moving into crew outputs or cloud services
- Supabase/cloud DB migration (local SQLite remains the current implementation)
