# Sprint 3: Canonical Application-Loop Bridge Hardening

**GitHub Project items:** `#126` feature, `#127`, `#128`, `#108`
**Sprint:** `Sprint 3`
**Lead worker:** planner/coordinator for routing, Codex for approved slices
**Status:** planning ready

## Why this sprint exists

Sprint 2 cleaned up the repo and the local tooling surface. The next high-value
work is not broad deletion. It is hardening the two weak bridge seams that still
join too many layers at once:

1. `jobpipe/cli/sync_evaluations.py`
2. `jobpipe/stages/application_pack.py`

These seams sit directly on the path to:

- canonical DB state
- generated document registration
- end-to-end smoke testing
- live JobSync / Reactive Resume workflow validation
- future CrewAI job-hunter authoring work

If these stay mixed, every downstream validation loop stays expensive.

## Sprint goal

Make the canonical application loop easier to inspect, safer to change, and
cheaper to validate by extracting bridge responsibilities out of the current CLI
and stage hubs without changing pipeline semantics casually.

## Governing constraints

- No DB schema changes.
- No connector or deployment work.
- No pipeline-semantic changes unless explicitly escalated.
- No authoring quality/prompt tuning in this sprint.
- No CrewAI runtime implementation in this sprint.
- Prefer one-file or two-file diffs per slice where possible.
- Keep changes reversible and test-backed.

## Ordered slice list

### Slice 1 — `#127`

**Title:** Extract and harden canonical sync bridge from `sync_evaluations.py`

**One-step objective:** Thin `mirror_to_primary_db()` so it stops directly
owning every bridge concern: replay input projection, evaluation row assembly,
decision persistence orchestration, monitoring persistence orchestration, and
watchlist aggregation.

**Default shape:** start with the smallest safe extraction. Prefer file-local or
nearby helper extraction over introducing a broad new service layer. A new owner
module is allowed only if the helper boundary is clearly better and the diff
stays narrow.

**Likely files:**

- `jobpipe/cli/sync_evaluations.py`
- `tests/test_sync_evaluations_primary_db.py`

**Potential narrow extension file if needed:**

- one new helper module under `jobpipe/runtime/` or `jobpipe/decision/`

**Acceptance direction:**

- `mirror_to_primary_db()` no longer assembles and persists everything inline
- helper ownership is explicit and traceable
- row and persistence contracts stay unchanged
- targeted validation passes

### Slice 2 — `#128`

**Title:** Extract and harden authoring/document persistence bridge from
`application_pack.py`

**One-step objective:** Thin `_sync_generated_documents()` so stage execution,
document registration, and persistence side effects are less entangled.

**Likely files:**

- `jobpipe/stages/application_pack.py`
- `tests/test_application_pack_db_sync.py`

**Acceptance direction:**

- document generation stays distinct from registration/persistence
- generated document semantics stay unchanged
- targeted validation passes

### Slice 3 — `#108` if still needed after slice 1

**Title:** Fix `GeneratedApplicationPackage.evidence_refs` type drift

**Why it is in this sprint:** it is adjacent to the canonical application-loop
hardening, but it should only be pulled if it is still unresolved after slices 1
and 2 or if the seam work touches the same contract.

**Default rule:** do **not** broaden slice 1 or 2 just to absorb `#108`. Treat
it as a small follow-up unless the fix naturally falls out of the seam cleanup.

## Explicit non-goals

- Reactivating the parked authoring-workspace lane
- Broad `core/` cleanup
- Reactive Resume workflow redesign
- JobSync UX redesign
- CrewAI job-hunter runtime work

## Validation baseline

Each slice must name its own exact commands, but the sprint baseline is:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -p no:debugging -p no:cacheprovider --basetemp "$env:TEMP\\jobpipe-pytest" <targeted-tests>
python compile_check.py
```

If a slice changes bridge behavior materially, add one bounded smoke assertion
for the touched seam before calling the slice done.

## Approval gates

Stop and escalate before:

- DB schema changes
- pipeline-semantic changes
- config-key changes
- migration of canonical ownership into external tool shapes
- new dependency adoption
- broad refactor beyond the named seam

## Exit criteria

Sprint 3 is complete when:

1. `#127` is merged
2. `#128` is merged
3. `#108` is either merged or explicitly marked unnecessary/superseded
4. the canonical application-loop bridge is clearer in code and docs
5. Sprint 4 can run one deterministic end-to-end smoke path without first
   rediscovering these seams

## Handoff notes

- `docs/current-state.json` is stale and should not be treated as the current
  sprint source of truth.
- Project #6 and the execplans under `docs/execplans/` are the active planning
  layer for this lane.
- The Vibe coding crew should consume the approved worker prompt artifacts for
  slices; it should not re-plan the seam from scratch.
